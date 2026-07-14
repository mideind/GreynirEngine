# Design sketch: moving token/terminal matching into the C++ core

Status: IMPLEMENTED (Phases 0-2) — 2026-07-14

## 0. Results (added after implementation)

Phase 0 instrumentation over a 242-sentence corpus: 1.74M match queries,
of which 69.1% classify as natively answerable (55.9% lemma literals).

Implemented as designed, with one delivery difference: token matching
data is fetched via a `MeaningsFunc` callback once per Earley column
(mirroring the existing `alloc_func` handshake) and cached per token key.
Additionally, unknown-word tokens (no BÍN meanings) are handled natively
via a per-terminal constant flag (`TF_MATCHES_EMPTY`).

Measured (CPython 3.13, typical 10-25 token sentences, cold matching
cache): **2.2x faster** overall parse time (1.40s -> 0.65s for the
8-sentence benchmark set); ~89% of Python matching callbacks eliminated.
The full test suite runs ~20% faster. PyPy 3.11: ~20% faster cold.
Warm-cache and long-sentence workloads: unchanged, as predicted.

Verification: query-level parity mode (`GREYNIR_MATCHING_PARITY=1`,
where every native decision is compared against the Python matcher)
reports zero discrepancies over the test corpus; the full test suite
passes with the fast path enabled by default. The fast path can be
disabled with `GREYNIR_DISABLE_CPP_MATCHING=1`, via the
`Fast_Parser._USE_CPP_MATCHING` class attribute, and is automatically
disabled for parser subclasses that override token wrapping
(the GreynirCorrect compatibility gate).

Incidental finding during verification: reduction of exact score ties
is not stable across repeated parses of the same sentence (independent
of this work - it reproduces with pure Python matching); see
test_native_matching.py for why forests, not reduced trees, are
compared there.

## 1. Motivation and measured cost

Profiling (CPython 3.13, warm grammar, fresh matching cache) shows that for
typical 10-25 token sentences, parse time divides roughly as:

| Component                                                  | Share |
|------------------------------------------------------------|-------|
| C++ Earley-Scott core (`earleyParse` self-time)             | ~42%  |
| Python matching callbacks (`matching_func` → `BIN_Token.matches`) | ~40%  |
| Reducer (`reducer.py`)                                      | ~9%   |
| Forest conversion (`Node.from_c_node`)                      | ~4.5% |
| Tokenization and misc                                       | ~4%   |

The callback share is first-encounter cost: the per-token match cache
(`alloc_func`/`matching_cache`) already eliminates repeat queries, giving a
2.6x speedup on cache-warm text. The target of this design is the fresh-text
path: eliminate most C→Python callbacks entirely, by making the C++ core
able to answer the common matching queries itself.

A secondary motivation: C→Python CFFI *callbacks* are a structural weak
spot on PyPy (measured ~50% slower than CPython 3.13 on typical text).
Removing the callback from the hot path benefits both interpreters.

## 2. Why this is feasible: the machinery is already half-built

Three observations from `binparser.py`:

1. **The terminal side is already bit-encoded.** `VariantHandler` maps each
   terminal's variants to `_vbits`/`_fbits` (39 distinct `VBIT_*` bits — fits
   in a `uint64_t` with headroom), and the workhorse predicates
   (`fbits_match`, `fbits_match_mask`) are pure bitmask tests.

2. **The token-meaning side maps to the same bit space.** `get_fbits()`
   converts a BÍN `beyging` inflection string into the same fbits, already
   cached per distinct `beyging` string.

3. **81% of all terminals are literals.** Of the 6,012 terminals in
   `Greynir.grammar`, 4,893 are literal terminals (`'lemma:cat'_variants` or
   `"form:cat"`), whose match semantics are: interned-string identity on the
   lemma or word form, an optional category filter, fbits, and (for
   single-quoted verb literals) an MM exclusion. All of this reduces to
   integer compares. The remaining ~1,100 category terminals are dominated
   by `lo` (378) and `so` (326); most non-verb category matchers
   (`matcher_default`, `abfn`, `pfn`, and the simple paths of `no`/`lo`)
   are already just fbits tests plus small special cases.

The genuinely complex logic is concentrated in a few places: verb argument
frames and subject cases (`verb_matches`, driven by Verbs.conf), adjective
subject cases (`matcher_lo` with `_ADJ_ARGUMENTS`), prepositions
(`matcher_fs`), person/street/proper-name matching, ending-constraint
variants (`_x.../_z...`), and the unknown-word fallbacks. These stay in
Python behind an escape hatch — indefinitely, if we like.

## 3. Design

### 3.1 Terminal spec table (built in Python, passed to C++ once)

Python already parses terminal names into structured form (`VariantHandler`),
so the classification is done at grammar-load time in Python and handed to
the C++ parser as a flat array — **no change to the binary grammar file**.

```c
enum TerminalKind : uint8_t {
    T_PYTHON = 0,      // escape hatch: call matching_func as today
    T_LIT_FORM,        // "form" - token text identity (case-folded id)
    T_LIT_LEMMA,       // 'lemma:cat'_variants - lemma id + cat + fbits
    T_LIT_LEMMA_MM,    // as above, verb lemma with the MM exclusion rule
    T_CAT,             // single category + fbits/mask test
    T_CAT_NOUN,        // category in {kk, kvk, hk} + noun special cases
};

struct TerminalSpec {
    uint8_t  nKind;
    uint8_t  nCatId;      // small enum of ordfl values; CAT_NONE if unused
    uint16_t nFlags;      // TF_HAS_GR, TF_ABBREV, TF_NO_INFO_OK, ...
    uint32_t nLitId;      // interned literal id (lemma or form), or 0
    uint64_t nFbits;      // required feature bits
    uint64_t nFbitMask;   // comparison mask (e.g. cases-only for abfn)
};
```

A new entry point `setTerminalSpecs(Parser*, const TerminalSpec*, UINT n)`
(or an extra argument to `newParser`) installs the table. Any terminal whose
semantics we have not (yet) encoded is simply `T_PYTHON`.

### 3.2 Token meaning records (built lazily in Python, once per token key)

For each distinct token (keyed exactly like today's `matching_cache`),
Python builds a compact meaning array once:

```c
struct MeaningRec {
    uint8_t  nCatId;      // ordfl as enum
    uint8_t  nFlags;      // MF_NO_BEYGING ('-'), MF_NAME_FL (fl in nafn/ætt), ...
    uint32_t nLemmaId;    // interned id, 0 if lemma not in grammar lexicon
    uint32_t nFormId;     // interned id of the (case-folded) word form
    uint64_t nFbits;      // get_fbits(m.beyging)
};
```

Interning: the id space is defined by the grammar's literal lexicon (the
~4,900 distinct lemma/form strings appearing in literal terminals, interned
at grammar load). A meaning whose lemma/form is not in that lexicon gets
id 0 and can never match a literal terminal — one dict lookup per meaning
at encoding time, integer compares forever after.

Delivery to C++ mirrors the existing cache handshake: a new callback

```c
typedef const BYTE* (*MeaningsFunc)(UINT nHandle, UINT nToken, UINT* pnCount);
```

which Python answers from a per-token-key cache (like `alloc_cache` today).
Non-WORD tokens (numbers, dates, persons, entities, punctuation...) return
a sentinel marking the token Python-only in this phase.

### 3.3 Matching in `Column::matches()`

```
if terminal spec is T_PYTHON, or token is Python-only:
    fall back to m_pMatchingFunc(...)   // exactly today's behavior
else:
    for each MeaningRec of the token:
        switch on spec.nKind: integer/bit compares only
    cache the result byte as today
```

The per-column byte cache and the cross-sentence buffer cache are unchanged;
warm-path behavior is identical. The only change is who computes a cache
miss for simple terminals.

### 3.4 What stays in Python (Phase 1)

- All `so_*` category terminals (verb frames, Verbs.conf subjects/arguments)
- `lo` terminals with subject-case variants (`_sþf`/`_sþgf`/`_sef`)
- Ending-constraint variants (`_x...`, `_z...`)
- `fs`, `person`, `gata`, `sérnafn`, `eo`, `stt` and other special matchers
- All unknown-word tokens (no BÍN meanings) and all non-WORD token kinds

**Compatibility requirement**: `verb_subject_matches` and
`verb_is_strictly_impersonal` are overridden by GreynirCorrect
(`reynir_correct.errfinder`), and any subclass may override matching
behavior. The fast path must therefore be gated: a class-level flag on
`BIN_Parser` (e.g. `_ALLOW_CPP_MATCHING`), turned off automatically when a
subclass overrides any matcher hook. Derived packages then keep bit-exact
behavior with zero changes, at today's speed.

### 3.5 Parity harness and rollout

- **Phase 0 — instrumentation**: count callback volume per matcher function
  on a realistic corpus, to rank phases by actual query volume (not
  terminal count).
- **Phase 1 — literal terminals** (81% of the terminal set; the profile's
  808k calls to `BIN_LiteralTerminal.matches` are pure string compares
  crossing the boundary today).
- **Phase 2 — fbits-only category terminals** (`matcher_default`, `abfn`,
  `pfn`, simple `no`/`lo`/`töl` paths).
- **Phase 3 (optional) — verb frames**: encode per-verb argument/subject
  sets (Verbs.conf) as id-keyed bitsets in C++. Largest complexity;
  do only if Phase 0 data shows verbs dominate remaining callbacks.
  Note that `verb_matches` is already `lru_cache`d in Python, which
  absorbs some of the repeat cost.
- **Parity mode**: a debug flag under which C++ computes its answer AND
  calls the Python matcher, asserting equality on every query; run the full
  test suite and a large corpus in this mode before each phase ships.
  Divergence in any query → the terminal is demoted to `T_PYTHON`.

### 3.6 Expected win

Fresh-text typical sentences: most of the ~40% callback share disappears
(bounded by Phase coverage of query volume — measure in Phase 0); estimated
overall parse speedup of 25-35% on novel text, larger on PyPy. Cache-warm
and very-long-sentence workloads: little change (already cache/C++-bound).

## 4. Alternatives considered and rejected

- **Eager full-row precomputation in Python** (fill all 6K terminal bytes
  per token up front): does strictly more work than lazy queries; most of
  a row is never queried.
- **Bitset vectorization in Python (numpy)**: adds a dependency and still
  pays per-query Python call overhead; the boundary is the problem.
- **Moving the reducer to C++**: only ~9% of typical-sentence time; poor
  effort/reward compared to the matching boundary.

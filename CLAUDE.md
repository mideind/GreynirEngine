# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

GreynirEngine (PyPI package name: `reynir`, imported as `reynir`) is an NLP engine
for parsing Icelandic text into sentence trees. It combines a hand-written
context-free grammar for Icelandic with a C++ Earley-Scott parser core, wrapped
via CFFI. Source lives in `src/reynir/`. Supports CPython 3.10+ and PyPy 3.11+.

## Commands

The project uses [uv](https://docs.astral.sh/uv/) with a committed `uv.lock`.
The dev dependencies (pytest, ruff, mypy, ...) are in `pyproject.toml` twice,
with the same content: as the `dev` dependency group, which a plain `uv sync`
installs, and as the `dev` extra, for `uv sync --extra dev` and
`pip install -e ".[dev]"`. Keep the two lists in step.

```sh
# Set up the dev environment (installs dev deps from uv.lock and
# compiles the C++ parser extension via CFFI)
uv sync

# Run all tests
uv run pytest

# Run a single test file / single test
uv run pytest test/test_parse.py
uv run pytest test/test_parse.py::test_long_parse

# Lint (CI runs this)
uv run ruff check src/reynir

# Type check (config in pyproject.toml [tool.mypy]; runs as a CI gate
# on non-PyPy jobs, so it must stay clean)
uv run mypy src/reynir

# Benchmark parsing speed (total and C++ core time, cold and warm)
uv run python benchmarks/bench_parse.py

# Digest of the parse forest of each sentence, for verifying that a
# change to the C++ core leaves its output unchanged (run before and
# after, and diff the outputs). With --unordered, the digests don't
# depend on the order of the families of children of each node.
uv run python benchmarks/bench_parse.py --digest
uv run python benchmarks/bench_parse.py --digest --unordered
```

Note: after changing the C++ sources (`eparser.cpp`, `ereducer.cpp`,
`eparser.h`) or `eparser_build.py`, force a rebuild of the `_eparser` CFFI
extension with
`uv sync --reinstall-package reynir` (the extension is compiled at install
time; see `setup.py`, which exists only for the `cffi_modules` hook — all
other metadata is in `pyproject.toml`). Extra compiler flags for
such a build (sanitizers, `-DEPARSER_ASSERT -UNDEBUG` to enable the
assertions of the core) go in `CXXFLAGS`, not `CFLAGS`, and need
`--no-cache`.

Environment variables that switch the C++ fast paths off or check them
against the Python implementations (all results must be the same either
way; only the speed differs):

| Variable | Effect |
|---|---|
| `GREYNIR_DISABLE_CPP_MATCHING` | Match tokens with terminals in Python only |
| `GREYNIR_MATCHING_PARITY` | Match both ways; count differences in `Fast_Parser.parity_mismatches` |
| `GREYNIR_DISABLE_CPP_REDUCER` | Convert and reduce the parse forest in Python |
| `GREYNIR_REDUCER_PARITY` | Reduce both ways; count differences in `Reducer.parity_mismatches` |
| `GREYNIR_DISABLE_LOOKAHEAD` | Turn off the lookahead filter of the parser core |

## Architecture

The parsing pipeline, orchestrated by the `Greynir` class in `reynir.py`
(`parse()`, `parse_single()`, `submit()`):

1. **Tokenization** — the external `tokenizer` package splits text into tokens;
   `bintokenizer.py` is a dictionary-aware layer that annotates each token with
   its possible meanings from BÍN (the Database of Icelandic Morphology), via
   `bindb.py`, which wraps the external `islenska`/BinPackage vocabulary database.
   `GreynirBin.lookup_g()` caches its results (up to 20,000 words), as the
   lookup of a word is much more work than fetching its entries; the
   cached tuples are shared between callers.

2. **Grammar** — `Greynir.grammar` is a ~7,500-line CFG for Icelandic in extended
   BNF, read by `grammar.py`. It is compiled to a binary form
   (`Greynir.grammar.bin`, gitignored) automatically at runtime whenever the
   source grammar file is newer. The binary is written atomically (temp file +
   `os.replace`), and regeneration is serialized across processes with a
   `filelock` lock file next to the binary (`Greynir.grammar.bin.lock`);
   acquisition times out with a `GrammarError` instead of hanging. The lock
   is only taken when the binary is missing or stale — the warm path is
   lock-free, guarded only by an in-process `threading.Lock` protecting the
   class-level grammar caches. `glock.py` is a deprecated compatibility shim
   over `filelock`, no longer used internally. The binary is a pure function
   of the grammar text (`test/test_binary_grammar.py` compiles it under two
   hash seeds): nothing in `grammar.py` that decides the order or numbering
   of productions may iterate over a set. A rule's free variants (those not
   in its nonterminal) expand to productions in order of first appearance,
   the first one varying fastest; the lowest production index wins exact
   score ties in the reducer.

3. **Parsing** — `fastparser.py` (`Fast_Parser`) wraps the C++ Earley-Scott
   parser (`eparser.cpp`) through the `_eparser` CFFI extension, producing a
   parse forest (SPPF) of all possible parses. `binparser.py` (`BIN_Parser`)
   maps BÍN token meanings to grammar terminals (e.g. `no_et_nf_kvk` = noun,
   singular, nominative, feminine); terminal matching logic lives here.
   `baseparser.py` holds a pure-Python reference parser. `incparser.py`
   handles incremental parsing of token streams by paragraph/sentence.
   The core processes the states of an Earley column in the order in
   which they are added (`Column::nextState()`), which determines the
   order of families in the forest and thereby the outcome of those exact
   score ties in the reducer that its content-based family key
   (production index and child spans; see `start_family()` in
   `reducer.py`) does not settle. A change to the core may alter that
   order, but must leave the content of the forest intact: check with
   `bench_parse.py --digest --unordered` before and after, and compare
   the final trees of a larger sample. Forest nodes live in a per-parse
   arena (`Forest`) that is freed as a whole by `deleteForest()`. See
   `doc/earley-core-performance.md`; `test/test_earley_core.py` tests the
   core in isolation with synthetic grammars.
   The core has a lookahead filter: a state is only created if what
   follows its dot can begin with the current token or derive nothing
   (`Parser::viable()`; the filters and the classes of nonterminals that
   it uses are calculated in `Grammar::analyze()` when a grammar is
   loaded). It must not change the content of the forest, nor the token
   index that a failed parse reports. Token/terminal matches and
   "can this class of nonterminals begin with this token" are cached per
   distinct token (by `BIN_Token.key`), two bits each, in
   `Fast_Parser._matching_cache`. Nearly all matches of words are decided
   natively in the core (`doc/cpp-matching-design.md`, and section 10 of
   the performance document), from tables built in `binparser.py`
   (`build_matching_table()`, `encode_token_matching_data()`). **The
   native matchers replicate the Python ones in `binparser.py`
   (`WordMatchers`, `BIN_Token.verb_matches()`): a change to the matching
   logic there must be made in `evalMatch()`/`verbMatchMeaning()` in
   `eparser.cpp`, or in the tables, as well.** `GREYNIR_MATCHING_PARITY=1`
   compares the two for every match that the parser evaluates, and
   `test/test_native_matching.py` for all terminals. Native matching also
   applies to parsers whose tokens are of a class derived from `BIN_Token`
   that only overrides the hooks that `BIN_Token.verb_matches()` calls, as
   in GreynirCorrect (`Fast_Parser._native_token_class()`); the hooks are
   consulted when the matching data of a token is created
   (`_verb_profile()`), so they must be pure functions of their arguments.

4. **Reduction** — `reducer.py` scores the parse forest and reduces it to the
   single most likely tree, using preferences from `config/Prefs.conf`,
   production priorities and `$score()` pragmas in the grammar, and
   verb-preposition matching driven by `config/Verbs.conf`.
   `Reducer.parse_and_reduce()` is what `Greynir` and `IncrementalParser`
   call: it parses and reduces in one go, with the forest staying in C++
   (`ereducer.cpp`) and Python objects only created for the nodes of the
   winning tree (`Node.from_serialized()`). The scores of token/terminal
   matches are still calculated in Python (`Reducer._score_options()`), as
   are the verb/preposition and verb/particle bonuses, through callbacks.
   The older route - `Fast_Parser.go()`, `Fast_Parser.num_combinations()`,
   `Reducer.go_with_score()` - does the same in Python on a forest of
   `Node` objects; it remains as public API, as the reference
   implementation and as the fallback (for forests with cycles or deeper
   than 1,000 levels, and when a derived class overrides what the C++
   code replicates). **The two must give identical results, down to the
   score of each node: a change to the scoring or reduction logic in
   `reducer.py`, or to `Node.from_c_node()`, must be made in
   `ereducer.cpp` as well.** `test/test_reducer.py` compares them on
   pseudo-random grammars; run a larger sample of real text with
   `GREYNIR_REDUCER_PARITY=1` after such a change.

5. **Output/API** — `simpletree.py` provides `SimpleTree`, the simplified tree
   API users interact with (`.tree.S.IP.NP_SUBJ`, `.lemmas`, `.nouns`, `.flat`,
   etc.). `matcher.py` implements pattern matching over these trees.
   `nounphrase.py` provides the `NounPhrase` class with case inflection through
   `__format__` (e.g. `f"{np:þgf}"`). `lemmatize.py`, `verbframe.py` and
   `ifdtagger.py` provide lemmatization, verb frames and IFD-style POS tagging.

Supporting data:

- `src/reynir/config/*.conf` — linguistic configuration (verbs with their
  argument cases and prepositions, phrase preferences, name preferences,
  adjective/noun predicates, etc.), loaded by `settings.py`.
- `src/reynir/resources/ord*.csv` — vocabulary additions layered on top of BÍN.

The public API is defined by the exports in `src/reynir/__init__.py`.
`Reynir` is retained as a compatibility alias for `Greynir`.

## Conventions

- Grammar terminal and category names are Icelandic abbreviations (`no`=noun,
  `so`=verb, `nf`/`þf`/`þgf`/`ef`=cases, `et`/`ft`=number, `kk`/`kvk`/`hk`=gender);
  these appear throughout the code, tests and grammar files.
- In the grammar, single-value variants ("eins gildis tilbrigði", e.g.
  `/p3 = p3`, `/et = et`) pin a nonterminal reference to one fixed variant
  value: `Tilvísunarsetning/tala/p3/kyn` unifies with the `p3` slice of a
  `/tala/pers/kyn` definition, since variant expansion is purely textual
  name generation. The value must be declared as a variant first.
- Ruff line length is 88; `E731` (lambda assignment) is ignored.
- CI (`.github/workflows/python-package.yml`) runs ruff + pytest via
  `uv sync --locked` on Python 3.10–3.14 and PyPy 3.11 on Linux, plus one
  job each on Windows and macOS. Wheels are built on tag push via a pinned
  cibuildwheel (`cp310` abi3 wheel for CPython, version-specific for PyPy).
- The `old/` and `build/` directories contain legacy/build artifacts — do not
  edit code there.

## Backlog (post-4.0.0 candidates)

Potential next steps from the 2026 grammar-coverage study (see release
notes for 3.9.0), from the 3.10.0 work and from the performance work of
4.0.0; none started:

- **Coverage clusters**: auxiliary/copula gapping in a second conjunct
  ("höfðu dáið og 23 særst"); smaller items — "var lýst sem" passives,
  "hann/hún" + name, repeated "sem", þykja-subject-first; the pronoun
  "hinn" cluster ("allir hinir", "okkur hinum"); "Ætli …?" questions.
- **Tokenizer**: amount ranges ("200 til 460 milljónir króna" strands
  "200 til").
- **Relative clauses** (left over from 3.10.0): stranded preposition
  after "vera" ("húsið sem hann hefur verið í"); multi-word stranded
  prepositions ("sem hún tók á móti"); "fundurinn sem halda á í dag";
  locative "þar sem" clauses ("Þar sem hann fór var mér kalt"); "kerfið
  sem til stendur að hjálpa/breyta" (dative/genitive object: the
  subject-gap reading still wins).
- **Reflexive agreement** (left over from the `_sjálfur` rules, which
  make "sjálfa sig"/"sjálfum sér" agree with the subject where the verb
  phrase nonterminals carry /tala/kyn): infinitive clauses with "að"
  ("hún er að skaða sjálfa sig", NhLiður has no variants); PPs attached
  to a noun ("þeir birtu myndir af sjálfum sér") or to an adjective
  inside such a clause ("að vera ósamkvæmir sjálfum sér"). Also seen:
  "sjálft sig" with "sig" read as a noun, "sjálfu sér" as noun + verb.
- **Ties left to the family order**: when two derivations of one
  production have the same score and spans but fill different optional
  items, the reducer falls back on the family order, which shifts when
  nonterminals are added. Fix in the grammar (as done for NlTöluorð,
  "f. 1985"). Seen in news text: EfLiðurForskeyti ("eins árs"), NlKjarni
  (NlViðbót?/Númer?), NlEind (relative clause/NlSkýring?),
  BeygingarliðurMeðUmröðun (Upptalning?/KommaAtvikssetning?), SögnMeðF_0.
- **Scoring**: the reducer's flat +12 for present participles
  (`reducer.py`) is why -andi nouns needed per-word Prefs.conf entries;
  a generic fix would cover the rest of the class.
- **Grammar hygiene, round 2**: inline ~60 thin single-production
  wrappers; consider a /kyn variant diet like the /pers one; score or
  drop sentence-initial SamkvæmtHeimild; run a second usage census over
  headings/non-news text before touching rules that only win in other
  text types.
- **Performance** (see "What remains" in sections 9 to 11 of
  `doc/earley-core-performance.md`): the core is the largest part of a
  warm parse again (precomputed nullability; the two per-token callbacks);
  the scoring of terminals in Python; tokenization would need fewer
  passes over the tokens; matching of tokens that are not words.
  GreynirServer's query module still calls
  `go()` + `num_combinations()` + `Reducer.go()`, and could use
  `Reducer.parse_and_reduce()` (which handles `no_reduce`).
- **Method note**: a "never wins in N sentences" census verdict is not
  proof of dead grammar — always re-probe a rule with the construction
  it actually targets before deleting (news-corpus frequency ≠ reachability).

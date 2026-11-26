# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

GreynirEngine (PyPI package name: `reynir`, imported as `reynir`) is an NLP engine
for parsing Icelandic text into sentence trees. It combines a hand-written
context-free grammar for Icelandic with a C++ Earley-Scott parser core, wrapped
via CFFI. Source lives in `src/reynir/`. Supports CPython 3.10+ (free-threaded
from 3.14t) and PyPy 3.11+.

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

# Run each test in 8 threads at once on free-threaded Python, as CI does
# on 3.14t and 3.15t (tests that use monkeypatch or capfd, or are marked
# thread_unsafe, run in one thread)
UV_PROJECT_ENVIRONMENT=.venv-3.14t uv run --python 3.14t pytest --parallel-threads=8

# Benchmark parsing speed (total and C++ core time, cold and warm)
uv run python benchmarks/bench_parse.py

# Digest of the parse forest of each sentence, for verifying that a
# change to the C++ core leaves its output unchanged (run before and
# after, and diff the outputs). With --unordered, the digests don't
# depend on the order of the families of children of each node.
uv run python benchmarks/bench_parse.py --digest
uv run python benchmarks/bench_parse.py --digest --unordered

# Build the documentation in doc/ (Sphinx, Python 3.11+; not a CI job).
# greynir.is/doc/ is such a build, served by GreynirServer's nginx
uv run --no-project --with sphinx python -m sphinx -W -b html doc /tmp/reynir-doc
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
   class-level grammar caches. The binary is a pure function
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
   arena (`Forest`) that is freed as a whole by `deleteForest()`. The
   buffers of the tokens that have been seen before (matching cache,
   matching data) are handed to the core when it is called
   (`ParseJob.known_buffers()`, `earleyParseEx()`); it asks for the
   others through callbacks (`alloc_func()`, `meanings_func()`). See
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
   Parses run concurrently in threads: the core always did (cffi releases
   the GIL around it), and on free-threaded Python the callbacks do too.
   The caches of a parser are shared by its parses and the core points into
   their buffers, so a buffer must never be replaced while a parse may use
   it (`setdefault()` in `ParseJob.alloc_cache()` and
   `token_matching_data()`; a full cache is replaced, not cleared).
   Grammars are read one at a time (`Grammar._read_lock`), as their items
   are numbered from class-level counters. Those counters are
   `itertools.count` objects: code that runs per instance or per parse must
   not assign to class attributes, as after 1,000 modifications a class
   loses CPython's type cache, and on free-threaded Python its attribute
   lookups then contend for an interpreter-wide lock (parsing in 16 threads
   was slower than in 8). `test/test_threads.py` checks parses in threads
   against serial ones.

4. **Reduction** — `reducer.py` scores the parse forest and reduces it to the
   single most likely tree, using preferences from `config/Prefs.conf`,
   production priorities and `$score()` pragmas in the grammar,
   verb-preposition matching driven by `config/Verbs.conf`, and
   noun-preposition matching driven by `config/NounPredicates.conf` and
   `config/NounPrepositions.conf`: a preposition in a phrase attached to
   a noun phrase (`FsRunaEftirNl`, tagged `noun_prep_scope`) gets a bonus
   if the head noun of that phrase takes it (`noun_prep_bonus()`;
   strong entries outweigh a verb that lists the preposition, entries
   marked `$weak` do not). The head noun is found as verbs are: a noun
   terminal passes its match up the tree, through noun phrase
   nonterminals (`Nl*`), those tagged `noun_head` (`Fyrirbæri` and what
   is below it) and the nonterminals that the grammar reader makes for
   `X?`, `X*` and `X+`; all others drop it, so the noun of a possessor
   or a relative clause does not get out. What the children of a family
   have yielded so far is the "current noun" of the children that
   follow, and a `noun_prep_scope` node makes its bonus zone of it. So
   the noun is the word as it is read in that tree ("sig" as a pronoun
   yields nothing), and it need not stand directly before the phrase
   ("áhrif stjórnvalda á málið"). Three rules, set against the gold
   standard: only the first phrase of a run is scored against the head
   ("lögreglan í Mehamn í Noregi": the second belongs to the nearer
   noun three times in four); the bonus is one lower when the noun is
   not directly before the preposition, so the nearer of two equally
   strong nouns wins; and a phrase on a noun phrase without a head noun
   (a name, a pronoun) gets a penalty (`_NOUN_PREP_NO_HEAD_PENALTY`).
   A new nonterminal on the path from a noun to its noun phrase needs
   the `noun_head` tag, or the nouns below it get no bonus.
   `Reducer.parse_and_reduce()` is what `Greynir` and `IncrementalParser`
   call: it parses and reduces in one go, with the forest staying in C++
   (`ereducer.cpp`) and Python objects only created for the nodes of the
   winning tree (`Node.from_serialized()`). The scores of token/terminal
   matches are still calculated in Python (`Reducer._score_options()`), as
   are the verb/preposition, noun/preposition and verb/particle bonuses,
   through callbacks (the noun/preposition bonus goes through the
   verb/preposition callback, with the terminal and the token of the
   noun in place of the verb's; terminal 0 stands for no head noun).
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
  `uv sync --locked` on Python 3.10–3.15, free-threaded 3.14t and 3.15t
  (also with `--parallel-threads=8`) and PyPy 3.11 on Linux, plus one
  job each on Windows and macOS. Wheels are built on tag push via pinned
  cibuildwheel versions (`cp310` abi3 wheel for CPython, version-specific
  for free-threaded CPython and for PyPy, as both pp73 and pp80; no PyPy
  wheels for x86_64 macOS). Check a change to `wheels.yml` by pushing a
  tag that contains `test`: the wheels are built and tested, but not
  published.
- The `old/` and `build/` directories contain legacy/build artifacts — do not
  edit code there.

## Backlog (post-4.2.0 candidates)

Potential next steps from the 2026 grammar-coverage study (see release
notes for 3.9.0), from the 3.10.0 work, from the performance work of
4.0.0, from the free-threading work of 4.1.0 and from the work on
parse quality of 4.2.0; none started.

**Measured priorities (November 2026).** Two measurements, both to be
repeated before and after a change (the data and scripts are outside
the repository; ask for the coverage study):

- *Sentences that do not parse*: 404 of a fixed sample of 5,000 news
  sentences of 2026 (8.1%) with 4.1.0, and 346 (6.9%) with 4.2.0. Of
  the 404, 232 are gaps in the grammar or the
  vocabulary, each diagnosed with a minimal failing sentence and a
  minimal parsing one. By size: names (43, of which 26 parse since the
  work on names described below), dates, numbers and measures (23: a
  weekday after "í gær"
  or "á morgun", "tímabil" as a time noun, "um það bil"/"yfir hundrað"
  before a numeral), fixed phrases (20: "af hálfu", "eitthvað slíkt"),
  punctuation (19: a clause in parentheses), verb frames (13), word
  order after a fronted element (13: "Þá kasta læknarnir fram tölum",
  "Í dag er spáð rigningu"), gapping (12), agreement stricter than usage
  (12: "Henni fylgir rigning og snjókoma"), "sem" phrases (11: "Þá
  starfaði hann sem kennari").
- *Names*: a capitalized word in the middle of a sentence that BÍN only
  knows in lower case ("El Mencho", "Meta", "Pars"; in all capitals also
  at the start, "EFLA") can match the bare `sérnafn` terminal
  (`matcher_sérnafn()`, `BIN_Token.is_capitalized_common_word`; the
  position is set in `BIN_Parser._wrap()` and is part of the token's
  key). An
  unknown name can have qualifiers in front (EinkunnOgSérnafn: "hinn 29
  ára gamli Sanches"), and names outside BÍN no longer count towards a
  sentence being foreign (`tokens_are_foreign()`). The sample of 5,000
  went from 404 to 351 unparsed. A name that these rules do not reach
  goes in the `[static_phrases]` section of `config/Phrases.conf`,
  which has lists of people, companies and places: there it is a name
  in all cases and at the start of a sentence too ("Adams", otherwise
  only the genitive of Adam; "Bondi", a form of a verb; "von der
  Leyen" without a first name; "Rolling Stones"). Where one phrase is
  the start of another, the longest that matches is taken, and the
  shorter one if the rest does not follow ("San Antonio Spurs" and "San
  Antonio"; `MatchingStream.process()`). Left: a first name in
  a case that BÍN has it in, with an unknown surname ("Carli Kierny
  sendi": the dative of Carl), where letting any person name match a
  caseless `sérnafn` is known to bring wrong parses (see
  `matches_PERSON()`); a single word in the static phrases that BÍN has
  as a person name ("í Indíana" stays the woman's name);
  a name that is also a word at the very start of a sentence and not in
  the list ("El Azizi lék"); a name
  directly before a noun, which is read as its prefix also where it is
  the subject ("Í júní birti SKE umræðuskjal": SKE umræðuskjal, as with
  KSÍ); photo credits ("EPA / Nafn Nafnsson") now parse, as a noun with
  a possessor.
- *Sentences that parse wrongly*: against the hand-corrected gold
  standard of GreynirCorpus (4,500 development trees; keep the 500 test
  trees for final figures), labelled bracket F1 is 0.75 and 73% of the
  prepositional phrases with the same span hang where the gold standard
  has them. Largest kinds of difference after PP attachment: an adverb
  of the clause read as a modifier of the next phrase ("Þetta er ekki
  ljóst", 525), a passive participle read as an adjective (354),
  accusative/dative confusion after "í"/"á"/"með" (about 300). The
  preposition "á" was read as the verb "eiga" in 136 places and is in 73
  (`Reducer._a_verb_adjustment()` lowers the verb where a noun phrase
  follows, the word before is not a likely subject and a finite verb
  stands earlier in the sentence): what is left has a name or a pronoun
  before "á", or no reading with the preposition at all, often because
  a subordinate clause may lack its subject ("bundu loksins enda á
  taphrinuna" reads "enda" as a conjunction). Part of the difference is
  convention, not error (the scorer's `normalise()` lists what it
  removes). The subject of a subordinate clause read as a predicate or
  an object in front of the verb ("að málið sé í skoðun") is penalised
  (SagnfyllingFremst, AndlagFremst); what the scorer still counts there
  is mostly convention ("hægt" in "er hægt að" is a subject in the gold
  standard), plus "sú sem hún er", where "hún" is the subject of a
  relative clause that lacks its predicate.
- *PP attachment, what is left*: "til", "með", "eftir" and
  "vegna" phrases on a noun are right about one time in three; where
  a possessor stands between a noun and a phrase and both nouns take
  the preposition equally strongly, the nearer one gets it ("skýrsla
  nefndarinnar um málið" hangs the phrase on "nefnd"); a name that
  BÍN has as one word gets no bonus through its last part
  ("Ingunnarskóli í Grafarholti"); a personal pronoun with a phrase
  is penalised twice (`FsEftirPfn` and the reducer's penalty for a
  phrase without a head noun), which could be one; a verb
  gives its preposition bonus to every phrase with that preposition,
  not to one; a phrase at the end of a subordinate clause goes to the
  verb of the main clause if only that verb lists its preposition in
  that case ("kom í ljós að leikarinn væri á bak við aðganginn").

- *The noun/preposition table* (NounPrepositions.conf) was audited in
  November 2026 and 374 of its 6,992 entries were removed (see the head
  of the file): those on words that are seldom nouns ("ekki /í",
  "sig /á"), which came from misparses and rewarded them; those of
  nouns whose forms are mostly verb forms ("vera /í", "koma /á",
  "taka /á"), which costs the noun its phrase where it is one ("við
  komu skipsins í Hvalfjörð"); those of time nouns with "í"/"á"; those
  of nouns in fixed phrases ("ljós /í"); and 202 that could never match
  (8 names got their capital letter instead, "Íslandsmót /í"; people
  and parties with a phrase of place did not). Tried and not done, as
  the figures got worse: weakening the strong entries where the
  preposition is no more common after the noun than after nouns in
  general, and dropping the weak ones where it is rarer. The generator
  is not in the repository (`harvest.py`, `mktable.py` and
  `np_prune.py`, with the coverage study): a regenerated file has to
  be pruned again.

Older items:

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
- **Question clauses** (left over from the work on joined question
  clauses, "hvar hann býr og hvenær hún fór", and on a noun phrase joined
  with a question clause, "um líðan mannsins eða hvort einhver hefði
  verið handtekinn"): two verb-first questions that share a question
  mark ("Fór hann í varðhald eða var hann settur í farbann?") are read
  as one question, as SpurnarsetningSögnFremst has no score beyond that
  of a single question (with one, the last verb of "Viljum við fara og
  klára þetta?" becomes a question of its own); the score of
  Spurnarsetning (+32) in turn splits a verb-first "question" off the
  end of a few statements that end with a question mark ("Jón ... og
  spurði hvaðan þetta hefði komið?"); a noun phrase followed by a list of
  clauses ("deila um fundi, hverjir voru boðaðir og hvernig hlutirnir
  voru": a rule for it, with the scores of FsNlOgSpurn/NlOgSpurn, took
  the second and third clause of plain three-clause lists); "hvorki X né
  hvernig ..."; clauses with a fronted object and a verb that requires
  one ("hvaða kunnáttu störfin krefjast"), with an oblique subject
  ("hvernig ávinnslu réttinda er háttað") or with the verb second ("hvar
  hefur barnið verið"); headings that are a bare question clause ("Hvar
  áhrifin verða minnst"), which no longer parse as statements; "og hvað
  þá X". Seen on the way, older than that work: "Ekki er ljóst hvort ..."
  has "ljóst" as the subject and the clause as an object; "Ég veit að
  hann kom og að hún fór" reads "að hún" as a prepositional phrase.
  The scores of these rules were set against five samples of news
  sentences (general, with "og/eða" + question word, with a question
  word, direct questions) and some 90 sentences with a known structure:
  when one of them is changed, check both the reading it competes with
  (a second main clause with the question clause as its subject) and
  the attachment of the clause (to the nearest noun phrase, or to the
  clause before it).
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
  `doc/earley-core-performance.md`, and section 12): the core is the
  largest part of a warm parse again (precomputed nullability; a memo of
  the predictions per distinct token);
  the scoring of terminals in Python; tokenization would need fewer
  passes over the tokens; matching of tokens that are not words.
  4.2.0 is about 7% slower than 4.1.0 on a warm pass over 1,000 news
  sentences (1.69 s against 1.58 s; the core 0.65 s against 0.63 s),
  with 14 more of them parsed: the rest is outside the core (the
  noun/preposition callbacks, the scoring of "á", the static phrases)
  and has not been profiled.
  GreynirServer's query module still calls
  `go()` + `num_combinations()` + `Reducer.go()`, and could use
  `Reducer.parse_and_reduce()` (which handles `no_reduce`).
- **Threads**: `Fast_Parser._load_binary_grammar()` (when the binary
  grammar has a new timestamp) and `Greynir.cleanup()` free the shared C++
  grammar while other threads may be parsing with it; the README tells
  users to call `cleanup()` only when no other thread is parsing.
- **Python 3.10** (end of life since October 2026): filelock has no
  release for it with the security fixes of 4.2.1, so `pyproject.toml`
  has two filelock requirements and `uv.lock` two versions (4.1.0 for
  3.10), and the Dependabot alerts for filelock stay open. Dropping 3.10
  (`requires-python`, the `cp310` abi3 tag in `setup.py`,
  `eparser_build.py` and `wheels.yml`, the CI matrix) removes both.
- **Method note**: a "never wins in N sentences" census verdict is not
  proof of dead grammar — always re-probe a rule with the construction
  it actually targets before deleting (news-corpus frequency ≠ reachability).

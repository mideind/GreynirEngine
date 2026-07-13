# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

GreynirEngine (PyPI package name: `reynir`, imported as `reynir`) is an NLP engine
for parsing Icelandic text into sentence trees. It combines a hand-written
context-free grammar for Icelandic with a C++ Earley-Scott parser core, wrapped
via CFFI. Source lives in `src/reynir/`. Supports CPython 3.10+ and PyPy 3.11+.

## Commands

The project uses [uv](https://docs.astral.sh/uv/) with a committed `uv.lock`;
dev dependencies live in `[dependency-groups]` in `pyproject.toml`.

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

# Type check (config in pyproject.toml [tool.mypy]; carries a handful of
# known pre-existing errors, so it is not a CI gate)
uv run mypy src/reynir
```

Note: after changing the C++ sources (`eparser.cpp`, `eparser.h`) or
`eparser_build.py`, force a rebuild of the `_eparser` CFFI extension with
`uv sync --reinstall-package reynir` (the extension is compiled at install
time; see `setup.py`, which exists only for the `cffi_modules` hook — all
other metadata is in `pyproject.toml`).

## Architecture

The parsing pipeline, orchestrated by the `Greynir` class in `reynir.py`
(`parse()`, `parse_single()`, `submit()`):

1. **Tokenization** — the external `tokenizer` package splits text into tokens;
   `bintokenizer.py` is a dictionary-aware layer that annotates each token with
   its possible meanings from BÍN (the Database of Icelandic Morphology), via
   `bindb.py`, which wraps the external `islenska`/BinPackage vocabulary database.

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
   over `filelock`, no longer used internally.

3. **Parsing** — `fastparser.py` (`Fast_Parser`) wraps the C++ Earley-Scott
   parser (`eparser.cpp`) through the `_eparser` CFFI extension, producing a
   parse forest (SPPF) of all possible parses. `binparser.py` (`BIN_Parser`)
   maps BÍN token meanings to grammar terminals (e.g. `no_et_nf_kvk` = noun,
   singular, nominative, feminine); terminal matching logic lives here.
   `baseparser.py` holds a pure-Python reference parser. `incparser.py`
   handles incremental parsing of token streams by paragraph/sentence.

4. **Reduction** — `reducer.py` scores the parse forest and reduces it to the
   single most likely tree, using preferences from `config/Prefs.conf`,
   production priorities and `$score()` pragmas in the grammar, and
   verb-preposition matching driven by `config/Verbs.conf`.

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
- Ruff line length is 88; `E731` (lambda assignment) is ignored.
- CI (`.github/workflows/python-package.yml`) runs ruff + pytest via
  `uv sync --locked` on Python 3.10–3.14 and PyPy 3.11 on Linux, plus one
  job each on Windows and macOS. Wheels are built on tag push via a pinned
  cibuildwheel (`cp310` abi3 wheel for CPython, version-specific for PyPy).
- The `old/` and `build/` directories contain legacy/build artifacts — do not
  edit code there.

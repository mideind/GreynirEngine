# Performance of the C++ Earley-Scott core

Status: IMPLEMENTED (stage 1) — 2026-11-09

## 0. Summary

Profiling of the parser core (`eparser.cpp`) on Icelandic text showed that
most of its time was not spent on the Earley-Scott algorithm as such, but
in three container operations that were linear where they should be
constant-time, plus some bookkeeping overhead. Fixing these makes the
core 4-5x faster, and parsing as a whole about 3x faster, **without
changing its output in any way**: the parse forests are identical, node
for node, including the order of the families of children of each node.

Measured with `benchmarks/bench_parse.py` (CPython 3.13, gcc 13, one core
of a 2.1 GHz Xeon cloud VM; the fastest pass of several):

| Corpus | Pass | Before, total | After, total | Speedup | Before, core | After, core | Speedup |
|---|---|---|---|---|---|---|---|
| `benchmarks/corpus.txt` (51 sentences, 599 tokens) | cold | 3.16 s | 1.29 s | 2.4x | 2.86 s | 1.01 s | 2.8x |
| | warm | 2.76 s | 0.83 s | 3.3x | 2.47 s | 0.56 s | 4.4x |
| Sentences from the test suite (466 sentences, 3876 tokens) | cold | 22.6 s | 8.7 s | 2.6x | 20.0 s | 6.1 s | 3.3x |
| | warm | 22.4 s | 6.1 s | 3.7x | 20.1 s | 3.8 s | 5.3x |

'Core' is the time spent inside `earleyParse()`, which includes the
callbacks from the core into Python (matching of tokens against terminals
that are not handled natively, in the cold pass; allocation of the
matching caches). 'Warm' means that the token/terminal matching cache of
the parser is populated, as in a long-running process.

When the core is run by itself, replaying the token/terminal matches of
real parses from a pure C++ driver, the speedup is 4.5-5x (about 300 →
1,500 tokens/second).

The core used to account for about 90% of the parsing time. It is now
63-78%, the rest being the reducer, the conversion of the forest to
Python objects, and tokenization.

## 1. What the profile showed

An Icelandic sentence is a demanding input for the core. The grammar has
about 7,200 nonterminals and 27,000 productions; a column of the Earley
chart holds about 5,000 states and 600 forest nodes, and about 250
completed nullable nonterminals (the H set of the Scott algorithm). The
core created about 11,000 states per token, of which half were discarded
immediately. Against that background:

1. **The H set was scanned linearly.** For every state with a nonterminal
   at the dot, the predictor walked the entire H set of the column to find
   the elements referring to that nonterminal. This was the largest
   single cost: about 43% of the instructions executed.
2. **The node dictionary was a linked list.** `NodeDict::lookupOrAdd()`
   compared the label being looked up with the labels of all nodes
   created in the column so far: about 18%.
3. **Finding the next state to process visited the hash bins one by one.**
   `Column::nextState()` enumerates the states of a column round robin
   over its 997 hash bins. When a column has few states with pending
   work, nearly all the bins visited are exhausted. This cost 6% on
   Icelandic text, but dominates completely in parses with small columns:
   75% of the time when parsing a programming language with the core.
4. **States were created only to be rejected.** A state whose dot is in
   front of a terminal that does not match the current token was
   constructed (along with its forest node), handed to `push()`, and
   destroyed there.
5. **Bookkeeping.** Every state allocation and release incremented an
   atomic counter (a `lock`-prefixed instruction on x86, and a shared
   cache line between concurrent parses); every chunk of state storage
   was zeroed before use; H set elements and node dictionary entries
   were allocated from the heap one by one.

## 2. The changes

All in `eparser.cpp` (and the declarations in `eparser.h`):

1. **H set index.** The H set elements of the current column are also
   linked in a list per nonterminal, whose heads are in an array indexed
   by nonterminal. The predictor visits only the relevant elements, in
   the same order as before.
2. **Hashed node dictionary.** `NodeDict` is a hash table with chaining.
   All entries are also linked in a single list, so resetting the
   dictionary (once per column) takes time proportional to the number of
   entries rather than the number of bins.
3. **Bitmap of pending hash bins.** Each column has a bitmap of the bins
   that contain states not yet returned by `nextState()`. Locating the
   next bin takes a few word operations. The enumeration order is
   exactly the same as before (see section 3).
4. **Checking terminals before creating states.** `Parser::canAdvance()`
   and `canPush()` test whether a state could be pushed before the state
   and its node are created. This halves the number of states created
   (and removes nearly all of the discards). The comment in `canAdvance()`
   explains why skipping the creation of the node is safe.
5. **Cheaper bookkeeping.** States are counted in plain counters in the
   state chunks and added to the global atomic counters when the chunks
   are freed; matching calls and node dictionary lookups are counted per
   column in the same way. The numbers shown by
   `printAllocationReport()` are still exact. State chunks are no longer
   zeroed, and H set elements and node dictionary entries come from
   small per-parse pools (`Pool<T>`).

One thing that was tried, did *not* pay off and was left out: a separate
open addressing hash table for detecting duplicate states. The hash
chains of a column are short enough that this was no faster.

## 3. The invariant: enumeration order

The order in which `Column::nextState()` returns the states of a column
determines the order in which families of children are added to forest
nodes. That order, in turn, decides which of several trees with exactly
the same score the reducer selects. Changing it would therefore change
the parse trees of some sentences - not incorrectly, but visibly.

Stage 1 deliberately preserves this order, as well as the order of
iteration over the H set, so that it is a pure optimization. Anyone
changing the core should either preserve the order or treat the change
as one that alters output.

## 4. Verification

* **Forest identity.** `benchmarks/bench_parse.py --digest` writes a
  digest of the forest of each sentence, as returned from the core,
  covering all nodes, their labels and their families in order. The
  digests before and after the change are identical for
  `benchmarks/corpus.txt` and for 453 parses of sentences collected from
  the test suite. The same comparison was made at the C++ level (with
  both gcc and clang builds) by replaying the token/terminal matches of
  real parses through the old and new core.

  Note that digests are only comparable between runs that use the same
  `Greynir.grammar.bin` file: the binary grammar is not byte-for-byte
  reproducible between generations (see section 5).
* **Sanitizers.** The replay runs clean under AddressSanitizer and
  UndefinedBehaviorSanitizer, with the assertions in the core enabled.
* **Tests.** `test/test_earley_core.py` tests the core in isolation, with
  synthetic grammars: tree counts against closed-form results and
  against an independent tree counter over pseudo-random grammars;
  nullable nonterminals; long inputs; columns with thousands of states;
  error positions; determinism of the forest, family order included; and
  the allocation counters. The tests pass on the previous core as well
  (they describe existing behavior), and each of six deliberately
  introduced bugs in the new data structures makes them fail.
* The existing test suite passes unchanged.

## 5. Possible next stages

In rough order of expected benefit for Icelandic text:

1. **The Python side.** With the core 4-5x faster, the work outside it
   (mainly the reducer and the conversion of the forest to Python
   objects) is now 22-37% of the parsing time, and first-encounter
   matching accounts for the difference between cold and warm passes.
2. **Forest memory.** About 85% of the forest nodes created during a
   parse are released before it ends, and nodes and their family entries
   are allocated from the heap one by one: `malloc`/`free` is 15-20% of
   the instructions that the core now executes. Allocating them from an arena owned by the
   forest would remove most of that, but changes how forests are released
   (they are reference counted, node by node, today).
3. **Decoupling enumeration order from hashing.** Processing the states
   of a column in insertion order instead of round robin by hash bin is
   simpler, and would allow the hash table of a column to be sized by
   need (a column currently occupies about 24 KB plus 8 bytes per
   nonterminal, which also limits the practical length of the input).
   This changes the family order, i.e. the outcome of exact score ties,
   once.
4. **Fewer states.** Precomputing, for each nonterminal, the closure of
   productions that the predictor adds, with the terminals that each can
   start with, would avoid creating prediction states one by one. Joop
   Leo's optimization for right recursion would make right-recursive
   rules linear.

An observation made along the way, unrelated to performance: generating
`Greynir.grammar.bin` twice from the same grammar gives files that differ
(the reason was not investigated). Nonterminal indices and production
ids feed into the state hash, so if these are what differs, the family
order - and thus the outcome of exact score ties - may differ between
two installations. This is worth a look; a reproducible binary grammar
would rule it out.

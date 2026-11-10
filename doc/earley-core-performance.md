# Performance of the C++ Earley-Scott core

Status: IMPLEMENTED (stages 1 and 2) — 2026-11-10

## 0. Summary

This document describes two rounds of work on the speed of the parser
core. Sections 0 to 5 are about the first one (stage 1), which left the
output of the core unchanged in every detail. Section 7 is about the
second one (stage 2), which changes the order of the families of children
in the parse forest but not their content, and also cuts down on the
calls from the core into Python. Taken together, on the machine where
stage 2 was done:

| `benchmarks/corpus.txt` | Before | After stage 2 | Speedup |
|---|---|---|---|
| Core, warm | 2.76 s | 0.125 s | 22x |
| Whole parse, warm | 3.08 s | 0.44 s | 7.0x |
| Core, cold | 3.23 s | 0.45 s | 7.1x |
| Whole parse, cold | 3.56 s | 0.78 s | 4.6x |

### Stage 1

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

  Note that at the time of this work, digests were only comparable
  between runs that used the same `Greynir.grammar.bin` file, as the
  binary grammar was not reproducible between generations. That has
  since been fixed (see section 6).
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

This is the list as it stood after stage 1. Items 2 and 3 were done in
stage 2, along with other things that a new profile brought up; see
section 7, which ends with a list of what remains.

1. **The Python side.** With the core 4-5x faster, the work outside it
   (mainly the reducer and the conversion of the forest to Python
   objects) is now 22-37% of the parsing time, and first-encounter
   matching accounts for the difference between cold and warm passes.
2. **Forest memory.** About 85% of the forest nodes created during a
   parse are released before it ends, and nodes and their family entries
   are allocated from the heap one by one: `malloc`/`free` is 15-20% of
   the instructions that the core now executes. Allocating them from an
   arena owned by the forest would remove most of that, but changes how
   forests are released (they are reference counted, node by node, today).
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

## 6. A reproducible binary grammar

An observation made along the way, unrelated to performance: generating
`Greynir.grammar.bin` twice from the same grammar gave files that
differed. The cause was in the grammar compiler (`grammar.py`), not in
the core.

A rule may use variants on its right hand side that do not occur in the
nonterminal being defined ("free variants"), and is expanded into one
production for each combination of their values. The free variants of a
rule were collected in a Python `set` of strings, and the order in which
such a set is iterated changes from one Python process to the next
(string hashes are randomized). For the 68 rules of the grammar that
have two or more free variants, the productions for the variant
combinations were thus generated in a different order - and given
different ids - each time the grammar was compiled; this applied to
2,556 of the 27,193 productions.

This was visible in the output of the parser. The reducer breaks exact
score ties between the families of a node in favor of the production
with the lowest id, so the winner of a tie between two variant
combinations of the same rule depended on which process had compiled the
binary grammar. In a sample of 3,041 sentences of news text, 27 got a
different tree under two of the possible orders. Most of them contain a
form such as "alla", "aðra" or "sjúka" standing without a noun, which is
both feminine singular and masculine plural in the accusative.

The free variants are now kept in the order in which they first appear
in the rule, with the first one varying fastest. The binary grammar is
thereby a pure function of the grammar text, and the order of the
variants in a rule has a defined meaning: in a rule that mentions
`/tala` before `/kyn`, all masculine combinations come before the
feminine ones, so an exact tie between a feminine singular and a
masculine plural reading goes to the masculine plural. (In the news
sample, that order gives the right reading for 15 of the disputed words;
the opposite order for 4.) `test/test_binary_grammar.py` checks both the
order and that two processes with different hash seeds produce the same
binary.

Ties of this kind remain a matter of grammar order, not of linguistic
judgment; where the order gets a common case wrong, the case calls for
a score or a preference of its own. One such case was "stöðu mála",
where a reading as the adjective "staður" with a masculine plural noun
tied with the intended noun and genitive. `Prefs.conf` now prefers the
noun "staða" over the adjective for the forms "staða" and "stöðu".

Another was "hún skammaði sjálfa sig", where "sjálfa" is feminine
singular but came out as masculine plural. No order of the variants is
right here, as "þeir skömmuðu sjálfa sig" needs the opposite answer: it
is the subject that decides. The grammar now has rules for "sjálfur"
with a reflexive pronoun that agrees in number and gender with the
subject of its verb, as a direct or indirect object and in a
prepositional phrase that follows the verb phrase. They cover the places
where the verb phrase nonterminals carry the number and gender of the
subject; a reflexive inside an infinitive clause with "að" ("hún er að
skaða sjálfa sig") or in a prepositional phrase attached to a noun
("þeir birtu myndir af sjálfum sér") still gets the grammar order.

### Ties that the family order still decides

Adding those rules changed the trees of 13 unrelated sentences in the
news sample, all of the form "f. 1985". The reducer breaks exact ties
between two families of a node by the production id and the spans of
the children, and only then by the index of the family in the forest.
That index follows from the state hashing in the core (section 3), and
shifts whenever nonterminals are added to the grammar, as their indices
are assigned in alphabetical order.

The cause was an ambiguity in the grammar. A rule of `NlTöluorð` had two
adjacent optional items for adjectives, `TöluorðForskeyti*` ("tæpar")
and `TöluorðLo?` ("efstu"). Inflected adjectives fit only one of them,
but an abbreviated adjective has no inflection info and matches every
adjective terminal, so "f." gave two derivations of the same rule, with
the same score and the same spans. The rule is now two rules, one
without and one with `TöluorðLo`; the two readings are then different
productions and the first one wins. With that, the new grammar rules
change no trees in the news sample.

The same kind of tie - one production, the same spans, assigned to
different optional items - occurs in six other rules in the news sample
(12 reductions in 3,041 sentences, against 29 for `NlTöluorð`):
`EfLiðurForskeyti` ("eins" as a pronoun or as a number), two rules of
`NlKjarni` (`NlViðbót?` or `Númer?`), `NlEind` (a relative clause or
`NlSkýring?`),
`BeygingarliðurMeðUmröðun` (`Upptalning?` or `KommaAtvikssetning?`) and
`SögnMeðF_0`. The outcome of those still depends on the family order.

## 7. Stage 2

Stage 1 kept the order of the families of children in the forest intact,
because the reducer falls back on that order when everything else is
equal. Section 6 shows that this order was never stable to begin with: it
shifts whenever a nonterminal is added to the grammar. Stage 2 therefore
no longer treats it as an invariant. What it does preserve is the content
of the forest: the same nodes, each with the same set of families.

### What the profile showed

Measured with callgrind on the warm pass over `benchmarks/corpus.txt`
(599 tokens; 3.35 million states, or 5,600 per token):

1. **Nothing on the hot path was inlined.** The extension is a shared
   library, and GCC must assume that any function with external linkage
   in a shared library can be replaced at load time. It thus neither
   inlined the small functions of the core (`push()`, the `State`
   constructor, `Production::operator[]`...) nor called them directly.
2. **83% of all states are predictions**, i.e. states with the dot at
   the start of a production, created by the Earley predictor. Such a
   state cannot already be in the column - each nonterminal is predicted
   once per column - but all of them went through the search for an
   identical state, in hash chains of five to six states on average.
   `Column::addState()` was 20% of the instructions executed.
3. **Forest nodes** were reference counted and allocated from the heap
   one by one (item 2 in section 5): about 15%.
4. **Setting up a column** cleared 24 KB of hash bins and an array with
   a pointer for every nonterminal of the grammar (58 KB).
5. **The predictor visited every production** of a predicted nonterminal
   to look at its first item, although nearly half are rejected on that
   item alone. Productions are separate heap objects, each with a
   separately allocated list of items.
6. On a **cold pass**, i.e. for words that the parser has not seen
   before, the core made 366 calls per token to the Python matching
   function. Half of them asked whether a literal terminal for a word
   (`'margur:lo'`) matches a token that is not a word at all - a number,
   a person name, a punctuation mark - and another fifth whether a verb
   or adjective terminal matches a word that has no verb or adjective
   among its meanings.

### The changes

1. **`-fno-semantic-interposition`** is added to the compiler flags on
   Linux (`eparser_build.py`). This alone made the core 19% faster.
2. **States are processed in the order in which they are added** to a
   column, which is kept as a simple list. Duplicate states are detected
   in a single open addressing hash table for the whole parse
   (`StateSet`), which is emptied between columns by incrementing a
   generation number. The hash bins and the bitmap of stage 1 are gone.
3. **Predicted states skip the search for duplicates** and are not
   entered into the table at all. (In the first column, the productions
   of the root nonterminal are there from the start, so the root is
   marked as already predicted.)
4. **The forest is an arena** (`Forest`). Nodes and family entries are
   allocated sequentially from 64 KB slabs and are never freed one by
   one; `deleteForest()` frees the slabs. There is no reference counting,
   and states have no destructor. The nodes that do not end up in the
   result (about 85%) now live until the forest is deleted, which
   `fastparser.py` does right after converting it to Python objects. The
   third member of `struct Node`, formerly the reference count, is now a
   pointer to the forest.
5. **Prediction tables.** Each nonterminal has a contiguous array of
   its productions with the first item of each, so the predictor only
   visits the productions that it creates states for. A state holds the
   item at its dot, and the item lists of productions are terminated by
   a zero item, so that the bounds check is not needed.
6. **The array of state lists by nonterminal** in a column is no longer
   cleared; a bitmap tells which of its elements are in use. One byte of
   flags per nonterminal tells the predictor both whether the nonterminal
   has been predicted and whether it has elements in the H set.
7. **Fewer calls into Python.** Two new flags in the native matching
   table (`TF_NO_NONWORD`, `TF_NEEDS_CAT`) let the core answer "no match"
   by itself for a terminal that can only match a word, when the token is
   not a word, and for a verb terminal - or an adjective terminal with an
   ending or subject case constraint - when no meaning of the word has
   that word category. Such terminals are still matched in Python when
   the answer could be yes. The conditions, and the reasoning for each,
   are in `_make_terminal_spec()` in `binparser.py`. The calls on a cold
   pass went from 366 to 77 per token.

### Verification

* **Forest content.** `benchmarks/bench_parse.py --digest --unordered`
  writes a digest of each forest that does not depend on the order of
  the families. These digests are identical before and after stage 2 for
  `benchmarks/corpus.txt` and for 677 sentences from the test suite.
* **Output.** The final trees of 3,041 sentences of news text are
  identical before and after, scores included. (Ties that fall to the
  family order - see section 6 - could have come out differently; in
  this sample, none did.)
* **Matching.** In parity mode (`GREYNIR_MATCHING_PARITY=1`), where every
  answer that the core gives by itself is compared with that of the
  Python matching function, there were no discrepancies in 3,816
  sentences.
* **Sanitizers.** The tests of the core, of the binary grammar and of
  native matching, and both sets of sentences above, run clean under
  AddressSanitizer and UndefinedBehaviorSanitizer with the assertions of
  the core enabled (`-DEPARSER_ASSERT -UNDEBUG`; note that the flags must
  be in `CXXFLAGS`, as `CFLAGS` are not used for C++ sources). This found
  one bug during the work: removing a member of `StateChunk` had left the
  storage for the states misaligned.
* **Tests.** `test/test_earley_core.py` has two new tests, for a column
  with thousands of states that go through the detection of duplicates,
  and for a root nonterminal that occurs in its own productions.

### What remains

The core is now 28% of the time of a warm parse and 58% of a cold one.

1. **The reducer and the conversion of the forest to Python objects**
   are now the largest part of a warm parse: about 55% and 18% of its
   time, respectively, when run under cProfile (which inflates the share
   of Python code). Both walk the whole forest in Python.
2. **The remaining calls into Python** on a cold pass (77 per token) are
   mostly verb terminals matched against verbs, which involves the verb
   frames of `Verbs.conf`, and terminals for numbers, names and the like.
3. **Fewer states** (item 4 in section 5). Predictions are still 83% of
   the states, and a production that starts with a nonterminal is
   predicted whether or not that nonterminal can begin with the current
   token. Filtering out the ones that cannot, or not representing
   predictions as states at all, would reduce the work of the core
   further, but is a redesign of its main loop.

# Performance of the C++ Earley-Scott core

Status: IMPLEMENTED (stages 1 to 5, and section 12) — 2026-11-11;
section 8: findings only (its lookahead filter is implemented in stage 3)

## 0. Summary

This document describes three rounds of work on the speed of parsing.
Sections 0 to 5 are about the first one (stage 1), which left the
output of the parser core unchanged in every detail. Section 7 is about
the second one (stage 2), which changes the order of the families of
children in the parse forest but not their content, and also cuts down on
the calls from the core into Python. Section 8 records an investigation of
further algorithmic changes (lookahead in the predictor, Leo's
optimization, GLR). Section 9 is about the third round (stage 3), which
goes beyond the core: the parse forest is now reduced in C++ rather than
in Python, the core has a lookahead filter, and the native matching of
tokens with terminals also serves GreynirCorrect. Stage 3 made parsing
of news text about 8x faster again (3.7x for text that has not been seen
before); its results are in section 9. Section 10 is about a fourth round
(stage 4), which deals with the work that is done the first time that a
token is seen, and makes a first pass over news text twice as fast again.
Section 11 (stage 5) is about tokenization and other work outside the
core, and makes a warm parse a quarter faster. Section 12 records where
the core spends its time after all this, and a small change that follows
from it.

Stages 1 and 2 taken together, on the machine where stage 2 was done:

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
   further, but is a redesign of its main loop. Section 8 has
   measurements and a prototype of such a filter.

## 8. Algorithmic options after stage 2 (investigated)

Status: FINDINGS ONLY — 2026-11-10. This section records what was
measured after stage 2, before stage 3 was done. Of what it suggests, the
reduction of the forest outside Python and the lookahead filter are now
implemented (section 9); the filter was done differently from the
prototype described here, in a way that has no cost on a cold pass.
Precomputed nullability is not implemented.

The question was whether a change of algorithm - Joop Leo's optimization
for right recursion, or a generalized LR parser (GLR) in place of Earley
- would cut parsing time further, given that the freedom that Earley
gives the grammar (left, middle and right recursion, ambiguity, empty
productions) is to be kept.

### Conclusions

1. **Leo's optimization would do nothing for this grammar**: it applies
   to about half a percent of the states.
2. **GLR is not worth a rewrite.** What it would bring is available
   within Earley, and several properties of this grammar count against
   it. (This is a judgment; no GLR parser was built.)
3. **One token of lookahead in the Earley predictor is worth having.** A
   crude prototype reduced the number of states to a fifth and made the
   core 1.5x faster on a warm pass, with the content of the forests
   unchanged. It needs a solution for the cold pass, though (see below).
4. **Precomputing nullability** is the natural step after that; it was
   not prototyped.
5. **All of this is bounded by the share of the core**, which is about
   30% of a warm parse. No change to the core can make a warm parse more
   than about 1.4x faster. The reducer and the conversion of the forest
   (item 1 at the end of section 7) are the larger target.

### What the core does, in numbers

Measured with a build of the stage 2 core that counts events in
`Parser::parse()`, over a cold and a warm pass of `benchmarks/corpus.txt`
(1,202 tokens in all). The grammar at the time had 7,315 nonterminals, of
which 1,453 are nullable, 27,573 productions and 6,264 terminals.

| Per token | |
|---|---|
| States processed in a column | 5,600 |
| Productions visited by the predictor | 9,630 |
| Predicted states created | 4,670 (83% of the states) |
| ... of which start with a nonterminal | 94% |
| ... of which are empty productions | 5.6% (260) |
| Nonterminals predicted | 2,265 |
| Completed states processed | 365 |
| ... of which span no tokens (nullable) | 71% (260) |
| States created by the completer | 800 |
| States created from the H set | 277 |
| States moved by the scanner | 19 |

* **84% of the predicted states are for productions that cannot begin
  with the current token** and cannot derive nothing either, going by
  the FIRST sets of the grammar and the set of terminals that the token
  matches.
* Looking back from the end of each parse, only 16% of the predicted
  states belong to a nonterminal that was ever completed from the
  position where it was predicted (13% of the predicted nonterminals).
  A filter on the next token thus removes nearly everything that a
  perfect oracle would.
* **3.9% of the states created by the completer are eligible for Leo's
  optimization**, i.e. come from a completion where a single state is
  waiting for the nonterminal, with the dot in front of its last item.
* The number of states processed per column does not grow with the
  position in the sentence: it is about 5,000 from the second token to
  the 25th. There is no quadratic behavior to remove at these sentence
  lengths.
* 13% of the states that go through the detection of duplicates are
  duplicates.

### Leo's optimization

Leo's optimization makes right-recursive rules linear rather than
quadratic, by not creating the chain of completions that follows when a
right-recursive rule is completed, in the cases where that chain is
deterministic. With 3.9% of the completer's states eligible, and the
completer creating a seventh of all states, it would remove at most half
a percent of the states. The grammar is too ambiguous for the condition
to hold often. It is also awkward to combine with returning the whole
forest, as the states that are skipped must then be reconstructed.

### GLR and related algorithms

The advantages of a GLR parser (or RNGLR, BRNGLR, GLL) over the present
core would be that it only pursues items that are consistent with the
next token, and that the closure of predictions is computed in advance,
in the states of the LR automaton. The first of these is the lookahead
filter below. Against GLR for this grammar:

* **Terminals are matched dynamically.** A token matches a set of
  terminals, some of them decided in Python. Looking up the actions of
  an LR state requires that whole set for every token, whereas Earley
  only asks about the terminals that it has predicted (77 calls into
  Python per token on a cold pass, after stage 2).
* **A fifth of the nonterminals are nullable.** Plain GLR handles empty
  productions badly; RNGLR is needed, and BRNGLR to keep the cubic bound.
* **The ambiguity is high** (a median of about 12,000 trees per
  sentence), so many stacks are alive at once and the main strength of
  LR parsing - a single stack that moves fast - rarely applies.
* The size of an LR automaton for 27,000 productions is not known; it
  was not built.
* The core, the construction of the forest and their verification would
  have to be redone.

### Lookahead in the predictor: the prototype

The prototype changes the predictor so that a production that starts
with a nonterminal is skipped if it can neither begin with the current
token nor derive nothing:

```cpp
// Once per grammar: for each nonterminal, its FIRST set as a bitmap of
// terminals (ntFirst) and whether it is nullable (ntNull), computed by
// the usual fixpoint iteration over the productions.
// Once per column: xM, a bitmap of the terminals that match the token
// (Column::matches() called for every terminal), and xV, a byte per
// nonterminal: 0 = not known, 1 = can begin with the token, 2 = cannot.

// In the predictor, for each production pp of the predicted nonterminal
// whose first item is a nonterminal:
bool alive = true;
for (UINT m = 0; ; m++) {
   INT it = (*pp)[m];
   if (it == 0) break;                 // All items nullable: keep
   if (it > 0) {                       // Terminal after nullable items
      alive = pEi->matches(nHandle, (UINT)it);
      break;
   }
   UINT b = ~((UINT)it);
   if (!xV[b])                         // FIRST(b) and xM intersect?
      xV[b] = intersects(ntFirst[b], xM) ? 1 : 2;
   if (xV[b] == 1) break;              // Can begin with the token: keep
   if (!ntNull[b]) { alive = false; break; }
   // Nullable, but cannot begin with the token: look at the next item
}
if (!alive) continue;                  // Skip the production
```

Results on `benchmarks/corpus.txt`, same machine and session as the
figures for the stage 2 core:

| | Stage 2 core | With the prototype |
|---|---|---|
| States created per token | 5,600 | 1,056 |
| Core, warm | 0.107-0.116 s | 0.072 s |
| Whole parse, warm | 0.36-0.39 s | 0.32 s |
| Core, cold | 0.35-0.41 s | 0.56 s |
| Whole parse, cold | 0.63-0.72 s | 0.83 s |

The digests of `bench_parse.py --digest --unordered` are identical with
and without the filter for all 51 sentences. With the filter, 657
nonterminals per token are tested for whether they can begin with the
token (32% can), and 683 productions per token are skipped directly; the
rest of the reduction comes from the nonterminals that are then never
predicted.

**The warm figure is a lower bound on the gain.** The prototype calls
`matches()` for all 6,264 terminals in every column, clears a byte per
nonterminal in every column, and tests a nonterminal by intersecting two
bitmaps of 98 words. A proper implementation would keep, for each token
(by the same key as the matching cache), a bitmap of the nonterminals
that can begin with it, and test one bit per production. That bitmap is
the union, over the terminals that the token matches, of a table that
gives the nonterminals with each terminal in their FIRST set.

**The cold pass is the problem to solve.** It became slower in the
prototype because all terminals are matched against every new token,
including those that are decided in Python. Possible ways out: evaluate
only the terminals that the word categories of the token make possible
(an index of terminals by category); treat a terminal whose answer is
not known natively as possibly matching, at the cost of a weaker filter;
or decide more terminals natively (item 2 at the end of section 7).

### Nullable nonterminals

After the filter, empty derivations would be a large part of what is
left: per token, 260 empty productions are predicted, 260 states that
span no tokens are completed, and 277 states are created from the H set
- out of about 1,000 states. All of this is the same in every column,
as it depends on the grammar alone. Precomputing which nonterminals are
nullable (as in Aycock and Horspool, "Practical Earley Parsing", 2002)
lets the predictor move the dot over a nullable nonterminal at once, and
the H set goes away. `Node.from_c_node()` in `fastparser.py` already
discards the nodes that span no tokens, so nothing that the reducer uses
would be lost; what the forest should contain in their place has to be
worked out. This was not prototyped, and the gain is an estimate.

### Suggested order of work

1. The reducer and the conversion of the forest: moving the walk of the
   forest, or at least the scoring pass, out of Python.
2. The lookahead filter, with a bitmap per token and a solution for the
   cold pass.
3. Precomputed nullability.
4. Not Leo's optimization, and not GLR.

## 9. Stage 3: reduction in C++, lookahead, and native matching for derived tokens

Status: IMPLEMENTED — 2026-11-10

After stage 2, the core was 28% of a warm parse of `benchmarks/corpus.txt`.
Timing the phases of a warm parse showed where the rest went (51 short
sentences; 1,000 sentences of news text, 19 tokens on average):

| Phase | `corpus.txt` | News text |
|---|---|---|
| Core (`earleyParse()`) | 28% | 14% |
| The forest in Python: conversion to Python objects, counting the trees, finding the terminals of each token, scoring and reduction | 59% | 82% |
| Tokenization | 6% | 3% |
| Simplification of the tree | 4% | 1.5% |

The forest that the core returns has about 700 nodes for a sentence of 12
tokens, and grows much faster than the sentence. Python walked all of it
four times (the conversion, which created an object for each node, and
three passes over those objects) to arrive at a tree of about 80 nodes.
For news text, this was six times the work of the core.

### 9.1 The reducer in C++

`ereducer.cpp` (new) does all of the above on the forest as the core left
it, and hands Python a serialized form of the resulting tree only:

1. It derives the logical forest from the binarized one, as
   `Node.from_c_node()` does: the interior nodes of a production are
   folded into the list of children of the completed nonterminal, nodes
   that span no tokens are dropped, and only the families with the highest
   priority are kept.
2. It counts the trees in the forest, with integers of arbitrary size
   (the longest sentences in a sample of news text have up to 8 x 10^24
   trees, which does not fit in 64 bits).
3. It lists the terminals that each token is matched with. Python scores
   those matches, with the same heuristics as before
   (`Reducer._score_options()`), and passes the scores back.
4. It scores the forest and picks the winning family of each node,
   following `ParseForestReducer.go()` to the letter: the same scopes for
   verbs and prepositions, the same memoization by context, the same
   tie-breaks.
5. It serializes the winning tree. `Node.from_serialized()` creates the
   Python nodes: about a tenth of what was created before.

What the reducer needs to know about the grammar (the tags of the
nonterminals, their score adjustments, the categories of the terminals)
arrives as tables when a parser is first used (`ReducerTables` in
`eparser.h`). What depends on the vocabulary is asked of Python through
two callbacks: does this verb take that preposition, or that particle?
They are few (about eight per sentence of news text) and are answered
by the same methods as before (`verb_prep_bonus()`,
`verb_particle_bonus()`).

**The Python implementation remains**, as the reference and as the
fallback. `Reducer.parse_and_reduce()` is the new entry point, used by
`Greynir` and `IncrementalParser`; it gives the same result as calling
`Fast_Parser.go()`, `Fast_Parser.num_combinations()` and
`Reducer.go_with_score()` in turn, which still work as before, in Python.
The C++ reducer stands aside, and the work is done in Python, if:

* the environment variable `GREYNIR_DISABLE_CPP_REDUCER` is set, or a
  class derived from `Reducer` sets `_USE_CPP_REDUCER = False`;
* a derived class overrides any of the methods that the C++ code
  replicates (`Reducer.go_with_score()`, `_reduce()`,
  `_calc_terminal_scores()`, `_find_options()`, the class of the forest
  reducer; `Fast_Parser.go()`, `num_combinations()`);
* the forest has a cycle, or is more than 1,000 levels deep (the limit
  bounds the use of the native stack; the Python implementation is bound
  by the recursion limit of the interpreter in the same way).

**The two must give identical results**: the same tree, the same score of
every node, the same number of trees. Some details that this required:

* The score that ends up on a node which is scored in several verb
  contexts is the one from the context that was first seen last.
* A node that is shared between two contexts in the resulting forest
  (possible below a nonterminal tagged `no_reduce`) is reduced the way
  that the first context to reach it wants.
* Lists of verbs are compared by content in the context signatures, so
  the C++ code interns them.

With the environment variable `GREYNIR_REDUCER_PARITY` set, every sentence
is reduced both ways and the results are compared, node by node
(`same_forest()` in `reducer.py`); differences are counted in
`Reducer.parity_mismatches`, and the Python result is returned. **A change
to `reducer.py` or to `Node.from_c_node()` must be mirrored in
`ereducer.cpp`**; `test/test_reducer.py` and the parity mode are there to
catch it if it is not.

### 9.2 The lookahead filter

A state of the parser can only ever advance if what follows its dot can
begin with the current token, or can derive nothing at all. States for
which neither holds are dead weight, and they were five out of six (section
8). They are no longer created. This applies to all states, not only to
the predictions: also to those that the completer and the scanner create.

When a grammar is loaded, `Grammar::analyze()` calculates:

* which nonterminals are nullable;
* a division of the nonterminals into classes, such that the
  nonterminals of a class can begin with exactly the same tokens. A class
  is a strongly connected component of the graph of "something derived
  from A can begin with B". The grammar has 7,315 nonterminals in about
  7,100 classes, so nearly all classes have one member, but those that
  have more make the graph of classes free of cycles;
* for each class, the terminals that its nonterminals can begin with
  directly, and the other classes that they can begin with;
* for each position of the dot in each production, a filter: what to look
  at to tell whether a state with that dot is viable (`LF_*` in
  `eparser.h`). For most positions this is a single terminal or a single
  class.

Whether a class can begin with a token is found out by a depth-first
search through the classes, asking whether the token matches their
terminals. The answer is kept in two bits per class, in the same buffer as
the matching cache of the token, so it is only calculated the first time
that a token (by its key) is seen in a process; after that, the test of a
state is a lookup. The search asks about a subset of the terminals that
the core asked about before, in a different order, so **a cold pass has no
more calls into Python than before**. This was the weakness of the
prototype in section 8, which matched all terminals with every token.

**The error position is unchanged.** With the filter, the core can find out
that a parse is going to fail one column earlier than it did. It then
stops, and reports the token where the failure would have been found
without the filter (`bStopped` in `Parser::parse()`), so `ParseError`
carries the same token index as before.

The filter can be turned off with the environment variable
`GREYNIR_DISABLE_LOOKAHEAD` (`setLookahead()` in the C interface). This
changes nothing but the time that a parse takes.

Results for the core, per token of `benchmarks/corpus.txt`: the warm
pass went from 0.21 ms to 0.055 ms.

### 9.3 Memory

The matching cache has an entry for every distinct token seen (up to
25,000 of them). An entry was a byte per terminal, 6,265 bytes. It is now
two bits per terminal and two bits per class of nonterminals, 3,340 bytes
in all, so the cache takes about half the memory that it did, lookahead
included. The entries of a token can be written by more than one thread;
bits are only ever set, and to the same values by all, so the worst that
can happen is that an answer is calculated twice.

Measured over 1,000 sentences of news text (5,957 distinct tokens):

| | Before | After |
|---|---|---|
| Growth of resident memory | 108 MB | 70 MB |
| Peak resident memory | 415 MB | 336 MB |
| Matching cache | 37.3 MB | 19.9 MB |

The peak is lower because far fewer states and tree nodes are created
during a parse, and because the forest no longer exists as Python objects.
A tree node of the core is 8 bytes larger than before (a pointer to its
counterpart in the reducer); the grammar takes about a megabyte more (the
filters and the classes).

### 9.4 Native matching for derived token classes

Native matching (stage 2 and before) was turned off for any parser that
overrides `wrap_token()`, since its tokens might match terminals
differently. That was the case for GreynirCorrect, which therefore matched
everything in Python, which was most of the time of a first pass over
new text.

The token class of GreynirCorrect only overrides what
`BIN_Token.verb_matches()` consults (`verb_matches_arguments()` and the
like), and that method is only used when a verb terminal is matched with a
verb, which is done in Python in any case. The gate now looks at the class
of the tokens that a parser creates (`Fast_Parser._native_token_class()`):
native matching is used if the class is `BIN_Token`, or is derived from it
without overriding anything but those hooks. No change is needed in
GreynirCorrect.

### Results

`benchmarks/bench_parse.py`, the commit before stage 3 against stage 3, on
the same machine; the fastest pass of several:

| `benchmarks/corpus.txt` (51 sentences, 599 tokens) | Before | After | Speedup |
|---|---|---|---|
| Whole parse, warm | 0.44 s | 0.105 s | 4.2x |
| Core, warm | 0.137 s | 0.033 s | 4.2x |
| Whole parse, cold | 0.79 s | 0.48 s | 1.6x |
| Core, cold | 0.46 s | 0.38 s | 1.2x |

| 1,000 sentences of news text (19,213 tokens) | Before | After | Speedup |
|---|---|---|---|
| Whole parse, warm | 36.5 s | 4.7 s | 7.8x |
| Core, warm | 5.0 s | 1.5 s | 3.3x |
| Whole parse, first pass | 41.9 s | 11.3 s | 3.7x |
| Core, first pass | 11.3 s | 7.9 s | 1.4x |

The first pass over the news text is 'cold' to the extent that its tokens
are new: this is what a process sees when it parses text that it has not
parsed before.

GreynirCorrect, checking 300 sentences of news text (its own work, such as
spelling correction, included):

| | Before | After | Speedup |
|---|---|---|---|
| First pass | 40.0 s | 6.8 s | 5.8x |
| Second pass | 15.4 s | 3.9 s | 3.9x |

### Verification

* **The reducer**: the C++ and Python implementations agree, node for
  node and score for score, on 3,709 sentences in parity mode (and on
  GreynirCorrect's error grammar). `test/test_reducer.py` compares the two
  on thousands of sentences of pseudo-random grammars, with random tags,
  priorities, scores and bonuses, which exercises what real text rarely
  does (`no_reduce`, nodes scored in several contexts, exact ties). Of 26
  bugs deliberately introduced into `ereducer.cpp`, one at a time, the
  tests catch 25; the remaining one is in a comparison that can't decide
  anything (the starting positions of children in a tie-break, which
  follow from the ending positions of the children before them).
* **The lookahead filter**: order-independent forest digests are identical
  with and without it for 728 sentences. `test/test_earley_core.py`
  compares forests and error positions with and without the filter over
  pseudo-random grammars, half of them with empty productions. Of 17 bugs
  deliberately introduced into the filter and the code around it, the
  tests catch 15; the other two make the filter let more states through
  than it should, which only costs time.
* **End to end**: trees, scores, numbers of trees and error positions are
  identical to those of the previous commit for 3,764 sentences (389 of
  which do not parse).
* **GreynirCorrect**: its test suite passes; trees and annotations for 300
  sentences are identical to those from the previous commit; no
  discrepancies in matching or reducer parity mode.
* **Sanitizers**: the core, reducer, matching and binary grammar tests,
  and 2,160 sentences in parity mode, run clean under AddressSanitizer and
  UBSan with the assertions of the core enabled. (This turned up an
  assertion in `Parser::push()` that was stricter than the code it guards;
  it has been removed.)
* The full test suite, ruff and mypy pass; the core, reducer and matching
  tests pass on PyPy 3.11; both C++ files compile with clang (libstdc++
  and libc++).

### What remains

A warm parse of news text now divides into: the core 33%, the reduction
30% (of which the C++ code is 17 points, the scoring of terminals in
Python 5 and the creation of the Python nodes 5), tokenization 22%, and
simplification of the tree 12%.

1. **Verb terminals on a cold pass.** A first pass over news text takes
   more than twice as long as a warm one, and about 40% of its time is
   spent in Python deciding whether tokens match terminals (43 calls per
   token): 77% of that for verb terminals (`BIN_Token.verb_matches()`: the
   argument frames of `Verbs.conf`, impersonal verbs, subject cases) and
   13% for adjective terminals. Verb terminals can be matched natively
   if each verb meaning of a token carries a summary
   of what the hooks say about its lemma (allowed argument cases, subject
   cases, impersonal or not), computed through the hooks of the token
   class so that GreynirCorrect is served as well. This is the largest
   remaining item for text that has not been seen before.
   **Done in stage 4; see section 10.**
2. **Tokenization** is now a fifth of a warm parse. It has not been looked
   at in this work.
3. **Nullable nonterminals** (section 8) are still handled through the H
   set of the core.
4. **The reducer** creates a hash table entry per node and context; flat
   tables indexed by node would be faster. Its Python part could move to
   C++ as well, if the heuristics of `_score_options()` are expressed as
   data.

## 10. Stage 4: the first encounter with a token

Status: IMPLEMENTED — 2026-11-10

After stage 3, a first pass over news text took 2.4 times as long as a
warm one. The difference is work that is done once for each distinct
token (by `BIN_Token.key`), with the results kept in the matching cache.
For 2,032 new tokens in 300 sentences of news text:

* **43 calls into Python per token**, to `BIN_Token.matches()`: 77% of
  the time in them for verb terminals, 13% for adjective terminals that
  demand a subject case, the rest for prepositions, names and the like.
* **3,045 terminals evaluated per new token**, nearly half of all the
  terminals in the grammar. Four out of five terminals are literals
  (`"vera:so"_et_p3`), and the parser gets to ask about most of them, one
  by one, for every new token.

### 10.1 Verb terminals

Whether a verb terminal (`so_1_þgf_et_p3`, `so_subj_op_þf`, ...) matches a
verb is decided by `BIN_Token.verb_matches()`, from three things: the
variants of the terminal, the BÍN inflection string of the verb form, and
what a handful of other methods say about the lemma: which argument cases
it takes (`verb_matches_arguments()`), which subjects
(`verb_subject_matches()`), and whether it is impersonal
(`verb_is_strictly_impersonal()`, `verb_cannot_be_impersonal()`).
GreynirCorrect overrides those four, and the class attribute
`_RESTRICTIVE_VARIANTS`.

The method is now replicated in C++ (`verbMatchMeaning()` in
`eparser.cpp`):

* The variants of the terminal and the features of the verb form were
  already bit sets, with the same bit for a variant and for its BÍN string
  (`BIN_Token.VBIT`), so most of the method becomes a few masks.
* What the other methods say about a verb is asked in advance, once for
  each lemma and inflection string, when the packed matching data of a
  token is created (`_verb_profile()` in `binparser.py`), and stored in
  the meaning record: a bit for each of the 14 combinations of argument
  cases that the verb terminals of the grammar have, a bit for each of the
  9 kinds of subject that they ask for, and four flags.
* The questions go to the methods of the class of the token. A derived
  class that overrides them, as GreynirCorrect's does, thus gets its own
  answers, and its verb terminals are matched natively as well.
  `_RESTRICTIVE_VARIANTS` is passed as a mask, per parser.
* If a derived class overrides `verb_matches()` itself, the verbs of its
  tokens are matched in Python as before (the token records then lack the
  flag `TKF_VERBS`).

All 367 verb terminals of the grammar are handled this way.

### 10.2 The other terminals that were matched in Python

* **Adjective terminals with a subject case** (`lo_sþgf_...`, 180
  terminals): the meaning record of an adjective says which cases its
  subject can be in.
* **Prepositions, proper names, person names, street names, and adverbs
  that are not prepositions** (`fs`, `sérnafn`, `person`, `gata`, `eo`): the
  matchers of these look at a property of the token as a whole, before
  anything else: is its text a known preposition, is it capitalized, has
  it a meaning that is a name. Those properties are now flags in the token
  record (`_word_token_flags()`), and the core does not call Python for a
  word that lacks the property. For `eo`, the flag is the whole answer.

Of the 6,264 terminals of the grammar, 42 can still lead to a call into
Python for a word with meanings in BÍN (36 of them only if the word has
the property in question). Tokens that are not words (numbers, dates,
person names and so on) are matched in Python as before, unless the
terminal is one that never matches such tokens.

Since the hooks are now called when the matching data of a token is
created, rather than when a match is evaluated, they must be pure
functions of their arguments. (`verb_matches()` was already cached on
that assumption.)

### 10.3 Prefilling the matching cache

A literal terminal can only match a word if the text of the word, or one
of its lemmas, is that literal. When a token is seen for the first time,
all literal terminals are marked as not matching it in one step, by
combining a prepared bit pattern with the (empty) matching cache of the
token (`Parser::prefillCache()`) - except those whose literal does occur
in the token, which are found through an index and left to be evaluated
in the normal way. For a token that is not a word, the pattern also
covers the terminals that never match such tokens. Nothing is prefilled
in parity mode, where every match is evaluated both ways.

### Results

For the 300 sentences: 43 calls into Python per token became 8, and
3,045 evaluations per new token became 597.

`benchmarks/bench_parse.py`, stage 3 against stage 4 on the same machine:

| | Stage 3 | Stage 4 | Speedup |
|---|---|---|---|
| 1,000 news sentences, first pass | 11.3 s | 5.6 s | 2.0x |
| ... of which in the core | 7.9 s | 2.5 s | 3.1x |
| `benchmarks/corpus.txt`, cold | 0.48 s | 0.19 s | 2.5x |
| GreynirCorrect, 300 news sentences, first pass | 6.8 s | 4.9 s | 1.4x |

Warm passes are unchanged (4.3 s for the news sentences), so a first pass
is now 1.3 times a warm one. Against the commit before stage 3, the first
pass over the news sentences is 7.5x faster (41.9 s to 5.6 s), and
GreynirCorrect's 8.2x (40.0 s to 4.9 s). Memory use is unchanged; a
meaning record is 16 bytes larger.

### Verification

* **Parity**: in matching parity mode, where every native decision is
  compared with that of `BIN_Token.matches()`, there are no differences
  over 3,709 sentences, nor in GreynirCorrect with its own token class
  over 300 sentences and its test suite.
* **Exhaustive tests** (`test/test_native_matching.py`): the parser only
  asks about the terminals that its predictions lead to, so the tests ask
  about all of them, through a test entry point (`nativeMatch()`): every
  verb terminal against every token of a set of sentences rich in verb
  forms; against verbs with pseudo-random inflection strings; with a token
  class that overrides the hooks; and with one that has its own
  `verb_matches()`. The prefilled cache entries are checked against
  Python as well.
* **Mutation testing**: of 47 bugs deliberately introduced into the new
  code, one at a time, the tests catch 45. The other two are in a test
  for subj terminals with middle voice, of which the grammar has none, and
  in a test that the next one repeats (as in the Python original).
* **End to end**: trees, scores, numbers of trees and error positions are
  identical to those from before stage 3 for 3,764 sentences;
  GreynirCorrect's trees and annotations are identical for 300 sentences.
* The tests and 1,175 sentences run clean under AddressSanitizer and UBSan
  with assertions enabled; the full suite (146 tests), ruff and mypy pass;
  the core, reducer and matching tests pass on PyPy 3.11.

### What remains of a first pass

What is left of the difference between a first pass and a warm one is
spread over: the lookups of new words in BÍN by the tokenizer; the
creation of the token records (some tens of microseconds per new token);
the calls into Python for tokens that are not words (8 per token overall);
and the 600 native evaluations per new token.

## 11. Stage 5: tokenization, and the work around the core

Status: IMPLEMENTED — 2026-11-10

After stage 4, a warm parse of news text divided into: the core 33%, the
reduction 32%, tokenization 22% and simplification of the tree 13%.

### 11.1 Tokenization: a cache of word lookups

Tokenization took 41 microseconds per token. The Tokenizer package itself
(seven stages, from splitting the text to recognizing dates) was a quarter
of that, about 5% of a warm parse, with no stage standing out; it was left
alone. Nearly half was a single stage of `bintokenizer.py`: `annotate()`,
which looks every word up in BÍN through `GreynirBin.lookup_g()`.

BinPackage caches the raw entries of a word form (4,096 word forms), but
a lookup does much more than fetch them, every time:

* It tries the word in other letter cases, depending on where it is in
  the sentence.
* A word that is not in BÍN is analyzed as a compound word, which takes
  many more lookups and is not cached at all.
* A named tuple is created for every entry found, and then another one
  from it (`BinEntry`, then `BIN_Tuple`).
* The cache of raw entries is too small for running text: a fifth of the
  lookups missed it on a repeated pass over 1,000 sentences.

The result depends on the word and two flags only, so `lookup_g()` now
keeps it (`GreynirBin._lookup_cache`): up to 20,000 results, with the
lemmas, categories and inflection strings interned, since the same ones
occur in entry after entry. The cache is emptied when it is full, like
the matching cache of the parser. An entry takes about 0.9 KB, so the
cache can grow to about 18 MB. Callers get a new list each time, as
before, but the tuples in it are shared.

Tokenization went from 41 to 23 microseconds per token.

The rest of the tokenization time is spread thinly over a dozen stages
that each handle every token. Two changes to the phrase matching at the
end of the pipeline were tried and dropped: they would have saved half a
percent of a parse.

### 11.2 The reducer

A profile of the C++ reducer (stage 3) showed a quarter of its work in
the allocation and release of memory, and more in its hash tables:

* The result of scoring a node in a context was kept in a hash table.
  Nearly all nodes are only ever scored in one context, so the first
  result is now kept in the node itself, and the hash table is only used
  for the others.
* The number of trees below each node was a vector of limbs. A number
  that fits in 64 bits (nearly all of them) is now kept without
  allocating anything.
* The token/terminal matches were collected through a hash table; they
  are now in a short linked list per token.

The reducer executes 37% fewer instructions, and takes 0.46 s for 1,000
news sentences instead of 0.80 s.

### 11.3 Simplification of the tree

`Simplifier` (in `simpletree.py`) walked the tree through the general
`ParseForestNavigator`, whose flexibility (memoization, results passed up
the tree, hooks for families) cost more time than the work done at the
nodes. It now walks the tree directly, unless a class derived from it is
in use. `simplify_terminal()` and `augment_terminal()`, two pure string
functions called for every token, are cached. Simplification takes 0.38 s
instead of 0.52 s.

### Results

| 1,000 news sentences | Stage 4 | Stage 5 | Speedup |
|---|---|---|---|
| Whole parse, warm | 4.3 s | 3.4 s | 1.27x |
| Whole parse, first pass | 5.6 s | 5.1 s | 1.10x |
| Tokenization, warm | 0.88 s | 0.50 s | 1.76x |

Against the commit before stage 3, a warm parse of the news sentences is
now 10.7x faster (36.5 s to 3.4 s) and a first pass 8.3x faster (41.9 s
to 5.1 s). Memory use is as before, the lookup cache included (it is
offset by the tuples that are no longer created for every word).

### Verification

* The tokens of 3,764 sentences (70,639 tokens, with their meanings) are
  identical with and without the lookup cache.
* Everything that a parse produces is identical to the output before this
  stage for the 3,764 sentences: trees, scores, numbers of trees, error
  positions, the full simplified tree (compared by digest), lemmas and
  categories.
* The C++ and Python reducers agree on 3,709 sentences in parity mode. Of
  34 bugs deliberately introduced into the reducer, the new code included,
  the tests catch 32; the other two do not change its output (one is
  described in section 9, the other creates duplicate entries in a list
  that is turned into a set).
* GreynirCorrect: its tests pass, and its trees and annotations for 300
  sentences are identical.
* Sanitizers, PyPy 3.11, the full test suite, ruff and mypy as before.

Note for comparisons like these: some values in tokens come from sets of
strings (the possible cases of an amount, the order of the variants of a
person name), so their order differs between processes unless
`PYTHONHASHSEED` is fixed. This is not new, and has not been seen to
affect a parse, but it has to be fixed to compare token dumps.

### What remains

A warm parse of news text now divides into: the core 40%, the reduction
28% (the C++ code 14 points, the scoring of terminals in Python 7, the
creation of the Python nodes 5), tokenization 17%, and simplification 11%.

1. **The core** is the largest part again. The lookahead filter left
   about a thousand states per token, a good part of them for nullable
   nonterminals (section 8). Two calls into Python per token per sentence
   remain in a warm parse (for the matching cache and the token record),
   which are about 4% of the core. **Those calls are no longer made for
   tokens that have been seen before; see section 12.**
2. **The scoring of terminals** (`Reducer._score_options()`) is Python
   code that works on dicts keyed by terminals, whose hash function is
   also Python code.
3. **Tokenization** would need restructuring to get much faster: fewer
   passes over the tokens, rather than faster ones.

## 12. Where the core spends its time, and handing the buffers over

Status: IMPLEMENTED — 2026-11-11

### What the core does, per token

To see what is left to gain in the core - and whether it would pay to
generate machine code for the grammar, or for each column - the core was
built with cycle counters around its parts (a temporary build, not in the
repository) and run on a warm pass over the 1,000 news sentences. The
core then takes about 215,000 cycles per token (63 µs on the i7-4770),
which is 40% of the parse. They divide as follows:

| Part of the core | Share | Per token |
|---|---|---|
| Predictor | 36% | 315 nonterminals predicted; 1,659 productions tested against the lookahead filter, 616 states created |
| Completer, spans with tokens | 35% | 179 completed states; 581 waiting states tested, 263 states created |
| Nullable nonterminals | 17% | 72 nullable nonterminals predicted, each of them through an empty production; 50 nonterminals predicted that can't begin with the token; 160 states created by stepping over nonterminals that derive nothing |
| Start and end of a column | 9% | of which the two calls into Python, for the matching cache and the token record: 4.9% |
| Scanner | 2% | 27 states tested, 16 moved to the next column |
| Setup and teardown of a parse | 2% | |

Of the 1,659 productions that the predictor tests per token, 440 begin
with a terminal (21 of which match the token), 965 with a nonterminal
that is not nullable (421 of which can begin with the token), 182 with
nullable nonterminals and 72 are empty.

The conclusions that were drawn from this:

* **Machine code would not buy much.** The inner loops are already
  short: a prediction that fails costs a few table lookups (two bits per
  terminal or class of nonterminals), and the rest of the time goes into
  creating states, looking them up and linking forest nodes, which
  generated code would have to do as well. Its gain was estimated to be
  of the same order as that of the items below, at many times the cost
  and with a platform dependency that the package does not have now.
* **The calls into Python at the start of each column** are the one part
  that is pure overhead. This is what was done; see below.
* **Nullable nonterminals** take a sixth of the core through the H set
  and the empty completions, although the grammar is fixed: which
  nonterminals derive nothing, and which states follow from stepping
  over them, could be calculated when the grammar is loaded (section 8).
  Estimated gain: 4 to 5% of a warm parse.
* **The predictor repeats itself**: what a nonterminal predicts in a
  column only depends on the nonterminal and on the token of the column,
  so the list of productions that pass the filter could be kept per
  distinct token, next to the matching cache. Estimated gain: 2 to 4%
  of a warm parse.

### The change

The core used to call back into Python twice at the start of every
column: `alloc_func()`, for the matching cache of the token of the
column, and `meanings_func()`, for its packed matching data. In a warm
parse, both calls end in a dictionary lookup that finds a buffer that
is already there.

`Fast_Parser.parse_forest()` now looks those buffers up before it calls
the core (`ParseJob.known_buffers()`), and passes them in two arrays, one
entry per token, to a new entry point, `earleyParseEx()`. An entry is
NULL for a token that has not been seen before (or for all tokens, if an
array is not given); `Column::startParse()` then asks for the buffer
through the callbacks, as before. The buffers are thus created by the
same code as before, at the same point in the parse, and those of tokens
that the core never gets to - the ones that follow an error - are not
created. `earleyParse()` remains, and is the same as `earleyParseEx()`
with no arrays.

### Results

Measured within one process, alternating between the two ways (best of
8 passes over the news sentences, and of 30 over the corpus file):

| Whole parse, warm | Callbacks | Hand-over | Gain |
|---|---|---|---|
| 1,000 news sentences | 3.38 s | 3.27 s | 3.4% |
| `benchmarks/corpus.txt` | 0.0856 s | 0.0838 s | 2.1% |

The time that `bench_parse.py` reports for the core goes from 1.38 s to
1.27 s for the news sentences, but part of that work has only moved: the
arrays are now built in Python before the core is called. A first pass
is as before, as it mostly consists of tokens that are new.

### Verification

* Trees, scores, numbers of trees and error positions of the 1,000 news
  sentences (1,003 as the parser splits them, 148 of which fail), in two
  passes, are identical to those of release 4.0.0 from PyPI.
* `test/test_earley_core.py::test_buffer_handover`: for pseudo-random
  grammars, with and without empty productions, the three ways of calling
  the core (`earleyParse()`, `earleyParseEx()` without arrays and with
  them) give the same forests and error positions, and the core asks for
  exactly the buffers that it was not handed.
* `test/test_native_matching.py::test_buffer_handover`: with the real
  grammar, a second pass over a set of sentences makes no calls for
  buffers, and all results are the same as in the first pass and as
  without the hand-over.
* The full test suite in the default mode and with
  `GREYNIR_MATCHING_PARITY=1 GREYNIR_REDUCER_PARITY=1`; the tests of the
  core, the matching and the reducer and the news sentences in a build
  with AddressSanitizer, UndefinedBehaviorSanitizer and the assertions of
  the core; ruff and mypy; the tests of GreynirCorrect.

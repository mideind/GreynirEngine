/*

   Greynir: Natural language processing for Icelandic

   C++ Earley parser module

   Copyright © 2026 Miðeind ehf.

   This software is licensed under the MIT License:

      Permission is hereby granted, free of charge, to any person
      obtaining a copy of this software and associated documentation
      files (the "Software"), to deal in the Software without restriction,
      including without limitation the rights to use, copy, modify, merge,
      publish, distribute, sublicense, and/or sell copies of the Software,
      and to permit persons to whom the Software is furnished to do so,
      subject to the following conditions:

      The above copyright notice and this permission notice shall be
      included in all copies or substantial portions of the Software.

      THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
      EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
      MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
      IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
      CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
      TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
      SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

   This module implements an optimized Earley parser in C++.
   It is designed to be called from Python code with
   already parsed and packed grammar structures.

   The Earley parser used here is the improved version described by Scott & Johnstone,
   referencing Tomita. This allows worst-case cubic (O(n^3)) order, where n is the
   length of the input sentence, while still returning all possible parse trees
   for an ambiguous grammar.

   See Elizabeth Scott, Adrian Johnstone:
   "Recognition is not parsing — SPPF-style parsing from cubic recognisers"
   Science of Computer Programming, Volume 75, Issues 1–2, 1 January 2010, Pages 55–70

*/

#include <stdlib.h>
#include <string.h>
#include <wchar.h>
#include <new>
#include <atomic>


// Assert macro. The assertions are enabled in DEBUG builds (which also
// write a trace of the parse to stdout), or - without the trace - by
// defining EPARSER_ASSERT. Note that NDEBUG must not be defined in
// either case; Python's default compiler flags do define it.
#if defined(DEBUG) || defined(EPARSER_ASSERT)
   #define ASSERT(x) assert(x)
#else
   #define ASSERT(x)
#endif


typedef unsigned int UINT;
typedef int INT;
typedef wchar_t WCHAR;
typedef char CHAR;
typedef unsigned char BYTE;
typedef bool BOOL;
typedef unsigned long long UINT64;


class Production;
class Parser;
class State;
class Column;
class NodeDict;
class Label;
class Forest;
class Reducer;
class StateSet;
struct StateChunk;
struct RNode;


class AllocCounter {

   // A utility class to count allocated instances
   // of an instrumented class. Add this as a static
   // member (named e.g. 'ac') of the class to be watched
   // and call ac++ and ac-- in the constructor and destructor,
   // respectively.

   // The counters are atomic (with relaxed ordering, which is
   // sufficient for statistics) so that concurrent parses in
   // multiple threads do not cause data races.

private:

   std::atomic<UINT> m_nAllocs;
   std::atomic<UINT> m_nFrees;

public:

   AllocCounter(void)
      : m_nAllocs(0), m_nFrees(0)
      { }
   ~AllocCounter(void)
      { }

   void operator++(int)
      { this->m_nAllocs.fetch_add(1, std::memory_order_relaxed); }
   void operator--(int)
      {
         ASSERT(this->numAllocs() > this->numFrees());
         this->m_nFrees.fetch_add(1, std::memory_order_relaxed);
      }
   // Add a batch of allocations and frees in one go. This is used
   // for objects that are created and destroyed at a high rate within
   // a single parse (States in particular): they are counted in plain
   // parse-local counters and added here once per chunk or column, since
   // an atomic increment per object is a measurable cost on the hot path.
   void add(UINT nAllocs, UINT nFrees)
      {
         if (nAllocs)
            this->m_nAllocs.fetch_add(nAllocs, std::memory_order_relaxed);
         if (nFrees)
            this->m_nFrees.fetch_add(nFrees, std::memory_order_relaxed);
      }
   UINT numAllocs(void) const
      { return this->m_nAllocs.load(std::memory_order_relaxed); }
   UINT numFrees(void) const
      { return this->m_nFrees.load(std::memory_order_relaxed); }
   INT getBalance(void) const
      { return (INT)(this->numAllocs() - this->numFrees()); }

};


// Lookahead filters. A state can only ever advance if what follows its
// dot can either begin with the current token, or derive nothing at all.
// For each position of the dot in each production, a filter tells how to
// find that out; it is calculated when the grammar is loaded (see
// Grammar::analyze()). The kind of the filter is in its two lowest bits
// and its argument in the bits above them.
#define LF_ALWAYS    0u  // What follows the dot can derive nothing: always viable
#define LF_TERMINAL  1u  // A terminal follows: does it match? (arg: the terminal)
#define LF_START     2u  // A nonterminal that can't derive nothing follows:
                         // can it begin with the token? (arg: its class)
#define LF_MULTI     3u  // One or more nonterminals that can derive nothing
                         // follow, and then an item that can't: can any of
                         // them begin with the token? (arg: their number)

struct Prediction {

   // An entry in the prediction table of a nonterminal:
   // one of its productions, along with the first item of the production
   // (a negative nonterminal index, a positive terminal index,
   // or 0 if the production is empty) and the lookahead filter
   // for the dot at the start of the production

   Production* pProd;
   INT iFirst;
   UINT nFilter;

};


class Nonterminal {

   // A Nonterminal has an associated list of owned Productions

   friend class AllocReporter;

private:

   WCHAR* m_pwzName;
   Production* m_pProd;
   // The prediction table: the productions of the nonterminal in a
   // contiguous array, in the same order as in the list of productions,
   // for the Earley predictor to go through. Most predicted productions
   // are rejected on their first item alone, and the table allows that
   // without visiting the productions themselves, which are scattered
   // around in memory.
   Prediction* m_pPredictions;
   UINT m_nPredictions;

   static AllocCounter ac;

protected:

public:

   Nonterminal(const WCHAR* pwzName);

   void buildPredictions(void);

   ~Nonterminal(void);

   void addProduction(Production* p);

   // Get the first right-hand-side production of this nonterminal
   Production* getHead(void) const
      { return this->m_pProd; }

   // Get the prediction table of this nonterminal
   const Prediction* getPredictions(UINT& n) const
      {
         n = this->m_nPredictions;
         return this->m_pPredictions;
      }

   WCHAR* getName(void) const
      { return this->m_pwzName; }

};


class Production {

   // A Production owns a local copy of an array of items,
   // where each item is a negative nonterminal index, or
   // positive terminal index. The array is terminated by a 0 item,
   // so indexing just past the end of the production yields 0.
   // The items are followed, in the same block of memory, by the
   // lookahead filters of the production: one for each position
   // of the dot, including the one at the end.

   friend class AllocReporter;

private:

   // Note: the layout of the following four members is known to
   // the Python side (see struct Production in eparser_build.py)
   UINT m_nId;             // Unique integer id (0-based) of this production
   UINT m_nPriority;       // Relative priority of this production
   UINT m_n;               // Number of items in production
   INT* m_pList;           // List of items in production
   Production* m_pNext;    // Next production of same nonterminal

   static AllocCounter ac;

protected:

public:

   Production(UINT nId, UINT nPriority, UINT n, const INT* pList);

   ~Production(void);

   void setNext(Production* p);
   Production* getNext(void) const
      { return this->m_pNext; }

   UINT getId(void) const
      { return this->m_nId; }
   UINT getLength(void) const
      { return this->m_n; }
   BOOL isEpsilon(void) const
      { return this->m_n == 0; }
   UINT getPriority(void) const
      { return this->m_nPriority; }

   // Get the item at the dot position within the production,
   // or 0 if the dot is at the end of the production
   INT operator[] (UINT nDot) const
      {
         ASSERT(nDot <= this->m_n);
         return this->m_pList[nDot];
      }

   // Get or set the lookahead filter for the given dot position
   UINT getFilter(UINT nDot) const
      {
         ASSERT(nDot <= this->m_n);
         return (UINT)this->m_pList[this->m_n + 1 + nDot];
      }
   void setFilter(UINT nDot, UINT nFilter)
      {
         ASSERT(nDot <= this->m_n);
         this->m_pList[this->m_n + 1 + nDot] = (INT)nFilter;
      }

};


class Grammar {

   // A Grammar is a collection of Nonterminals
   // with their Productions.

   friend class AllocReporter;

private:

   // Note: the layout of the following three members is known to
   // the Python side (see struct Grammar in eparser_build.py)
   UINT m_nNonterminals;   // Number of nonterminals
   UINT m_nTerminals;      // Number of terminals (indexed from 1)
   INT m_iRoot;            // Index of root nonterminal (negative)
   Nonterminal** m_nts;    // Array of Nonterminal pointers, owned by the Grammar class

   // Lookahead support, calculated by analyze(). The nonterminals are
   // divided into classes, such that the nonterminals of a class can all
   // begin with exactly the same tokens (each of them can occur at the
   // start of something derived from any other). A class is described by
   // the terminals that its nonterminals can begin with directly, and by
   // the other classes whose nonterminals they can begin with.
   UINT m_nClasses;        // Number of classes
   UINT* m_pnClass;        // The class of each nonterminal
   UINT* m_pnClassOffset;  // For each class, the index of its data in m_pnClassData
   UINT* m_pnClassData;    // For each class: the number of terminals, the
                           // terminals, the number of classes, the classes

   void analyze(void);

   static AllocCounter ac;

protected:

public:

   Grammar(UINT nNonterminals, UINT nTerminals, INT iRoot = -1);
   Grammar(void);
   ~Grammar(void);

   void reset(void);

   BOOL readBinary(const CHAR* pszFilename);

   // Lookahead support
   UINT getNumClasses(void) const
      { return this->m_nClasses; }
   UINT getClass(INT iNt) const
      { return this->m_pnClass[~((UINT)iNt)]; }
   const UINT* getClassData(UINT nClass) const
      { return this->m_pnClassData + this->m_pnClassOffset[nClass]; }

   UINT getNumNonterminals(void) const
      { return this->m_nNonterminals; }
   UINT getNumTerminals(void) const
      { return this->m_nTerminals; }
   INT getRoot(void) const
      { return this->m_iRoot; }

   void setNonterminal(INT iIndex, Nonterminal*);

   Nonterminal* operator[] (INT iIndex) const;

   const WCHAR* nameOfNt(INT iNt) const;

};


class Label {

   // A Label is associated with a Node.

   friend class Node;
   friend class Reducer;

private:

   INT m_iNt;
   UINT m_nDot;
   Production* m_pProd;
   UINT m_nI;
   UINT m_nJ;

public:

   Label(INT iNt, UINT nDot, Production* pProd, UINT nI, UINT nJ)
      : m_iNt(iNt), m_nDot(nDot), m_pProd(pProd), m_nI(nI), m_nJ(nJ)
      { }

   // Note: member-wise comparison, rather than memcmp() of the
   // whole struct, which would depend on the absence of padding
   BOOL operator==(const Label& other) const
      {
         return this->m_iNt == other.m_iNt &&
            this->m_nDot == other.m_nDot &&
            this->m_pProd == other.m_pProd &&
            this->m_nI == other.m_nI &&
            this->m_nJ == other.m_nJ;
      }

   // Content-based hash, deliberately independent of memory
   // addresses (the production is represented by its id, not
   // its pointer), so that hash-derived orderings are stable
   // between runs
   UINT getHash(void) const
      {
         UINT h = (UINT)this->m_iNt;
         h = h * 31 + this->m_nDot;
         h = h * 31 + (this->m_pProd ? this->m_pProd->getId() : (UINT)-1);
         h = h * 31 + this->m_nI;
         h = h * 31 + this->m_nJ;
         return h;
      }

};


class Node {

   // A node in the parse forest (SPPF). Nodes are created within
   // a Forest, which owns their storage: they are not deleted
   // individually, but all at once when the Forest is deleted.

   friend class AllocReporter;
   friend class Reducer;

private:

   struct FamilyEntry {
      Production* pProd;
      Node* p1;
      Node* p2;
      FamilyEntry* pNext;
   };

   // Note: the layout of the following three members is known to
   // the Python side (see struct Node in eparser_build.py)
   Label m_label;
   FamilyEntry* m_pHead;
   Forest* m_pForest;      // The forest that owns this node
   // The node of the reducer (see ereducer.cpp) that corresponds
   // to this node, if any
   struct RNode* m_pR;

   static AllocCounter ac;

   void _dump(Grammar*, UINT nIndent);

protected:

public:

   Node(const Label&, Forest*);

   // Account for a batch of node allocations and frees
   // (nodes are not counted individually, for performance reasons)
   static void count(UINT nAllocs, UINT nFrees)
      { Node::ac.add(nAllocs, nFrees); }

   void addFamily(Production*, Node* pW, Node* pV);

   BOOL hasLabel(const Label& label) const
      { return this->m_label == label; }

   // Deterministic content-based hash of this node's label
   UINT getHash(void) const
      { return this->m_label.getHash(); }

   void dump(Grammar*);

   static UINT numCombinations(Node*);

   // Delete the forest that a node belongs to
   static void destroyForest(Node*);

};


class Forest {

   // A Forest owns the storage of all tree nodes, and of their families
   // of children, that are created during a parse. Storage is handed
   // out sequentially from large slabs and is never released piecemeal:
   // it is all freed in one go when the Forest is deleted, which happens
   // in deleteForest() - or at the end of the parse, if it fails.

   // Most nodes created during a parse do not end up in the resulting
   // tree. They used to be reference counted and released as soon as
   // possible, at a considerable cost on the hot path of the parser.
   // Now, they simply stay in the Forest until it is deleted, which is
   // typically a few milliseconds after the parse completes.

private:

   static const UINT SLAB_ITEMS = 8 * 1024; // 64 KB on a 64-bit platform

   struct Slab {
      Slab* pNext;
      void* aStorage[SLAB_ITEMS];   // Pointer-aligned storage
   };

   // A block of storage that is too large for a slab
   struct Large {
      Large* pNext;
   };

   Slab* m_pSlabs;      // List of all slabs, the newest one first
   Large* m_pLarge;     // List of large blocks
   BYTE* m_pFree;       // The first free byte in the newest slab
   BYTE* m_pEnd;        // The end of the newest slab
   UINT m_nNodes;       // The number of nodes allocated
   UINT m_nCounted;     // The number of nodes added to the global counter

   void addSlab(void)
      {
         Slab* pSlab = new Slab;
         pSlab->pNext = this->m_pSlabs;
         this->m_pSlabs = pSlab;
         this->m_pFree = (BYTE*)pSlab->aStorage;
         this->m_pEnd = this->m_pFree + sizeof(pSlab->aStorage);
      }

public:

   Forest(void)
      : m_pSlabs(NULL), m_pLarge(NULL), m_pFree(NULL), m_pEnd(NULL),
         m_nNodes(0), m_nCounted(0)
      { }

   ~Forest(void)
      {
         Slab* p = this->m_pSlabs;
         while (p) {
            Slab* pNext = p->pNext;
            delete p;
            p = pNext;
         }
         Large* pl = this->m_pLarge;
         while (pl) {
            Large* pNext = pl->pNext;
            ::operator delete((void*)pl);
            pl = pNext;
         }
         // All nodes are hereby freed
         Node::count(this->m_nNodes - this->m_nCounted, this->m_nNodes);
      }

   // Allocate storage; the size is rounded up to a multiple of the pointer size
   void* alloc(size_t nBytes)
      {
         nBytes = (nBytes + sizeof(void*) - 1) & ~(sizeof(void*) - 1);
         if ((size_t)(this->m_pEnd - this->m_pFree) < nBytes) {
            if (nBytes > sizeof(void*) * SLAB_ITEMS / 4) {
               // A large request: give it a block of its own, instead
               // of abandoning what is left of the current slab
               // (or overflowing a new one)
               const size_t nHeader = 2 * sizeof(void*);
               Large* pl = (Large*)::operator new(nHeader + nBytes);
               pl->pNext = this->m_pLarge;
               this->m_pLarge = pl;
               return (void*)((BYTE*)pl + nHeader);
            }
            this->addSlab();
         }
         void* pv = (void*)this->m_pFree;
         this->m_pFree += nBytes;
         return pv;
      }

   // Create a node within the forest
   Node* newNode(const Label& label)
      {
         this->m_nNodes++;
         return new (this->alloc(sizeof(Node))) Node(label, this);
      }

   // Account for the nodes allocated so far in the global counter
   void countNodes(void)
      {
         Node::count(this->m_nNodes - this->m_nCounted, 0);
         this->m_nCounted = this->m_nNodes;
      }

};


// Token-terminal matching function
typedef BOOL (*MatchingFunc)(UINT nHandle, UINT nToken, UINT nTerminal);

// Allocator for token/terminal matching cache
typedef BYTE* (*AllocFunc)(UINT nHandle, UINT nToken, UINT nTerminals);

// Provider of packed token matching data (TokenRec header
// followed by MeaningRec entries) for native matching
typedef const BYTE* (*MeaningsFunc)(UINT nHandle, UINT nToken);

// Default matching function that simply
// compares the token value with the terminal number
BOOL defaultMatcher(UINT nHandle, UINT nToken, UINT nTerminal);


// Native token/terminal matching support.
// A table of TerminalSpec entries, built on the Python side by
// build_matching_table() in binparser.py, describes for each terminal
// how the C++ core can decide token/terminal matches natively,
// without calling back into Python. Terminals whose matching semantics
// are not natively encodable are marked T_PYTHON and continue to be
// matched via the MatchingFunc callback. The structure layouts below
// are mirrored byte-for-byte by the Python encoder (little-endian).

// Terminal spec kinds (low byte of TerminalSpec::nKindFlags)
#define T_PYTHON        0  // Always match via the Python callback
#define T_TEXT          1  // Strong literal without category: token text identity
#define T_TEXT_CAT      2  // Strong literal with category
#define T_LEMMA         3  // Lemma literal, with optional category
#define T_CAT_DEFAULT   4  // Category terminal, default matcher semantics
#define T_CAT_MASK      5  // Category terminal, masked fbits test (abfn/pfn)
#define T_CAT_FIRST     6  // Category terminal, category test only (töl)
#define T_CAT_NOUN      7  // Noun terminal (no_...)
#define T_CAT_LO        8  // Adjective terminal (lo_...)
#define T_CAT_AO        9  // Adverb terminal (ao_...)

// Terminal spec flags (higher bits of TerminalSpec::nKindFlags)
#define TF_ABBREV        0x0100u  // no_abbrev: matches only meanings without inflection info
#define TF_MM_EXCLUDE    0x0200u  // Verb lemma literal: don't match middle voice (MM)
#define TF_MATCHES_EMPTY 0x0400u  // Terminal matches unknown words (no_..._et_hk without gr)
// The following two flags allow the core to decide that a terminal does
// not match a token, without calling the Python matching function, also
// for terminals that are otherwise matched in Python (T_PYTHON)
#define TF_NO_NONWORD    0x0800u  // Terminal never matches a token that is not a word
#define TF_NEEDS_CAT     0x1000u  // Terminal only matches word meanings of category nCatId

// Token header flags (high 16 bits of TokenRec::nCountFlags)
#define TKF_FAST        0x00010000u  // Word token with BÍN meanings: fully matchable natively
#define TKF_EMPTY_WORD  0x00020000u  // Word token without BÍN meanings
#define TKF_NONWORD     0x00040000u  // Not a word token (number, person name, punctuation...)

// Meaning record flags
#define MF_NO_BEYGING   1u  // Meaning has no inflection info (beyging == "-")
#define MF_NAME_FL      2u  // Meaning fl is 'nafn' or 'ætt' (person names)
#define MF_IS_NOUN      4u  // Meaning ordfl is kk, kvk or hk
#define MF_IS_LO_SO     8u  // Meaning ordfl is lo or so

struct TerminalSpec {
   UINT nKindFlags;    // Kind in low byte, TF_* flags above
   UINT nCatId;        // Category id to compare, or 0
   UINT nLitId;        // Interned literal (lemma/form) id, or 0
   UINT nReserved;
   UINT64 nFbits;      // Required feature bits
   UINT64 nMask;       // Comparison mask (T_CAT_MASK)
};

struct MeaningRec {
   UINT nLemmaId;      // Interned lemma id, or 0
   UINT nCatId;        // Raw category (ordfl) id
   UINT nMappedCatId;  // Terminal-name-mapped category id (kk/kvk/hk -> no)
   UINT nFlags;        // MF_* flags
   UINT64 nFbits;      // Feature bits of this meaning (gender-augmented)
};

struct TokenRec {
   UINT nFormId;       // Interned id of the (lower-cased) token text, or 0
   UINT nCountFlags;   // Meaning count in low 16 bits, TKF_* flags above
   // Followed by (nCountFlags & 0xFFFF) MeaningRec entries
};

struct MatchMasks {
   // Bit masks for the feature bit space, passed from Python
   // (the bit layout is defined by BIN_Token.VBIT)
   UINT64 genders;
   UINT64 number;
   UINT64 et;
   UINT64 gr;
   UINT64 mm;
};


// Support for reducing a parse forest to its highest-scoring tree
// within the C++ module (see ereducer.cpp). The reduction follows the
// algorithm of the ParseForestReducer class in reducer.py to the letter;
// the two tables below, and the two callbacks, give it the parts of the
// grammar and of the vocabulary that the algorithm consults.

// Nonterminal flags for the reducer (one UINT per nonterminal)
#define RN_ENABLE_PREP_BONUS     0x0001u  // Tag enable_prep_bonus
#define RN_BEGIN_PREP_SCOPE      0x0002u  // Tag begin_prep_scope
#define RN_NOUN_PHRASE           0x0004u  // The nonterminal is a noun phrase (Nl*)
#define RN_VERB_PARTICLE         0x0008u  // Tag verb_particle
#define RN_APPLY_PARTICLE_BONUS  0x0010u  // Tag apply_particle_bonus
#define RN_APPLY_LENGTH_BONUS    0x0020u  // Tag apply_length_bonus
#define RN_APPLY_PREP_BONUS      0x0040u  // Tag apply_prep_bonus
#define RN_PICK_UP_VERB          0x0080u  // Tag pick_up_verb
#define RN_PURGE_VERB            0x0100u  // Tag purge_verb
#define RN_NO_REDUCE             0x0200u  // Tag no_reduce

// Terminal flags for the reducer (one BYTE per terminal, 1-based)
#define RT_AO_LITERAL   0x01u  // Literal terminal of the adverb category
#define RT_FS           0x02u  // Preposition terminal
#define RT_SO           0x04u  // Verb terminal

// Return the bonus (or penalty) for a preposition terminal, matching
// a token, in the context of a verb terminal matching another token
typedef INT (*PrepBonusFunc)(UINT nHandle, UINT nPrepTerminal, UINT nPrepToken,
   UINT nVerbTerminal, UINT nVerbToken);

// Return the bonus (or penalty) for a verb particle, i.e. the token
// with the given index, in the context of a list of verbs. The list
// consists of nVerbs pairs of (terminal index, token index).
typedef INT (*ParticleBonusFunc)(UINT nHandle, UINT nParticleToken,
   const UINT* pnVerbs, UINT nVerbs);

struct ReducerTables {
   UINT nNonterminals;
   UINT* pnNtFlags;        // RN_* flags of each nonterminal
   INT* pnNtScores;        // Score adjustment of each nonterminal
   UINT nTerminals;        // Number of terminals + 1, as they are 1-based
   BYTE* pbTermFlags;      // RT_* flags of each terminal
   PrepBonusFunc fpPrepBonus;
   ParticleBonusFunc fpParticleBonus;
   INT nPrepBonus;         // Bonus for nonterminals tagged apply_prep_bonus
   INT nLengthFactor;      // Factor for nonterminals tagged apply_length_bonus
};

struct Reduction {

   // The state of the reduction of a parse forest, which is done
   // in two steps: reduceStart() and reduceFinish(). The object
   // lives in the Forest that it describes, and is deleted with it.

   // Note: the layout of the first part of this structure is known
   // to the Python side (see struct Reduction in eparser_build.py)

   // Available after reduceStart():
   UINT nStart;            // The span of the root node
   UINT nEnd;
   UINT nOptions;          // The number of distinct token/terminal matches
   const INT* pnOptions;   // nOptions pairs of (token index, terminal index)
   UINT nCombBytes;        // The number of trees in the forest, as an
   const BYTE* pbComb;     // unsigned little-endian integer of nCombBytes bytes
   // Available after reduceFinish():
   INT nScore;             // The score of the root node
   UINT nOut;              // The resulting tree (or forest), serialized as
   const INT* pnOut;       // nOut integers; see Reducer::emit()

   // The following members are private to the C++ side
   Parser* pParser;
   Forest* pForest;
   struct RNode* pRoot;

};


class Parser {

   // Earley-Scott parser for a given Grammar

   friend class AllocReporter;
   friend class Column;

private:

   // Grammar pointer, not owned by the Parser
   Grammar* m_pGrammar;
   MatchingFunc m_pMatchingFunc;
   AllocFunc m_pAllocFunc;

   // Native matching support (may be absent)
   TerminalSpec* m_pSpecs;     // Owned copy of the terminal spec table, or NULL
   UINT m_nSpecs;              // Number of entries in m_pSpecs
   MeaningsFunc m_pMeaningsFunc;
   MatchMasks m_masks;
   BOOL m_bParity;             // Parity checking mode
   // Atomic (like the diagnostic allocation counters), since it is
   // incremented from within concurrent parses
   std::atomic<UINT> m_nParityMismatches;

   // Tables for the reducer (may be absent)
   ReducerTables m_rt;

   // Is the lookahead filter in use?
   BOOL m_bLookahead;

   // Add a state to a column, or to the list of states to be scanned
   void pushNew(State*, Column*, State*& pQ);
   void push(UINT nHandle, State*, Column*, State*& pQ, StateChunk*, StateSet&);

   BOOL viableMulti(const Production*, UINT nDot, UINT nCount, Column*, UINT nHandle);
   BOOL viable(UINT nFilter, const Production*, UINT nDot, Column*, UINT nHandle);
   BOOL canAdvance(State*, Column*, UINT nHandle, INT& iNext);

   Node* makeNode(State* pState, UINT nEnd, Node* pV, NodeDict& ndV);

   // Internal token/terminal matching cache management
   BYTE* allocCache(UINT nHandle, UINT nToken, BOOL* pbNeedsRelease);
   void releaseCache(BYTE* abCache);
   // The number of bytes that the matching results of a token occupy
   static UINT matchCacheSize(UINT nTerminals)
      { return (nTerminals + 1 + 3) / 4; }

protected:

public:

   Parser(Grammar*, MatchingFunc = defaultMatcher, AllocFunc = NULL);
   ~Parser(void);

   UINT getNumTerminals(void) const
      { return this->m_pGrammar->getNumTerminals(); }
   UINT getNumNonterminals(void) const
      { return this->m_pGrammar->getNumNonterminals(); }
   MatchingFunc getMatchingFunc(void) const
      { return this->m_pMatchingFunc; }
   Grammar* getGrammar(void) const
      { return this->m_pGrammar; }

   // Native matching support
   void setMatchingTable(const BYTE* pSpecs, UINT nSpecs,
      MeaningsFunc fpMeanings, const BYTE* pMasks, BOOL bParity);
   const TerminalSpec* getSpec(UINT nTerminal) const
      {
         return (this->m_pSpecs && nTerminal < this->m_nSpecs)
            ? &this->m_pSpecs[nTerminal] : NULL;
      }
   const BYTE* fetchTokenRec(UINT nHandle, UINT nToken) const
      {
         return this->m_pMeaningsFunc
            ? this->m_pMeaningsFunc(nHandle, nToken) : NULL;
      }
   const MatchMasks& getMasks(void) const
      { return this->m_masks; }
   BOOL parityMode(void) const
      { return this->m_bParity; }
   void countParityMismatch(void)
      { this->m_nParityMismatches.fetch_add(1, std::memory_order_relaxed); }
   UINT getParityMismatches(void) const
      { return this->m_nParityMismatches.load(std::memory_order_relaxed); }

   // Turn the lookahead filter on (the default) or off. It has no
   // effect on the content of the parse forest, only on the amount of
   // work that it takes to create it.
   void setLookahead(BOOL b)
      { this->m_bLookahead = b; }
   BOOL getLookahead(void) const
      { return this->m_bLookahead; }

   // Reducer support: the tables are copied
   void setReducerTables(const ReducerTables*);
   const ReducerTables* getReducerTables(void) const
      { return this->m_rt.pnNtFlags ? &this->m_rt : NULL; }

   // Evaluate a native token/terminal match
   static BOOL evalMatch(const TerminalSpec*, const BYTE* pTokenRec, const MatchMasks&);

   // If pnToklist is NULL, a sequence of integers 0..nTokens-1 will be used
   Node* parse(UINT nHandle, INT iStartNt, UINT* pnErrorToken,
      UINT nTokens, const UINT pnToklist[] = NULL);

};

// Print a report on memory allocation
extern "C" void printAllocationReport(void);

// Parse a token stream
extern "C" Node* earleyParse(Parser*, UINT nTokens, INT iRoot, UINT nHandle, UINT* pnErrorToken);

extern "C" Grammar* newGrammar(const CHAR* pszGrammarFile);

extern "C" void deleteGrammar(Grammar*);

extern "C" Parser* newParser(Grammar*, MatchingFunc fpMatcher = defaultMatcher, AllocFunc fpAlloc = NULL);

extern "C" void deleteParser(Parser*);

// Install a native matching table (see TerminalSpec above);
// pMasks points to a MatchMasks structure
extern "C" void setMatchingTable(Parser*, const BYTE* pSpecs, UINT nSpecs,
   MeaningsFunc fpMeanings, const BYTE* pMasks, BOOL bParity);

// Return the number of native/Python matching discrepancies
// detected while running in parity mode
extern "C" UINT getParityMismatches(Parser*);

// Turn the lookahead filter of the parser on (the default) or off
extern "C" void setLookahead(Parser*, BOOL);

// Install the tables and callbacks that the reducer needs. The tables
// have one entry per nonterminal, and one per terminal (1-based, so
// nTerminals is the number of terminals in the grammar plus one).
extern "C" void setReducerTables(Parser*,
   const UINT* pnNtFlags, const INT* pnNtScores, UINT nNonterminals,
   const BYTE* pbTermFlags, UINT nTerminals,
   PrepBonusFunc fpPrepBonus, ParticleBonusFunc fpParticleBonus,
   INT nPrepBonus, INT nLengthFactor);

// Begin the reduction of a parse forest: analyze it, count its trees
// and list its token/terminal matches. Returns NULL if the forest
// can't be handled here; the caller then falls back on doing things
// by itself. The returned object is deleted by deleteForest().
extern "C" Reduction* reduceStart(Parser*, Node* pRoot);

// Complete the reduction, given the scores of the token/terminal
// matches (in the order of Reduction::pnOptions), and serialize the
// resulting tree. If pnScores is NULL, the forest is not reduced, but
// serialized as it is. Returns false if the reduction could not
// be completed.
extern "C" BOOL reduceFinish(Reduction*, const INT* pnScores, UINT nHandle);

extern "C" void deleteForest(Node*);

extern "C" void dumpForest(Node*, Grammar*);

extern "C" UINT numCombinations(Node*);


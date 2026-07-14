/*

   Greynir: Natural language processing for Icelandic

   C++ Earley parser module

   Copyright © 2023 Miðeind ehf.

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
#include <atomic>


// Assert macro
#ifdef DEBUG
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
struct StateChunk;


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
   UINT numAllocs(void) const
      { return this->m_nAllocs.load(std::memory_order_relaxed); }
   UINT numFrees(void) const
      { return this->m_nFrees.load(std::memory_order_relaxed); }
   INT getBalance(void) const
      { return (INT)(this->numAllocs() - this->numFrees()); }

};


class Nonterminal {

   // A Nonterminal has an associated list of owned Productions

   friend class AllocReporter;

private:

   WCHAR* m_pwzName;
   Production* m_pProd;

   static AllocCounter ac;

protected:

public:

   Nonterminal(const WCHAR* pwzName);

   ~Nonterminal(void);

   void addProduction(Production* p);

   // Get the first right-hand-side production of this nonterminal
   Production* getHead(void) const
      { return this->m_pProd; }

   WCHAR* getName(void) const
      { return this->m_pwzName; }

};


class Production {

   // A Production owns a local copy of an array of items,
   // where each item is a negative nonterminal index, or
   // positive terminal index. Attempts to index past the
   // end of the production yield a 0 item.

   friend class AllocReporter;

private:

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

   // Get the item at the dot position within the production
   INT operator[] (UINT nDot) const;

};


class Grammar {

   // A Grammar is a collection of Nonterminals
   // with their Productions.

   friend class AllocReporter;

private:

   UINT m_nNonterminals;   // Number of nonterminals
   UINT m_nTerminals;      // Number of terminals (indexed from 1)
   INT m_iRoot;            // Index of root nonterminal (negative)
   Nonterminal** m_nts;    // Array of Nonterminal pointers, owned by the Grammar class

   static AllocCounter ac;

protected:

public:

   Grammar(UINT nNonterminals, UINT nTerminals, INT iRoot = -1);
   Grammar(void);
   ~Grammar(void);

   void reset(void);

   BOOL readBinary(const CHAR* pszFilename);

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

};


class Node {

   friend class AllocReporter;

private:

   struct FamilyEntry {
      Production* pProd;
      Node* p1;
      Node* p2;
      FamilyEntry* pNext;
   };

   Label m_label;
   FamilyEntry* m_pHead;
   UINT m_nRefCount;

   static AllocCounter ac;

   void _dump(Grammar*, UINT nIndent);

protected:

public:

   Node(const Label&);
   ~Node(void);

   void addRef(void)
      { this->m_nRefCount++; }
   void delRef(void);

   void addFamily(Production*, Node* pW, Node* pV);

   BOOL hasLabel(const Label& label) const
      { return this->m_label == label; }

   void dump(Grammar*);

   static UINT numCombinations(Node*);

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

// Token header flags (high 16 bits of TokenRec::nCountFlags)
#define TKF_FAST        0x00010000u  // Word token with BÍN meanings: fully matchable natively
#define TKF_EMPTY_WORD  0x00020000u  // Word token without BÍN meanings

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
   UINT m_nParityMismatches;

   void push(UINT nHandle, State*, Column*, State*&, StateChunk*);

   Node* makeNode(State* pState, UINT nEnd, Node* pV, NodeDict& ndV);

   // Internal token/terminal matching cache management
   BYTE* allocCache(UINT nHandle, UINT nToken, BOOL* pbNeedsRelease);
   void releaseCache(BYTE* abCache);

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
      { this->m_nParityMismatches++; }
   UINT getParityMismatches(void) const
      { return this->m_nParityMismatches; }

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

extern "C" void deleteForest(Node*);

extern "C" void dumpForest(Node*, Grammar*);

extern "C" UINT numCombinations(Node*);


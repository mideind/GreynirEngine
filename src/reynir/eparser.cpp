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
   It is designed to be called from Python code via CFFI with
   already parsed and packed grammar structures.

   The Earley parser used here is the improved version described by Scott & Johnstone,
   referencing Tomita. This allows worst-case cubic (O(n^3)) order, where n is the
   length of the input sentence, while still returning all possible parse trees
   for an ambiguous grammar.

   See Elizabeth Scott, Adrian Johnstone:
   "Recognition is not parsing — SPPF-style parsing from cubic recognisers"
   Science of Computer Programming, Volume 75, Issues 1–2, 1 January 2010, Pages 55–70

*/

// #define DEBUG

#include <stdio.h>
#include <stdint.h>
#include <assert.h>
#include <time.h>
#include <new>
#include <vector>

#include "eparser.h"


// Local implementation classes


class AllocReporter {

   // A debugging aid to diagnose and report memory leaks

private:
protected:
public:

   AllocReporter(void);
   ~AllocReporter(void);

   void report(void) const;

};

void printAllocationReport(void)
{
   AllocReporter reporter;
   reporter.report();
}


class State {

   // Parser state, contained within a Column

friend class AllocReporter;

private:

   INT m_iNt;              // Nonterminal (negative index)
   INT m_iItem;            // The item at the dot, i.e. prod[dot] (0 if at the end)
   Production* m_pProd;    // Production
   UINT m_nDot;            // Dot (position in production)
   UINT m_nStart;          // Start token index
   Node* m_pw;             // Tree node
   State* m_pNext;         // Next state within column
   State* m_pNtNext;       // Next state with same Nt at prod[dot]

   static AllocCounter ac;

protected:

public:

   State(INT iNt, Production* pProd, INT iFirst, UINT nStart);
   State(State*, Node* pw, INT iItem);

   // Account for a batch of state allocations and frees
   // (states are not counted individually, for performance reasons)
   static void count(UINT nAllocs, UINT nFrees)
      { State::ac.add(nAllocs, nFrees); }

   void increment(Node* pwNew, INT iItem);

   void setNext(State*);
   void setNtNext(State*);

   State* getNext(void) const
      { return this->m_pNext; }
   State* getNtNext(void) const
      { return this->m_pNtNext; }

   UINT getHash(void) const
      {
         // Hash for the detection of duplicate states (see StateSet).
         // The states of a column are processed in the order in which
         // they were added to it, so this hash has no influence on the
         // resulting parse forest, and it is fine for it to depend on
         // a memory address (that of the tree node).
         // The nonterminal is implied by the production.
         UINT h = (this->m_pProd ? this->m_pProd->getId() : (UINT)-1) * 0x9E3779B1u;
         h ^= (this->m_nDot + 1) * 0x85EBCA6Bu;
         h ^= (this->m_nStart + 1) * 0xC2B2AE35u;
         h ^= (UINT)(((uintptr_t)this->m_pw) >> 3) * 0x27D4EB2Fu;
         h ^= h >> 15;
         h *= 0x2C1B3C6Du;
         h ^= h >> 13;
         return h;
      }
   BOOL operator==(const State& other) const
      {
         const State& t = *this;
         return t.m_iNt == other.m_iNt &&
            t.m_pProd == other.m_pProd &&
            t.m_nDot == other.m_nDot &&
            t.m_nStart == other.m_nStart &&
            t.m_pw == other.m_pw;
      }

   // Get the terminal or nonterminal at the dot. This is kept in the
   // state itself, to avoid a visit to the production (which is likely
   // to be a cache miss) every time a state is looked at.
   INT prodDot(void) const
      { return this->m_iItem; }
   // Get the terminal or nonterminal after the one at the dot
   INT nextItem(void) const
      { return (*this->m_pProd)[this->m_nDot + 1]; }

   INT getNt(void) const
      { return this->m_iNt; }
   UINT getStart(void) const
      { return this->m_nStart; }
   UINT getDot(void) const
      { return this->m_nDot; }
   Production* getProd(void) const
      { return this->m_pProd; }
   Node* getNode(void) const
      { return this->m_pw; }
   Node* getResult(INT iStartNt) const;

};


template<class T> class Pool {

   // A simple pool allocator for small objects of a single type that
   // are created and destroyed at a high rate within a parse. Storage
   // for released objects is kept in a free list and handed out again;
   // all memory is returned to the heap when the pool is destroyed.
   // The pool hands out raw storage: use placement new to construct
   // objects in it and call their destructors explicitly, if needed.
   // A pool is owned and used by a single parse, i.e. a single thread.

private:

   static const UINT SLAB_SIZE = 256; // Number of objects in each slab

   union Slot {
      Slot* pNext;            // Next free slot
      void* pAlign;           // Ensure pointer alignment
      BYTE ab[sizeof(T)];     // Storage for an object
   };

   struct Slab {
      Slab* pNext;
      Slot aSlots[SLAB_SIZE];
   };

   Slab* m_pSlabs;   // List of all slabs
   Slot* m_pFree;    // List of free slots
   UINT m_nUsed;     // Number of slots handed out from the newest slab

public:

   Pool(void)
      : m_pSlabs(NULL), m_pFree(NULL), m_nUsed(SLAB_SIZE)
      { }
   ~Pool(void)
      {
         Slab* p = this->m_pSlabs;
         while (p) {
            Slab* pNext = p->pNext;
            delete p;
            p = pNext;
         }
      }

   void* alloc(void)
      {
         Slot* p = this->m_pFree;
         if (p) {
            // Re-use a previously released slot
            this->m_pFree = p->pNext;
            return (void*)p;
         }
         if (this->m_nUsed >= SLAB_SIZE) {
            // The newest slab is exhausted (or there is none): add a slab
            Slab* pSlab = new Slab;
            pSlab->pNext = this->m_pSlabs;
            this->m_pSlabs = pSlab;
            this->m_nUsed = 0;
         }
         return (void*)&this->m_pSlabs->aSlots[this->m_nUsed++];
      }

   void release(void* pv)
      {
         Slot* p = (Slot*)pv;
         p->pNext = this->m_pFree;
         this->m_pFree = p;
      }

};


class Column {

   // An Earley column
   // A Parser cointains one Column for each token in the input, plus a sentinel

   // The states of a column are kept in a list, in the order in which
   // they were added, and are processed (enumerated) in that order.
   // States can be - and are - added during the enumeration.
   // The column does not check whether a state is already present;
   // that is done by the parser (see StateSet) for the kinds of states
   // that can occur more than once.

friend class AllocReporter;

private:

   Parser* m_pParser; // The associated parser
   UINT m_nToken; // The input token associated with this column
   // States linked by the nonterminal at their prod[dot]: for each
   // nonterminal, the head of a list linked via State::getNtNext().
   // The array of heads is not initialized when the column is created,
   // as only a part of the nonterminals occur in any given column, and
   // clearing an array of several thousand pointers for every column
   // has a noticeable cost. Instead, a bitmap tells which elements of
   // the array are in use.
   State** m_pNtStates;
   UINT64* m_pNtUsed; // Bitmap of the elements of m_pNtStates that are in use
   MatchingFunc m_pMatchingFunc; // Pointer to the token/terminal matching function
   // Matching cache: for every terminal in the grammar, two bits that
   // tell whether the terminal matches the token of the column
   // (0: not known yet; 2: no; 3: yes)
   BYTE* m_abCache;
   // Lookahead cache: for every class of nonterminals in the grammar, two
   // bits that tell whether its nonterminals can begin with the token of
   // the column (0: not known yet; 1: yes; 2: no). It follows the matching
   // cache in the same buffer, and is thus kept with it between parses.
   BYTE* m_abStart;
   BOOL m_bNeedsRelease; // Does the matching cache need to be explicitly released?
   const BYTE* m_pTokenRec; // Packed matching data for this column's token, or NULL
   State* m_pHead; // The first state in the column
   State* m_pTail; // The last state in the column
   State* m_pEnum; // The state most recently returned by nextState()
   // Statistics, accumulated locally and added to the (atomic)
   // global counters when the column is done
   mutable UINT m_nMatches; // Calls to the matching function
   mutable UINT m_nNativeMatches; // Native match evaluations

   static AllocCounter ac;
   static AllocCounter acMatches;
   static AllocCounter acNativeMatches;

   // Obtain a matching result that is not in the cache
   BOOL matchUncached(UINT nHandle, UINT nTerminal) const;

   // Find out whether a class of nonterminals can begin with
   // the token of the column, and note it in the lookahead cache
   BOOL computeStart(UINT nHandle, UINT nClass);

   UINT getStart(UINT nClass) const
      { return (this->m_abStart[nClass >> 2] >> ((nClass & 3) << 1)) & 3; }
   // Note: the cache can be shared with parses of the same token in
   // other threads, and this is not an atomic update. An update can
   // therefore be lost, in which case the entry stays 'not known' and
   // is simply calculated again; an entry never gets a wrong value.
   void setStart(UINT nClass, UINT nValue)
      { this->m_abStart[nClass >> 2] |= (BYTE)(nValue << ((nClass & 3) << 1)); }

protected:

public:

   Column(Parser*, UINT nToken);
   ~Column(void);

   UINT getToken(void) const
      { return this->m_nToken; }

   void startParse(UINT nHandle);
   void stopParse(void);

   // Add a state to the column, at the end of the state list
   void addState(State* p)
      {
         p->setNext(NULL);
         if (this->m_pTail)
            this->m_pTail->setNext(p);
         else
            this->m_pHead = p;
         this->m_pTail = p;
         // Get the item at prod[dot]
         INT iItem = p->prodDot();
         if (iItem < 0) {
            // Nonterminal: add at the head of its linked list
            UINT nIndex = ~((UINT)iItem);
            UINT64& w = this->m_pNtUsed[nIndex >> 6];
            UINT64 bit = ((UINT64)1) << (nIndex & 63);
            if (w & bit)
               p->setNtNext(this->m_pNtStates[nIndex]);
            else {
               // First state for this nonterminal
               w |= bit;
               p->setNtNext(NULL);
            }
            this->m_pNtStates[nIndex] = p;
         }
      }

   // Is the column without states?
   BOOL isEmpty(void) const
      { return this->m_pHead == NULL; }

   // Start a fresh enumeration of the states
   void resetEnum(void)
      { this->m_pEnum = NULL; }

   // Return the next state in the enumeration, or NULL if all states
   // that have been added so far have been returned. After a NULL
   // return, the enumeration continues if more states are added.
   State* nextState(void)
      {
         State* p = this->m_pEnum ? this->m_pEnum->getNext() : this->m_pHead;
         if (p)
            this->m_pEnum = p;
         return p;
      }

   State* getNtHead(INT iNt) const
      {
         UINT nIndex = ~((UINT)iNt);
         if (!((this->m_pNtUsed[nIndex >> 6] >> (nIndex & 63)) & 1))
            // No states for this nonterminal
            return NULL;
         return this->m_pNtStates[nIndex];
      }

   BOOL matches(UINT nHandle, UINT nTerminal) const
      {
         if (this->m_nToken == (UINT)-1)
            // Sentinel token in last column never matches
            return false;
         ASSERT(this->m_abCache != NULL);
         UINT b = this->m_abCache[nTerminal >> 2] >> ((nTerminal & 3) << 1);
         if (b & 2)
            // We already have a cached result for this terminal
            return (BOOL)(b & 1);
         return this->matchUncached(nHandle, nTerminal);
      }

   // Can the nonterminals of the given class begin with the token
   // of this column, i.e. derive something that starts with it?
   BOOL canStart(UINT nHandle, UINT nClass)
      {
         if (this->m_nToken == (UINT)-1)
            // Nothing begins with the sentinel token in the last column
            return false;
         UINT nValue = this->getStart(nClass);
         if (nValue)
            return nValue == 1;
         return this->computeStart(nHandle, nClass);
      }

};


class StateSet {

   // The set of states in the Earley column that is currently being
   // added to, for the detection of duplicate states. This is an open
   // addressing hash table with linear probing. The parser adds states
   // to only one column at a time, so a single table serves the whole
   // parse: it is emptied when the parser moves on to the next column,
   // which only takes incrementing a generation number.

   // States created by the Earley predictor are not added to the set,
   // since they can never be duplicates (see Parser::parse()).

private:

   struct Entry {
      State* pState;
      UINT nHash;
      UINT nGen;     // The entry is in use if this is the current generation
   };

   Entry* m_pEntries;
   UINT m_nSize;     // Number of entries in the table; a power of 2
   UINT m_nCount;    // Number of entries in use
   UINT m_nGen;      // Current generation; never 0

   void grow(void)
      {
         // Double the size of the table
         Entry* pOld = this->m_pEntries;
         UINT nOldSize = this->m_nSize;
         UINT nSize = nOldSize * 2;
         Entry* pNew = new Entry[nSize];
         memset(pNew, 0, nSize * sizeof(Entry));
         UINT nMask = nSize - 1;
         for (UINT i = 0; i < nOldSize; i++)
            if (pOld[i].nGen == this->m_nGen) {
               UINT ix = pOld[i].nHash & nMask;
               while (pNew[ix].nGen == this->m_nGen)
                  ix = (ix + 1) & nMask;
               pNew[ix] = pOld[i];
            }
         this->m_pEntries = pNew;
         this->m_nSize = nSize;
         delete [] pOld;
      }

public:

   StateSet(void)
      : m_pEntries(NULL), m_nSize(4096), m_nCount(0), m_nGen(1)
      {
         this->m_pEntries = new Entry[this->m_nSize];
         memset(this->m_pEntries, 0, this->m_nSize * sizeof(Entry));
      }
   ~StateSet(void)
      { delete [] this->m_pEntries; }

   // Empty the set
   void clear(void)
      {
         this->m_nCount = 0;
         if (++this->m_nGen == 0) {
            // The generation number has wrapped around
            // (after four billion columns): really clear the table
            memset(this->m_pEntries, 0, this->m_nSize * sizeof(Entry));
            this->m_nGen = 1;
         }
      }

   // Add a state to the set. Returns false, and does not add
   // the state, if an identical state is already in the set.
   BOOL add(State* p)
      {
         UINT nHash = p->getHash();
         UINT nMask = this->m_nSize - 1;
         UINT ix = nHash & nMask;
         for (;;) {
            Entry& e = this->m_pEntries[ix];
            if (e.nGen != this->m_nGen) {
               // Free entry: the state is not in the set
               e.pState = p;
               e.nHash = nHash;
               e.nGen = this->m_nGen;
               if (++this->m_nCount * 2 > this->m_nSize)
                  // Keep the table at most half full
                  this->grow();
               return true;
            }
            if (e.nHash == nHash && (*e.pState) == (*p))
               // Identical state
               return false;
            ix = (ix + 1) & nMask;
         }
      }

};

class HNode {

   // Represents an element in the H set,
   // corresponding to a completed nullable
   // production of the associated nonterminal

friend class AllocReporter;

private:

   INT m_iNt;
   Node* m_pv;
   HNode* m_pNext;         // Next element in the H set
   HNode* m_pNtNext;       // Next element in the H set with the same nonterminal

   static AllocCounter ac;

protected:

public:

   HNode(INT iNt, Node* pv)
      : m_iNt(iNt), m_pv(pv), m_pNext(NULL), m_pNtNext(NULL)
      { HNode::ac++; }

   ~HNode()
      { HNode::ac--; }

   INT getNt(void) const
      { return this->m_iNt; }
   Node* getV(void) const
      { return this->m_pv; }
   HNode* getNext(void) const
      { return this->m_pNext; }
   void setNext(HNode* ph)
      { this->m_pNext = ph; }
   HNode* getNtNext(void) const
      { return this->m_pNtNext; }
   void setNtNext(HNode* ph)
      { this->m_pNtNext = ph; }

};

AllocCounter HNode::ac;


class NodeDict {

   // Dictionary to map labels to node pointers.
   // This is a hash table, with the entries in each hash bin chained
   // together. In addition, all entries are linked in a single list,
   // allowing the dictionary to be reset (which happens once for every
   // Earley column) in time proportional to the number of entries,
   // not to the number of hash bins.

friend class AllocReporter;

private:

   static const UINT HASH_BITS = 12;
   static const UINT HASH_BINS = 1u << HASH_BITS;

   struct NdEntry {
      Node* pNode;
      NdEntry* pNext;   // Next entry in the list of all entries
      NdEntry* pChain;  // Next entry in the same hash bin
   };

   Forest* m_pForest;   // The forest in which nodes are created
   NdEntry* m_pHead;    // Head of the list of all entries
   NdEntry** m_ppBins;  // The hash bins
   Pool<NdEntry> m_pool; // Storage for the entries
   UINT m_nLookups;     // Lookups since last reset (statistics)

   static UINT binOf(UINT nHash)
      {
         // Multiplicative (Fibonacci) hashing: spread the label hash
         // and use the most significant bits as a bin index
         return (UINT)((nHash * 2654435761u) & 0xFFFFFFFFu) >> (32 - HASH_BITS);
      }

   static AllocCounter acLookups;

protected:

public:

   NodeDict(Forest*);
   ~NodeDict(void);

   Node* lookupOrAdd(const Label&);

   void reset(void);

};

AllocCounter NodeDict::acLookups;


AllocCounter Nonterminal::ac;

Nonterminal::Nonterminal(const WCHAR* pwzName)
   : m_pwzName(NULL), m_pProd(NULL), m_pPredictions(NULL), m_nPredictions(0)
{
   Nonterminal::ac++;
   this->m_pwzName = pwzName ? ::wcsdup(pwzName) : NULL;
}

Nonterminal::~Nonterminal(void)
{
   if (this->m_pwzName)
      free(this->m_pwzName);
   if (this->m_pPredictions)
      delete [] this->m_pPredictions;
   // Delete the associated productions
   Production* p = this->m_pProd;
   while (p) {
      Production* pNext = p->getNext();
      delete p;
      p = pNext;
   }
   Nonterminal::ac--;
}

void Nonterminal::addProduction(Production* p)
{
   // Add a production at the head of the linked list
   p->setNext(this->m_pProd);
   this->m_pProd = p;
   // Keep the prediction table in sync with the list. (This makes adding
   // productions quadratic in their number, but a nonterminal only has
   // a handful of them, and they are added once, when a grammar is loaded.)
   this->buildPredictions();
}

void Nonterminal::buildPredictions(void)
{
   // (Re)build the prediction table from the list of productions
   UINT n = 0;
   for (Production* p = this->m_pProd; p; p = p->getNext())
      n++;
   Prediction* pNew = new Prediction[n];
   UINT i = 0;
   for (Production* p = this->m_pProd; p; p = p->getNext(), i++) {
      pNew[i].pProd = p;
      pNew[i].iFirst = (*p)[0];
      pNew[i].nFilter = p->getFilter(0);
   }
   if (this->m_pPredictions)
      delete [] this->m_pPredictions;
   this->m_pPredictions = pNew;
   this->m_nPredictions = n;
}


AllocCounter Production::ac;

Production::Production(UINT nId, UINT nPriority, UINT n, const INT* pList)
   : m_nId(nId), m_nPriority(nPriority), m_n(n), m_pList(NULL), m_pNext(NULL)
{
   Production::ac++;
   // The list of items is terminated by a 0 item, and
   // followed by a lookahead filter for each dot position
   this->m_pList = new INT[2 * (n + 1)];
   if (n > 0)
      ::memcpy((void*)this->m_pList, (void*)pList, n * sizeof(INT));
   this->m_pList[n] = 0;
   // Until the grammar has been analyzed (see Grammar::analyze()),
   // the filters only look at a terminal at the dot
   for (UINT i = 0; i <= n; i++) {
      INT iItem = this->m_pList[i];
      this->setFilter(i, iItem > 0 ? (LF_TERMINAL | ((UINT)iItem << 2)) : LF_ALWAYS);
   }
}

Production::~Production(void) {
   // Destructor
   if (this->m_pList)
      delete [] this->m_pList;
   Production::ac--;
}

void Production::setNext(Production* p)
{
   this->m_pNext = p;
}


// States are allocated in chunks, rather than individually
static const UINT CHUNK_SIZE = 2048 * sizeof(State);

struct StateChunk {

   StateChunk* m_pNext;
   UINT m_nIndex;
   // Statistics, accumulated here (in whichever chunk is at the head
   // of the chunk list at the time) and added to the global counters
   // when the chunks are freed at the end of the parse
   UINT m_nAllocs;      // States allocated
   UINT m_nDiscarded;   // States discarded and their space reclaimed
   // The storage for the states. Note that it must be aligned for
   // State objects, irrespective of the members that precede it.
   alignas(State) BYTE m_ast[CHUNK_SIZE];

   StateChunk(StateChunk* pNext)
      : m_pNext(pNext), m_nIndex(0), m_nAllocs(0), m_nDiscarded(0)
      {
         // Note: the state storage is deliberately left uninitialized.
         // States are constructed in place, and the State constructors
         // initialize all member variables.
      }

};

static AllocCounter acChunks;

void* operator new(size_t nBytes, StateChunk*& pChunkHead)
{
   ASSERT(nBytes == sizeof(State));
   // Allocate a new place for a state in a state chunk
   StateChunk* p = pChunkHead;
   if (!p || (p->m_nIndex + nBytes >= CHUNK_SIZE)) {
      StateChunk* pNew = new StateChunk(p);
      acChunks++;
      pChunkHead = p = pNew;
   }
   void* pPlace = (void*)(p->m_ast + p->m_nIndex);
   p->m_nIndex += (UINT)nBytes;
   p->m_nAllocs++;
   ASSERT(p->m_nIndex <= CHUNK_SIZE);
   return pPlace;
}

// Counter of states that are allocated and then immediately discarded
// (atomic for the same reason as the AllocCounter members)
static std::atomic<UINT> nDiscardedStates(0);

AllocCounter State::ac;

static void freeStates(StateChunk*& pChunkHead)
{
   // Free the state chunks, and add the state statistics
   // accumulated in them to the global counters. States have no
   // resources of their own (the tree nodes that they point to are
   // owned by the Forest), so they are not destroyed one by one.
   UINT nAllocs = 0, nDiscarded = 0;
   StateChunk* pChunk = pChunkHead;
   while (pChunk) {
      StateChunk* pNext = pChunk->m_pNext;
      nAllocs += pChunk->m_nAllocs;
      nDiscarded += pChunk->m_nDiscarded;
      delete pChunk;
      acChunks--;
      pChunk = pNext;
   }
   pChunkHead = NULL;
   State::count(nAllocs, nAllocs);
   if (nDiscarded)
      nDiscardedStates.fetch_add(nDiscarded, std::memory_order_relaxed);
}

State::State(INT iNt, Production* pProd, INT iFirst, UINT nStart)
   : m_iNt(iNt), m_iItem(iFirst), m_pProd(pProd), m_nDot(0), m_nStart(nStart),
      m_pw(NULL), m_pNext(NULL), m_pNtNext(NULL)
{
   // Create a state with the dot at the start of a production,
   // whose first item is iFirst
   // Note: State allocations and frees are not counted here, one by one,
   // but in batches; see StateChunk and freeStates()
   ASSERT(iFirst == (*pProd)[0]);
}

State::State(State* ps, Node* pw, INT iItem)
   : m_iNt(ps->m_iNt), m_iItem(iItem), m_pProd(ps->m_pProd), m_nDot(ps->m_nDot + 1),
      m_nStart(ps->m_nStart), m_pw(pw), m_pNext(NULL), m_pNtNext(NULL)
{
   // Create a new state by advancing one item forward from an existing
   // state; iItem is the item at the dot of the new state
   ASSERT(iItem == ps->nextItem());
}

void State::increment(Node* pwNew, INT iItem)
{
   // 'Increment' the state, i.e. move the dot right by one step
   // and put in a new node pointer; iItem is the item at the new dot
   ASSERT(iItem == this->nextItem());
   this->m_nDot++;
   this->m_iItem = iItem;
   this->m_pNext = NULL;
   ASSERT(this->m_pNtNext == NULL);
   this->m_pw = pwNew;
}

void State::setNext(State* p)
{
   this->m_pNext = p;
}

void State::setNtNext(State* p)
{
   this->m_pNtNext = p;
}

Node* State::getResult(INT iStartNt) const
{
   if (this->m_iNt == iStartNt && this->prodDot() == 0 &&
      this->m_nStart == 0)
      return this->m_pw;
   return NULL;
}


AllocCounter Column::ac;
AllocCounter Column::acMatches;
AllocCounter Column::acNativeMatches;

// Counter of native matching tables allocated by setMatchingTable()
static AllocCounter acMatchingTables;

Column::Column(Parser* pParser, UINT nToken)
   : m_pParser(pParser),
      m_nToken(nToken),
      m_pNtStates(NULL), m_pNtUsed(NULL),
      m_pMatchingFunc(pParser->getMatchingFunc()),
      m_abCache(NULL), m_abStart(NULL), m_bNeedsRelease(false),
      m_pTokenRec(NULL),
      m_pHead(NULL), m_pTail(NULL), m_pEnum(NULL),
      m_nMatches(0), m_nNativeMatches(0)
{
   Column::ac++;
   ASSERT(this->m_pMatchingFunc != NULL);
   UINT nNonterminals = pParser->getNumNonterminals();
   // Allocate the array of linked lists by nonterminal at prod[dot],
   // leaving it uninitialized, and clear the bitmap of elements in use
   this->m_pNtStates = new State* [nNonterminals];
   UINT nWords = (nNonterminals + 63) / 64;
   this->m_pNtUsed = new UINT64 [nWords];
   memset(this->m_pNtUsed, 0, nWords * sizeof(UINT64));
}

Column::~Column(void)
{
   // The states of the column are not destroyed here;
   // their storage is released in freeStates()
   // Delete array of linked lists by nonterminal at prod[dot]
   delete [] this->m_pNtStates;
   delete [] this->m_pNtUsed;
   // Delete matching cache and seen array, if still allocated
   this->stopParse();
   Column::ac--;
}

void Column::startParse(UINT nHandle)
{
   // Called when the parser starts processing this column
   ASSERT(this->m_abCache == NULL);
   // Ask the parser to create a matching cache for us
   // (or eventually re-use a previous one)
   if (this->m_nToken != (UINT)-1) {
      this->m_abCache = this->m_pParser->allocCache(nHandle, this->m_nToken, &this->m_bNeedsRelease);
      // The lookahead cache follows the matching cache
      this->m_abStart = this->m_abCache + Parser::matchCacheSize(this->m_pParser->getNumTerminals());
      // Fetch the packed matching data for this column's token,
      // if a native matching table has been installed
      this->m_pTokenRec = this->m_pParser->fetchTokenRec(nHandle, this->m_nToken);
      if (this->m_pTokenRec && !(this->m_abCache[0] & 3))
         // The token has not been seen before: mark the terminals
         // that it can't match by the look of it
         this->m_pParser->prefillCache(this->m_abCache, this->m_pTokenRec);
   }
}

void Column::stopParse(void)
{
   // Called when the parser is finished processing this column
   if (this->m_abCache && this->m_bNeedsRelease)
      // The matching cache needs to be released
      this->m_pParser->releaseCache(this->m_abCache);
   this->m_abCache = NULL;
   this->m_abStart = NULL;
   this->m_pTokenRec = NULL;
   // Flush the locally accumulated matching statistics
   if (this->m_nMatches) {
      Column::acMatches.add(this->m_nMatches, 0);
      this->m_nMatches = 0;
   }
   if (this->m_nNativeMatches) {
      Column::acNativeMatches.add(this->m_nNativeMatches, 0);
      this->m_nNativeMatches = 0;
   }
}

static inline BOOL hasCategory(const BYTE* pTokenRec, UINT nCatId)
{
   // Return true if any meaning of the token has the given (raw) category
   const TokenRec* pHdr = (const TokenRec*)pTokenRec;
   const UINT n = pHdr->nCountFlags & 0xFFFFu;
   const MeaningRec* pm = (const MeaningRec*)(pTokenRec + sizeof(TokenRec));
   for (UINT i = 0; i < n; i++)
      if (pm[i].nCatId == nCatId)
         return true;
   return false;
}

BOOL Column::computeStart(UINT nHandle, UINT nClass)
{
   // Find out whether the nonterminals of a class can begin with the
   // token of this column: they can if the token matches one of the
   // terminals that they can begin with directly, or if the nonterminals
   // of another class that they can begin with can. The classes form a
   // directed graph without cycles (see Grammar::analyze()), which is
   // searched depth-first here. The answers found on the way are noted in
   // the lookahead cache; a class is never looked into more than once
   // for a given token.
   struct Frame {
      UINT nClass;
      UINT iTerminal;   // The next terminal to look at
      UINT iNext;       // The next class to look at
   };
   std::vector<Frame> stack;
   const Grammar* pGrammar = this->m_pParser->getGrammar();
   Frame first = { nClass, 0, 0 };
   stack.push_back(first);
   while (!stack.empty()) {
      Frame& f = stack.back();
      const UINT* pData = pGrammar->getClassData(f.nClass);
      UINT nTerminals = *pData++;
      const UINT* pTerminals = pData;
      pData += nTerminals;
      UINT nNext = *pData++;
      BOOL bFound = false;
      BOOL bDescend = false;
      while (f.iTerminal < nTerminals)
         if (this->matches(nHandle, pTerminals[f.iTerminal++])) {
            bFound = true;
            break;
         }
      while (!bFound && f.iNext < nNext) {
         UINT nNextClass = pData[f.iNext++];
         UINT nValue = this->getStart(nNextClass);
         if (nValue == 1)
            bFound = true;
         else
         if (nValue == 0) {
            // Not known: look into that class
            bDescend = true;
            Frame next = { nNextClass, 0, 0 };
            stack.push_back(next); // Note: this invalidates f
            break;
         }
      }
      if (bFound) {
         // The classes on the stack lead to each other, so the
         // nonterminals of all of them can begin with the token
         for (size_t i = 0; i < stack.size(); i++)
            this->setStart(stack[i].nClass, 1);
         return true;
      }
      if (bDescend)
         continue;
      // Neither the terminals of the class nor its other classes
      this->setStart(f.nClass, 2);
      stack.pop_back();
   }
   return false;
}

BOOL Parser::matchNatively(UINT nTerminal, const BYTE* pRec, BOOL& b) const
{
   // Decide whether a terminal matches a token, given the packed
   // matching data of the token, if that can be done without asking
   // Python. Returns true if so, and the answer in b.
   b = false;
   const TerminalSpec* pSpec = this->getSpec(nTerminal);
   if (pSpec == NULL || pRec == NULL)
      return false;
   const UINT nKindFlags = pSpec->nKindFlags;
   const UINT nKind = nKindFlags & 0xFFu;
   const UINT nTokenFlags = ((const TokenRec*)pRec)->nCountFlags;
   if (nKind != T_PYTHON &&
      (nKind == T_TEXT || (nTokenFlags & (TKF_FAST | TKF_EMPTY_WORD)) != 0) &&
      (nKind != T_CAT_SO || (nTokenFlags & (TKF_VERBS | TKF_EMPTY_WORD)) != 0)) {
      // The native fast path can decide T_TEXT terminals for any token,
      // and all non-T_PYTHON terminals for word tokens (TKF_FAST for
      // tokens with BÍN meanings, TKF_EMPTY_WORD for unknown words) -
      // except that verb terminals can only be decided for tokens
      // whose meaning records describe their verbs (TKF_VERBS)
      b = Parser::evalMatch(pSpec, pRec, this->m_masks);
      return true;
   }
   if ((nKindFlags & TF_NO_NONWORD) != 0 && (nTokenFlags & TKF_NONWORD) != 0)
      // The terminal can only match word tokens, and this is not one
      // (it is a number, a person name, punctuation, etc.): no match
      return true;
   if ((nKindFlags & TF_NEEDS_CAT) != 0 && (nTokenFlags & TKF_FAST) != 0 &&
      !hasCategory(pRec, pSpec->nCatId))
      // The terminal is matched in Python, but it can only match a
      // meaning of its own word category, and the token has none
      // (typically, a verb terminal and a word that is not a verb)
      return true;
   if ((nKindFlags & (TF_NEEDS_FLAG | TF_IS_FLAG)) != 0 && (nTokenFlags & TKF_FAST) != 0) {
      // The terminal is matched in Python, by a matcher that depends
      // on a property of the token which is noted in its flags
      if ((nTokenFlags & pSpec->nExtra) == 0)
         // The token lacks the property: no match (typically,
         // a preposition terminal and a word that is not a preposition)
         return true;
      if (nKindFlags & TF_IS_FLAG) {
         // The property is all that the matcher looks at
         b = true;
         return true;
      }
   }
   return false;
}

BOOL Column::matchUncached(UINT nHandle, UINT nTerminal) const
{
   // Not cached: obtain a result and store it in the cache
   BOOL b = false;
   BOOL bNative = this->m_pParser->matchNatively(nTerminal, this->m_pTokenRec, b);
   if (bNative) {
      this->m_nNativeMatches++; // Count native match evaluations
      if (this->m_pParser->parityMode()) {
         // Parity mode: also obtain the Python result; count any
         // discrepancy and return the Python (canonical) answer
         BOOL bPy = this->m_pMatchingFunc(nHandle, this->m_nToken, nTerminal) != 0;
         if ((bPy != 0) != (b != 0))
            this->m_pParser->countParityMismatch();
         b = bPy;
      }
   }
   else {
      b = this->m_pMatchingFunc(nHandle, this->m_nToken, nTerminal) != 0;
   }
   this->m_nMatches++; // Count calls to the matching function
   // Mark our cache
   // Note: as for the lookahead cache (see setStart()), this update is
   // not atomic, and the cache can be shared with other threads. Bits are
   // only ever set, and to the same values by all threads, so an entry
   // can't get a wrong value; if an update is lost, the entry stays
   // 'not known' and the match is simply evaluated again.
   this->m_abCache[nTerminal >> 2] |= (BYTE)((b ? 3u : 2u) << ((nTerminal & 3) << 1));
   return b;
}


class File {

   // Safe wrapper for FILE*

private:

   FILE* m_f;

public:

   File(const CHAR* pszFilename, const CHAR* pszMode)
      { this->m_f = fopen(pszFilename, pszMode); }
   ~File(void)
      { if (this->m_f) fclose(this->m_f); }

   operator FILE*() const
      { return this->m_f; }
   operator BOOL() const
      { return this->m_f != NULL; }

   UINT read(void* pb, UINT nLen)
      { return this->m_f ? (UINT)fread(pb, 1, nLen, this->m_f) : 0; }
   UINT write(void* pb, UINT nLen)
      { return this->m_f ? (UINT)fwrite(pb, 1, nLen, this->m_f) : 0; }

   BOOL read_UINT(UINT& n)
      { return this->read(&n, sizeof(UINT)) == sizeof(UINT); }
   BOOL read_INT(INT& i)
      { return this->read(&i, sizeof(INT)) == sizeof(INT); }

};


AllocCounter Grammar::ac;

Grammar::Grammar(UINT nNonterminals, UINT nTerminals, INT iRoot)
   : m_nNonterminals(nNonterminals), m_nTerminals(nTerminals), m_iRoot(iRoot), m_nts(NULL),
      m_nClasses(0), m_pnClass(NULL), m_pnClassOffset(NULL), m_pnClassData(NULL)
{
   Grammar::ac++;
   this->m_nts = new Nonterminal*[nNonterminals];
   memset(this->m_nts, 0, nNonterminals * sizeof(Nonterminal*));
}

Grammar::Grammar(void)
   : m_nNonterminals(0), m_nTerminals(0), m_iRoot(0), m_nts(NULL),
      m_nClasses(0), m_pnClass(NULL), m_pnClassOffset(NULL), m_pnClassData(NULL)
{
   Grammar::ac++;
}

Grammar::~Grammar(void)
{
   this->reset();
   Grammar::ac--;
}

void Grammar::reset(void)
{
   for (UINT i = 0; i < this->m_nNonterminals; i++)
      if (this->m_nts[i])
         delete this->m_nts[i];
   if (this->m_nts) {
      delete [] this->m_nts;
      this->m_nts = NULL;
   }
   this->m_nNonterminals = 0;
   this->m_nTerminals = 0;
   this->m_iRoot = 0;
   delete [] this->m_pnClass;
   delete [] this->m_pnClassOffset;
   delete [] this->m_pnClassData;
   this->m_nClasses = 0;
   this->m_pnClass = NULL;
   this->m_pnClassOffset = NULL;
   this->m_pnClassData = NULL;
}

void Grammar::analyze(void)
{
   // Calculate what the lookahead filter of the parser needs to know
   // about the grammar: the filters of the productions (see the LF_*
   // constants in eparser.h) and the classes of nonterminals.
   UINT nNt = this->m_nNonterminals;
   if (!nNt || this->m_pnClass)
      return;

   // Step 1: find the nullable nonterminals, i.e. those that can derive
   // nothing, by iterating until nothing changes
   std::vector<BYTE> nullable(nNt, 0);
   for (BOOL bChanged = true; bChanged; ) {
      bChanged = false;
      for (UINT i = 0; i < nNt; i++) {
         if (nullable[i] || !this->m_nts[i])
            continue;
         for (Production* p = this->m_nts[i]->getHead(); p; p = p->getNext()) {
            UINT n = p->getLength();
            UINT k = 0;
            while (k < n && (*p)[k] < 0 && nullable[~((UINT)(*p)[k])])
               k++;
            if (k == n) {
               // All items are nullable (or there are none)
               nullable[i] = 1;
               bChanged = true;
               break;
            }
         }
      }
   }

   // Step 2: for each nonterminal A, list the nonterminals B that
   // something derived from A can begin with in one step: those that
   // are first in a production of A, or are only preceded there by
   // nullable nonterminals
   std::vector<UINT> edgeStart(nNt + 1, 0);
   std::vector<UINT> edges;
   for (UINT i = 0; i < nNt; i++) {
      edgeStart[i] = (UINT)edges.size();
      if (!this->m_nts[i])
         continue;
      for (Production* p = this->m_nts[i]->getHead(); p; p = p->getNext())
         for (UINT k = 0; (*p)[k] < 0; k++) {
            UINT nB = ~((UINT)(*p)[k]);
            edges.push_back(nB);
            if (!nullable[nB])
               break;
         }
   }
   edgeStart[nNt] = (UINT)edges.size();

   // Step 3: divide the nonterminals into classes, where two nonterminals
   // are in the same class if each can occur at the start of something
   // derived from the other. Such nonterminals can begin with exactly the
   // same tokens. The classes are the strongly connected components of
   // the graph from step 2 (Tarjan's algorithm, without recursion, since
   // the chains in the graph can be long).
   const UINT NONE = (UINT)-1;
   std::vector<UINT> index(nNt, NONE);
   std::vector<UINT> low(nNt, 0);
   std::vector<UINT> cls(nNt, NONE);
   std::vector<BYTE> onStack(nNt, 0);
   std::vector<UINT> stack;
   struct Frame {
      UINT nNt;
      UINT nEdge;
   };
   std::vector<Frame> calls;
   UINT nIndex = 0;
   UINT nClasses = 0;
   for (UINT nRoot = 0; nRoot < nNt; nRoot++) {
      if (index[nRoot] != NONE)
         continue;
      Frame root = { nRoot, edgeStart[nRoot] };
      calls.push_back(root);
      index[nRoot] = low[nRoot] = nIndex++;
      stack.push_back(nRoot);
      onStack[nRoot] = 1;
      while (!calls.empty()) {
         Frame& f = calls.back();
         UINT v = f.nNt;
         if (f.nEdge < edgeStart[v + 1]) {
            UINT w = edges[f.nEdge++];
            if (index[w] == NONE) {
               index[w] = low[w] = nIndex++;
               stack.push_back(w);
               onStack[w] = 1;
               Frame next = { w, edgeStart[w] };
               calls.push_back(next); // Note: this invalidates f
            }
            else
            if (onStack[w] && index[w] < low[v])
               low[v] = index[w];
         }
         else {
            if (low[v] == index[v]) {
               // v is the root of a component
               UINT w;
               do {
                  w = stack.back();
                  stack.pop_back();
                  onStack[w] = 0;
                  cls[w] = nClasses;
               } while (w != v);
               nClasses++;
            }
            calls.pop_back();
            if (!calls.empty()) {
               UINT u = calls.back().nNt;
               if (low[v] < low[u])
                  low[u] = low[v];
            }
         }
      }
   }

   // Step 4: describe each class by the terminals that its nonterminals
   // can begin with directly, and by the other classes that their
   // nonterminals can begin with. This is a graph without cycles.
   std::vector<UINT> memberStart(nClasses + 1, 0);
   std::vector<UINT> members(nNt);
   for (UINT i = 0; i < nNt; i++)
      memberStart[cls[i] + 1]++;
   for (UINT c = 0; c < nClasses; c++)
      memberStart[c + 1] += memberStart[c];
   std::vector<UINT> fill(memberStart.begin(), memberStart.end() - 1);
   for (UINT i = 0; i < nNt; i++)
      members[fill[cls[i]]++] = i;
   std::vector<UINT> seenTerminal(this->m_nTerminals + 1, NONE);
   std::vector<UINT> seenClass(nClasses, NONE);
   std::vector<UINT> offsets(nClasses, 0);
   std::vector<UINT> data;
   std::vector<UINT> terminals;
   std::vector<UINT> classes;
   for (UINT c = 0; c < nClasses; c++) {
      terminals.clear();
      classes.clear();
      for (UINT m = memberStart[c]; m < memberStart[c + 1]; m++) {
         Nonterminal* pnt = this->m_nts[members[m]];
         if (!pnt)
            continue;
         for (Production* p = pnt->getHead(); p; p = p->getNext())
            for (UINT k = 0; ; k++) {
               INT iItem = (*p)[k];
               if (iItem == 0)
                  break;
               if (iItem > 0) {
                  if (seenTerminal[iItem] != c) {
                     seenTerminal[iItem] = c;
                     terminals.push_back((UINT)iItem);
                  }
                  break;
               }
               UINT nB = ~((UINT)iItem);
               UINT nClassB = cls[nB];
               if (nClassB != c && seenClass[nClassB] != c) {
                  seenClass[nClassB] = c;
                  classes.push_back(nClassB);
               }
               if (!nullable[nB])
                  break;
            }
      }
      offsets[c] = (UINT)data.size();
      data.push_back((UINT)terminals.size());
      data.insert(data.end(), terminals.begin(), terminals.end());
      data.push_back((UINT)classes.size());
      data.insert(data.end(), classes.begin(), classes.end());
   }

   // Step 5: set the lookahead filter for each dot position of each
   // production, working from the end of the production
   for (UINT i = 0; i < nNt; i++) {
      if (!this->m_nts[i])
         continue;
      for (Production* p = this->m_nts[i]->getHead(); p; p = p->getNext()) {
         UINT n = p->getLength();
         // Can everything from the dot to the end derive nothing?
         BOOL bNullable = true;
         UINT nNext = LF_ALWAYS; // The filter for the dot one step further
         p->setFilter(n, LF_ALWAYS);
         for (UINT d = n; d-- > 0; ) {
            INT iItem = (*p)[d];
            UINT nFilter;
            if (iItem > 0) {
               nFilter = LF_TERMINAL | ((UINT)iItem << 2);
               bNullable = false;
            }
            else
            if (!nullable[~((UINT)iItem)]) {
               nFilter = LF_START | (cls[~((UINT)iItem)] << 2);
               bNullable = false;
            }
            else
            if (bNullable)
               nFilter = LF_ALWAYS;
            else {
               // A nullable nonterminal, followed by something that
               // is not nullable as a whole: the nonterminal counts,
               // along with the items that count for the next position
               UINT nCount = 1 + ((nNext & 3) == LF_MULTI ? (nNext >> 2) : 1);
               nFilter = LF_MULTI | (nCount << 2);
            }
            p->setFilter(d, nFilter);
            nNext = nFilter;
         }
      }
      // The prediction table has a copy of the filters for the first position
      this->m_nts[i]->buildPredictions();
   }

   // Keep the description of the classes
   UINT* pnClass = NULL;
   UINT* pnClassOffset = NULL;
   UINT* pnClassData = NULL;
   try {
      pnClass = new UINT[nNt];
      pnClassOffset = new UINT[nClasses];
      pnClassData = new UINT[data.size()];
   }
   catch (...) {
      delete [] pnClass;
      delete [] pnClassOffset;
      delete [] pnClassData;
      throw;
   }
   memcpy(pnClass, &cls[0], nNt * sizeof(UINT));
   memcpy(pnClassOffset, &offsets[0], nClasses * sizeof(UINT));
   memcpy(pnClassData, &data[0], data.size() * sizeof(UINT));
   this->m_nClasses = nClasses;
   this->m_pnClass = pnClass;
   this->m_pnClassOffset = pnClassOffset;
   this->m_pnClassData = pnClassData;
}

class GrammarResetter {

   // Resets a grammar to a known zero state unless
   // explicitly disarmed

private:

   Grammar* m_pGrammar;

public:

   GrammarResetter(Grammar* pGrammar)
      : m_pGrammar(pGrammar)
      { }
   ~GrammarResetter(void)
      { if (this->m_pGrammar) this->m_pGrammar->reset(); }

   void disarm(void)
      { this->m_pGrammar = NULL; }

};

BOOL Grammar::readBinary(const CHAR* pszFilename)
{
   // Attempt to read grammar from binary file.
   // Returns true if successful, otherwise false.
#ifdef DEBUG   
   printf("Reading binary grammar file %s\n", pszFilename);
#endif
   this->reset();
   File f(pszFilename, "rb");
   if (!f)
      return false;
   const UINT SIGNATURE_LENGTH = 16;
   BYTE abSignature[SIGNATURE_LENGTH];
   UINT n = f.read(abSignature, sizeof(abSignature));
   if (n < sizeof(abSignature))
      return false;
   // Check the signature - should start with 'Greynir'
   if (memcmp(abSignature, "Greynir", 7) != 0) {
#ifdef DEBUG
      printf("Signature mismatch\n");
#endif      
      return false;
   }
   UINT nNonterminals, nTerminals;
   if (!f.read_UINT(nTerminals))
      return false;
   if (!f.read_UINT(nNonterminals))
      return false;
#ifdef DEBUG
   printf("Reading %u terminals and %u nonterminals\n", nTerminals, nNonterminals);
#endif
   // Sanity check on the counts, to fail cleanly on a corrupt file
   // rather than attempting a huge allocation
   const UINT MAX_SYMBOLS = 1u << 24;
   if (nTerminals > MAX_SYMBOLS || nNonterminals > MAX_SYMBOLS)
      return false;
   if (!nNonterminals)
      // No nonterminals to read: we're done
      return true;
   INT iRoot;
   if (!f.read_INT(iRoot))
      return false;
#ifdef DEBUG
   printf("Root nonterminal index is %d\n", iRoot);
#endif
   // The root must be a valid nonterminal index (negative, within range)
   if (iRoot >= 0 || ~((UINT)iRoot) >= nNonterminals)
      return false;
   // Initialize the nonterminals array
   Nonterminal** ppnts = new Nonterminal*[nNonterminals];
   memset(ppnts, 0, nNonterminals * sizeof(Nonterminal*));
   this->m_nts = ppnts;
   this->m_nNonterminals = nNonterminals;
   this->m_nTerminals = nTerminals;
   this->m_iRoot = iRoot;
   // Ensure we clean up properly in case of exit with error
   GrammarResetter resetter(this);
   // Loop through the nonterminals
   for (n = 0; n < nNonterminals; n++) {
      // How many productions?
      UINT nLenPlist;
      if (!f.read_UINT(nLenPlist))
         return false;
      Nonterminal* pnt = new Nonterminal(L"");
      // Loop through the productions
      for (UINT j = 0; j < nLenPlist; j++) {
         UINT nId;
         if (!f.read_UINT(nId)) {
            delete pnt;
            return false;
         }
         UINT nPriority;
         if (!f.read_UINT(nPriority)) {
            delete pnt;
            return false;
         }
         UINT nLenProd;
         if (!f.read_UINT(nLenProd)) {
            delete pnt;
            return false;
         }
         const UINT MAX_LEN_PROD = 256;
         if (nLenProd > MAX_LEN_PROD) {
            // Production too long
#ifdef DEBUG
            printf("Production too long\n");
#endif
            delete pnt;
            return false;
         }
         // Read the production
         INT aiProd[MAX_LEN_PROD];
         if (f.read(aiProd, nLenProd * sizeof(INT)) != nLenProd * sizeof(INT)) {
            // Truncated file
            delete pnt;
            return false;
         }
         // Validate the production items: a negative item must be a
         // valid nonterminal index and a positive item a valid terminal
         // index (terminals are 1-based); zero items are not allowed
         for (UINT k = 0; k < nLenProd; k++) {
            INT iItem = aiProd[k];
            BOOL bValid = (iItem < 0)
               ? ~((UINT)iItem) < nNonterminals
               : (iItem > 0 && (UINT)iItem <= nTerminals);
            if (!bValid) {
#ifdef DEBUG
               printf("Invalid item %d in production %u\n", iItem, nId);
#endif
               delete pnt;
               return false;
            }
         }
         // Create a fresh production object
         Production* pprod = new Production(nId, nPriority, nLenProd, aiProd);
         // Add it to the nonterminal
         pnt->addProduction(pprod);
      }
      // Add the nonterminal to the grammar
      this->setNonterminal(-1 -(INT)n, pnt);
   }
#ifdef DEBUG   
   printf("Reading completed\n");
   fflush(stdout);
#endif
   // Calculate the lookahead filters
   this->analyze();
   // No error: we disarm the resetter
   resetter.disarm();
   return true;
}

void Grammar::setNonterminal(INT iIndex, Nonterminal* pnt)
{
   // iIndex is negative
   ASSERT(iIndex < 0);
   UINT nIndex = ~((UINT)iIndex); // -1 becomes 0, -2 becomes 1, etc.
   ASSERT(nIndex < this->m_nNonterminals);
   if (nIndex < this->m_nNonterminals)
      this->m_nts[nIndex] = pnt;
}

Nonterminal* Grammar::operator[] (INT iIndex) const
{
   // Return the nonterminal with index nIndex (1-based)
   ASSERT(iIndex < 0);
   UINT nIndex = ~((UINT)iIndex); // -1 becomes 0, -2 becomes 1, etc.
   return (nIndex < this->m_nNonterminals) ? this->m_nts[nIndex] : NULL;
}

const WCHAR* Grammar::nameOfNt(INT iNt) const
{
   Nonterminal* pnt = (*this)[iNt];
   return pnt ? pnt->getName() : L"[None]";
}


AllocCounter Node::ac;


Node::Node(const Label& label, Forest* pForest)
   : m_label(label), m_pHead(NULL), m_pForest(pForest), m_pR(NULL)
{
   // Note: nodes are counted in batches, by the Forest
}

void Node::addFamily(Production* pProd, Node* pW, Node* pV)
{
   // pW may be NULL, or both may be NULL if epsilon
   FamilyEntry* p = this->m_pHead;
   while (p) {
      if (p->pProd == pProd && p->p1 == pW && p->p2 == pV)
         // We already have the same family entry
         return;
      p = p->pNext;
   }
   // Not already there: create a new entry
   p = (FamilyEntry*)this->m_pForest->alloc(sizeof(FamilyEntry));
   p->pProd = pProd;
   p->p1 = pW;
   p->p2 = pV;
   p->pNext = this->m_pHead;
   this->m_pHead = p;
}

void Node::destroyForest(Node* pNode)
{
   // Delete the forest that the node belongs to, and thereby the node itself
   if (pNode)
      delete pNode->m_pForest;
}

void Node::_dump(Grammar* pGrammar, UINT nIndent)
{
   for (UINT i = 0; i < nIndent; i++)
      printf("  ");
   Production* pProd = this->m_label.m_pProd;
   UINT nDot = this->m_label.m_nDot;
   INT iDotProd = pProd ? (*pProd)[nDot] : 0;
   INT iNt = this->m_label.m_iNt;
   const WCHAR* pwzName;
   WCHAR wchBuf[16];
   if (iNt < 0) {
      // Nonterminal
      pwzName = pGrammar->nameOfNt(iNt);
      if (!pwzName || wcslen(pwzName) == 0) {
         swprintf(wchBuf, 16, L"(Nt %d)", iNt);
         pwzName = wchBuf;
      }
   }
   else {
      // Token
      swprintf(wchBuf, 16, L"(Token %d)", iNt);
      pwzName = wchBuf;
   }
   printf("Label: %ls %u %d [%u:%u]\n",
      pwzName,
      nDot,
      iDotProd,
      this->m_label.m_nI,
      this->m_label.m_nJ);
   FamilyEntry* p = this->m_pHead;
   UINT nOption = 0;
   while (p) {
      if (nOption || p->pNext) {
         // Don't print 'Option 1' if there is only one option
         for (UINT i = 0; i < nIndent; i++)
            printf("  ");
         printf("Option %u\n", nOption + 1);
      }
      if (p->p1)
         p->p1->_dump(pGrammar, nIndent + 1);
      if (p->p2)
         p->p2->_dump(pGrammar, nIndent + 1);
      p = p->pNext;
      nOption++;
   }
   fflush(stdout);
}

void Node::dump(Grammar* pGrammar)
{
   this->_dump(pGrammar, 0);
}

UINT Node::numCombinations(Node* pNode)
{
   // Be careful when calling this function: it may take a long
   // time to execute since it visits nodes for every possible
   // combination of nodes in the tree. In other words, it ignores
   // the packing of the tree. The Python version keeps track of
   // already visited nodes and is much more efficient for large
   // trees.
   if (!pNode || pNode->m_label.m_iNt >= 0)
      return 1;
   UINT nComb = 0;
   FamilyEntry* p = pNode->m_pHead;
   while (p) {
      UINT n1 = p->p1 ? Node::numCombinations(p->p1) : 1;
      UINT n2 = p->p2 ? Node::numCombinations(p->p2) : 1;
      nComb += n1 * n2;
      p = p->pNext;
   }
   return nComb == 0 ? 1 : nComb;
}


NodeDict::NodeDict(Forest* pForest)
   : m_pForest(pForest), m_pHead(NULL), m_ppBins(NULL), m_nLookups(0)
{
   this->m_ppBins = new NdEntry* [HASH_BINS];
   memset(this->m_ppBins, 0, HASH_BINS * sizeof(NdEntry*));
}

NodeDict::~NodeDict(void)
{
   this->reset();
   delete [] this->m_ppBins;
}

Node* NodeDict::lookupOrAdd(const Label& label)
{
   // If the label is already found in the NodeDict,
   // return the corresponding node.
   // Otherwise, create a new node, add it to the dict
   // under the label, and return it.
   this->m_nLookups++;
   NdEntry*& pBin = this->m_ppBins[NodeDict::binOf(label.getHash())];
   NdEntry* p = pBin;
   while (p) {
      if (p->pNode->hasLabel(label))
         return p->pNode;
      p = p->pChain;
   }
   // Not found: add to the dict
   p = (NdEntry*)this->m_pool.alloc();
   p->pNode = this->m_pForest->newNode(label);
   p->pNext = this->m_pHead;
   this->m_pHead = p;
   p->pChain = pBin;
   pBin = p;
   return p->pNode;
}

void NodeDict::reset(void)
{
   NdEntry* p = this->m_pHead;
   while (p) {
      NdEntry* pNext = p->pNext;
      // Clear the hash bin of the entry (this may happen more than
      // once for the same bin, which is harmless)
      this->m_ppBins[NodeDict::binOf(p->pNode->getHash())] = NULL;
      this->m_pool.release(p);
      p = pNext;
   }
   this->m_pHead = NULL;
   // Flush the locally accumulated lookup statistics
   if (this->m_nLookups) {
      NodeDict::acLookups.add(this->m_nLookups, 0);
      this->m_nLookups = 0;
   }
}


Parser::Parser(Grammar* p, MatchingFunc pMatchingFunc, AllocFunc pAllocFunc)
   : m_pGrammar(p), m_pMatchingFunc(pMatchingFunc), m_pAllocFunc(pAllocFunc),
      m_pSpecs(NULL), m_nSpecs(0), m_pMeaningsFunc(NULL),
      m_bParity(false), m_nParityMismatches(0), m_bLookahead(true)
{
   ASSERT(this->m_pGrammar != NULL);
   ASSERT(this->m_pMatchingFunc != NULL);
   memset(&this->m_masks, 0, sizeof(MatchMasks));
   memset(&this->m_rt, 0, sizeof(ReducerTables));
}

Parser::~Parser(void)
{
   this->setReducerTables(NULL);
   if (this->m_pSpecs) {
      delete [] this->m_pSpecs;
      acMatchingTables--;
   }
}

void Parser::setMatchingTable(const BYTE* pSpecs, UINT nSpecs,
   MeaningsFunc fpMeanings, const BYTE* pMasks, BOOL bParity)
{
   // Install (or remove, if pSpecs is NULL) a native matching table.
   // The spec table and mask structure are copied, so the caller's
   // buffers need not outlive this call.
   if (this->m_pSpecs) {
      delete [] this->m_pSpecs;
      this->m_pSpecs = NULL;
      acMatchingTables--;
   }
   this->m_nSpecs = 0;
   this->m_pMeaningsFunc = NULL;
   this->m_bParity = bParity;
   this->m_nParityMismatches.store(0, std::memory_order_relaxed);
   memset(&this->m_masks, 0, sizeof(MatchMasks));
   this->m_prefillWord.clear();
   this->m_prefillNonword.clear();
   this->m_litStart.clear();
   this->m_litTerminals.clear();
   if (!pSpecs || !nSpecs || !fpMeanings || !pMasks)
      return;
   this->m_pSpecs = new TerminalSpec[nSpecs];
   acMatchingTables++;
   memcpy(this->m_pSpecs, pSpecs, nSpecs * sizeof(TerminalSpec));
   this->m_nSpecs = nSpecs;
   memcpy(&this->m_masks, pMasks, sizeof(MatchMasks));
   this->m_pMeaningsFunc = fpMeanings;

   // Prepare for prefilling of matching caches (see prefillCache()).
   // In parity mode, every match is evaluated, so nothing is prefilled.
   if (bParity)
      return;
   UINT nTerminals = this->getNumTerminals();
   UINT nLast = nSpecs - 1 < nTerminals ? nSpecs - 1 : nTerminals;
   UINT nBytes = Parser::matchCacheSize(nTerminals);
   std::vector<BYTE> word(nBytes, 0);
   std::vector<BYTE> nonword(nBytes, 0);
   UINT nMaxLit = 0;
   for (UINT t = 1; t <= nLast; t++) {
      const TerminalSpec& spec = this->m_pSpecs[t];
      UINT nKind = spec.nKindFlags & 0xFFu;
      BOOL bLiteral = nKind == T_TEXT || nKind == T_TEXT_CAT || nKind == T_LEMMA;
      // The value 2 in the matching cache means 'known not to match'
      BYTE bNo = (BYTE)(2u << ((t & 3) << 1));
      if (bLiteral) {
         // A literal terminal can't match a word unless the text of
         // the word, or one of its lemmas, is the literal (cf. evalMatch())
         word[t >> 2] |= bNo;
         if (spec.nLitId > nMaxLit)
            nMaxLit = spec.nLitId;
      }
      if (nKind == T_TEXT || (spec.nKindFlags & TF_NO_NONWORD))
         // A strong literal without a category can't match a token that
         // is not a word unless its text is the literal; and some
         // terminals never match such tokens (cf. matchUncached())
         nonword[t >> 2] |= bNo;
   }
   // Index the literal terminals by the id of their literal
   std::vector<UINT> start(nMaxLit + 2, 0);
   for (UINT t = 1; t <= nLast; t++) {
      const TerminalSpec& spec = this->m_pSpecs[t];
      UINT nKind = spec.nKindFlags & 0xFFu;
      if (nKind == T_TEXT || nKind == T_TEXT_CAT || nKind == T_LEMMA)
         start[spec.nLitId + 1]++;
   }
   for (UINT i = 0; i <= nMaxLit; i++)
      start[i + 1] += start[i];
   std::vector<UINT> terminals(start[nMaxLit + 1], 0);
   std::vector<UINT> fill(start.begin(), start.end() - 1);
   for (UINT t = 1; t <= nLast; t++) {
      const TerminalSpec& spec = this->m_pSpecs[t];
      UINT nKind = spec.nKindFlags & 0xFFu;
      if (nKind == T_TEXT || nKind == T_TEXT_CAT || nKind == T_LEMMA)
         terminals[fill[spec.nLitId]++] = t;
   }
   this->m_prefillWord.swap(word);
   this->m_prefillNonword.swap(nonword);
   this->m_litStart.swap(start);
   this->m_litTerminals.swap(terminals);
}

void Parser::prefillCache(BYTE* abCache, const BYTE* pTokenRec) const
{
   // Called when a token is seen for the first time, i.e. when its
   // matching cache is empty. Most of the terminals of the grammar are
   // literals, which can only match a token if its text or one of its
   // lemmas is that very literal. Rather than finding that out for one
   // terminal at a time, as the parser happens to ask about them (it
   // asks about half of all terminals for every new token), we mark all
   // literal terminals as not matching in one go - except the few whose
   // literal does occur in the token, which are left to be evaluated
   // in the normal way. For a token that is not a word, the same goes
   // for the terminals that never match such tokens.
   const TokenRec* pHdr = (const TokenRec*)pTokenRec;
   const UINT nTokenFlags = pHdr->nCountFlags;
   const std::vector<BYTE>& pattern =
      (nTokenFlags & (TKF_FAST | TKF_EMPTY_WORD)) ? this->m_prefillWord : this->m_prefillNonword;
   if (pattern.empty() || !(nTokenFlags & (TKF_FAST | TKF_EMPTY_WORD | TKF_NONWORD)))
      return;
   std::vector<BYTE> fill(pattern);
   const UINT nLits = (UINT)this->m_litStart.size();
   // Leave the terminals of a literal that occurs in the token alone
   UINT nCount = (nTokenFlags & TKF_FAST) ? (nTokenFlags & 0xFFFFu) : 0;
   const MeaningRec* pm = (const MeaningRec*)(pTokenRec + sizeof(TokenRec));
   for (UINT i = 0; i <= nCount; i++) {
      UINT nLit = i == 0 ? pHdr->nFormId : pm[i - 1].nLemmaId;
      if (!nLit || nLit + 1 >= nLits)
         continue;
      for (UINT k = this->m_litStart[nLit]; k < this->m_litStart[nLit + 1]; k++) {
         UINT t = this->m_litTerminals[k];
         fill[t >> 2] &= (BYTE)~(3u << ((t & 3) << 1));
      }
   }
   // As elsewhere, bits are only ever set in a matching cache, and to
   // the same values by all threads that may be working on the same token
   for (size_t i = 0; i < fill.size(); i++)
      abCache[i] |= fill[i];
   // The entry of terminal 0, which does not exist,
   // tells that the cache has been prefilled
   abCache[0] |= 3;
}

static inline BOOL defaultMatchMeaning(const TerminalSpec* pSpec,
   const MeaningRec& m, const MatchMasks& mk)
{
   // Mirrors the feature bit logic of WordMatchers.matcher_default()
   // in binparser.py
   if (m.nFlags & MF_NO_BEYGING) {
      if (m.nFlags & MF_IS_LO_SO)
         // Adjective or verb abbreviation: matches irrespective of variants
         return true;
      if (m.nFlags & MF_IS_NOUN)
         // Noun abbreviation: check gender, permit singular forms only
         return (pSpec->nFbits & (mk.genders | mk.number) & ~(m.nFbits | mk.et)) == 0;
      return pSpec->nFbits == 0;
   }
   return (pSpec->nFbits & ~m.nFbits) == 0;
}

static BOOL verbMatchMeaning(const TerminalSpec* pSpec,
   const MeaningRec& m, const MatchMasks& mk)
{
   // Mirrors BIN_Token.verb_matches() in binparser.py: does a verb
   // terminal (so_...) match a meaning of a verb? T has a bit for each
   // variant of the terminal, and F a bit for each variant whose BÍN
   // string occurs in the inflection string of the verb. What the Python
   // method asks other methods about the lemma of the verb has been asked
   // in advance, and is in the meaning record (see _verb_profile()).
   // The order of the tests is that of the Python method.
   const UINT64 T = pSpec->nFbits;
   const UINT64 F = m.nFbits;
   const UINT nFlags = pSpec->nExtra;
   if (T & mk.subj) {
      // A verb whose subject is not in the nominative case
      // ('mig langar', 'Páli þykir')
      if ((T & mk.nh) && !(F & mk.nh))
         return false;
      if (T & mk.mm)
         // For subj_mm, nothing but the middle voice matters
         return (F & mk.mm) != 0;
      if ((T & mk.gm) && !(F & mk.gm))
         return false;
      if ((T & mk.et) && !(F & mk.et))
         return false;
      if ((T & mk.ft) && !(F & mk.ft))
         return false;
      if (F & mk.expl)
         // No expletive forms for subj terminals
         return false;
      const BOOL bFormLh = (F & mk.lhpt) != 0;
      if (T & mk.lhpt)
         // Subject kind 0 is 'lhþt'
         return bFormLh && (m.nSubjects & 1u) != 0;
      if (bFormLh)
         return false;
      const BOOL bFormSagnb = (F & mk.sagnb) != 0;
      if (nFlags & SF_NONE) {
         if (((T & mk.sagnb) != 0) != bFormSagnb)
            return false;
         // Subject kind 1 is 'none'
         return (m.nSubjects & 2u) != 0;
      }
      if (bFormSagnb && !(T & mk.sagnb))
         return false;
      if ((T & mk.op) && (m.nVerbFlags & VF_CANNOT_BE_IMPERSONAL))
         return false;
      if (nFlags & SF_SUBJ_NARGS) {
         // so_1_þf_subj_op_þgf: one argument, in the given case
         if (nFlags & SF_SUBJ_LAST_EF)
            // A genitive subject is not combined with an object
            return false;
         if (!((m.nArgsPlain >> ((pSpec->nMask >> 8) & 0xFFu)) & 1u))
            return false;
      }
      // Finally, the subject case, which is the last variant of the terminal
      return ((m.nSubjects >> ((pSpec->nMask >> 16) & 0xFFu)) & 1u) != 0;
   }
   // Not a subj terminal
   if (m.nVerbFlags & VF_STRICTLY_IMPERSONAL)
      return false;
   if ((T & mk.expl) && !(F & mk.expl))
      return false;
   if ((T & mk.et) && (F & mk.ft))
      return false;
   if ((T & mk.ft) && (F & mk.et))
      return false;
   if (T & mk.verbVariants & ~F)
      // The terminal has a variant (person, mood, voice, etc.)
      // that the verb form does not have
      return false;
   if (F & mk.restrictive & ~T)
      // The verb form has a variant that must be
      // explicitly present in the terminal, but is not
      return false;
   if ((T & mk.lhpt) && (F & mk.vb) && !(T & mk.vb))
      // Only the strong declension of the past participle, unless
      // the weak one is asked for
      return false;
   if ((T & mk.bh) && (m.nVerbFlags & VF_ST))
      // Not the clipped imperative
      return false;
   if (!(nFlags & SF_HAS_NARGS)) {
      // No number of arguments in the terminal: all verbs match,
      // except that a past participle terminal can specify a case
      if ((T & mk.lhpt) && (T & mk.cases & ~F))
         return false;
      return true;
   }
   // Can the verb take arguments in the cases that the terminal has?
   if ((m.nArgs >> (pSpec->nMask & 0xFFu)) & 1u)
      return true;
   // An unknown verb can match a terminal without arguments
   return (nFlags & SF_NO_CASES) && (m.nVerbFlags & VF_UNKNOWN);
}

BOOL Parser::evalMatch(const TerminalSpec* pSpec, const BYTE* pTokenRec,
   const MatchMasks& mk)
{
   // Native token/terminal matching. This function mirrors, exactly,
   // the semantics of the corresponding Python matchers in binparser.py
   // for the terminal kinds that are encoded natively; parity between
   // the two implementations is asserted by tests (and can be verified
   // at run-time via the parity mode).
   const TokenRec* pHdr = (const TokenRec*)pTokenRec;
   const UINT nKind = pSpec->nKindFlags & 0xFFu;
   if (nKind == T_TEXT)
      // Strong literal without category: pure token text identity,
      // valid for all token kinds (mirrors shortcut_match)
      return pHdr->nFormId != 0 && pHdr->nFormId == pSpec->nLitId;
   if (pHdr->nCountFlags & TKF_EMPTY_WORD)
      // Unknown word without BÍN meanings: per BIN_Token.matches_WORD(),
      // only a no_..._et_hk terminal without 'gr' can match natively
      // (sérnafn terminals are T_PYTHON and don't reach this point)
      return nKind == T_CAT_NOUN && (pSpec->nKindFlags & TF_MATCHES_EMPTY) != 0;
   if (nKind == T_TEXT_CAT && pHdr->nFormId != pSpec->nLitId)
      // Strong literal with category: the token text must be identical
      return false;
   const UINT n = pHdr->nCountFlags & 0xFFFFu;
   const MeaningRec* pm = (const MeaningRec*)(pTokenRec + sizeof(TokenRec));
   for (UINT i = 0; i < n; i++) {
      const MeaningRec& m = pm[i];
      switch (nKind) {
         case T_TEXT_CAT:
            // Token text already matched: require the specified category
            if (m.nCatId == pSpec->nCatId)
               return true;
            break;
         case T_LEMMA:
            // Lemma literal: interned lemma identity, optional category,
            // then default matcher logic, then the middle voice exclusion
            // for verb lemma literals (matcher_lemma_literal)
            if (m.nLemmaId != 0 && m.nLemmaId == pSpec->nLitId
               && (pSpec->nCatId == 0 || m.nCatId == pSpec->nCatId)
               && defaultMatchMeaning(pSpec, m, mk)
               && (!(pSpec->nKindFlags & TF_MM_EXCLUDE) || !(m.nFbits & mk.mm)))
               return true;
            break;
         case T_CAT_DEFAULT:
            if (m.nMappedCatId == pSpec->nCatId
               && defaultMatchMeaning(pSpec, m, mk))
               return true;
            break;
         case T_CAT_MASK:
            // abfn/pfn: masked feature bit test (matcher_abfn/matcher_pfn)
            if (m.nCatId == pSpec->nCatId
               && (pSpec->nFbits & pSpec->nMask & ~m.nFbits) == 0)
               return true;
            break;
         case T_CAT_FIRST:
            // töl: category only, variants don't disqualify (matcher_töl)
            if (m.nMappedCatId == pSpec->nCatId)
               return true;
            break;
         case T_CAT_NOUN:
            // no_...: mirrors matcher_no()
            if (!(m.nFlags & MF_IS_NOUN))
               break;
            if (pSpec->nKindFlags & TF_ABBREV) {
               // no_abbrev: only match meanings without inflection info
               if (m.nFlags & MF_NO_BEYGING)
                  return true;
               break;
            }
            if (m.nFlags & MF_NAME_FL)
               // Person/family names are only matched by person terminals
               break;
            if (m.nFlags & MF_NO_BEYGING) {
               // No case/number info (probably a foreign word):
               // check gender only, and don't match a demand for
               // the definite article ('gr')
               if ((pSpec->nFbits & mk.genders & ~m.nFbits) == 0
                  && (pSpec->nFbits & mk.gr) == 0)
                  return true;
            }
            else {
               if ((pSpec->nFbits & ~m.nFbits) == 0)
                  return true;
            }
            break;
         case T_CAT_LO:
            // lo_... without ending constraints (matcher_lo)
            if (m.nCatId != pSpec->nCatId)
               break;
            if ((pSpec->nKindFlags & TF_SCASE) && !((m.nSubjects >> pSpec->nExtra) & 1u))
               // The terminal demands an adjective that can take a subject
               // in a particular case, and this one can not
               break;
            // Abbreviations match regardless of variants
            if ((m.nFlags & MF_NO_BEYGING) || (pSpec->nFbits & ~m.nFbits) == 0)
               return true;
            break;
         case T_CAT_SO:
            // so_...: mirrors matcher_so()
            if (m.nCatId != pSpec->nCatId)
               break;
            if (m.nFlags & MF_NO_BEYGING) {
               // An abbreviated verb matches all forms
               // except the present participle
               if ((pSpec->nFbits & mk.lhnt) != mk.lhnt)
                  return true;
               break;
            }
            if (verbMatchMeaning(pSpec, m, mk))
               return true;
            break;
         case T_CAT_AO:
            // ao_... without ending constraints (matcher_ao)
            if (m.nCatId == pSpec->nCatId
               && (pSpec->nFbits & ~m.nFbits) == 0)
               return true;
            break;
         default:
            break;
      }
   }
   return false;
}

BYTE* Parser::allocCache(UINT nHandle, UINT nToken, BOOL* pbNeedRelease)
{
   // Create a fresh token/terminal matching cache: two bits for each
   // terminal (which are numbered from 1), followed by the lookahead
   // cache, which has two bits for each class of nonterminals
   // (see Column::matches() and Column::canStart())
   UINT nSize = Parser::matchCacheSize(this->getNumTerminals()) +
      (this->m_pGrammar->getNumClasses() + 3) / 4;
   BYTE* abCache = NULL;
   *pbNeedRelease = false;
   if (this->m_pAllocFunc)
      // There is a cache allocation function: call it
      abCache = this->m_pAllocFunc(nHandle, nToken, nSize);
   if (!abCache) {
      // Either no cache allocation function, or it returned NULL
      // Allocate our own buffer and initialize it to zero
      abCache = new BYTE[nSize];
      memset(abCache, 0, nSize * sizeof(BYTE));
      *pbNeedRelease = true;
   }
   return abCache;
}

void Parser::releaseCache(BYTE* abCache)
{
   // Release a token/terminal matching cache
   // (Only call if *pbNeedRelease was true after calling allocCache())
   delete [] abCache;
}

BOOL Parser::viableMulti(const Production* pProd, UINT nDot, UINT nCount,
   Column* pE, UINT nHandle)
{
   // The dot is followed by nCount items, all of them nullable
   // nonterminals except the last one: can any of them begin with
   // the token of the column?
   for (UINT k = 0; k < nCount; k++) {
      INT iItem = (*pProd)[nDot + k];
      if (iItem > 0) {
         if (pE->matches(nHandle, (UINT)iItem))
            return true;
      }
      else
      if (pE->canStart(nHandle, this->m_pGrammar->getClass(iItem)))
         return true;
   }
   return false;
}

inline BOOL Parser::viable(UINT nFilter, const Production* pProd, UINT nDot,
   Column* pE, UINT nHandle)
{
   // Return true if a state of the given production, with the dot at
   // the given position, can be of any use in the column pE. It can be
   // if what follows the dot can begin with the token of the column, or
   // can derive nothing; otherwise the dot can never move, and the state
   // would be dead weight. The filter (see the LF_* constants in
   // eparser.h) says what needs to be looked at to find that out.

   // Leaving such states out does not alter the resulting parse forest.
   // A state that can't advance is never completed, and the tree nodes
   // that it would refer to (cf. makeNode()) are interior ones, labeled
   // with the production and the dot, that could only be reached from
   // states identical to it.

   // Without the lookahead filter, only a terminal at the dot is looked at.
   UINT nKind = nFilter & 3;
   if (nKind == LF_ALWAYS)
      return true;
   if (nKind == LF_TERMINAL)
      return pE->matches(nHandle, nFilter >> 2);
   if (!this->m_bLookahead)
      return true;
   if (nKind == LF_START)
      return pE->canStart(nHandle, nFilter >> 2);
   return this->viableMulti(pProd, nDot, nFilter >> 2, pE, nHandle);
}

inline BOOL Parser::canAdvance(State* pState, Column* pE, UINT nHandle, INT& iNext)
{
   // Return true if the state that results from moving the dot of pState
   // one step to the right can be pushed to the column pE. If not, we can
   // save the effort of creating the advanced state and its tree node -
   // which is a significant saving, since in a large grammar a majority
   // of candidate states are immediately rejected by the current token.

   // iNext receives the item that will be at the dot of the advanced state.
   const Production* pProd = pState->getProd();
   UINT nDot = pState->getDot() + 1;
   iNext = (*pProd)[nDot];
   return this->viable(pProd->getFilter(nDot), pProd, nDot, pE, nHandle);
}

Node* Parser::makeNode(State* pState, UINT nEnd, Node* pV, NodeDict& ndV)
{
   UINT nDot = pState->getDot() + 1;
   Production* pProd = pState->getProd();
   UINT nLen = pProd->getLength();
   if (nDot == 1 && nLen >= 2)
      return pV;

   INT iNtB = pState->getNt();
   UINT nStart = pState->getStart();
   Node* pW = pState->getNode();
   Production* pProdLabel = pProd;
   if (nDot >= nLen) {
      // Completed production: label by nonterminal only
      nDot = 0;
      pProdLabel = NULL;
   }
   Label label(iNtB, nDot, pProdLabel, nStart, nEnd);
   Node* pY = ndV.lookupOrAdd(label);
   pY->addFamily(pProd, pW, pV); // pW may be NULL
   return pY;
}

void Parser::pushNew(State* pState, Column* pE, State*& pQ)
{
   // Push a state that is known not to be in the column already,
   // and whose item at the dot - if it is a terminal - is known to
   // match the current token. This applies to the states that are
   // created by the Earley predictor.
   if (pState->prodDot() <= 0)
      // Nonterminal or epsilon: add state to column
      pE->addState(pState);
   else {
      // Terminal: link into list whose head is pQ
      pState->setNext(pQ);
      pQ = pState;
   }
}

void Parser::push(UINT nHandle, State* pState, Column* pE, State*& pQ,
   StateChunk* pChunkHead, StateSet& states)
{
   INT iItem = pState->prodDot();
   if (iItem <= 0) {
      // Nonterminal or epsilon: add state to column,
      // unless an identical state is already there
      if (states.add(pState)) {
         pE->addState(pState);
         return;
      }
   }
   else
   if (pE->matches(nHandle, (UINT)iItem)) {
      // Terminal matching the current token
      // Link into list whose head is pQ
      pState->setNext(pQ);
      pQ = pState;
      return;
   }
   // We did not actually push the state; discard it. Note that the
   // state is not necessarily a newly allocated one: the scanner re-uses
   // states, and the newest chunk can even be empty at this point.
   ASSERT(pChunkHead != NULL);
   if ((BYTE*)pState + sizeof(State) == pChunkHead->m_ast + pChunkHead->m_nIndex) {
      // The state is the most recently allocated one in the chunk
      // (a very common case): go back one location in the chunk
      pChunkHead->m_nIndex -= sizeof(State);
      pChunkHead->m_nDiscarded++;
   }
}

Node* Parser::parse(UINT nHandle, INT iStartNt, UINT* pnErrorToken,
   UINT nTokens, const UINT pnToklist[])
{
   // If pnToklist is NULL, a sequence of integers 0..nTokens-1 will be used
   // Sanity checks
   if (!nTokens)
      return NULL;
   if (!this->m_pGrammar)
      return NULL;
   if (iStartNt >= 0)
      // Root must be nonterminal (index < 0)
      return NULL;
   Nonterminal* pRootNt = (*this->m_pGrammar)[iStartNt];
   if (!pRootNt)
      // No or invalid root nonterminal
      return NULL;
   if (pnErrorToken)
      *pnErrorToken = 0;

   // Initialize the Earley columns
   UINT i;
   Column** pCol = new Column* [nTokens + 1];
   for (i = 0; i < nTokens; i++)
      pCol[i] = new Column(this, pnToklist ? pnToklist[i] : i);
   pCol[i] = new Column(this, (UINT)-1); // Sentinel column

   // Initialize parser state
   State* pQ0 = NULL;
   StateChunk* pChunkHead = NULL;
   // The forest owns all tree nodes created during the parse
   Forest* pForest = new Forest();
   // The states of the column that is currently being added to,
   // for detecting duplicates
   StateSet states;

   // Prepare the the first column
   pCol[0]->startParse(nHandle);

   // The lookahead filter can find out that the parse is going to fail
   // one column earlier than is found out without it. In that case, the
   // parse is stopped, and the error is reported at the token where it
   // would have been found without the filter.
   BOOL bStopped = false;
   // Would any state have been pushed without the lookahead filter?
   BOOL bOther = false;

   // Prepare the initial states: the productions of the root nonterminal
   UINT nPred;
   const Prediction* pPred = pRootNt->getPredictions(nPred);
   for (UINT k = 0; k < nPred; k++) {
      if (!this->viable(pPred[k].nFilter, pPred[k].pProd, 0, pCol[0], nHandle)) {
         if (pPred[k].iFirst < 0)
            bOther = true;
         continue;
      }
      State* ps = new (pChunkHead) State(iStartNt, pPred[k].pProd, pPred[k].iFirst, 0);
#ifdef DEBUG
      printf("For initial state, pushing production starting with item %d\n", pPred[k].iFirst);
#endif
      this->push(nHandle, ps, pCol[0], pQ0, pChunkHead, states);
   }
   if (bOther && !pQ0 && pCol[0]->isEmpty()) {
      // Nothing that the root nonterminal derives begins with the first
      // token. Without the filter, this is found out in the second column.
      bStopped = true;
      if (pnErrorToken)
         *pnErrorToken = 1;
   }

   // Main parse loop
   State* pQ = NULL;
   NodeDict ndV(pForest); // Node dictionary
   UINT nNumNonterminals = this->getNumNonterminals();
   // Flags for each nonterminal, valid within the current column
   const BYTE NT_PREDICTED = 1;  // The nonterminal has been predicted
   const BYTE NT_IN_H = 2;       // The nonterminal has elements in the H set
   BYTE* pbNtFlags = new BYTE[nNumNonterminals];
   Pool<HNode> poolH; // Storage for the elements of the H sets
   // The H set of the current column, indexed by nonterminal: for each
   // nonterminal, the head of a list of the H set elements that refer to
   // it, linked via HNode::getNtNext(), most recently added first.
   // This saves the predictor from looking through the entire H set
   // (which can have hundreds of elements in a column) for every
   // state that has a nonterminal at the dot. The array is all NULLs
   // between columns; only the entries used are reset after each column.
   HNode** ppHByNt = new HNode* [nNumNonterminals];
   memset(ppHByNt, 0, nNumNonterminals * sizeof(HNode*));

#ifdef DEBUG
   clock_t clockStart = clock();
   clock_t clockLast = clockStart;
#endif

   for (i = 0; !bStopped && i < nTokens + 1; i++) {

      Column* pEi = pCol[i];
      State* pState = pEi->nextState();

#ifdef DEBUG
      printf("Column %u, token %d\n", i, pEi->getToken());
#endif

      if (!pState && !pQ0) {
         // No parse available at token i-1
         if (pnErrorToken)
            *pnErrorToken = i;
         break;
      }

      pQ = pQ0;
      pQ0 = NULL;
      HNode* pH = NULL;

      // No nonterminals seen yet
      memset(pbNtFlags, 0, nNumNonterminals * sizeof(BYTE));
      if (i == 0)
         // The productions of the root nonterminal are already in the
         // first column: don't let the predictor push them again
         pbNtFlags[~((UINT)iStartNt)] = NT_PREDICTED;

      while (pState) {

         INT iItem = pState->prodDot();

         if (iItem < 0) {
            // Nonterminal at the dot: Earley predictor
            UINT nNt = ~((UINT)iItem);
            // Don't push the same nonterminal more than once to the same column
            if (!(pbNtFlags[nNt] & NT_PREDICTED)) {
               // Push all right hand sides of this nonterminal.
               // The states created here are unique within the column:
               // each nonterminal is predicted only once in a column, and
               // all other states in it have the dot past the first item
               // (or, in the first column, belong to the root nonterminal,
               // which is not predicted again). We thus skip looking for
               // identical states, which matters since a large majority
               // of all states are created here.
               pbNtFlags[nNt] |= NT_PREDICTED;
               pPred = (*this->m_pGrammar)[iItem]->getPredictions(nPred);
               for (UINT k = 0; k < nPred; k++) {
                  // Only create a state for the production if it is of
                  // any use, i.e. if the production can begin with the
                  // current token or derive nothing
                  if (this->viable(pPred[k].nFilter, pPred[k].pProd, 0, pEi, nHandle)) {
                     State* psNew = new (pChunkHead) State(iItem, pPred[k].pProd,
                        pPred[k].iFirst, i);
                     this->pushNew(psNew, pEi, pQ);
                  }
               }
            }
            // Add elements from the H set that refer to the
            // nonterminal iItem (nt_C)
            // NOTE: this code should NOT be within the above if-statement
            // (visited in the same order as they occur in the H set itself,
            // i.e. the most recently added first)
            if (pbNtFlags[nNt] & NT_IN_H) {
               INT iNext;
               if (this->canAdvance(pState, pEi, nHandle, iNext)) {
                  HNode* ph = ppHByNt[nNt];
                  while (ph) {
                     ASSERT(ph->getNt() == iItem);
                     Node* pY = this->makeNode(pState, i, ph->getV(), ndV);
                     State* psNew = new (pChunkHead) State(pState, pY, iNext);
                     this->push(nHandle, psNew, pEi, pQ, pChunkHead, states);
                     ph = ph->getNtNext();
                  }
               }
            }
         }
         else
         if (iItem == 0) {
            // Production completed: Earley completer
            INT iNtB = pState->getNt();
            UINT nStart = pState->getStart();
            Node* pW = pState->getNode();
            if (!pW) {
               Label label(iNtB, 0, NULL, i, i);
               pW = ndV.lookupOrAdd(label);
               pW->addFamily(pState->getProd(), NULL, NULL); // Epsilon production
            }
            if (nStart == i) {
               HNode* ph = new (poolH.alloc()) HNode(iNtB, pW);
               ph->setNext(pH);
               pH = ph;
               // Also link it at the head of the list for its nonterminal
               HNode*& phNtHead = ppHByNt[~((UINT)iNtB)];
               ph->setNtNext(phNtHead);
               phNtHead = ph;
               pbNtFlags[~((UINT)iNtB)] |= NT_IN_H;
            }
            State* psNt = pCol[nStart]->getNtHead(iNtB);
            while (psNt) {
               INT iNext;
               if (this->canAdvance(psNt, pEi, nHandle, iNext)) {
                  Node* pY = this->makeNode(psNt, i, pW, ndV);
                  State* psNew = new (pChunkHead) State(psNt, pY, iNext);
                  this->push(nHandle, psNew, pEi, pQ, pChunkHead, states);
               }
               psNt = psNt->getNtNext();
            }
         }

         // Move to the next item on the agenda
         // (which may have been enlarged by the previous code)
         pState = pEi->nextState();

      }

      // Clean up the H set
      while (pH) {
         HNode* ph = pH->getNext();
         ppHByNt[~((UINT)pH->getNt())] = NULL;
         pH->~HNode();
         poolH.release(pH);
         pH = ph;
      }

      // Reset the node dictionary
      ndV.reset();
      Node* pV = NULL;

      // Done processing this column: let it clean up
      pEi->stopParse();

      // From here on, states are added to the next column
      states.clear();

      if (pQ) {
         Label label(pEi->getToken(), 0, NULL, i, i + 1);
         pV = pForest->newNode(label);
         // Open up the next column
         pCol[i + 1]->startParse(nHandle);
      }

      bOther = false;
      BOOL bScanned = pQ != NULL;

      while (pQ) {
         // Earley scanner
         State* psNext = pQ->getNext();
         ASSERT(i + 1 <= nTokens);
         INT iNext;
         if (this->canAdvance(pQ, pCol[i + 1], nHandle, iNext)) {
            Node* pY = this->makeNode(pQ, i + 1, pV, ndV);
            // Instead of throwing away the old state and creating
            // a new almost identical one, re-use the old after
            // 'incrementing' it by moving the dot one step to the right
            pQ->increment(pY, iNext);
            this->push(nHandle, pQ, pCol[i + 1], pQ0, pChunkHead, states);
         }
         else
         if (iNext < 0)
            // The state can't be moved to the next column, and is left
            // behind; without the lookahead filter, it would have been
            // moved, as it does not have a terminal at the dot
            bOther = true;
         // Otherwise, the state can't be moved to the next column,
         // and is simply left behind
         pQ = psNext;
      }

      if (bScanned && bOther && !pQ0 && pCol[i + 1]->isEmpty()) {
         // No state made it to the next column, so the parse fails.
         // Without the lookahead filter, the next column would not be
         // empty, and the failure would be found out one column later
         // (or at the end of the parse, if the next column is the last
         // one): report it accordingly.
         pCol[i + 1]->stopParse();
         bStopped = true;
         if (pnErrorToken)
            *pnErrorToken = (i + 1 >= nTokens) ? nTokens : i + 2;
         break;
      }

#ifdef DEBUG
      clock_t clockNow = clock();
      clock_t clockElapsed = clockNow - clockStart;
      clock_t clockThis = clockNow - clockLast;
      clockLast = clockNow;
      printf ("Column %u finished in %.3f sec, elapsed %.3f sec\n", i,
         ((float)clockThis) / CLOCKS_PER_SEC, ((float)clockElapsed) / CLOCKS_PER_SEC);
      fflush(stdout);
#endif
   }

#ifdef DEBUG
   clock_t clockNow = clock() - clockStart;
   printf("Parse loop finished, elapsed %.3f sec\n",
      ((float)clockNow) / CLOCKS_PER_SEC);
#endif

   ASSERT(pQ == NULL);
   ASSERT(pQ0 == NULL);

   Node* pResult = NULL;
   if (i > nTokens) {
      // Completed the token loop
      pCol[nTokens]->resetEnum();
      State* ps = pCol[nTokens]->nextState();
      while (ps && !pResult) {
         // Look through the end states until we find one that spans the
         // entire parse tree and derives the starting nonterminal
         pResult = ps->getResult(iStartNt);
         if (!pResult)
            ps = pCol[nTokens]->nextState();
      }
      if (!pResult && pnErrorToken)
         // No parse available at the last column
         *pnErrorToken = nTokens;
   }

#ifdef DEBUG
   clockNow = clock() - clockStart;
   printf("Result found, elapsed %.3f sec\n",
      ((float)clockNow) / CLOCKS_PER_SEC);
#endif

   // Cleanup
   delete[] pbNtFlags;
   delete[] ppHByNt;
   for (i = 0; i < nTokens + 1; i++)
      delete pCol[i];
   delete [] pCol;

   freeStates(pChunkHead);

   // The resulting tree lives in the forest, which is deleted when
   // the caller calls deleteForest() on the result node. If there
   // is no result, we delete the forest here.
   pForest->countNodes();
   if (!pResult)
      delete pForest;

#ifdef DEBUG
   clockNow = clock() - clockStart;
   printf("Cleanup finished, elapsed %.3f sec\n",
      ((float)clockNow) / CLOCKS_PER_SEC);
   if (pResult)
      pResult->dump(this->m_pGrammar);
#endif

   return pResult; // The caller should call Node::destroyForest() on this after using it
}

void Parser::setReducerTables(const ReducerTables* prt)
{
   // Install (or remove, if prt is NULL) the tables of the reducer.
   // The tables are copied, so the caller's buffers need not outlive
   // this call. The tables are only installed if they fit the grammar.
   delete [] this->m_rt.pnNtFlags;
   delete [] this->m_rt.pnNtScores;
   delete [] this->m_rt.pbTermFlags;
   memset(&this->m_rt, 0, sizeof(ReducerTables));
   if (!prt || !prt->pnNtFlags || !prt->pnNtScores || !prt->pbTermFlags ||
      !prt->fpPrepBonus || !prt->fpParticleBonus)
      return;
   if (prt->nNonterminals != this->m_pGrammar->getNumNonterminals() ||
      prt->nTerminals != this->m_pGrammar->getNumTerminals() + 1)
      return;
   UINT* pnNtFlags = NULL;
   INT* pnNtScores = NULL;
   BYTE* pbTermFlags = NULL;
   try {
      pnNtFlags = new UINT[prt->nNonterminals];
      pnNtScores = new INT[prt->nNonterminals];
      pbTermFlags = new BYTE[prt->nTerminals];
   }
   catch (...) {
      delete [] pnNtFlags;
      delete [] pnNtScores;
      delete [] pbTermFlags;
      throw;
   }
   memcpy(pnNtFlags, prt->pnNtFlags, prt->nNonterminals * sizeof(UINT));
   memcpy(pnNtScores, prt->pnNtScores, prt->nNonterminals * sizeof(INT));
   memcpy(pbTermFlags, prt->pbTermFlags, prt->nTerminals * sizeof(BYTE));
   this->m_rt = *prt;
   this->m_rt.pnNtFlags = pnNtFlags;
   this->m_rt.pnNtScores = pnNtScores;
   this->m_rt.pbTermFlags = pbTermFlags;
}


AllocReporter::AllocReporter(void)
{
}

AllocReporter::~AllocReporter(void)
{
}

void AllocReporter::report(void) const
{
   printf("\nMemory allocation status\n");
   printf("------------------------\n");
   printf("Nonterminals    : %6d %8d\n", Nonterminal::ac.getBalance(), Nonterminal::ac.numAllocs());
   printf("Productions     : %6d %8d\n", Production::ac.getBalance(), Production::ac.numAllocs());
   printf("Grammars        : %6d %8d\n", Grammar::ac.getBalance(), Grammar::ac.numAllocs());
   printf("Nodes           : %6d %8d\n", Node::ac.getBalance(), Node::ac.numAllocs());
   printf("States          : %6d %8d\n", State::ac.getBalance(), State::ac.numAllocs());
   printf("...discarded    : %6s %8d\n", "", nDiscardedStates.load(std::memory_order_relaxed));
   printf("StateChunks     : %6d %8d\n", acChunks.getBalance(), acChunks.numAllocs());
   printf("Columns         : %6d %8d\n", Column::ac.getBalance(), Column::ac.numAllocs());
   printf("HNodes          : %6d %8d\n", HNode::ac.getBalance(), HNode::ac.numAllocs());
   printf("NodeDict lookups: %6s %8d\n", "", NodeDict::acLookups.numAllocs());
   printf("Matching calls  : %6s %8d\n", "", Column::acMatches.numAllocs());
   printf("...thereof native: %5s %8d\n", "", Column::acNativeMatches.numAllocs());
   printf("MatchingTables  : %6d %8d\n", acMatchingTables.getBalance(), acMatchingTables.numAllocs());
   fflush(stdout); // !!! Debugging
}


// The functions below are declared extern "C" for external invocation
// of the parser (e.g. from CFFI)

// Token-terminal matching function
BOOL defaultMatcher(UINT nHandle, UINT nToken, UINT nTerminal)
{
   // printf("defaultMatcher(): token is %u, terminal is %u\n", nToken, nTerminal);
   return nToken == nTerminal;
}

Grammar* newGrammar(const CHAR* pszGrammarFile)
{
   // Note: the extern "C" entry points that allocate memory catch
   // all C++ exceptions (out-of-memory in particular) and return NULL
   // instead, since an exception must never propagate through the
   // C ABI boundary into the CFFI caller (that would be undefined
   // behavior)
   if (!pszGrammarFile)
      return NULL;
   try {
      // Read grammar from binary file
      Grammar* pGrammar = new Grammar();
      if (!pGrammar->readBinary(pszGrammarFile)) {
#ifdef DEBUG
         printf("Unable to read binary grammar file %s\n", pszGrammarFile);
#endif
         delete pGrammar;
         return NULL;
      }
      return pGrammar;
   }
   catch (...) {
      return NULL;
   }
}

void deleteGrammar(Grammar* pGrammar)
{
   if (pGrammar)
      delete pGrammar;
}

Parser* newParser(Grammar* pGrammar, MatchingFunc fpMatcher, AllocFunc fpAlloc)
{
   if (!pGrammar || !fpMatcher)
      return NULL;
   try {
      return new Parser(pGrammar, fpMatcher, fpAlloc);
   }
   catch (...) {
      // See note in newGrammar()
      return NULL;
   }
}

void deleteParser(Parser* pParser)
{
   if (pParser)
      delete pParser;
}

void setMatchingTable(Parser* pParser, const BYTE* pSpecs, UINT nSpecs,
   MeaningsFunc fpMeanings, const BYTE* pMasks, BOOL bParity)
{
   if (!pParser)
      return;
   try {
      pParser->setMatchingTable(pSpecs, nSpecs, fpMeanings, pMasks, bParity);
   }
   catch (...) {
      // See note in newGrammar(); out of memory here simply means
      // no native matching table, i.e. Python matching throughout
      pParser->setMatchingTable(NULL, 0, NULL, NULL, false);
   }
}

void setReducerTables(Parser* pParser,
   const UINT* pnNtFlags, const INT* pnNtScores, UINT nNonterminals,
   const BYTE* pbTermFlags, UINT nTerminals,
   PrepBonusFunc fpPrepBonus, ParticleBonusFunc fpParticleBonus,
   INT nPrepBonus, INT nLengthFactor)
{
   if (!pParser)
      return;
   ReducerTables rt;
   rt.nNonterminals = nNonterminals;
   rt.pnNtFlags = const_cast<UINT*>(pnNtFlags);
   rt.pnNtScores = const_cast<INT*>(pnNtScores);
   rt.nTerminals = nTerminals;
   rt.pbTermFlags = const_cast<BYTE*>(pbTermFlags);
   rt.fpPrepBonus = fpPrepBonus;
   rt.fpParticleBonus = fpParticleBonus;
   rt.nPrepBonus = nPrepBonus;
   rt.nLengthFactor = nLengthFactor;
   try {
      pParser->setReducerTables(&rt);
   }
   catch (...) {
      // See note in newGrammar(); out of memory here simply means
      // that the reducer has no tables, and reduction is left to Python
   }
}

UINT getParityMismatches(Parser* pParser)
{
   return pParser ? pParser->getParityMismatches() : 0;
}

void setLookahead(Parser* pParser, BOOL bLookahead)
{
   if (pParser)
      pParser->setLookahead(bLookahead);
}

INT nativeMatch(Parser* pParser, const BYTE* pTokenRec, UINT nTerminal)
{
   if (!pParser || !pTokenRec)
      return -1;
   BOOL b;
   if (!pParser->matchNatively(nTerminal, pTokenRec, b))
      return -1;
   return b ? 1 : 0;
}

void prefillMatchCache(Parser* pParser, BYTE* abCache, const BYTE* pTokenRec)
{
   if (!pParser || !abCache || !pTokenRec)
      return;
   try {
      pParser->prefillCache(abCache, pTokenRec);
   }
   catch (...) {
      // See note in newGrammar()
   }
}

void deleteForest(Node* pNode)
{
   Node::destroyForest(pNode);
}

void dumpForest(Node* pNode, Grammar* pGrammar)
{
   if (pNode && pGrammar)
      pNode->dump(pGrammar);
}

UINT numCombinations(Node* pNode)
{
   return pNode ? Node::numCombinations(pNode) : 0;
}

Node* earleyParse(Parser* pParser, UINT nTokens, INT iRoot, UINT nHandle, UINT* pnErrorToken)
{
   // Preparation and sanity checks
   if (!nTokens)
      return NULL;
   if (!pParser)
      return NULL;
   Grammar* pGrammar = pParser->getGrammar();
   if (!pGrammar)
      return NULL;
   if (iRoot == 0)
      // Root not specified: Run parser from the default root
      iRoot = pGrammar->getRoot();
   if (iRoot >= 0)
      return NULL; // Root must be a nonterminal (i.e. have a negative index)
   if (pnErrorToken)
      *pnErrorToken = 0;

#ifdef DEBUG
   printf("Calling pParser->parse()\n"); fflush(stdout);
#endif
   Node* pNode;
   try {
      pNode = pParser->parse(nHandle, iRoot, pnErrorToken, nTokens);
   }
   catch (...) {
      // See note in newGrammar(). If an exception (most likely
      // out-of-memory) is thrown mid-parse, the working memory of the
      // parse is not reclaimed, but that is preferable to undefined
      // behavior at the C ABI boundary.
      return NULL;
   }
#ifdef DEBUG
   printf("Back from pParser->parse()\n"); fflush(stdout);
#endif

   return pNode;
}



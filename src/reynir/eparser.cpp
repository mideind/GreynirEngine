/*

   Reynir: Natural language processing for Icelandic

   C++ Earley parser module

   Copyright (C) 2017 Miðeind ehf.

      This program is free software: you can redistribute it and/or modify
      it under the terms of the GNU General Public License as published by
      the Free Software Foundation, either version 3 of the License, or
      (at your option) any later version.
      This program is distributed in the hope that it will be useful,
      but WITHOUT ANY WARRANTY; without even the implied warranty of
      MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
      GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program.  If not, see http://www.gnu.org/licenses/.


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
   Production* m_pProd;    // Production
   UINT m_nDot;            // Dot (position in production)
   UINT m_nStart;          // Start token index
   Node* m_pw;             // Tree node
   State* m_pNext;         // Next state within column
   State* m_pNtNext;       // Next state with same Nt at prod[dot]

   static AllocCounter ac;

protected:

public:

   State(INT iNt, UINT nDot, Production* pProd, UINT nStart, Node* pw);
   State(State*, Node* pw);
   ~State(void);

   void increment(Node* pwNew);

   void setNext(State*);
   void setNtNext(State*);

   State* getNext(void) const
      { return this->m_pNext; }
   State* getNtNext(void) const
      { return this->m_pNtNext; }

   UINT getHash(void) const
      {
         return ((UINT)this->m_iNt) ^
            ((UINT)((uintptr_t)this->m_pProd) & 0xFFFFFFFF) ^
            (this->m_nDot << 7) ^ (this->m_nStart << 9) ^
            (((UINT)((uintptr_t)this->m_pw) & 0xFFFFFFFF) << 1);
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

   // Get the terminal or nonterminal at the dot
   INT prodDot(void) const
      { return (*this->m_pProd)[this->m_nDot]; }

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


class Column {

   // An Earley column
   // A Parser cointains one Column for each token in the input, plus a sentinel

friend class AllocReporter;

private:

   // The contained States are stored an array of hash bins

   static const UINT HASH_BINS = 997; /* 499; */ // Prime number

   struct HashBin {
      State* m_pHead; // The first state in this hash bin
      State* m_pTail; // The last state in this hash bin
      State* m_pEnum; // The last enumerated state in this hash bin
   };

   Parser* m_pParser; // The associated parser
   UINT m_nToken; // The input token associated with this column
   State** m_pNtStates; // States linked by the nonterminal at their prod[dot]
   MatchingFunc m_pMatchingFunc; // Pointer to the token/terminal matching function
   BYTE* m_abCache; // Matching cache, a true/false flag for every terminal in the grammar
   BOOL m_bNeedsRelease; // Does the matching cache need to be explicitly released?
   HashBin m_aHash[HASH_BINS]; // The hash bin array
   UINT m_nEnumBin; // Round robin used during enumeration of states

   static AllocCounter ac;
   static AllocCounter acMatches;

protected:

public:

   Column(Parser*, UINT nToken);
   ~Column(void);

   UINT getToken(void) const
      { return this->m_nToken; }

   void startParse(UINT nHandle);
   void stopParse(void);

   // Add a state to the column, at the end of the state list
   BOOL addState(State* p);

   void resetEnum(void);
   State* nextState(void);

   State* getNtHead(INT iNt) const;

   BOOL matches(UINT nHandle, UINT nTerminal) const;

};

class HNode {

   // Represents an element in the H set,
   // corresponding to a completed nullable
   // production of the associated nonterminal

friend class AllocReporter;

private:

   INT m_iNt;
   Node* m_pv;
   HNode* m_pNext;

   static AllocCounter ac;

protected:

public:

   HNode(INT iNt, Node* pv)
      : m_iNt(iNt), m_pv(pv)
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

};

AllocCounter HNode::ac;


class NodeDict {

   // Dictionary to map labels to node pointers

friend class AllocReporter;

private:

   struct NdEntry {
      Node* pNode;
      NdEntry* pNext;
   };

   NdEntry* m_pHead;

   static AllocCounter acLookups;

protected:

public:

   NodeDict(void);
   ~NodeDict(void);

   Node* lookupOrAdd(const Label&);

   void reset(void);

};

AllocCounter NodeDict::acLookups;


AllocCounter Nonterminal::ac;

Nonterminal::Nonterminal(const WCHAR* pwzName)
   : m_pwzName(NULL), m_pProd(NULL)
{
   Nonterminal::ac++;
   this->m_pwzName = pwzName ? ::wcsdup(pwzName) : NULL;
}

Nonterminal::~Nonterminal(void)
{
   if (this->m_pwzName)
      free(this->m_pwzName);
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
}


AllocCounter Production::ac;

Production::Production(UINT nId, UINT nPriority, UINT n, const INT* pList)
   : m_nId(nId), m_nPriority(nPriority), m_n(n), m_pList(NULL), m_pNext(NULL)
{
   Production::ac++;
   if (n > 0) {
      this->m_pList = new INT[n];
      ::memcpy((void*)this->m_pList, (void*)pList, n * sizeof(INT));
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

INT Production::operator[] (UINT nDot) const
{
   // Return the terminal or nonterminal at prod[dot]
   // or 0 if indexing past the end of the production
   return nDot < this->m_n ? this->m_pList[nDot] : 0;
}


// States are allocated in chunks, rather than individually
static const UINT CHUNK_SIZE = 2048 * sizeof(State);

struct StateChunk {

   StateChunk* m_pNext;
   UINT m_nIndex;
   BYTE m_ast[CHUNK_SIZE];

   StateChunk(StateChunk* pNext)
      : m_pNext(pNext), m_nIndex(0)
      { memset(this->m_ast, 0, CHUNK_SIZE); }

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
   ASSERT(p->m_nIndex <= CHUNK_SIZE);
   return pPlace;
}

static void freeStates(StateChunk*& pChunkHead)
{
   StateChunk* pChunk = pChunkHead;
   while (pChunk) {
      StateChunk* pNext = pChunk->m_pNext;
      delete pChunk;
      acChunks--;
      pChunk = pNext;
   }
   pChunkHead = NULL;
}

// Counter of states that are allocated and then immediately discarded
static UINT nDiscardedStates = 0;

AllocCounter State::ac;

State::State(INT iNt, UINT nDot, Production* pProd, UINT nStart, Node* pw)
   : m_iNt(iNt), m_pProd(pProd), m_nDot(nDot), m_nStart(nStart), m_pw(pw),
      m_pNext(NULL), m_pNtNext(NULL)
{
   State::ac++;
   if (pw)
      pw->addRef();
}

State::State(State* ps, Node* pw)
   : m_iNt(ps->m_iNt), m_pProd(ps->m_pProd), m_nDot(ps->m_nDot + 1),
      m_nStart(ps->m_nStart), m_pw(pw), m_pNext(NULL), m_pNtNext(NULL)
{
   // Create a new state by advancing one item forward from an existing state
   State::ac++;
   if (pw)
      pw->addRef();
}

State::~State(void)
{
   if (this->m_pw) {
      this->m_pw->delRef();
      this->m_pw = NULL;
   }
   State::ac--;
}

void State::increment(Node* pwNew)
{
   // 'Increment' the state, i.e. move the dot right by one step
   // and put in a new node pointer
   this->m_nDot++;
   this->m_pNext = NULL;
   ASSERT(this->m_pNtNext == NULL);
   if (pwNew)
      pwNew->addRef(); // Do this first, for safety
   if (this->m_pw)
      this->m_pw->delRef();
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

Column::Column(Parser* pParser, UINT nToken)
   : m_pParser(pParser),
      m_nToken(nToken),
      m_pNtStates(NULL),
      m_pMatchingFunc(pParser->getMatchingFunc()),
      m_abCache(NULL), m_bNeedsRelease(false),
      m_nEnumBin(0)
{
   Column::ac++;
   ASSERT(this->m_pMatchingFunc != NULL);
   UINT nNonterminals = pParser->getNumNonterminals();
   // Initialize array of linked lists by nonterminal at prod[dot]
   this->m_pNtStates = new State* [nNonterminals];
   memset(this->m_pNtStates, 0, nNonterminals * sizeof(State*));
   // Initialize the hash bins to zero
   memset(this->m_aHash, 0, sizeof(HashBin) * HASH_BINS);
}

Column::~Column(void)
{
   // Destroy the states still owned by the column
   for (UINT i = 0; i < HASH_BINS; i++) {
      // Clean up each hash bin in turn
      HashBin* ph = &this->m_aHash[i];
      State* q = ph->m_pHead;
      while (q) {
         State* pNext = q->getNext();
         ASSERT(pNext != NULL || q == ph->m_pTail);
         // The states are allocated via placement new, so
         // they are not deleted ordinarily - we just run their destructor
         q->~State();
         q = pNext;
      }
      ph->m_pHead = NULL;
      ph->m_pTail = NULL;
   }
   // Delete array of linked lists by nonterminal at prod[dot]
   delete [] this->m_pNtStates;
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
   if (this->m_nToken != (UINT)-1)
      this->m_abCache = this->m_pParser->allocCache(nHandle, this->m_nToken, &this->m_bNeedsRelease);
}

void Column::stopParse(void)
{
   // Called when the parser is finished processing this column
   if (this->m_abCache && this->m_bNeedsRelease)
      // The matching cache needs to be released
      this->m_pParser->releaseCache(this->m_abCache);
   this->m_abCache = NULL;
}

BOOL Column::addState(State* p)
{
   // Check to see whether an identical state is
   // already present in the hash bin
   UINT nBin = p->getHash() % HASH_BINS;
   HashBin* ph = &this->m_aHash[nBin];
   State* q = ph->m_pHead;
   while (q) {
      if ((*q) == (*p))
         // Identical state: we're done
         return false;
      q = q->getNext();
   }
   // Not already found: link into place within the hash bin
   p->setNext(NULL);
   if (!ph->m_pHead) {
      // Establish linked list with one item
      ph->m_pHead = ph->m_pTail = p;
   }
   else {
      // Link the new element at the tail
      ph->m_pTail->setNext(p);
      ph->m_pTail = p;
   }
   // Get the item at prod[dot]
   INT iItem = p->prodDot();
   if (iItem < 0) {
      // Nonterminal: add to linked list
      UINT nIndex = ~((UINT)iItem);
      State*& psHead = this->m_pNtStates[nIndex];
      p->setNtNext(psHead);
      psHead = p;
   }
   return true;
}

State* Column::nextState(void)
{
   // Start our enumeration attempt from the last bin we looked at
   UINT n = this->m_nEnumBin;
   do {
      HashBin* ph = &this->m_aHash[n];
      if (!ph->m_pEnum && ph->m_pHead) {
         // Haven't enumerated from this one before,
         // but it has an entry: return it
         ph->m_pEnum = ph->m_pHead;
         this->m_nEnumBin = n;
         return ph->m_pEnum;
      }
      // Try the next item after the one we last returned
      State* pNext = ph->m_pEnum ? ph->m_pEnum->getNext() : NULL;
      if (pNext) {
         // There is such an item: return it
         ph->m_pEnum = pNext;
         this->m_nEnumBin = n;
         return pNext;
      }
      // Can't enumerate any more from this bin: go to the next one
      n = (n + 1) % HASH_BINS;
   } while (n != this->m_nEnumBin);
   // Gone full circle: Nothing more to enumerate
   return NULL;
}

void Column::resetEnum(void)
{
   // Start a fresh enumeration
   for (UINT i = 0; i < HASH_BINS; i++)
      this->m_aHash[i].m_pEnum = NULL;
   this->m_nEnumBin = 0;
}

State* Column::getNtHead(INT iNt) const
{
   UINT nIndex = ~((UINT)iNt);
   return this->m_pNtStates[nIndex];
}

BOOL Column::matches(UINT nHandle, UINT nTerminal) const
{
   if (this->m_nToken == (UINT)-1)
      // Sentinel token in last column never matches
      return false;
   ASSERT(this->m_abCache != NULL);
   if (this->m_abCache[nTerminal] & 0x80)
      // We already have a cached result for this terminal
      return (BOOL)(this->m_abCache[nTerminal] & 0x01);
   // Not cached: obtain a result and store it in the cache
   BOOL b = this->m_pMatchingFunc(nHandle, this->m_nToken, nTerminal) != 0;
   Column::acMatches++; // Count calls to the matching function
   // Mark our cache
   this->m_abCache[nTerminal] = b ? (BYTE)0x81 : (BYTE)0x80;
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
   : m_nNonterminals(nNonterminals), m_nTerminals(nTerminals), m_iRoot(iRoot), m_nts(NULL)
{
   Grammar::ac++;
   this->m_nts = new Nonterminal*[nNonterminals];
   memset(this->m_nts, 0, nNonterminals * sizeof(Nonterminal*));
}

Grammar::Grammar(void)
   : m_nNonterminals(0), m_nTerminals(0), m_iRoot(0), m_nts(NULL)
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
   // Check the signature - should start with 'Reynir '
   if (memcmp(abSignature, "Reynir ", 7) != 0) {
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
   if (!nNonterminals)
      // No nonterminals to read: we're done
      return true;
   INT iRoot;
   if (!f.read_INT(iRoot))
      return false;
#ifdef DEBUG   
   printf("Root nonterminal index is %d\n", iRoot);
#endif
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
         if (!f.read_UINT(nId))
            return false;
         UINT nPriority;
         if (!f.read_UINT(nPriority))
            return false;
         UINT nLenProd;
         if (!f.read_UINT(nLenProd))
            return false;
         const UINT MAX_LEN_PROD = 256;
         if (nLenProd > MAX_LEN_PROD) {
            // Production too long
#ifdef DEBUG            
            printf("Production too long\n");
#endif            
            return false;
         }
         // Read the production
         INT aiProd[MAX_LEN_PROD];
         f.read(aiProd, nLenProd * sizeof(INT));
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

Node::Node(const Label& label)
   : m_label(label), m_pHead(NULL), m_nRefCount(1)
{
   Node::ac++;
}

Node::~Node(void)
{
   FamilyEntry* p = this->m_pHead;
   while (p) {
      FamilyEntry* pNext = p->pNext;
      if (p->p1)
         p->p1->delRef();
      if (p->p2)
         p->p2->delRef();
      delete p;
      p = pNext;
   }
   this->m_pHead = NULL;
   Node::ac--;
}

void Node::delRef(void)
{
   ASSERT(this->m_nRefCount > 0);
   if (!--this->m_nRefCount)
      delete this;
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
   p = new FamilyEntry();
   p->pProd = pProd;
   p->p1 = pW;
   p->p2 = pV;
   if (pW)
      pW->addRef();
   if (pV)
      pV->addRef();
   p->pNext = this->m_pHead;
   this->m_pHead = p;
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


NodeDict::NodeDict(void)
   : m_pHead(NULL)
{
}

NodeDict::~NodeDict(void)
{
   this->reset();
}

Node* NodeDict::lookupOrAdd(const Label& label)
{
   // If the label is already found in the NodeDict,
   // return the corresponding node.
   // Otherwise, create a new node, add it to the dict
   // under the label, and return it.
   NodeDict::acLookups++;
   NdEntry* p = this->m_pHead;
   while (p) {
      if (p->pNode->hasLabel(label))
         return p->pNode;
      p = p->pNext;
   }
   // Not found: add to the dict
   p = new NdEntry();
   p->pNode = new Node(label);
   p->pNext = this->m_pHead;
   this->m_pHead = p;
   return p->pNode;
}

void NodeDict::reset(void)
{
   NdEntry* p = this->m_pHead;
   while (p) {
      NdEntry* pNext = p->pNext;
      p->pNode->delRef();
      delete p;
      p = pNext;
   }
   this->m_pHead = NULL;
}


Parser::Parser(Grammar* p, MatchingFunc pMatchingFunc, AllocFunc pAllocFunc)
   : m_pGrammar(p), m_pMatchingFunc(pMatchingFunc), m_pAllocFunc(pAllocFunc)
{
   ASSERT(this->m_pGrammar != NULL);
   ASSERT(this->m_pMatchingFunc != NULL);
}

Parser::~Parser(void)
{
}

BYTE* Parser::allocCache(UINT nHandle, UINT nToken, BOOL* pbNeedRelease)
{
   // Create a fresh token/terminal matching cache
   UINT nTerminals = this->getNumTerminals();
   BYTE* abCache = NULL;
   *pbNeedRelease = false;
   if (this->m_pAllocFunc)
      // There is a cache allocation function: call it
      abCache = this->m_pAllocFunc(nHandle, nToken, nTerminals + 1);
   if (!abCache) {
      // Either no cache allocation function, or it returned NULL
      // Allocate our own buffer and initialize it to zero
      abCache = new BYTE[nTerminals + 1];
      memset(abCache, 0, (nTerminals + 1) * sizeof(BYTE));
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

void Parser::push(UINT nHandle, State* pState, Column* pE, State*& pQ, StateChunk* pChunkHead)
{
   INT iItem = pState->prodDot();
   if (iItem <= 0) {
      // Nonterminal or epsilon: add state to column
      if (pE->addState(pState))
         // State did not already exist in the column: we're done
         return;
   }
   else
   if (pE->matches(nHandle, (UINT)iItem)) {
      // Terminal matching the current token
      // Link into list whose head is pQ
      pState->setNext(pQ);
      pQ = pState;
      return;
   }
   // We did not actually push the state; discard it
   pState->~State();
   ASSERT(pChunkHead != NULL);
   ASSERT(pChunkHead->m_nIndex >= sizeof(State));
   if ((BYTE*)pState + sizeof(State) == pChunkHead->m_ast + pChunkHead->m_nIndex) {
      // The state is the most recently allocated one in the chunk
      // (a very common case): go back one location in the chunk
      pChunkHead->m_nIndex -= sizeof(State);
      nDiscardedStates++;
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

   // Prepare the the first column
   pCol[0]->startParse(nHandle);

   // Prepare the initial state
   Production* p = pRootNt->getHead();
   while (p) {
      State* ps = new (pChunkHead) State(iStartNt, 0, p, 0, NULL);
#ifdef DEBUG
      printf("For initial state, pushing production starting with nonterminal %d\n", (INT)(*p)[0]);
#endif
      this->push(nHandle, ps, pCol[0], pQ0, pChunkHead);
      p = p->getNext();
   }

   // Main parse loop
   State* pQ = NULL;
   NodeDict ndV; // Node dictionary
   UINT nNumNonterminals = this->getNumNonterminals();
   BYTE* pbSeen = new BYTE[nNumNonterminals];

#ifdef DEBUG
   clock_t clockStart = clock();
   clock_t clockLast = clockStart;
#endif

   for (i = 0; i < nTokens + 1; i++) {

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
      memset(pbSeen, 0, nNumNonterminals * sizeof(BYTE));

      while (pState) {

         INT iItem = pState->prodDot();

         if (iItem < 0) {
            // Nonterminal at the dot: Earley predictor
            // Don't push the same nonterminal more than once to the same column
            if (!pbSeen[~((UINT)iItem)]) {
               // Earley predictor
               // Push all right hand sides of this nonterminal
               pbSeen[~((UINT)iItem)] = 1;
               p = (*this->m_pGrammar)[iItem]->getHead();
               while (p) {
                  State* psNew = new (pChunkHead) State(iItem, 0, p, i, NULL);
                  this->push(nHandle, psNew, pEi, pQ, pChunkHead);
                  p = p->getNext();
               }
            }
            // Add elements from the H set that refer to the
            // nonterminal iItem (nt_C)
            // NOTE: this code should NOT be within the above if(!pbSeen[...])
            HNode* ph = pH;
            while (ph) {
               if (ph->getNt() == iItem) {
                  Node* pY = this->makeNode(pState, i, ph->getV(), ndV);
                  State* psNew = new (pChunkHead) State(pState, pY);
                  this->push(nHandle, psNew, pEi, pQ, pChunkHead);
               }
               ph = ph->getNext();
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
               HNode* ph = new HNode(iNtB, pW);
               ph->setNext(pH);
               pH = ph;
            }
            State* psNt = pCol[nStart]->getNtHead(iNtB);
            while (psNt) {
               Node* pY = this->makeNode(psNt, i, pW, ndV);
               State* psNew = new (pChunkHead) State(psNt, pY);
               this->push(nHandle, psNew, pEi, pQ, pChunkHead);
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
         delete pH;
         pH = ph;
      }

      // Reset the node dictionary
      ndV.reset();
      Node* pV = NULL;

      // Done processing this column: let it clean up
      pEi->stopParse();

      if (pQ) {
         Label label(pEi->getToken(), 0, NULL, i, i + 1);
         pV = new Node(label); // Reference is deleted below
         // Open up the next column
         pCol[i + 1]->startParse(nHandle);
      }

      while (pQ) {
         // Earley scanner
         State* psNext = pQ->getNext();
         Node* pY = this->makeNode(pQ, i + 1, pV, ndV);
         // Instead of throwing away the old state and creating
         // a new almost identical one, re-use the old after
         // 'incrementing' it by moving the dot one step to the right
         pQ->increment(pY);
         ASSERT(i + 1 <= nTokens);
         this->push(nHandle, pQ, pCol[i + 1], pQ0, pChunkHead);
         pQ = psNext;
      }

      // Clean up reference to pV created above
      if (pV)
         pV->delRef();

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
         if (pResult)
            // Save the result node from being deleted when the
            // column states are deleted
            pResult->addRef();
         else
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
   delete[] pbSeen;
   for (i = 0; i < nTokens + 1; i++)
      delete pCol[i];
   delete [] pCol;

   freeStates(pChunkHead);

#ifdef DEBUG
   clockNow = clock() - clockStart;
   printf("Cleanup finished, elapsed %.3f sec\n",
      ((float)clockNow) / CLOCKS_PER_SEC);
   if (pResult)
      pResult->dump(this->m_pGrammar);
#endif

   return pResult; // The caller should call delRef() on this after using it
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
   printf("...discarded    : %6s %8d\n", "", nDiscardedStates);
   printf("StateChunks     : %6d %8d\n", acChunks.getBalance(), acChunks.numAllocs());
   printf("Columns         : %6d %8d\n", Column::ac.getBalance(), Column::ac.numAllocs());
   printf("HNodes          : %6d %8d\n", HNode::ac.getBalance(), HNode::ac.numAllocs());
   printf("NodeDict lookups: %6s %8d\n", "", NodeDict::acLookups.numAllocs());
   printf("Matching calls  : %6s %8d\n", "", Column::acMatches.numAllocs());
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
   if (!pszGrammarFile)
      return NULL;
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

void deleteGrammar(Grammar* pGrammar)
{
   if (pGrammar)
      delete pGrammar;
}

Parser* newParser(Grammar* pGrammar, MatchingFunc fpMatcher, AllocFunc fpAlloc)
{
   if (!pGrammar || !fpMatcher)
      return NULL;
   return new Parser(pGrammar, fpMatcher, fpAlloc);
}

void deleteParser(Parser* pParser)
{
   if (pParser)
      delete pParser;
}

void deleteForest(Node* pNode)
{
   if (pNode)
      pNode->delRef();
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
   Node* pNode = pParser->parse(nHandle, iRoot, pnErrorToken, nTokens);
#ifdef DEBUG
   printf("Back from pParser->parse()\n"); fflush(stdout);
#endif

   return pNode;
}



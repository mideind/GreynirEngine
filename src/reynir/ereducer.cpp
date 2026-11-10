/*

   Greynir: Natural language processing for Icelandic

   C++ parse forest reducer module

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

   This module takes the parse forest (SPPF) that the Earley-Scott parser
   in eparser.cpp creates, and does what used to be done by walking the
   whole forest in Python:

   * It derives the 'logical' forest from the binarized one, as
     Node.from_c_node() in fastparser.py does: the interior nodes of a
     production are folded into the list of children of the completed
     nonterminal, nodes that span no tokens are dropped, and only the
     families of children with the highest priority are kept.
   * It counts the trees in the forest (Fast_Parser.num_combinations()).
   * It lists the terminals that each token is matched with in the
     forest (OptionFinder in reducer.py).
   * Given a score for each such match, it finds the highest-scoring
     tree in the forest (ParseForestReducer in reducer.py).
   * It serializes that tree, so that Python objects only need to be
     created for the nodes that are in it, typically a tenth of the
     nodes of the forest.

   The Python implementations remain, both as the reference for this
   code and as the fallback when it declines to handle a forest. The two
   must give identical results: same tree, same scores of nodes, same
   number of trees. The Python code decides the order in which things
   are done here wherever that order can affect the outcome; comments
   point out where that is the case. Running with the environment
   variable GREYNIR_REDUCER_PARITY set compares the two for every
   sentence parsed (see reducer.py).

   The parts of the reduction that need the vocabulary (does this verb
   take that preposition?) are callbacks into Python, as are the
   heuristics that score the token/terminal matches. Everything that
   depends on the grammar alone arrives as tables (see ReducerTables
   in eparser.h).

*/

#include <stdio.h>
#include <stdint.h>
#include <assert.h>

#include <new>
#include <vector>
#include <unordered_map>

#include "eparser.h"


// The maximum depth of recursion while scoring, reducing and serializing
// a forest. A forest that is deeper than this is left to the Python
// implementation, which is bound by the recursion limit of the Python
// interpreter (1000 by default) in the same way. The limit keeps the
// use of the native stack bounded, at well under half a megabyte.
static const UINT MAX_DEPTH = 1000;

// The second half of the context signature of a token (see calcToken())
static const UINT TOKEN_SIG = 0xFFFFFFFFu;


// What the reducer learns about a subtree by scoring it
// (the ResultDict of reducer.py)
struct RResult {
   INT nSc;       // The score
   UINT nSo;      // The verbs contained in the subtree (a list id, or 0)
   UINT nSl;      // The verbs that are in effect after the subtree
   UINT nPcl;     // A verb particle: the index of its token + 1, or 0
   UINT nAo;      // A token matched by a literal adverb terminal, likewise
};

// A memoized result for a node in a given context
struct RMemo {
   RResult r;
   INT iChosen;         // The winning family
   size_t nSigOffset;   // The contexts of its children (see Reducer::m_sigs)
};


// The logical forest. Its storage comes from the Forest of the parse,
// and is freed with it.

struct RChild {

   // A child within a family: a nonterminal node (pR is non-NULL), a
   // token matched by a terminal (iTerminal is > 0), or nothing at all,
   // in which case the child only holds a place in the production

   RNode* pR;
   INT iTerminal;       // The terminal that matches the token
   UINT nToken;         // The index of the token
   UINT nStart;         // The span of the child
   UINT nEnd;
   UINT nOption;        // The index of the token/terminal match
   INT nScore;          // The score of the token, as last calculated
   // The result for the token in the first context that it was scored
   // in. Few tokens are scored in more than one; the results for other
   // contexts are in a hash table (see Reducer::m_memo).
   BOOL bMemo;          // Is there a first result?
   BOOL bMemoMore;      // Are there results for other contexts?
   UINT nMemoSig;
   RResult memo;

   BOOL isNone(void) const
      { return this->pR == NULL && this->iTerminal == 0; }

};

struct RFamily {

   // A family of children of a node, i.e. one of its possible derivations

   Production* pProd;
   UINT nChildren;
   RChild* pChildren;

};

struct RNode {

   // A nonterminal node, spanning one or more tokens. It is either a
   // completed nonterminal, or an interior node: a position within a
   // production that could be reached in more than one way.

   Node* pNode;         // The corresponding node of the parser
   INT iNt;             // The index of the nonterminal (negative)
   UINT nStart;         // The span of the node
   UINT nEnd;
   BOOL bCompleted;
   UINT nFamilies;
   RFamily* pFamilies;
   UINT nSeq;           // The sequence number of the node within the forest
   UINT nState;         // 0: not seen; 1: being counted; 2: counted
   INT nScore;          // The score of the node, as last calculated
   BOOL bReduced;       // Has the node been reduced?
   INT iChosen;         // The surviving family, or -1 if they all survive
   UINT nOutId;         // The number of the node when serialized; 0 if not yet
   // The result for the node in the first context that it was scored in
   // (cf. RChild above)
   BOOL bMemo;
   BOOL bMemoMore;
   UINT nMemoA;
   UINT nMemoB;
   RMemo memo;

};


class BigNum {

   // An unsigned integer of arbitrary size: enough of one to count the
   // trees in a forest, of which there can be many more than fit in
   // 64 bits. Nearly all the numbers that occur are small, though, so a
   // value that fits in 64 bits is kept in m_lo, without any allocation
   // of memory. Larger values are in m_v: little-endian limbs of 32 bits,
   // at least three of them.

private:

   UINT64 m_lo;
   std::vector<UINT> m_v;

   BOOL isBig(void) const
      { return !this->m_v.empty(); }

   // Get the value as limbs
   void getLimbs(std::vector<UINT>& v) const
      {
         if (this->isBig()) {
            v = this->m_v;
            return;
         }
         v.clear();
         if (this->m_lo) {
            v.push_back((UINT)this->m_lo);
            if (this->m_lo >> 32)
               v.push_back((UINT)(this->m_lo >> 32));
         }
      }

   // Set the value from limbs (which are taken over)
   void setLimbs(std::vector<UINT>& v)
      {
         while (!v.empty() && v.back() == 0)
            v.pop_back();
         if (v.size() > 2) {
            this->m_v.swap(v);
            this->m_lo = 0;
            return;
         }
         this->m_lo = v.empty() ? 0 :
            ((UINT64)v[0] | (v.size() > 1 ? ((UINT64)v[1] << 32) : 0));
         this->m_v.clear();
      }

public:

   BigNum(void)
      : m_lo(0)
      { }

   BOOL isZero(void) const
      { return this->m_lo == 0 && !this->isBig(); }
   BOOL isOne(void) const
      { return this->m_lo == 1 && !this->isBig(); }

   void set(UINT n)
      {
         this->m_lo = n;
         this->m_v.clear();
      }

   void swap(BigNum& other)
      {
         UINT64 n = this->m_lo;
         this->m_lo = other.m_lo;
         other.m_lo = n;
         this->m_v.swap(other.m_v);
      }

   // Add another number; scratch is working storage
   void add(const BigNum& other, BigNum& scratch)
      {
         if (!this->isBig() && !other.isBig()) {
            UINT64 n = this->m_lo + other.m_lo;
            if (n >= this->m_lo) {
               // No overflow
               this->m_lo = n;
               return;
            }
         }
         std::vector<UINT> a;
         std::vector<UINT>& o = scratch.m_v;
         this->getLimbs(a);
         other.getLimbs(o);
         if (a.size() < o.size())
            a.resize(o.size(), 0);
         UINT64 nCarry = 0;
         for (size_t i = 0; i < a.size(); i++) {
            UINT64 n = (UINT64)a[i] + (i < o.size() ? o[i] : 0) + nCarry;
            a[i] = (UINT)n;
            nCarry = n >> 32;
         }
         if (nCarry)
            a.push_back((UINT)nCarry);
         o.clear();
         this->setLimbs(a);
      }

   // Multiply by another number, which must be a different object;
   // scratch is working storage
   void mul(const BigNum& other, BigNum& scratch)
      {
         if (other.isOne())
            return;
         if (this->isZero() || other.isZero()) {
            this->set(0);
            return;
         }
         if (!this->isBig() && !other.isBig()) {
            UINT64 a = this->m_lo;
            UINT64 b = other.m_lo;
            if (((a | b) >> 32) == 0 || a <= ~((UINT64)0) / b) {
               // The product fits in 64 bits
               this->m_lo = a * b;
               return;
            }
         }
         std::vector<UINT> a;
         std::vector<UINT>& o = scratch.m_v;
         this->getLimbs(a);
         other.getLimbs(o);
         std::vector<UINT> r(a.size() + o.size(), 0);
         for (size_t i = 0; i < a.size(); i++) {
            UINT64 nCarry = 0;
            UINT64 n1 = a[i];
            for (size_t j = 0; j < o.size(); j++) {
               UINT64 n = n1 * o[j] + r[i + j] + nCarry;
               r[i + j] = (UINT)n;
               nCarry = n >> 32;
            }
            r[i + o.size()] = (UINT)nCarry;
         }
         o.clear();
         this->setLimbs(r);
      }

   // The number as little-endian bytes
   size_t numBytes(void) const
      { return this->isBig() ? this->m_v.size() * 4 : 8; }
   void getBytes(BYTE* pb) const
      {
         if (!this->isBig()) {
            for (UINT i = 0; i < 8; i++)
               *pb++ = (BYTE)(this->m_lo >> (8 * i));
            return;
         }
         for (size_t i = 0; i < this->m_v.size(); i++) {
            UINT n = this->m_v[i];
            *pb++ = (BYTE)n;
            *pb++ = (BYTE)(n >> 8);
            *pb++ = (BYTE)(n >> 16);
            *pb++ = (BYTE)(n >> 24);
         }
      }

};


class Reducer {

   // The working state of one of the two steps of a reduction.
   // An instance only lives for the duration of a call to
   // Reducer::start() or Reducer::finish(), on the stack.

private:

   // A family while its node is being built
   struct TmpFamily {
      Production* pProd;
      size_t nOffset;      // The first child within m_tmpChildren
      UINT nCount;
   };

   // The state of a node while the trees below it are being counted
   struct Frame {
      RNode* pR;
      UINT iFamily;
      UINT iChild;
      BigNum sum;          // The number of trees in the families done so far
      BigNum prod;         // The number of trees in the current family, so far
      Frame(RNode* p)
         : pR(p), iFamily(0), iChild(0)
         { this->prod.set(1); }
   };

   // A list of verbs: a slice of m_elems
   struct ListRec {
      UINT nOffset;
      UINT nLen;
   };

   // The key of the memoization table: a node or a token within a
   // family, and the context that it was scored in
   struct MemoKey {
      const void* p;
      UINT a;
      UINT b;
      bool operator==(const MemoKey& o) const
         { return this->p == o.p && this->a == o.a && this->b == o.b; }
   };
   struct MemoHash {
      size_t operator()(const MemoKey& k) const
         {
            UINT64 h = (UINT64)(uintptr_t)k.p;
            h = (h ^ (h >> 29)) * 0x9E3779B97F4A7C15ull;
            h = (h ^ k.a) * 0x9E3779B97F4A7C15ull;
            h = (h ^ k.b) * 0x9E3779B97F4A7C15ull;
            return (size_t)(h ^ (h >> 32));
         }
   };
   struct BonusKey {
      UINT64 nPrep;
      UINT64 nVerb;
      bool operator==(const BonusKey& o) const
         { return this->nPrep == o.nPrep && this->nVerb == o.nVerb; }
   };
   struct BonusHash {
      size_t operator()(const BonusKey& k) const
         {
            UINT64 h = k.nPrep * 0x9E3779B97F4A7C15ull;
            h = (h ^ (h >> 31) ^ k.nVerb) * 0x9E3779B97F4A7C15ull;
            return (size_t)(h ^ (h >> 32));
         }
   };

   typedef std::unordered_map<MemoKey, RMemo, MemoHash> Memo;

   Parser* m_pParser;
   Forest* m_pForest;
   BOOL m_bFail;           // Give up: the forest can't be handled here
   UINT m_nDepth;          // The current depth of recursion

   // Building the logical forest
   UINT m_nNodes;
   std::vector<RNode*> m_work;
   std::vector<TmpFamily> m_tmpFamilies;
   std::vector<Node*> m_tmpChildren;
   std::vector<Node*> m_stack;

   // Scoring
   const ReducerTables* m_prt;
   const INT* m_pnScores;
   UINT m_nHandle;
   std::vector<UINT> m_prepBonus;      // The stack of preposition bonus verbs
   std::vector<UINT> m_currentVerb;    // The stack of current verbs
   std::vector<UINT64> m_elems;        // The verbs of all lists of verbs
   std::vector<ListRec> m_lists;       // The lists of verbs; entry 0 is 'none'
   std::unordered_multimap<UINT64, UINT> m_listIndex;
   std::vector<UINT64> m_tmpList;
   Memo m_memo;
   std::vector<RResult> m_accs;         // Results of the families being scored
   std::vector<UINT> m_tmpSigs;        // Contexts of their children
   std::vector<size_t> m_tmpOffsets;
   std::vector<UINT> m_sigs;           // Contexts of the children of winners
   std::unordered_map<BonusKey, INT, BonusHash> m_bonusCache;
   std::vector<UINT> m_tmpVerbs;

   // Serializing
   std::vector<INT> m_out;
   std::vector<INT> m_ids;
   UINT m_nOutIds;

   void* alloc(size_t nBytes)
      { return this->m_pForest->alloc(nBytes); }

   RNode* newRNode(Node*);
   void pushPair(Node* p1, Node* p2);
   void buildFamilies(RNode*);
   BOOL walk(Reduction*);
   Reduction* analyze(Node* pRoot);

   UINT internList(const UINT64* pElems, UINT nLen);
   UINT concat(UINT nList1, UINT nList2);
   UINT ntFlags(const RNode* pR) const
      {
         return pR->bCompleted ? this->m_prt->pnNtFlags[~((UINT)pR->iNt)] : 0;
      }
   void contextSig(const RNode*, UINT& a, UINT& b) const;
   INT prepBonus(const RChild&, UINT64 nVerb);
   INT particleBonus(UINT nParticleToken, UINT nVerbs);
   void addChild(RResult& acc, const RResult& r, UINT nFlags);
   RResult calcToken(RChild&, UINT nPrepBonus);
   RResult calc(RNode*, UINT a, UINT b);
   const RMemo* findMemo(const RNode*, UINT a, UINT b) const;
   void addMemo(RNode*, UINT a, UINT b, const RMemo&);
   void apply(RNode*, UINT a, UINT b);

   INT emitToken(const RChild&);
   INT emit(RNode*);

   BOOL run(Reduction*, const INT* pnScores, UINT nHandle);

   Reducer(Parser* pParser, Forest* pForest)
      : m_pParser(pParser), m_pForest(pForest), m_bFail(false), m_nDepth(0),
         m_nNodes(0), m_prt(NULL), m_pnScores(NULL), m_nHandle(0), m_nOutIds(0)
      { }

public:

   static Reduction* start(Parser*, Node* pRoot);
   static BOOL finish(Reduction*, const INT* pnScores, UINT nHandle);

};


// Step 1: the logical forest, its number of trees and its
// token/terminal matches

RNode* Reducer::newRNode(Node* pNode)
{
   // Create the logical node that corresponds to a nonterminal node
   // of the parser, and schedule its families for building
   RNode* pR = (RNode*)this->alloc(sizeof(RNode));
   memset(pR, 0, sizeof(RNode));
   const Label& lb = pNode->m_label;
   pR->pNode = pNode;
   pR->iNt = lb.m_iNt;
   pR->nStart = lb.m_nI;
   pR->nEnd = lb.m_nJ;
   pR->bCompleted = lb.m_pProd == NULL;
   pR->nSeq = this->m_nNodes++;
   pR->iChosen = -1;
   pNode->m_pR = pR;
   this->m_work.push_back(pR);
   return pR;
}

void Reducer::pushPair(Node* p1, Node* p2)
{
   // Push the two children of a family of the parser onto the stack of
   // nodes waiting to be placed in a family, so that they are popped
   // in left-to-right order
   if (p1 && p2) {
      this->m_stack.push_back(p2);
      this->m_stack.push_back(p1);
   }
   else
      this->m_stack.push_back(p2 ? p2 : p1);
}

void Reducer::buildFamilies(RNode* pR)
{
   // Build the families of children of a node. This follows
   // Node.from_c_node() and Node._add_family() in fastparser.py.
   Node* pNode = pR->pNode;
   INT iNt = pR->iNt;
   std::vector<TmpFamily>& families = this->m_tmpFamilies;
   std::vector<Node*>& children = this->m_tmpChildren;
   families.clear();
   children.clear();
   UINT nHighest = 0;

   for (Node::FamilyEntry* pfe = pNode->m_pHead; pfe; pfe = pfe->pNext) {
      // Only the families with the highest priority (i.e. the lowest
      // priority number) survive
      UINT nPriority = pfe->pProd->getPriority();
      if (!families.empty()) {
         if (nPriority > nHighest)
            continue;
         if (nPriority < nHighest) {
            families.clear();
            children.clear();
         }
      }
      nHighest = nPriority;
      // Fold the interior nodes of the production into the list of
      // children of this node: an interior node holds the children that
      // precede the last one. This can continue while the interior nodes
      // are unambiguous, i.e. have a single family of children.
      size_t nOffset = children.size();
      this->m_stack.clear();
      this->pushPair(pfe->p1, pfe->p2);
      while (!this->m_stack.empty()) {
         Node* p = this->m_stack.back();
         this->m_stack.pop_back();
         if (p && p->m_label.m_iNt == iNt && p->m_label.m_pProd != NULL && p->m_pHead) {
            // An interior node of the same nonterminal
            if (p->m_pHead->pNext == NULL)
               // Unambiguous: replace it with its children
               this->pushPair(p->m_pHead->p1, p->m_pHead->p2);
            else {
               // Ambiguous: it stays as a node in its own right, with its
               // own families. It stands for all the items of the
               // production up to its dot, so it is preceded and followed
               // by placeholders, to keep the list of children
               // aligned with the items of the production.
               UINT nDot = p->m_label.m_nDot;
               for (UINT i = 2; i < nDot; i++)
                  children.push_back(NULL);
               children.push_back(p);
               children.push_back(NULL);
            }
         }
         else
            // A token, a completed nonterminal or nothing
            children.push_back(p);
      }
      TmpFamily tf;
      tf.pProd = pfe->pProd;
      tf.nOffset = nOffset;
      tf.nCount = (UINT)(children.size() - nOffset);
      families.push_back(tf);
   }

   UINT nFamilies = (UINT)families.size();
   pR->nFamilies = nFamilies;
   if (!nFamilies)
      return;
   pR->pFamilies = (RFamily*)this->alloc(nFamilies * sizeof(RFamily));
   UINT nTerminals = this->m_pParser->getNumTerminals();

   for (UINT i = 0; i < nFamilies; i++) {
      const TmpFamily& tf = families[i];
      RFamily& f = pR->pFamilies[i];
      f.pProd = tf.pProd;
      f.nChildren = tf.nCount;
      f.pChildren = NULL;
      if (!tf.nCount)
         continue;
      f.pChildren = (RChild*)this->alloc(tf.nCount * sizeof(RChild));
      memset(f.pChildren, 0, tf.nCount * sizeof(RChild));
      for (UINT j = 0; j < tf.nCount; j++) {
         // Note: creating a node below adds to m_work, but
         // leaves the vectors that we are iterating over alone
         Node* p = children[tf.nOffset + j];
         if (!p)
            continue;
         const Label& lb = p->m_label;
         if (lb.m_nI >= lb.m_nJ)
            // A node that spans no tokens only holds a place
            continue;
         RChild& c = f.pChildren[j];
         c.nStart = lb.m_nI;
         c.nEnd = lb.m_nJ;
         if (lb.m_iNt >= 0) {
            // A token: the terminal that it matches is the
            // corresponding item of the production
            INT iTerminal = j < tf.pProd->getLength() ? (*tf.pProd)[j] : 0;
            if (iTerminal <= 0 || (UINT)iTerminal > nTerminals) {
               // Should not happen
               this->m_bFail = true;
               return;
            }
            c.iTerminal = iTerminal;
            c.nToken = (UINT)lb.m_iNt;
         }
         else
            c.pR = p->m_pR ? p->m_pR : this->newRNode(p);
      }
   }
}

BOOL Reducer::walk(Reduction* pRed)
{
   // Walk the forest, counting the trees in it as
   // Fast_Parser.num_combinations() does, and collecting the distinct
   // token/terminal matches in the order in which the OptionFinder class
   // of reducer.py comes across them: depth-first, each node once.
   std::vector<Frame> stack;
   std::vector<BigNum> comb(this->m_nNodes);
   std::vector<INT> options;
   // The options of each token are in a linked list: the first option
   // of the token with a given index, and the next option of each option
   const UINT NONE = (UINT)-1;
   std::vector<UINT> firstOption(pRed->nEnd, NONE);
   std::vector<UINT> nextOption;
   BigNum scratch;

   RNode* pRoot = pRed->pRoot;
   pRoot->nState = 1;
   stack.push_back(Frame(pRoot));

   while (!stack.empty()) {
      Frame& f = stack.back();
      RNode* p = f.pR;
      if (f.iFamily >= p->nFamilies) {
         // All families done: the sum is the number of trees below the node
         if (f.sum.isZero())
            f.sum.set(1);
         BigNum& result = comb[p->nSeq];
         result.swap(f.sum);
         p->nState = 2;
         stack.pop_back();
         if (!stack.empty())
            stack.back().prod.mul(result, scratch);
         continue;
      }
      const RFamily& family = p->pFamilies[f.iFamily];
      if (f.iChild >= family.nChildren) {
         // The family is done
         f.sum.add(f.prod, scratch);
         f.prod.set(1);
         f.iFamily++;
         f.iChild = 0;
         continue;
      }
      RChild& c = family.pChildren[f.iChild++];
      if (c.iTerminal) {
         // A token: note its terminal, if it has not been seen before
         // (a token only matches a handful of terminals in a forest)
         if (c.nStart >= firstOption.size())
            firstOption.resize(c.nStart + 1, NONE);
         UINT nOption = firstOption[c.nStart];
         while (nOption != NONE && options[2 * nOption + 1] != c.iTerminal)
            nOption = nextOption[nOption];
         if (nOption == NONE) {
            nOption = (UINT)(options.size() / 2);
            options.push_back((INT)c.nStart);
            options.push_back(c.iTerminal);
            nextOption.push_back(firstOption[c.nStart]);
            firstOption[c.nStart] = nOption;
         }
         c.nOption = nOption;
      }
      else
      if (c.pR) {
         RNode* q = c.pR;
         if (q->nState == 2)
            // Already counted
            f.prod.mul(comb[q->nSeq], scratch);
         else
         if (q->nState == 1)
            // The forest has a cycle: leave it alone
            return false;
         else {
            q->nState = 1;
            stack.push_back(Frame(q)); // Note: this invalidates f
         }
      }
   }

   // Hand the results over, in storage that lives as long as the forest
   const BigNum& total = comb[pRoot->nSeq];
   UINT nBytes = (UINT)total.numBytes();
   BYTE* pb = (BYTE*)this->alloc(nBytes ? nBytes : 1);
   total.getBytes(pb);
   pRed->nCombBytes = nBytes;
   pRed->pbComb = pb;
   UINT nInts = (UINT)options.size();
   INT* pn = (INT*)this->alloc((nInts ? nInts : 1) * sizeof(INT));
   if (nInts)
      memcpy(pn, &options[0], nInts * sizeof(INT));
   pRed->nOptions = nInts / 2;
   pRed->pnOptions = pn;
   return true;
}

Reduction* Reducer::analyze(Node* pRoot)
{
   Reduction* pRed = (Reduction*)this->alloc(sizeof(Reduction));
   memset(pRed, 0, sizeof(Reduction));
   pRed->pParser = this->m_pParser;
   pRed->pForest = this->m_pForest;
   // Build the logical forest, starting with the root. Nodes are built
   // as they are reached; the order does not matter.
   RNode* pR = this->newRNode(pRoot);
   pRed->pRoot = pR;
   pRed->nStart = pR->nStart;
   pRed->nEnd = pR->nEnd;
   while (!this->m_work.empty()) {
      RNode* p = this->m_work.back();
      this->m_work.pop_back();
      this->buildFamilies(p);
      if (this->m_bFail)
         return NULL;
   }
   if (!this->walk(pRed))
      return NULL;
   return pRed;
}

Reduction* Reducer::start(Parser* pParser, Node* pRoot)
{
   if (!pParser || !pRoot)
      return NULL;
   const Label& lb = pRoot->m_label;
   if (lb.m_iNt >= 0 || lb.m_nI >= lb.m_nJ)
      // The root must be a nonterminal that spans tokens
      return NULL;
   if (pRoot->m_pR)
      // The forest has already been analyzed
      return NULL;
   Reducer reducer(pParser, pRoot->m_pForest);
   return reducer.analyze(pRoot);
}


// Step 2: scoring and reduction. This follows ParseForestReducer.go()
// in reducer.py, where the algorithm is explained.

UINT Reducer::internList(const UINT64* pElems, UINT nLen)
{
   // Return the id of a list of verbs. Lists with the same content
   // have the same id, so that an id can stand for the content of a list
   // in a context signature. A verb is a terminal index and a token index.
   UINT64 h = 0xCBF29CE484222325ull ^ nLen;
   for (UINT i = 0; i < nLen; i++)
      h = (h ^ pElems[i] ^ (pElems[i] >> 32)) * 0x100000001B3ull;
   typedef std::unordered_multimap<UINT64, UINT>::iterator Iter;
   std::pair<Iter, Iter> range = this->m_listIndex.equal_range(h);
   for (Iter it = range.first; it != range.second; ++it) {
      const ListRec& rec = this->m_lists[it->second];
      if (rec.nLen == nLen &&
         (!nLen || memcmp(&this->m_elems[rec.nOffset], pElems, nLen * sizeof(UINT64)) == 0))
         return it->second;
   }
   ListRec rec;
   rec.nOffset = (UINT)this->m_elems.size();
   rec.nLen = nLen;
   this->m_elems.insert(this->m_elems.end(), pElems, pElems + nLen);
   UINT nId = (UINT)this->m_lists.size();
   this->m_lists.push_back(rec);
   this->m_listIndex.insert(std::make_pair(h, nId));
   return nId;
}

UINT Reducer::concat(UINT nList1, UINT nList2)
{
   // Return the list that consists of the verbs of two lists
   const ListRec r1 = this->m_lists[nList1];
   const ListRec r2 = this->m_lists[nList2];
   std::vector<UINT64>& tmp = this->m_tmpList;
   tmp.clear();
   tmp.insert(tmp.end(),
      this->m_elems.begin() + r1.nOffset, this->m_elems.begin() + r1.nOffset + r1.nLen);
   tmp.insert(tmp.end(),
      this->m_elems.begin() + r2.nOffset, this->m_elems.begin() + r2.nOffset + r2.nLen);
   return this->internList(tmp.empty() ? NULL : &tmp[0], (UINT)tmp.size());
}

void Reducer::contextSig(const RNode* pR, UINT& a, UINT& b) const
{
   // The part of the state of the reducer that the score of a subtree
   // can depend on: the preposition bonus verbs and the current verb
   if (pR->bCompleted) {
      if (this->ntFlags(pR) & (RN_BEGIN_PREP_SCOPE | RN_NOUN_PHRASE)) {
         // The node resets both on entry
         a = b = 0;
         return;
      }
      if (pR->nFamilies == 0 ||
         (pR->nFamilies == 1 && pR->pFamilies[0].nChildren == 0)) {
         // An empty node
         a = b = 0;
         return;
      }
   }
   a = this->m_prepBonus.back();
   b = this->m_currentVerb.back();
}

INT Reducer::prepBonus(const RChild& c, UINT64 nVerb)
{
   // The bonus for a preposition in the context of a verb
   BonusKey key;
   key.nPrep = ((UINT64)(UINT)c.iTerminal << 32) | c.nToken;
   key.nVerb = nVerb;
   std::unordered_map<BonusKey, INT, BonusHash>::iterator it = this->m_bonusCache.find(key);
   if (it != this->m_bonusCache.end())
      return it->second;
   INT nBonus = this->m_prt->fpPrepBonus(this->m_nHandle,
      (UINT)c.iTerminal, c.nToken, (UINT)(nVerb >> 32), (UINT)nVerb);
   this->m_bonusCache[key] = nBonus;
   return nBonus;
}

INT Reducer::particleBonus(UINT nParticleToken, UINT nVerbs)
{
   // The bonus for a verb particle in the context of a list of verbs
   const ListRec rec = this->m_lists[nVerbs];
   std::vector<UINT>& tmp = this->m_tmpVerbs;
   tmp.clear();
   for (UINT i = 0; i < rec.nLen; i++) {
      UINT64 nVerb = this->m_elems[rec.nOffset + i];
      tmp.push_back((UINT)(nVerb >> 32));
      tmp.push_back((UINT)nVerb);
   }
   return this->m_prt->fpParticleBonus(this->m_nHandle, nParticleToken,
      tmp.empty() ? NULL : &tmp[0], rec.nLen);
}

void Reducer::addChild(RResult& acc, const RResult& r, UINT nFlags)
{
   // Add the result of a child to the result of its family
   // (_ReductionScope.add_child() in reducer.py)
   acc.nSc += r.nSc;
   if (r.nAo && (nFlags & RN_VERB_PARTICLE))
      // A verb particle: note it, so that the enclosing
      // verb phrase can check it against the verb
      acc.nPcl = r.nAo;
   else
   if (r.nPcl)
      acc.nPcl = r.nPcl;
   // Carry information about contained verbs up the tree
   if (r.nSo)
      acc.nSo = acc.nSo ? this->concat(acc.nSo, r.nSo) : r.nSo;
   if (r.nSl) {
      acc.nSl = acc.nSl ? this->concat(acc.nSl, r.nSl) : r.nSl;
      this->m_currentVerb.back() = r.nSl;
   }
}

const RMemo* Reducer::findMemo(const RNode* pR, UINT a, UINT b) const
{
   // Find the memoized result for a node in a context, if there is one
   if (!pR->bMemo)
      return NULL;
   if (pR->nMemoA == a && pR->nMemoB == b)
      return &pR->memo;
   if (!pR->bMemoMore)
      return NULL;
   MemoKey key = { (const void*)pR, a, b };
   Memo::const_iterator it = this->m_memo.find(key);
   return it == this->m_memo.end() ? NULL : &it->second;
}

void Reducer::addMemo(RNode* pR, UINT a, UINT b, const RMemo& memo)
{
   // Memoize the result for a node in a context: in the node itself, if
   // this is the first context that it is scored in; otherwise in the
   // hash table
   if (!pR->bMemo) {
      pR->bMemo = true;
      pR->nMemoA = a;
      pR->nMemoB = b;
      pR->memo = memo;
      return;
   }
   pR->bMemoMore = true;
   MemoKey key = { (const void*)pR, a, b };
   this->m_memo.insert(std::make_pair(key, memo));
}

RResult Reducer::calcToken(RChild& c, UINT nPrepBonus)
{
   // The result for a token matched by a terminal, in the context
   // of the given preposition bonus verbs
   // (ParseForestReducer.visit_token() in reducer.py)
   MemoKey key = { (const void*)&c, nPrepBonus, TOKEN_SIG };
   if (c.bMemo) {
      if (c.nMemoSig == nPrepBonus)
         return c.memo;
      if (c.bMemoMore) {
         Memo::iterator it = this->m_memo.find(key);
         if (it != this->m_memo.end())
            return it->second.r;
      }
   }
   RMemo e;
   memset(&e, 0, sizeof(e));
   UINT nFlags = this->m_prt->pbTermFlags[c.iTerminal];
   INT nSc = this->m_pnScores[c.nOption];
   if (nFlags & RT_AO_LITERAL)
      e.r.nAo = c.nToken + 1;
   if (nFlags & RT_FS) {
      if (nPrepBonus) {
         // Within a preposition bonus zone: give the
         // highest bonus that any of the enclosing verbs yields
         const ListRec rec = this->m_lists[nPrepBonus];
         BOOL bAny = false;
         INT nBest = 0;
         for (UINT i = 0; i < rec.nLen; i++) {
            INT nBonus = this->prepBonus(c, this->m_elems[rec.nOffset + i]);
            if (!bAny || nBonus > nBest)
               nBest = nBonus;
            bAny = true;
         }
         if (bAny)
            nSc += nBest;
      }
   }
   else
   if (nFlags & RT_SO) {
      // A verb: pick it up
      UINT64 nVerb = ((UINT64)(UINT)c.iTerminal << 32) | c.nToken;
      e.r.nSo = this->internList(&nVerb, 1);
   }
   e.r.nSc = nSc;
   // The score of a node is the one from the context that was
   // first seen last, as in the Python implementation
   c.nScore = nSc;
   if (!c.bMemo) {
      c.bMemo = true;
      c.nMemoSig = nPrepBonus;
      c.memo = e.r;
   }
   else {
      c.bMemoMore = true;
      this->m_memo.insert(std::make_pair(key, e));
   }
   return e.r;
}

RResult Reducer::calc(RNode* pR, UINT a, UINT b)
{
   // The result for the subtree below a node, in a given context:
   // score all families of the node, and note which one wins.
   // The forest is not changed.
   const RMemo* pMemo = this->findMemo(pR, a, b);
   if (pMemo)
      return pMemo->r;
   RMemo e;
   memset(&e, 0, sizeof(e));
   if (this->m_bFail)
      return e.r;
   UINT nFamilies = pR->nFamilies;

   if (nFamilies) {

      if (++this->m_nDepth > MAX_DEPTH) {
         this->m_bFail = true;
         this->m_nDepth--;
         return e.r;
      }

      // Enter the scope of the node (_ReductionScope.__init__())
      UINT nFlags = this->ntFlags(pR);
      UINT nVerb = this->m_currentVerb.back();
      BOOL bPushed = false;
      if (nFlags & RN_ENABLE_PREP_BONUS) {
         this->m_prepBonus.push_back(nVerb);
         bPushed = true;
      }
      else
      if (nFlags & (RN_BEGIN_PREP_SCOPE | RN_NOUN_PHRASE)) {
         this->m_prepBonus.push_back(0);
         bPushed = true;
         nVerb = 0;
      }
      this->m_currentVerb.push_back(nVerb);

      // Score the families. The vectors used here are shared by
      // all levels of the recursion, each level working at their end,
      // so they are indexed, not pointed into.
      size_t nAccBase = this->m_accs.size();
      size_t nSigBase = this->m_tmpSigs.size();
      size_t nOffsetBase = this->m_tmpOffsets.size();
      this->m_accs.resize(nAccBase + nFamilies);

      for (UINT i = 0; i < nFamilies; i++) {
         const RFamily& family = pR->pFamilies[i];
         // Productions with higher priorities (lower
         // priority numbers) get a starting bonus
         RResult acc = { -10 * (INT)family.pProd->getPriority(), 0, 0, 0, 0 };
         this->m_currentVerb.back() = nVerb;
         this->m_tmpOffsets.push_back(this->m_tmpSigs.size());
         for (UINT j = 0; j < family.nChildren; j++) {
            RChild& c = family.pChildren[j];
            if (c.iTerminal) {
               UINT nSig = this->m_prepBonus.back();
               this->m_tmpSigs.push_back(nSig);
               this->m_tmpSigs.push_back(TOKEN_SIG);
               this->addChild(acc, this->calcToken(c, nSig), nFlags);
            }
            else
            if (c.pR) {
               UINT ca, cb;
               this->contextSig(c.pR, ca, cb);
               this->m_tmpSigs.push_back(ca);
               this->m_tmpSigs.push_back(cb);
               this->addChild(acc, this->calc(c.pR, ca, cb), nFlags);
            }
         }
         this->m_accs[nAccBase + i] = acc;
      }
      this->m_tmpOffsets.push_back(this->m_tmpSigs.size());

      // Find the winner (_ReductionScope.process())
      if (nFlags & RN_APPLY_PARTICLE_BONUS) {
         // Adjust the score of each family that contains a verb
         // particle by whether its verbs take that particle
         for (UINT i = 0; i < nFamilies; i++) {
            UINT nPcl = this->m_accs[nAccBase + i].nPcl;
            if (nPcl) {
               INT nBonus = this->particleBonus(nPcl - 1, this->m_accs[nAccBase + i].nSo);
               this->m_accs[nAccBase + i].nPcl = 0;
               this->m_accs[nAccBase + i].nSc += nBonus;
            }
         }
      }
      UINT iBest = 0;
      for (UINT i = 1; i < nFamilies; i++) {
         // The highest score wins. Ties are broken by the content of the
         // families: the production that comes first in the grammar wins,
         // then the family whose children have the higher spans (taken in
         // order, as a sequence of start and end positions); only then
         // does the order of the families decide, the first one winning.
         const RResult& r = this->m_accs[nAccBase + i];
         const RResult& rBest = this->m_accs[nAccBase + iBest];
         if (r.nSc != rBest.nSc) {
            if (r.nSc > rBest.nSc)
               iBest = i;
            continue;
         }
         const RFamily& f = pR->pFamilies[i];
         const RFamily& fBest = pR->pFamilies[iBest];
         if (f.pProd->getId() != fBest.pProd->getId()) {
            if (f.pProd->getId() < fBest.pProd->getId())
               iBest = i;
            continue;
         }
         UINT j = 0, k = 0;
         for (;;) {
            while (j < f.nChildren && f.pChildren[j].isNone())
               j++;
            while (k < fBest.nChildren && fBest.pChildren[k].isNone())
               k++;
            if (j >= f.nChildren || k >= fBest.nChildren) {
               // The longer sequence is the higher one
               if (j < f.nChildren)
                  iBest = i;
               break;
            }
            const RChild& c = f.pChildren[j++];
            const RChild& cBest = fBest.pChildren[k++];
            if (c.nStart != cBest.nStart) {
               if (c.nStart > cBest.nStart)
                  iBest = i;
               break;
            }
            if (c.nEnd != cBest.nEnd) {
               if (c.nEnd > cBest.nEnd)
                  iBest = i;
               break;
            }
         }
      }

      RResult r = this->m_accs[nAccBase + iBest];
      if (pR->bCompleted) {
         // The score adjustment of the nonterminal ($score() in the grammar)
         r.nSc += this->m_prt->pnNtScores[~((UINT)pR->iNt)];
         if (nFlags & RN_APPLY_LENGTH_BONUS)
            // A bonus that depends on the number of tokens spanned
            r.nSc += ((INT)(pR->nEnd - pR->nStart) - 1) * this->m_prt->nLengthFactor;
         if ((nFlags & RN_APPLY_PREP_BONUS) && this->m_prepBonus.back() != 0)
            // A nonterminal that we like to see in a verb context
            r.nSc += this->m_prt->nPrepBonus;
         if ((nFlags & RN_PICK_UP_VERB) && r.nSo)
            r.nSl = r.nSo;
         if (nFlags & (RN_BEGIN_PREP_SCOPE | RN_PURGE_VERB))
            // Forget the contained verbs
            r.nSo = r.nSl = r.nPcl = 0;
      }
      e.r = r;
      e.iChosen = (INT)iBest;

      // Keep the contexts in which the children were scored: those of
      // the winning family - or of all families, if they all survive
      size_t nFrom, nTo;
      if (nFlags & RN_NO_REDUCE) {
         nFrom = nSigBase;
         nTo = this->m_tmpSigs.size();
      }
      else {
         nFrom = this->m_tmpOffsets[nOffsetBase + iBest];
         nTo = this->m_tmpOffsets[nOffsetBase + iBest + 1];
      }
      e.nSigOffset = this->m_sigs.size();
      this->m_sigs.insert(this->m_sigs.end(),
         this->m_tmpSigs.begin() + nFrom, this->m_tmpSigs.begin() + nTo);

      // Leave the scope
      this->m_accs.resize(nAccBase);
      this->m_tmpSigs.resize(nSigBase);
      this->m_tmpOffsets.resize(nOffsetBase);
      if (bPushed)
         this->m_prepBonus.pop_back();
      this->m_currentVerb.pop_back();
      this->m_nDepth--;
   }

   this->addMemo(pR, a, b, e);
   // As for tokens, the score of a node that is scored in more than one
   // context is the one from the context that was first seen last
   pR->nScore = e.r.nSc;
   return e.r;
}

void Reducer::apply(RNode* pR, UINT a, UINT b)
{
   // Walk the winning tree, reducing each node to the family that won
   // in the context that the node is used in. A node that is shared
   // between contexts can only be reduced one way: the first context
   // to reach it decides.
   if (pR->bReduced || this->m_bFail)
      return;
   pR->bReduced = true;
   UINT nFamilies = pR->nFamilies;
   if (!nFamilies)
      return;
   const RMemo* pMemo = this->findMemo(pR, a, b);
   if (pMemo == NULL || ++this->m_nDepth > MAX_DEPTH) {
      this->m_bFail = true;
      return;
   }
   const RMemo& e = *pMemo;
   UINT iFirst = 0;
   UINT iLast = nFamilies;
   if (!(this->ntFlags(pR) & RN_NO_REDUCE)) {
      // The key action of the reducer: only the winner survives
      pR->iChosen = e.iChosen;
      iFirst = (UINT)e.iChosen;
      iLast = iFirst + 1;
   }
   size_t nSig = e.nSigOffset;
   for (UINT i = iFirst; i < iLast; i++) {
      const RFamily& family = pR->pFamilies[i];
      for (UINT j = 0; j < family.nChildren; j++) {
         const RChild& c = family.pChildren[j];
         if (c.isNone())
            continue;
         if (c.pR)
            // Note: no results are memoized, and nothing is added
            // to m_sigs, during this pass, so e stays valid
            this->apply(c.pR, this->m_sigs[nSig], this->m_sigs[nSig + 1]);
         nSig += 2;
      }
   }
   this->m_nDepth--;
}


// Serialization of the resulting tree (or of the whole forest,
// if it was not reduced)

INT Reducer::emitToken(const RChild& c)
{
   // A token: 1, terminal index, token index, start, end, score
   this->m_out.push_back(1);
   this->m_out.push_back(c.iTerminal);
   this->m_out.push_back((INT)c.nToken);
   this->m_out.push_back((INT)c.nStart);
   this->m_out.push_back((INT)c.nEnd);
   this->m_out.push_back(c.nScore);
   return (INT)++this->m_nOutIds;
}

INT Reducer::emit(RNode* pR)
{
   // Serialize the node and what is below it, and return the number of
   // the node. Nodes are numbered from 1, in the order in which they are
   // written; a node is written after its children, so that a reader can
   // create the nodes in one pass. A node that is reached more than once
   // is only written once. The format of a nonterminal node is:
   //    0, nonterminal index, start, end, 1 if completed else 0, score,
   //    number of families, and then for each family:
   //       production id, number of children, and for each child
   //       its number, or 0 if there is no child in that place
   if (pR->nOutId)
      return (INT)pR->nOutId;
   if (this->m_bFail)
      return 0;
   if (++this->m_nDepth > MAX_DEPTH) {
      this->m_bFail = true;
      return 0;
   }
   UINT iFirst = 0;
   UINT iLast = pR->nFamilies;
   if (pR->iChosen >= 0) {
      iFirst = (UINT)pR->iChosen;
      iLast = iFirst + 1;
   }
   // The numbers of the children are collected at the end
   // of a vector that all levels of the recursion share
   size_t nBase = this->m_ids.size();
   for (UINT i = iFirst; i < iLast; i++) {
      const RFamily& family = pR->pFamilies[i];
      for (UINT j = 0; j < family.nChildren; j++) {
         const RChild& c = family.pChildren[j];
         INT nId = 0;
         if (c.iTerminal)
            nId = this->emitToken(c);
         else
         if (c.pR)
            nId = this->emit(c.pR);
         this->m_ids.push_back(nId);
      }
   }
   std::vector<INT>& out = this->m_out;
   out.push_back(0);
   out.push_back(pR->iNt);
   out.push_back((INT)pR->nStart);
   out.push_back((INT)pR->nEnd);
   out.push_back(pR->bCompleted ? 1 : 0);
   out.push_back(pR->nScore);
   out.push_back((INT)(iLast - iFirst));
   size_t nId = nBase;
   for (UINT i = iFirst; i < iLast; i++) {
      const RFamily& family = pR->pFamilies[i];
      out.push_back((INT)family.pProd->getId());
      out.push_back((INT)family.nChildren);
      out.insert(out.end(),
         this->m_ids.begin() + nId, this->m_ids.begin() + nId + family.nChildren);
      nId += family.nChildren;
   }
   this->m_ids.resize(nBase);
   this->m_nDepth--;
   pR->nOutId = ++this->m_nOutIds;
   return (INT)pR->nOutId;
}

BOOL Reducer::run(Reduction* pRed, const INT* pnScores, UINT nHandle)
{
   RNode* pRoot = pRed->pRoot;
   if (pnScores) {
      // Score the forest and reduce it
      this->m_prt = this->m_pParser->getReducerTables();
      if (!this->m_prt)
         return false;
      this->m_pnScores = pnScores;
      this->m_nHandle = nHandle;
      // List 0 stands for no list at all
      ListRec none = { 0, 0 };
      this->m_lists.push_back(none);
      this->m_prepBonus.push_back(0);
      this->m_currentVerb.push_back(0);
      UINT a, b;
      this->contextSig(pRoot, a, b);
      // First pass: score the forest without changing it
      RResult r = this->calc(pRoot, a, b);
      if (this->m_bFail)
         return false;
      // Second pass: reduce the forest to the winning tree
      this->m_nDepth = 0;
      this->apply(pRoot, a, b);
      if (this->m_bFail)
         return false;
      pRed->nScore = r.nSc;
   }
   this->m_nDepth = 0;
   this->emit(pRoot);
   if (this->m_bFail)
      return false;
   UINT nOut = (UINT)this->m_out.size();
   INT* pn = (INT*)this->alloc(nOut * sizeof(INT));
   memcpy(pn, &this->m_out[0], nOut * sizeof(INT));
   pRed->nOut = nOut;
   pRed->pnOut = pn;
   return true;
}

BOOL Reducer::finish(Reduction* pRed, const INT* pnScores, UINT nHandle)
{
   if (!pRed || !pRed->pRoot || pRed->pnOut)
      return false;
   Reducer reducer(pRed->pParser, pRed->pForest);
   return reducer.run(pRed, pnScores, nHandle);
}


// The interface of the module. As in eparser.cpp, no C++ exception
// may propagate through these functions (see newGrammar() there).
// Running out of memory here means that the forest is left to
// the Python implementation.

Reduction* reduceStart(Parser* pParser, Node* pRoot)
{
   try {
      return Reducer::start(pParser, pRoot);
   }
   catch (...) {
      return NULL;
   }
}

BOOL reduceFinish(Reduction* pRed, const INT* pnScores, UINT nHandle)
{
   try {
      return Reducer::finish(pRed, pnScores, nHandle);
   }
   catch (...) {
      return false;
   }
}

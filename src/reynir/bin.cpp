/*

   Reynir: Natural language processing for Icelandic

   C++ BÍN lookup module

   Copyright (C) 2018 Miðeind ehf.

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

   This module implements lookup of words in a compressed, memory-mapped
   byte buffer containing the Database of Modern Icelandic Inflection
   (Beygingarlýsing íslensks nútímamáls, BÍN).

   See https://greynir.is/doc/copyright.html for important copyright and
   licensing information.

*/

// #define DEBUG

#include <stdio.h>
#include <assert.h>
#include <time.h>

#include "bin.h"


#define TRUE 1
#define FALSE 0

typedef int INT;
typedef bool BOOL;


class BIN_Compressed {

private:

#pragma pack(push, 1)
   struct Header {
      BYTE abSignature[16];
      UINT nMappingsOffset;
      UINT nFormsOffset;
      UINT nStemsOffset;
      UINT nMeaningsOffset;
      UINT nAlphabetOffset;
   };
#pragma pack(pop)

   const BYTE* m_pbMap;
   const Header* m_pHeader;
   UINT m_nFormsRootHeader;
   UINT m_nWordLen;
   const BYTE* m_pbWordLatin;
   UINT m_nAlphabetLength;
   BYTE* m_pbAlphabet;

   INT matches(UINT nNodeOffset, UINT nHdr, UINT nFragmentIndex);
   UINT lookup(UINT nNodeOffset, UINT nHdr, UINT nFragmentIndex);

public:

   BIN_Compressed(const BYTE* pbMap);
   ~BIN_Compressed();

   UINT mapping(const BYTE* pbWord);

};


INT BIN_Compressed::matches(UINT nNodeOffset, UINT nHdr, UINT nFragmentIndex)
{
   /* If the lookup fragment word[fragment_index:] matches the node,
      return the number of characters matched. Otherwise,
      return -1 if the node is lexicographically less than the
      lookup fragment, or 0 if the node is greater than the fragment.
      (The lexicographical ordering here is actually a comparison
      between the Latin-1 ordinal numbers of characters.)
   */
#ifdef DEBUG
   printf("matches(%08x, %08x, %u)\n", nNodeOffset, nHdr, nFragmentIndex);
#endif
   if (nHdr & 0x80000000) {
      // Single-character fragment
      UINT nIx = ((nHdr >> 23) & 0x7F) - 1; // Index of character in alphabet
      BYTE ch = this->m_pbAlphabet[nIx];
      BYTE chWord = this->m_pbWordLatin[nFragmentIndex];
#ifdef DEBUG
      printf("Single-character fragment: comparing %c and %c\n", ch, chWord);
#endif
      if (ch == chWord) {
         // Match
#ifdef DEBUG
         printf("Returning match (1)\n");
#endif
         return 1;
      }
#ifdef DEBUG
      printf("Returning no match (%d)\n", (ch > chWord) ? 0 : -1);
#endif
      return (ch > chWord) ? 0 : -1;
   }
   UINT nFrag;
   if (nHdr & 0x40000000) {
      // Childless node
      nFrag = nNodeOffset + sizeof(UINT);
   }
   else {
      UINT nNumChildren = *(UINT*)(this->m_pbMap + nNodeOffset + sizeof(UINT));
      nFrag = nNodeOffset + 2 * sizeof(UINT) + sizeof(UINT) * nNumChildren;
   }
   INT iMatched = 0;
   UINT nWordLen = this->m_nWordLen;
   BYTE* pFrag = (BYTE*)(this->m_pbMap + nFrag);
#ifdef DEBUG
   printf("Multi-character fragment: initial compare %c and %c\n",
      *pFrag, this->m_pbWordLatin[nFragmentIndex]);
#endif
   while (*pFrag && (nFragmentIndex + iMatched < nWordLen) &&
      (*pFrag == this->m_pbWordLatin[nFragmentIndex + iMatched])) {
      pFrag++;
      iMatched++;
#ifdef DEBUG
      printf("Multi-character fragment: next compare %c and %c\n",
         *pFrag, (nFragmentIndex + iMatched < nWordLen) ? this->m_pbWordLatin[nFragmentIndex + iMatched] : '\0');
#endif
   }
   if (!*pFrag) {
      // Matched the entire fragment: success
#ifdef DEBUG
      printf("Multi-char fragment returning match (%d)\n", iMatched);
#endif
      return iMatched;
   }
   if (nFragmentIndex + iMatched >= nWordLen) {
      // The node is longer and thus greater than the fragment
#ifdef DEBUG
      printf("Multi-char fragment returning no match (0)\n");
#endif
      return 0;
   }
#ifdef DEBUG
   printf("Multi-char fragment returning no match (%d)\n",
      (*pFrag > this->m_pbWordLatin[nFragmentIndex + iMatched]) ? 0 : -1);
#endif
   return (*pFrag > this->m_pbWordLatin[nFragmentIndex + iMatched]) ? 0 : -1;
}

UINT BIN_Compressed::lookup(UINT nNodeOffset, UINT nHdr, UINT nFragmentIndex)
{
#ifdef DEBUG
   printf("lookup(%08x, %08x, %u)\n", nNodeOffset, nHdr, nFragmentIndex);
#endif
   while (1) {
#ifdef DEBUG
      printf("   head of outer while loop (%08x, %08x, %u)\n", nNodeOffset, nHdr, nFragmentIndex);
#endif
      if (nFragmentIndex >= this->m_nWordLen) {
         // We've arrived at our destination:
         // return the associated value (unless this is an interim node)
         UINT nValue = nHdr & 0x007FFFFF;
         return (nValue == 0x007FFFFF) ? ((UINT)-1) : nValue;
      }
      if (nHdr & 0x40000000) {
         // Childless node: nowhere to go
         return ((UINT)-1);
      }
      UINT nNumChildren = *(UINT*)(this->m_pbMap + nNodeOffset + sizeof(UINT));
      UINT nChildOffset = nNodeOffset + 2 * sizeof(UINT);
      // Binary search for a matching child node
      UINT nLo = 0;
      UINT nHi = nNumChildren;
      BOOL fContinue = TRUE;
      do {
#ifdef DEBUG
         printf("   head of inner while loop, nLo %u, nHi %u\n", nLo, nHi);
#endif
         if (nLo >= nHi) {
            // No child route matches
            return ((UINT)-1);
         }
         UINT nMid = (nLo + nHi) / 2;
         UINT nMidLoc = nChildOffset + nMid * sizeof(UINT);
         UINT nMidOffset = *(UINT*)(this->m_pbMap + nMidLoc);
         nHdr = *(UINT*)(this->m_pbMap + nMidOffset);
         INT iMatchLen = this->matches(nMidOffset, nHdr, nFragmentIndex);
         if (iMatchLen > 0) {
             // Set a new starting point and restart from the top
             nNodeOffset = nMidOffset;
             nFragmentIndex += iMatchLen;
             fContinue = FALSE;
         }
         else
         if (iMatchLen < 0) {
            nLo = nMid + 1;
         }
         else {
            nHi = nMid;
         }
      } while (fContinue);
   }
#ifdef DEBUG
   printf("Error: should not get here\n");
#endif
   assert(FALSE);
}

BIN_Compressed::BIN_Compressed(const BYTE* pbMap)
   : m_pbMap(pbMap), m_pHeader((const Header*)pbMap),
      m_nFormsRootHeader(*(UINT*)(pbMap + m_pHeader->nFormsOffset)),
      m_pbWordLatin(NULL),
      m_nWordLen(0),
      m_nAlphabetLength(*(UINT*)(this->m_pbMap + m_pHeader->nAlphabetOffset)),
      m_pbAlphabet((BYTE*)(this->m_pbMap + m_pHeader->nAlphabetOffset + sizeof(UINT)))
{
#ifdef DEBUG
   printf("BIN_Compressed constructor: m_nAlphabetLength is %u, sizeof(UINT) is %u\n",
      this->m_nAlphabetLength, (UINT)sizeof(UINT));
#endif
}

BIN_Compressed::~BIN_Compressed()
{
}

UINT BIN_Compressed::mapping(const BYTE* pbWordLatin)
{
   if (!pbWordLatin) {
      return 0;
   }
   this->m_pbWordLatin = pbWordLatin;
   this->m_nWordLen = (UINT)(strlen((const char*)pbWordLatin));
#ifdef DEBUG
   printf("m_nWordLen is %u\n", this->m_nWordLen);
#endif
   return this->lookup(this->m_pHeader->nFormsOffset, this->m_nFormsRootHeader, 0);
}

UINT mapping(const BYTE* pbMap, const BYTE* pbWordLatin)
{
   BIN_Compressed bc(pbMap);
   return bc.mapping(pbWordLatin);
}


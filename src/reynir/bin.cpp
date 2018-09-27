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

#define DEBUG

#include <stdio.h>
#include <assert.h>
#include <time.h>

#include "bin.h"


class BIN_Compressed {

private:

#pragma pack(push, 1)
   struct Header {
      CHAR achSignature[16];
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
   const CHAR* m_pchWordLatin;
   UINT m_nAlphabetLength;
   CHAR* m_pchAlphabet;

   INT matches(UINT nNodeOffset, UINT nHdr, UINT nFragmentIndex);
   UINT lookup(UINT nNodeOffset, UINT nHdr, UINT nFragmentIndex);

public:

   BIN_Compressed(const BYTE* pbMap);
   ~BIN_Compressed();

   UINT mapping(const CHAR* pszWord);

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
   printf("matches(%x, %x, %u)\n", nNodeOffset, nHdr, nFragmentIndex);
   if (nHdr & 0x80000000) {
      // Single-character fragment
      UINT nIx = (nHdr >> 23) & 0x7F; // Index of character in alphabet
      CHAR ch = this->m_pchAlphabet[nIx];
      CHAR chWord = this->m_pchWordLatin[nFragmentIndex];
      printf("Single-character fragment: comparing %c and %c\n", ch, chWord);
      if (ch == chWord)
         // Match
         return 1;
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
   CHAR* pFrag = (CHAR*)(this->m_pbMap + nFrag);
   while (*pFrag && (nFragmentIndex + iMatched < nWordLen) &&
      (*pFrag == this->m_pchWordLatin[nFragmentIndex + iMatched])) {
      printf("Multi-character fragment: comparing %c and %c\n",
         *pFrag, this->m_pchWordLatin[nFragmentIndex + iMatched]);
      pFrag++;
      iMatched++;
   }
   if (!*pFrag)
      // Matched the entire fragment: success
      return iMatched;
   if (nFragmentIndex + iMatched >= nWordLen)
      // The node is longer and thus greater than the fragment
      return 0;
   return (*pFrag > this->m_pchWordLatin[nFragmentIndex + iMatched]) ? 0 : -1;
}

UINT BIN_Compressed::lookup(UINT nNodeOffset, UINT nHdr, UINT nFragmentIndex)
{
   printf("lookup(%u, %u, %u)\n", nNodeOffset, nHdr, nFragmentIndex);
   while (1) {
      if (nFragmentIndex >= this->m_nWordLen) {
         // We've arrived at our destination:
         // return the associated value (unless this is an interim node)
         UINT nValue = nHdr & 0x007FFFFF;
         return (nValue == 0x007FFFFF) ? 0 : nValue;
      }
      if (nHdr & 0x40000000)
         // Childless node: nowhere to go
         return 0;
      UINT nNumChildren = *(UINT*)(this->m_pbMap + nNodeOffset + sizeof(UINT));
      UINT nChildOffset = nNodeOffset + 2 * sizeof(UINT);
      // Binary search for a matching child node
      UINT nLo = 0;
      UINT nHi = nNumChildren;
      while (1) {
         if (nLo >= nHi)
            // No child route matches
            return 0;
         UINT nMid = (nLo + nHi) >> 1;
         UINT nMidLoc = nChildOffset + nMid * sizeof(UINT);
         UINT nMidOffset = *(UINT*)(this->m_pbMap + nMidLoc);
         nHdr = *(UINT*)(this->m_pbMap + nMidOffset);
         INT iMatchLen = this->matches(nMidOffset, nHdr, nFragmentIndex);
         if (iMatchLen > 0) {
             // Set a new starting point and restart from the top
             nNodeOffset = nMidOffset;
             nFragmentIndex += iMatchLen;
             break;
         }
         if (iMatchLen < 0)
            nLo = nMid + 1;
         else
            nHi = nMid;
      }
   }
}

BIN_Compressed::BIN_Compressed(const BYTE* pbMap)
   : m_pbMap(pbMap), m_pHeader((const Header*)pbMap),
      m_nFormsRootHeader(*(UINT*)(pbMap + m_pHeader->nFormsOffset)),
      m_pchWordLatin(NULL),
      m_nWordLen(0),
      m_nAlphabetLength(*(UINT*)(this->m_pbMap + m_pHeader->nAlphabetOffset)),
      m_pchAlphabet((CHAR*)(this->m_pbMap + m_pHeader->nAlphabetOffset + sizeof(UINT)))
{
   printf("BIN_Compressed constructor: m_nAlphabetLength is %u\n", this->m_nAlphabetLength);
}

BIN_Compressed::~BIN_Compressed()
{
}

UINT BIN_Compressed::mapping(const CHAR* pszWordLatin)
{
   if (!pszWordLatin) {
      printf("pszWordLatin is NULL, returning\n");
      return 0;
   }
   this->m_pchWordLatin = pszWordLatin;
   this->m_nWordLen = (UINT)(strlen((const char*)pszWordLatin));
   printf("m_nWordLen is %u\n", this->m_nWordLen);
   return this->lookup(this->m_pHeader->nFormsOffset, this->m_nFormsRootHeader, 0);
}

UINT mapping(const BYTE* pbMap, const CHAR* pszWordLatin)
{
   BIN_Compressed bc(pbMap);
   return bc.mapping(pszWordLatin);
}

int main(int argc, char* argv[]) {
   printf("Welcome to Bin!\n");
}

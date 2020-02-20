/*

   Reynir: Natural language processing for Icelandic

   C++ BÍN lookup module

   Copyright (C) 2020 Miðeind ehf.
   Original Author: Vilhjálmur Þorsteinsson

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

#include <stdlib.h>
#include <string.h>
#include <stdint.h>


// Assert macro
#ifdef DEBUG
   #define ASSERT(x) assert(x)
#else
   #define ASSERT(x)
#endif


typedef unsigned int UINT;
typedef uint8_t BYTE;


// Map a word to an offset within the memory mapped buffer
extern "C" UINT mapping(const BYTE* pbMap, const BYTE* pbWordLatin);


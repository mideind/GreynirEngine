/*

   Greynir: Natural language processing for Icelandic

   C++ BÍN lookup module

   Copyright (C) 2020 Miðeind ehf.
   Original Author: Vilhjálmur Þorsteinsson

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

   This module implements lookup of words in a compressed, memory-mapped
   byte buffer containing the Database of Modern Icelandic Inflection
   (Beygingarlýsing íslensks nútímamáls, BÍN).

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


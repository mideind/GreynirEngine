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
#include <stdint.h>
#include <assert.h>
#include <time.h>

#include "bin.h"


UINT mapping(BYTE* pbMap, CHAR* pszWord)
{
#ifdef DEBUG
   printf("In mapping()\n"); fflush(stdout);
#endif
   return 0;
}



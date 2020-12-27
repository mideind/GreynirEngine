#!/usr/bin/env python
"""

    Greynir: Natural language processing for Icelandic

    BÍN compressor module

    Copyright (C) 2020 Miðeind ehf.
    Original author: Vilhjálmur Þorsteinsson

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

    This module manages a compressed BÍN dictionary in memory, allowing
    various kinds of lookups. The dictionary is read into memory as
    a BLOB (via mmap). No auxiliary dictionaries or other data structures
    should be needed. The binary image is shared between running processes.

    ************************************************************************

    LICENSE NOTICE:

    GreynirPackage embeds the 'Database of Modern Icelandic Inflection' /
    'Beygingarlýsing íslensks nútímamáls' (see https://bin.arnastofnun.is),
    abbreviated BÍN.

    The BÍN source data are publicly available under the CC-BY-4.0 license, as further
    detailed here in English: https://bin.arnastofnun.is/DMII/LTdata/conditions/
    and here in Icelandic: https://bin.arnastofnun.is/gogn/mimisbrunnur/.

    In accordance with the BÍN license terms, credit is hereby given as follows:

        Beygingarlýsing íslensks nútímamáls.
        Stofnun Árna Magnússonar í íslenskum fræðum.
        Höfundur og ritstjóri Kristín Bjarnadóttir.

    See the comments in the binpack.py file for further information.

"""

from typing import Any, Set, Tuple, Dict, List, Optional, Callable

import os
import io
import time
import struct
import functools
import mmap
import pkg_resources
from collections import defaultdict

# Import the CFFI wrapper for the bin.cpp C++ module (see also build_bin.py)
# This is not needed for command-line invocation of bincompress.py,
# i.e. when generating a new ord.compressed file.
# pylint: disable=no-name-in-module
from ._bin import lib as bin_cffi, ffi  # type: ignore

# pylint: enable=no-name-in-module
from .basics import (
    MeaningTuple,
    ALL_GENDERS,
    BIN_COMPRESSOR_VERSION,
    BIN_COMPRESSED_FILE,
)


_PATH = os.path.dirname(__file__) or "."

INT32 = struct.Struct("<i")
UINT32 = struct.Struct("<I")

CASES = ("NF", "ÞF", "ÞGF", "EF")
CASES_LATIN = tuple(case.encode("latin-1") for case in CASES)


class BIN_Compressed:

    """ A wrapper for the compressed binary dictionary,
        allowing read-only lookups of word forms """

    # Note: the resource path below should NOT use os.path.join()
    _FNAME = pkg_resources.resource_filename(
        __name__, "resources/" + BIN_COMPRESSED_FILE
    )

    # Unique indicator used to signify no utg field
    # (needed since None is a valid utg value)
    NoUtg = object()

    def __init__(self) -> None:
        """ We use a memory map, provided by the mmap module, to
            directly map the compressed file into memory without
            having to read it into a byte buffer. This also allows
            the same memory map to be shared between processes. """
        with open(self._FNAME, "rb") as stream:
            self._b = mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ)
        # Check that the file version matches what we expect
        assert (
            self._b[0:16] == BIN_COMPRESSOR_VERSION
        ), "Invalid signature in ord.compressed (git-lfs might be missing)"
        (
            mappings_offset,
            forms_offset,
            stems_offset,
            variants_offset,
            meanings_offset,
            alphabet_offset,
        ) = struct.unpack("<IIIIII", self._b[16:40])
        self._forms_offset = forms_offset
        self._mappings = self._b[mappings_offset:]
        self._stems = self._b[stems_offset:]
        self._case_variants = self._b[variants_offset:]
        self._meanings = self._b[meanings_offset:]
        # Create partial unpacking functions for speed
        self._partial_UINT = functools.partial(UINT32.unpack_from, self._b)
        self._partial_mappings = functools.partial(UINT32.unpack_from, self._mappings)
        # Cache the trie root header
        self._forms_root_hdr = self._UINT(forms_offset)
        # The alphabet header occupies the next 16 bytes
        # Read the alphabet length
        alphabet_length = self._UINT(alphabet_offset)
        self._alphabet_bytes = bytes(
            self._b[alphabet_offset + 4 : alphabet_offset + 4 + alphabet_length]
        )
        # Create a CFFI buffer object pointing to the memory map
        self._mmap_buffer = ffi.from_buffer(self._b)

    def _UINT(self, offset: int) -> int:
        """ Return the 32-bit UINT at the indicated offset
            in the memory-mapped buffer """
        return self._partial_UINT(offset)[0]

    def close(self) -> None:
        """ Close the memory map """
        if self._b is not None:
            self._mappings = None  # type: ignore
            self._stems = None  # type: ignore
            self._meanings = None  # type: ignore
            self._alphabet = set()  # type: Set[str]
            self._alphabet_bytes = bytes()
            self._mmap_buffer = None
            self._b.close()
            self._b = None  # type: ignore

    def meaning(self, ix: int) -> Tuple[str, str, str]:
        """ Find and decode a meaning (ordfl, fl, beyging) tuple,
            given its index """
        (off,) = UINT32.unpack_from(self._meanings, ix * 4)
        b = bytes(self._b[off : off + 24])
        s = b.decode("latin-1").split(maxsplit=4)
        return s[0], s[1], s[2]  # ordfl, fl, beyging

    def stem(self, ix: int) -> Tuple[str, int]:
        """ Find and decode a stem (utg, stofn) tuple, given its index """
        (off,) = UINT32.unpack_from(self._stems, ix * 4)
        wid = self._UINT(off)
        # The id (utg) is stored in the lower 31 bits, after adding 1
        wid = (wid & 0x7FFFFFFF) - 1
        p = off + 4
        lw = self._b[p]  # Length byte
        p += 1
        b = bytes(self._b[p : p + lw])
        return b.decode("latin-1"), wid  # stofn, utg

    def case_variants(self, ix: int, case: bytes = b"NF") -> List[bytes]:
        """ Return all word forms having the given case, that are
            associated with the stem whose index is in ix """

        def read_set(p: int, base: Optional[bytes] = None) -> Tuple[List[bytes], int]:
            """ Decompress a set of strings compressed by compress_set() """
            b = self._case_variants
            if base is None:
                lw = b[p]
                p += 1
                last_w = b[p : p + lw]
                p += lw
                c = [last_w]
            else:
                last_w = base
                lw = len(last_w)
                c = []
            while True:
                # How many letters should we cut off the end of the
                # last word before appending the divergent part?
                cut = b[p]
                p += 1
                if cut == 255:
                    # Done
                    break
                # Calculate the number of common characters between
                # this word and the last one
                common = lw - cut
                lw = b[p]
                p += 1
                # Assemble this word and append it to our result
                w = last_w[0:common] + b[p : p + lw]
                p += lw
                c.append(w)
                last_w = w
                lw += common
            # Return the set as a list of strings, as well as the current byte pointer
            return c, p

        (off,) = UINT32.unpack_from(self._stems, ix * 4)
        wid = self._UINT(off)
        # The id (utg) is stored in the lower 31 bits, after adding 1
        if wid & 0x80000000 == 0:
            # No case_variants associated with this stem
            return []
        # Skip past the stem itself
        p = off + 4
        lw = self._b[p]  # Length byte
        stem = bytes(self._b[p + 1 : p + 1 + lw])
        lw += 1
        if lw & 3:
            lw += 4 - (lw & 3)
        p += lw
        # Make p point to the case variant offset within the
        # self._case_variants buffer
        p = self._UINT(p)
        # Read the sets of case_variants from the byte buffer, starting at p.
        # They are stored in case order: NF, ÞF, ÞGF, EF
        for this_case in CASES_LATIN:
            c, p = read_set(p, base=stem)
            if case == this_case:
                # That's us: return
                return c
        assert False, "Unknown case requested in case_variants()"
        return []

    def _mapping_cffi(self, word: str) -> Optional[int]:
        """ Call the C++ mapping() function that has been wrapped using CFFI"""
        try:
            m = bin_cffi.mapping(
                ffi.cast("uint8_t*", self._mmap_buffer), word.encode("latin-1")
            )
            return None if m == 0xFFFFFFFF else m
        except UnicodeEncodeError:
            # The word contains a non-latin-1 character:
            # it can't be in the trie
            return None

    def _raw_lookup(self, word: str) -> List[Tuple[int, int]]:
        """ Return a list of stem/meaning tuples for the word, or
            an empty list if it is not found in the trie """
        mapping = self._mapping_cffi(word)
        if mapping is None:
            # Word not found in trie: return an empty list of meanings
            return []
        # Found the word in the trie; return potentially multiple meanings
        # Fetch the mapping-to-stem/meaning tuples
        result = []
        while True:
            (stem_meaning,) = self._partial_mappings(mapping * 4)
            stem_index = (stem_meaning >> 11) & (2 ** 20 - 1)
            meaning_index = stem_meaning & (2 ** 11 - 1)
            result.append((stem_index, meaning_index))
            if stem_meaning & 0x80000000:
                # Last mapping indicator: we're done
                break
            mapping += 1
        return result

    def contains(self, word: str) -> bool:
        """ Returns True if the trie contains the given word form"""
        return self._mapping_cffi(word) is not None

    def __contains__(self, word: str) -> bool:
        """ Returns True if the trie contains the given word form"""
        return self._mapping_cffi(word) is not None

    def lookup(
        self,
        word: str,
        cat: Optional[str] = None,
        stem: Optional[str] = None,
        utg: Any = NoUtg,
        beyging_func: Optional[Callable[[str], bool]] = None,
    ):
        """ Returns a list of BÍN meanings for the given word form,
            eventually constrained to the requested word category,
            stem, utg number and/or the given beyging_func filter function,
            which is called with the beyging field as a parameter. """
        # Category set
        if cat is None:
            cats = None
        elif cat == "no":
            # Allow a cat of "no" to mean a noun of any gender
            cats = ALL_GENDERS
        else:
            cats = frozenset([cat])
        result = []
        for stem_index, meaning_index in self._raw_lookup(word):
            meaning = self.meaning(meaning_index)
            if cats is not None and meaning[0] not in cats:
                # Fails the word category constraint
                continue
            word_stem = self.stem(stem_index)
            if stem is not None and word_stem[0] != stem:
                # Fails the stem filter
                continue
            word_utg = None if word_stem[1] == -1 else word_stem[1]
            if utg is not BIN_Compressed.NoUtg and word_utg != utg:
                # Fails the utg filter
                continue
            beyging = meaning[2]
            if beyging_func is not None and not (beyging_func(beyging)):
                # Fails the beyging_func filter
                continue
            # stofn, utg, ordfl, fl, ordmynd, beyging
            result.append(
                (word_stem[0], word_utg, meaning[0], meaning[1], word, beyging)
            )
        return result

    def lookup_case(
        self,
        word: str,
        case: str,
        *,
        singular: bool = False,
        indefinite: bool = False,
        cat: Optional[str] = None,
        stem: Optional[str] = None,
        utg: Any = NoUtg,
        beyging_filter: Optional[Callable[[str], bool]] = None
    ):
        """ Returns a set of meanings, in the requested case, derived
            from the lemmas of the given word form, optionally constrained
            by word category and by the other arguments given. The
            beyging_filter argument, if present, should be a function that
            filters on the beyging field of each candidate BÍN meaning.
            Note that the word form is case-sensitive. """

        # Note that singular=True means that we force the result to be
        # singular even if the original word given is plural.
        # singular=False does not force the result to be plural; it
        # simply means that no forcing to singular occurs.
        # The same applies to indefinite=True and False, mutatis mutandis.

        result = set()  # type: Set[MeaningTuple]
        case_latin = case.encode("latin-1")
        # Category set
        if cat is None:
            cats = None
        elif cat == "no":
            # Allow a cat of "no" to mean a noun of any gender
            cats = ALL_GENDERS
        else:
            cats = frozenset([cat])
        wanted_beyging = ""

        def simplify_beyging(beyging: str) -> str:
            """ Removes case-related information from a beyging string """
            # Note that we also remove '2' and '3' in cases like
            # 'ÞGF2' and 'EF2', where alternate declination forms are
            # being specified.
            for s in ("NF", "ÞF", "ÞGF", "EF", "2", "3"):
                beyging = beyging.replace(s, "")
            if singular:
                for s in ("ET", "FT"):
                    beyging = beyging.replace(s, "")
            if indefinite:
                beyging = beyging.replace("gr", "")
                # For adjectives, we neutralize weak and strong
                # declension ('VB', 'SB'), but keep the degree (F, M, E)
                beyging = beyging.replace("EVB", "ESB").replace("FVB", "FSB")
            return beyging

        def beyging_func(beyging: str) -> bool:
            """ This function is passed to self.lookup() as a filter
                on the beyging field """
            if case not in beyging:
                # We get all BIN entries having the word form we ask
                # for from self.lookup(), so we need to be careful to
                # filter again on the case
                return False
            if singular and ("ET" not in beyging):
                return False
            if indefinite and any(b in beyging for b in ("gr", "FVB", "EVB")):
                # For indefinite forms, we don't want the attached definite
                # article ('gr') or weak declensions of adjectives
                return False
            if beyging_filter is not None and not beyging_filter(beyging):
                # The user-defined filter fails: return False
                return False
            # Apply our own filter, making sure we have effectively
            # the same beyging string as the word form we're coming
            # from, except for the case
            return simplify_beyging(beyging) == wanted_beyging

        for stem_index, meaning_index in self._raw_lookup(word):
            # Check the category filter, if present
            meaning = self.meaning(meaning_index)
            if cats is not None:
                if meaning[0] not in cats:
                    # Not the category we're looking for
                    continue
            word_stem = self.stem(stem_index)
            if stem is not None and stem != word_stem[0]:
                # Not the stem we're looking for
                continue
            word_utg = None if word_stem[1] == -1 else word_stem[1]
            if utg is not BIN_Compressed.NoUtg and utg != word_utg:
                # Not the utg we're looking for (note that None is a valid utg)
                continue
            # Go through the variants of this
            # stem, for the requested case
            wanted_beyging = simplify_beyging(meaning[2])
            for c_latin in self.case_variants(stem_index, case=case_latin):
                # TODO: Encoding and decoding back and forth is not terribly efficient
                c = c_latin.decode("latin-1")
                # Make sure we only include each result once.
                # Also note that we need to check again for the word
                # category constraint because different inflection
                # forms may be identical to forms of other stems
                # and categories.
                result.update(
                    m
                    for m in self.lookup(
                        c,
                        cat=meaning[0],
                        stem=word_stem[0],
                        utg=word_utg,
                        beyging_func=beyging_func,
                    )
                )
        return result

    def raw_nominative(self, word: str) -> Set[MeaningTuple]:
        """ Returns a set of all nominative forms of the stems of the given word form.
            Note that the word form is case-sensitive. """
        result = set()  # type: Set[MeaningTuple]
        for stem_index, _ in self._raw_lookup(word):
            for c_latin in self.case_variants(stem_index):
                c = c_latin.decode("latin-1")
                # Make sure we only include each result once
                result.update(m for m in self.lookup(c) if "NF" in m[5])
        return result

    def nominative(self, word: str, **options) -> Set[MeaningTuple]:
        """ Returns a set of all nominative forms of the stems of the given word form,
            subject to the constraints in **options.
            Note that the word form is case-sensitive. """
        return self.lookup_case(word, "NF", **options)

    def accusative(self, word: str, **options) -> Set[MeaningTuple]:
        """ Returns a set of all accusative forms of the stems of the given word form,
            subject to the given constraints on the beyging field.
            Note that the word form is case-sensitive. """
        return self.lookup_case(word, "ÞF", **options)

    def dative(self, word: str, **options) -> Set[MeaningTuple]:
        """ Returns a set of all dative forms of the stems of the given word form,
            subject to the given constraints on the beyging field.
            Note that the word form is case-sensitive. """
        return self.lookup_case(word, "ÞGF", **options)

    def genitive(self, word: str, **options) -> Set[MeaningTuple]:
        """ Returns a set of all genitive forms of the stems of the given word form,
            subject to the given constraints on the beyging field.
            Note that the word form is case-sensitive. """
        return self.lookup_case(word, "EF", **options)

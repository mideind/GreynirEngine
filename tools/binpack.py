#!/usr/bin/env python
"""

    Greynir: Natural language processing for Icelandic

    BÍN packing/compression program

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

    This module compresses the BÍN dictionary from a ~300 MB uncompressed
    form into a compact binary representation. A radix trie data structure
    is used to store a mapping from word forms to integer indices.
    These indices are then used to look up word stems, categories and meanings.

    The data format is a tradeoff between storage space and retrieval
    speed. The resulting binary image is designed to be read into memory as
    a BLOB (via mmap) and used directly to look up word forms. No auxiliary
    dictionaries or other data structures should be needed. The binary image
    is shared between running processes.

    binpack.py reads the files ord.csv (originally SHsnid.csv from BÍN), ord.auka.csv
    (additional vocabulary), and ord.add.csv (generated from config/Vocab.conf
    by the program utils/vocab.py in the Greynir repository). Additionally,
    errata from the BinErrata.conf file are applied during the compression process.
    These additions and modifications are not a part of the original BÍN source data.

    The run-time counterpart of this module is bincompress.py.

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

    This module makes certain additions and modifications to the original
    BÍN source data during the generation of the compressed file.
    These are described in the comments above.

"""

from typing import Any, Set, Tuple, Dict, List, Optional, Callable, Iterable, IO

import os
import io
import time
import struct
from collections import defaultdict

from reynir.basics import MeaningTuple, BIN_COMPRESSOR_VERSION, BIN_COMPRESSED_FILE
from reynir.settings import Settings, BinErrata, BinDeletions


_PATH = os.path.dirname(__file__) or "."
if _PATH == "tools":
    # Running from the base directory (.)
    _PATH = "./src/reynir"
else:
    # Running from the tools directory (./tools)
    _PATH = "../src/reynir"

INT32 = struct.Struct("<i")
UINT32 = struct.Struct("<I")

# A dictionary of BÍN errata, loaded from BinErrata.conf
_BIN_ERRATA: Dict[Tuple[str, str], str] = {}
# A set of BÍN deletions, loaded from BinErrata.conf
_BIN_DELETIONS: Set[Tuple[str, str, str]] = set()

CASES = ("NF", "ÞF", "ÞGF", "EF")
CASES_LATIN = tuple(case.encode("latin-1") for case in CASES)

# Note: the following constants are also declared in bincompress.py
# and their values must be identical

# Bits allocated for the stem index
STEM_BITS = 20
# Bits allocated for the meaning index
MEANING_BITS = 11
# Bits allocated for the utg number
UTG_BITS = 23
# Bits allocated for the subcategory index (fl)
SUBCAT_BITS = 8


class _Node:

    """ A Node within a Trie """

    def __init__(self, fragment: bytes, value: Any) -> None:
        # The key fragment that leads into this node (and value)
        self.fragment = fragment
        self.value = value
        # List of outgoing nodes
        self.children: Optional[List[_Node]] = None

    def add(self, fragment: bytes, value: Any) -> Any:
        """ Add the given remaining key fragment to this node """
        if len(fragment) == 0:
            if self.value is not None:
                # This key already exists: return its value
                return self.value
            # This was previously an internal node without value;
            # turn it into a proper value node
            self.value = value
            return None

        if self.children is None:
            # Trivial case: add an only child
            self.children = [_Node(fragment, value)]
            return None

        # Check whether we need to take existing child nodes into account
        lo = 0
        hi = len(self.children)
        ch = fragment[0]
        while hi > lo:
            mid = (lo + hi) // 2
            mid_ch = self.children[mid].fragment[0]
            if mid_ch < ch:
                lo = mid + 1
            elif mid_ch > ch:
                hi = mid
            else:
                break

        if hi == lo:
            # No common prefix with any child:
            # simply insert a new child into the sorted list
            # if lo > 0:
            #     assert self._children[lo - 1]._fragment[0] < fragment[0]
            # if lo < len(self._children):
            #     assert self._children[lo]._fragment[0] > fragment[0]
            self.children.insert(lo, _Node(fragment, value))
            return None

        assert hi > lo
        # Found a child with at least one common prefix character
        # noinspection PyUnboundLocalVariable
        child = self.children[mid]
        child_fragment = child.fragment
        # assert child_fragment[0] == ch
        # Count the number of common prefix characters
        common = 1
        len_fragment = len(fragment)
        len_child_fragment = len(child_fragment)
        while (
            common < len_fragment
            and common < len_child_fragment
            and fragment[common] == child_fragment[common]
        ):
            common += 1
        if common == len_child_fragment:
            # We have 'abcd' but the child is 'ab':
            # Recursively add the remaining 'cd' fragment to the child
            return child.add(fragment[common:], value)
        # Here we can have two cases:
        # either the fragment is a proper prefix of the child,
        # or the two diverge after #common characters
        # assert common < len_child_fragment
        # assert common <= len_fragment
        # We have 'ab' but the child is 'abcd',
        # or we have 'abd' but the child is 'acd'
        child.fragment = child_fragment[common:]  # 'cd'
        if common == len_fragment:
            # The fragment is a proper prefix of the child,
            # i.e. it is 'ab' while the child is 'abcd':
            # Break the child up into two nodes, 'ab' and 'cd'
            node = _Node(fragment, value)  # New parent 'ab'
            node.children = [child]  # Make 'cd' a child of 'ab'
        else:
            # The fragment and the child diverge,
            # i.e. we have 'abd' but the child is 'acd'
            new_fragment = fragment[common:]  # 'bd'
            # Make an internal node without a value
            node = _Node(fragment[0:common], None)  # 'a'
            # assert new_fragment[0] != child._fragment[0]
            if new_fragment[0] < child.fragment[0]:
                # Children: 'bd', 'cd'
                node.children = [_Node(new_fragment, value), child]
            else:
                node.children = [child, _Node(new_fragment, value)]
        # Replace 'abcd' in the original children list
        self.children[mid] = node
        return None

    def lookup(self, fragment: bytes) -> Any:
        """ Lookup the given key fragment in this node and its children
            as necessary """
        if not fragment:
            # We've arrived at our destination: return the value
            return self.value
        if self.children is None:
            # Nowhere to go: the key was not found
            return None
        # Note: The following could be a faster binary search,
        # but this lookup is not used in time critical code,
        # so the optimization is probably not worth it.
        for child in self.children:
            if fragment.startswith(child.fragment):
                # This is a continuation route: take it
                return child.lookup(fragment[len(child.fragment) :])
        # No route matches: the key was not found
        return None

    def __str__(self) -> str:
        s = "Fragment: '{0!r}', value '{1}'\n".format(self.fragment, self.value)
        c = ["   {0}".format(child) for child in self.children] if self.children else []
        return s + "\n".join(c)


class Trie:

    """ Wrapper class for a radix (compact) trie data structure.
        Each node in the trie contains a prefix string, leading
        to its children. """

    def __init__(self, root_fragment: bytes = b"") -> None:
        self._cnt = 0
        self._root = _Node(root_fragment, None)

    @property
    def root(self) -> _Node:
        return self._root

    def add(self, key: bytes, value: Any = None) -> Any:
        """ Add the given (key, value) pair to the trie.
            Duplicates are not allowed and not added to the trie.
            If the value is None, it is set to the number of entries
            already in the trie, thereby making it function as
            an automatic generator of list indices. """
        assert key
        if value is None:
            value = self._cnt
        prev_value = self._root.add(key, value)
        if prev_value is not None:
            # The key was already found in the trie: return the
            # corresponding value
            return prev_value
        # Not already in the trie: add to the count and return the new value
        self._cnt += 1
        return value

    def get(self, key: bytes, default: Any = None) -> Any:
        """ Lookup the given key and return the associated value,
            or the default if the key is not found. """
        value = self._root.lookup(key)
        return default if value is None else value

    def __getitem__(self, key: bytes) -> Any:
        """ Lookup in square bracket notation """
        value = self._root.lookup(key)
        if value is None:
            raise KeyError(key)
        return value

    def __len__(self) -> int:
        """ Return the number of unique keys within the trie """
        return self._cnt


class Indexer:

    """ A thin dict wrapper that maps unique keys to indices,
        and is invertible, i.e. can be converted to a index->key map """

    def __init__(self) -> None:
        self._d: Dict[Any, Any] = dict()

    def add(self, s: Any) -> int:
        try:
            return self._d[s]
        except KeyError:
            ix = len(self._d)
            self._d[s] = ix
            return ix

    def invert(self) -> None:
        """ Invert the index, so it is index->key instead of key->index """
        self._d = {v: k for k, v in self._d.items()}

    def __len__(self) -> int:
        return len(self._d)

    def __getitem__(self, key: Any) -> Any:
        return self._d[key]

    def get(self, key: Any, default: Any = None) -> Any:
        return self._d.get(key, default)

    def __str__(self) -> str:
        return str(self._d)


class BIN_Compressor:

    """ This class generates a compressed binary file from plain-text
        dictionary data. The input plain-text file is assumed to be coded
        in UTF-8 and have five columns, delimited by semicolons (';'), i.e.:

        (Icelandic) stofn;utg;ordfl;fl;ordmynd;beyging
        (English)   stem;version;category;subcategory;form;meaning

        The compression is not particularly intensive, as there is a
        tradeoff between the compression level and lookup speed. The
        resulting binary file is assumed to be read completely into
        memory as a BLOB and usable directly for lookup without further
        unpacking into higher-level data structures. See the BIN_Compressed
        class for the lookup code.

        Note that all text strings and characters in the binary BLOB
        are in Latin-1 encoding, and Latin-1 ordinal numbers are
        used directly as sort keys.

        To help the packing of common Trie nodes (single-character ones),
        a mapping of the source alphabet to 7-bit indices is used.
        This means that the source alphabet can contain no more than
        127 characters (ordinal 0 is reserved).

        The current set of possible subcategories is as follows:

            heö, alm, ism, föð, móð, fyr, bibl, gæl, lönd, gras, efna, tölv, lækn,
            örn, tón, natt, göt, lög, íþr, málfr, tími, við, fjár, bíl, ffl, mat,
            bygg, tung, erl, hetja, bær, þor, mvirk, brag, jard, stærð, hug, erm,
            mæl, titl, gjald, stja, dýr, hann, ætt, ob, entity, spurn

    """

    def __init__(self) -> None:
        self._forms = Trie()        # ordmynd
        self._stems = Indexer()     # stofn
        self._meanings = Indexer()  # beyging
        self._subcats = Indexer()   # fl
        self._alphabet: Set[int] = set()
        self._alphabet_bytes = bytes()
        # map form index -> { (stem_ix, meaning_ix) }
        self._lookup_form: Dict[int, Set[Tuple[int, int]]] = defaultdict(set)
        # map stem index -> { case: { form } }
        self._lookup_stem: Dict[int, Dict[bytes, Set[bytes]]] = defaultdict(
            lambda: defaultdict(set)
        )
        # Count of stem word categories
        self._stem_cat_count: Dict[str, int] = defaultdict(int)
        # Count of word forms for each case for each stem
        self._canonical_count: Dict[bytes, int] = defaultdict(int)
        # map declension pattern -> { offset }
        self._case_variants: Dict[bytes, int] = dict()

    def read(self, fnames: Iterable[str]) -> None:
        """ Read the given .csv text files in turn and add them to the
            compressed data structures """
        cnt = 0
        stem_cnt = -1
        max_wix = 0
        start_time = time.time()
        for fname in fnames:
            print("Reading file '{0}'...\n".format(fname))
            with open(fname, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line[0] == "#":
                        # Empty line or comment: skip
                        continue
                    t = line.split(";")
                    s_stem, wid, s_ordfl, s_fl, s_form, s_meaning = t
                    # Silently skip word forms with spaces in them
                    if " " in s_form:
                        continue
                    assert " " not in line
                    # Skip this if present in _BIN_DELETIONS,
                    # or if the stem is capitalized differently than the word form
                    # (which is a bug in BÍN)
                    if (s_stem, s_ordfl, s_fl) in _BIN_DELETIONS or (
                        s_stem[0].isupper() != s_form[0].isupper()
                    ):
                        print(
                            "Skipping {stem} {wid} {ordfl} {fl} {form} {meaning}".format(
                                stem=s_stem,
                                wid=wid,
                                ordfl=s_ordfl,
                                fl=s_fl,
                                form=s_form,
                                meaning=s_meaning,
                            )
                        )
                        continue
                    # Convert uninflectable number words to "töl" for compatibility
                    if s_ordfl == "to" and s_meaning == "OBEYGJANLEGT":
                        s_ordfl = "töl"
                    # Convert uninflectable indicator to "-" for compatibility
                    if s_meaning == "OBEYGJANLEGT":
                        s_meaning = "-"
                    # Convert "afn" (reflexive pronoun) to "abfn" for compatibility
                    if s_ordfl == "afn":
                        s_ordfl = "abfn"
                    # Convert "rt" (ordinal number) to "lo" (adjective)
                    # for compatibility
                    if s_ordfl == "rt":
                        s_ordfl = "lo"
                    # Apply a fix if we have one for this
                    # particular (stem, ordfl) combination
                    s_fl = _BIN_ERRATA.get((s_stem, s_ordfl), s_fl)
                    stem = s_stem.encode("latin-1")
                    ordfl = s_ordfl.encode("latin-1")
                    fl = s_fl.encode("latin-1")
                    form = s_form.encode("latin-1")
                    meaning = s_meaning.encode("latin-1")
                    self._alphabet |= set(form)
                    # Map null (no string) in utg to -1
                    wix = int(wid) if wid else -1
                    cix = self._subcats.add(fl)
                    if wix > max_wix:
                        max_wix = wix
                    six = self._stems.add((stem, wix, cix))
                    if six > stem_cnt:
                        # New stem, not seen before: count its category (ordfl)
                        self._stem_cat_count[s_ordfl] += 1
                        stem_cnt = six
                    fix = self._forms.add(form)  # Add to a trie
                    mix = self._meanings.add((ordfl, meaning))
                    self._lookup_form[fix].add((six, mix))
                    case_forms = self._lookup_stem[six]
                    for case in CASES_LATIN:
                        if case in meaning:
                            # Store each case with the stem
                            if form not in case_forms[case]:
                                case_forms[case].add(form)
                                self._canonical_count[case] += 1
                    cnt += 1
                    # Progress indicator
                    if cnt % 10000 == 0:
                        print(cnt, end="\r")
        print("{0} done\n".format(cnt))
        print("Time: {0:.1f} seconds".format(time.time() - start_time))
        print("Highest utg (wix) is {0}".format(max_wix))
        self._stems.invert()
        self._meanings.invert()
        self._subcats.invert()
        # Convert alphabet set to contiguous byte array, sorted by ordinal
        self._alphabet_bytes = bytes(sorted(self._alphabet))

    def print_stats(self) -> None:
        """ Print a few key statistics about the dictionary """
        print("Forms are {0}".format(len(self._forms)))
        print("Stems are {0}".format(len(self._stems)))
        print("They are distributed as follows:")
        for key, val in self._stem_cat_count.items():
            print("   {0:6s} {1:8d}".format(key, val))
        for index, case in enumerate(
            ("Nominative", "Accusative", "Dative", "Possessive")
        ):
            print(
                "{0} forms associated with stems are {1}".format(
                    case, self._canonical_count[CASES_LATIN[index]]
                )
            )
        print("Subcategories are {0}".format(len(self._subcats)))
        print("Meanings are {0}".format(len(self._meanings)))
        print("The alphabet is '{0!r}'".format(self._alphabet_bytes))
        print("It contains {0} characters".format(len(self._alphabet_bytes)))

    def lookup(self, form: str) -> List[MeaningTuple]:
        """ Test lookup from uncompressed data """
        form_latin = form.encode("latin-1")
        try:
            values = self._lookup_form[self._forms[form_latin]]
            # Obtain the stem and meaning tuples corresponding to the word form
            result = [(self._stems[six], self._meanings[mix]) for six, mix in values]
            # Convert to Unicode and return a 5-tuple
            # (stofn, utg, ordfl, fl, ordmynd, beyging)
            return [
                (
                    s[0].decode("latin-1"),  # stofn
                    s[1],                    # utg
                    m[0].decode("latin-1"),  # ordfl
                    self._subcats[s[2]].decode("latin-1"),  # fl
                    form,                    # ordmynd
                    m[1].decode("latin-1"),  # beyging
                )
                for s, m in result
            ]
        except KeyError:
            return []

    def lookup_forms(self, form: str, case: str = "NF") -> List[Tuple[str, str]]:
        """ Test lookup of all forms having the same stem as the given form """
        form_latin = form.encode("latin-1")
        case_latin = case.encode("latin-1")
        try:
            values = self._lookup_form[self._forms[form_latin]]
            # Obtain the stem and meaning tuples corresponding to the word form
            v = []
            # Go through the distinct stems found for this word form
            for six in set(v[0] for v in values):
                # Look at all forms of this stem that may be canonical
                if six in self._lookup_stem and case in self._lookup_stem[six]:
                    for canonical in self._lookup_stem[six][case_latin]:
                        for s, m in self._lookup_form[self._forms[canonical]]:
                            if s == six:
                                b = self._meanings[m][1]
                                if case_latin in b:
                                    # Nominative
                                    v.append((b, canonical))
            return [(m.decode("latin-1"), f.decode("latin-1")) for m, f in v]
        except KeyError:
            return []

    def write_forms(self, f: IO, alphabet: bytes, lookup_map: List[int]) -> None:
        """ Write the forms trie contents to a packed binary stream """
        # We assume that the alphabet can be represented in 7 bits
        assert len(alphabet) + 1 < 2 ** 7
        todo = []
        node_cnt = 0
        single_char_node_count = 0
        multi_char_node_count = 0
        no_child_node_count = 0

        def write_node(node: _Node, parent_loc: int) -> None:
            """ Write a single node to the packed binary stream,
                and fix up the parent's pointer to the location
                of this node """
            loc = f.tell()
            val = 0x007FFFFF if node.value is None else lookup_map[node.value]
            assert val < 2 ** 23
            nonlocal node_cnt, single_char_node_count, multi_char_node_count
            nonlocal no_child_node_count
            node_cnt += 1
            childless_bit = 0 if node.children else 0x40000000
            if len(node.fragment) <= 1:
                # Single-character fragment:
                # Pack it into 32 bits, with the high bit
                # being 1, the childless bit following it,
                # the fragment occupying the next 7 bits,
                # and the value occupying the remaining 23 bits
                if len(node.fragment) == 0:
                    chix = 0
                else:
                    chix = alphabet.index(node.fragment[0]) + 1
                assert chix < 2 ** 7
                f.write(
                    UINT32.pack(
                        0x80000000 | childless_bit | (chix << 23) | (val & 0x007FFFFF)
                    )
                )
                single_char_node_count += 1
                b = None
            else:
                # Multi-character fragment:
                # Store the value first, in 32 bits, and then
                # the fragment bytes with a trailing zero, padded to 32 bits
                f.write(UINT32.pack(childless_bit | (val & 0x007FFFFF)))
                b = node.fragment
                multi_char_node_count += 1
            # Write the child nodes, if any
            if node.children:
                f.write(UINT32.pack(len(node.children)))
                for child in node.children:
                    todo.append((child, f.tell()))
                    # Write a placeholder - will be overwritten
                    f.write(UINT32.pack(0xFFFFFFFF))
            else:
                no_child_node_count += 1
            if b is not None:
                f.write(struct.pack("{0}s0I".format(len(b) + 1), b))
            if parent_loc > 0:
                # Fix up the parent
                end = f.tell()
                f.seek(parent_loc)
                f.write(UINT32.pack(loc))
                f.seek(end)

        write_node(self._forms.root, 0)
        while todo:
            write_node(*todo.pop())

        print(
            "Written {0} nodes, thereof {1} single-char nodes and {2} multi-char.".format(
                node_cnt, single_char_node_count, multi_char_node_count
            )
        )
        print("Childless nodes are {0}.".format(no_child_node_count))

    def write_binary(self, fname: str) -> None:
        """ Write the compressed structure to a packed binary file """
        print("Writing file '{0}'...".format(fname))
        # Create a byte buffer stream
        f = io.BytesIO()

        # Version header
        f.write(BIN_COMPRESSOR_VERSION)

        # Placeholders for pointers to the major sections of the file
        mapping_offset = f.tell()
        f.write(UINT32.pack(0))
        forms_offset = f.tell()
        f.write(UINT32.pack(0))
        stems_offset = f.tell()
        f.write(UINT32.pack(0))
        variants_offset = f.tell()
        f.write(UINT32.pack(0))
        meanings_offset = f.tell()
        f.write(UINT32.pack(0))
        alphabet_offset = f.tell()
        f.write(UINT32.pack(0))
        subcats_offset = f.tell()
        f.write(UINT32.pack(0))

        def write_padded(b: bytes, n: int) -> None:
            assert len(b) <= n
            f.write(b + b"\x00" * (n - len(b)))

        def write_aligned(s: bytes) -> None:
            """ Write a string in the latin-1 charset, zero-terminated,
                padded to align on a DWORD (32-bit) boundary """
            f.write(struct.pack("{0}s0I".format(len(s) + 1), s))

        def write_spaced(s: bytes) -> None:
            """ Write a string in the latin-1 charset, zero-terminated,
                padded to align on a DWORD (32-bit) boundary """
            pad = 4 - (len(s) & 0x03)  # Always add at least one space
            f.write(s + b" " * pad)

        def write_string(s: bytes) -> None:
            """ Write a string preceded by a length byte, aligned to a
                DWORD (32-bit) boundary """
            f.write(struct.pack("B{0}s0I".format(len(s)), len(s), s))

        def compress_set(s: Set[bytes], base: Optional[bytes] = None) -> bytearray:
            """ Write a set of strings as a single compressed string. """

            # Each string is written as a variation of the previous
            # string, or the given base string, or the lexicographically
            # smallest string if no base is given. A variation consists
            # of a leading byte indicating the number of characters to be
            # cut off the end of the previous string, before appending the
            # following characters (prefixed by a length byte). The
            # set "hestur", "hest", "hesti", "hests" is thus encoded
            # like so, assuming "hestur" is the base (stem):
            # 1) The set is sorted to become the list
            #    "hest", "hesti", "hests", "hestur"
            # 2) "hest" is written as 2, 0, ""
            # 3) "hesti" is written as 0, 1, "i"
            # 4) "hests" is written as 1, 1, "s"
            # 5) "hestur" is written as 1, 2, "ur"
            # Note that a variation string such as this one, with four components,
            # is stored only once and then referred to by index. This saves
            # a lot of space since declension variants are identical
            # for many different stems.

            # Sort the set for maximum compression
            ss = sorted(s)
            b = bytearray()
            if base is None:
                # Use the first word in the set as a base
                last_w = ss[0]
                llast = len(last_w)
                b.append(len(last_w))
                b += last_w
                it = ss[1:]
            else:
                # Use the given base
                last_w = base
                llast = len(last_w)
                it = ss
            for w in it:
                lw = len(w)
                # Find number of common characters in front
                i = 0
                while i < llast and i < lw and last_w[i] == w[i]:
                    i += 1
                # Write the number of characters to cut off from the end
                b.append(llast - i)
                # Remember the last word
                last_w = w
                # Cut the common chars off
                w = w[i:]
                # Write the divergent part
                b.append(len(w))
                b += w
                llast = lw
            # End of list marker
            b.append(255)
            return b

        def fixup(ptr: int) -> None:
            """ Go back and fix up a previous pointer to point at the
                current offset in the stream """
            loc = f.tell()
            f.seek(ptr)
            f.write(UINT32.pack(loc))
            f.seek(loc)

        # Write the alphabet
        write_padded(b"[alphabet]", 16)
        fixup(alphabet_offset)
        f.write(UINT32.pack(len(self._alphabet_bytes)))
        write_aligned(self._alphabet_bytes)

        # Write the form to meaning mapping
        write_padded(b"[mapping]", 16)
        fixup(mapping_offset)
        lookup_map: List[int] = []
        cnt = 0
        # Loop through word forms
        for fix in range(len(self._forms)):
            lookup_map.append(cnt)
            # Each word form may have multiple meanings:
            # loop through them
            num_meanings = len(self._lookup_form[fix])
            for i, (six, mix) in enumerate(self._lookup_form[fix]):
                # Allocate 19 bits for the stem index
                assert six < 2 ** STEM_BITS
                # Allocate 12 bits for the meaning index
                assert mix < 2 ** MEANING_BITS
                # Mark the last meaning with the high bit
                last_indicator = 0x80000000 if i == num_meanings - 1 else 0
                f.write(UINT32.pack(last_indicator | (six << MEANING_BITS) | mix))
                cnt += 1

        # Write the the compact radix trie structure that
        # holds the word forms themselves, mapping them
        # to indices
        fixup(forms_offset)
        self.write_forms(f, self._alphabet_bytes, lookup_map)

        # Write the stems
        write_padded(b"[stems]", 16)
        lookup_map = []
        f.write(UINT32.pack(len(self._stems)))
        # Keep track of the number of bytes that will be written
        # to the case variant buffer
        num_sets_bytes = 0
        for ix in range(len(self._stems)):
            lookup_map.append(f.tell())
            # Squeeze the utg (word id) and subcategory index into the lower 31 bits.
            # The uppermost bit flags whether a canonical forms list is present.
            stem, utg, cix = self._stems[ix]
            utg += 1  # -1 becomes 0
            assert 0 <= utg < 2 ** UTG_BITS
            assert 0 <= cix < 2 ** SUBCAT_BITS
            bits = (utg << SUBCAT_BITS) | cix
            has_case_variants = False
            if self._lookup_stem.get(ix):
                # We have a set of word forms in four cases
                # for this stem
                bits |= 0x80000000
                has_case_variants = True
            f.write(UINT32.pack(bits))
            # Write the stem
            write_string(stem)
            # Write the set of word forms in four cases, compressed,
            # if this stem has such a set
            if has_case_variants:
                case_forms = self._lookup_stem[ix]
                sets = []
                for case in CASES_LATIN:
                    sets.append(compress_set(case_forms[case], base=stem))
                sets_bytes = b"".join(sets)
                # Have we seen this set of case variants before?
                case_variant_offset = self._case_variants.get(sets_bytes)
                if case_variant_offset is None:
                    # No: put it in the index, at the current offset
                    case_variant_offset = num_sets_bytes
                    num_sets_bytes += len(sets_bytes)
                    self._case_variants[sets_bytes] = case_variant_offset
                f.write(UINT32.pack(case_variant_offset))

        print("Different case variants are {0}".format(len(self._case_variants)))
        print(
            "Bytes used for case variants are {0}".format(
                num_sets_bytes + 4 * len(self._case_variants)
            )
        )

        # Write the index-to-offset mapping table for stems
        fixup(stems_offset)
        for offset in lookup_map:
            f.write(UINT32.pack(offset))

        # Write the case variants
        write_padded(b"[variants]", 16)
        fixup(variants_offset)
        # Sort the case variants array by increasing offset
        check = 0
        for sets_bytes, offset in sorted(
            self._case_variants.items(), key=lambda x: x[1]
        ):
            assert offset == check
            f.write(sets_bytes)
            check += len(sets_bytes)
        # Align to a 16-byte boundary
        align = check % 16
        if align:
            f.write(b"\x00" * (16 - align))

        # Write the meanings
        write_padded(b"[meanings]", 16)
        lookup_map = []
        num_meanings = len(self._meanings)
        f.write(UINT32.pack(num_meanings))
        for ix in range(num_meanings):
            lookup_map.append(f.tell())
            write_spaced(b" ".join(self._meanings[ix]))  # ordfl, beyging
        f.write(b" " * 24)

        # Write the index-to-offset mapping table for meanings
        fixup(meanings_offset)
        for offset in lookup_map:
            f.write(UINT32.pack(offset))

        # Write the subcategories, space-separated
        fixup(subcats_offset)
        b = b" ".join(self._subcats[ix] for ix in range(len(self._subcats)))
        f.write(UINT32.pack(len(b)))
        write_aligned(b)

        # Write the entire byte buffer stream to the compressed file
        with open(fname, "wb") as stream:
            stream.write(f.getvalue())


print("Welcome to the Greynir compressed vocabulary file generator")

# config_file = os.path.join(_PATH, "config", "BinErrata.conf")
config_file = "config/BinErrata.conf"
Settings.read(config_file, force=True)
_BIN_ERRATA = BinErrata.DICT
_BIN_DELETIONS = BinDeletions.SET

b = BIN_Compressor()
b.read(
    [
        os.path.join(_PATH, "resources", "ord.csv"),
        os.path.join(_PATH, "resources", "ord.add.csv"),
        os.path.join(_PATH, "resources", "ord.auka.csv"),
        os.path.join(_PATH, "resources", "systematic_additions.csv"),
        # os.path.join(_PATH, "resources", "other_errors.csv"),
        # os.path.join(_PATH, "resources", "systematic_errors.csv"),
    ]
)
b.print_stats()

filename = os.path.join(_PATH, "resources", BIN_COMPRESSED_FILE)
b.write_binary(filename)
print("Done; the compressed vocabulary was written to {0}".format(filename))

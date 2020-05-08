#!/usr/bin/env python
"""

    Reynir: Natural language processing for Icelandic

    BÍN compressor module

    Copyright (C) 2020 Miðeind ehf.
    Original author: Vilhjálmur Þorsteinsson

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


    This module compresses the BÍN dictionary from a ~300 MB uncompressed
    form into a compact binary representation. A radix trie data structure
    is used to store a mapping from word forms to integer indices.
    These indices are then used to look up word stems, categories and meanings.

    The data format is a tradeoff between storage space and retrieval
    speed. The resulting binary image is designed to be read into memory as
    a BLOB (via mmap) and used directly to look up word forms. No auxiliary
    dictionaries or other data structures should be needed. The binary image
    is shared between running processes.

    When invoked from the command line, bincompress.py reads the files
    ord.csv (original from BÍN), ord.auka.csv (additional vocabulary),
    and ord.add.csv (generated from config/Vocab.conf by the program utils/vocab.py
    in the Reynir repository).

    ************************************************************************

    IMPORTANT NOTE: It is not permitted to reverse engineer this file format
    in order to extract the original BÍN source data. This source data
    is subject to a license from 'Stofnun Árna Magnússonar í íslenskum fræðum'
    of Reykjavík, Iceland, which holds the copyright to 'Beygingarlýsing
    íslensks nútímamáls' (BÍN).

    The BÍN source data should only be obtained via the official application
    process at the bin.arnastofnun.is website and in accordance with the terms
    of that license, cf. http://bin.arnastofnun.is/gogn/skilmalar/

    Miðeind ehf. is a licensee of the BÍN data in accordance with the above
    mentioned terms. With reference to article 3 of the license terms, the data
    is redistributed in a proprietary binary format, exclusively as an integral
    part of the Reynir project. Any subsequent distribution of this
    data must be done only in full compliance with the original BÍN license
    terms.

"""

import os
import io
import time
import struct
import functools
import mmap
from collections import defaultdict

# pylint: disable=no-name-in-module
# pylint: disable=import-error
if __package__:
    # Import the CFFI wrapper for the bin.cpp C++ module (see also build_bin.py)
    # This is not needed for command-line invocation of bincompress.py,
    # i.e. when generating a new ord.compressed file.
    from ._bin import lib as bin_cffi, ffi  # type: ignore
else:
    from _bin import lib as bin_cffi, ffi  # type: ignore


_PATH = os.path.dirname(__file__) or "."

INT32 = struct.Struct("<i")
UINT32 = struct.Struct("<I")

# A dictionary of BÍN errata, loaded from BinErrata.conf if
# bincompress.py is invoked as a main program
_BIN_ERRATA = None
# A set of BÍN deletions, loaded from BinErrata.conf
_BIN_DELETIONS = None

CASES = ("NF", "ÞF", "ÞGF", "EF")
CASES_LATIN = tuple(case.encode("latin-1") for case in CASES)

GENDERS_SET = frozenset(("kk", "kvk", "hk"))

FILENAME = "ord.compressed"


class _Node:

    """ A Node within a Trie """

    def __init__(self, fragment, value):
        # The key fragment that leads into this node (and value)
        self.fragment = fragment
        self.value = value
        # List of outgoing nodes
        self.children = None

    def add(self, fragment, value):
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

    def lookup(self, fragment):
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

    def __str__(self):
        s = "Fragment: '{0}', value '{1}'\n".format(self.fragment, self.value)
        c = ["   {0}".format(child) for child in self.children] if self.children else []
        return s + "\n".join(c)


class Trie:

    """ Wrapper class for a radix (compact) trie data structure.
        Each node in the trie contains a prefix string, leading
        to its children. """

    def __init__(self, root_fragment=b""):
        self._cnt = 0
        self._root = _Node(root_fragment, None)

    @property
    def root(self):
        return self._root

    def add(self, key, value=None):
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

    def get(self, key, default=None):
        """ Lookup the given key and return the associated value,
            or the default if the key is not found. """
        value = self._root.lookup(key)
        return default if value is None else value

    def __getitem__(self, key):
        """ Lookup in square bracket notation """
        value = self._root.lookup(key)
        if value is None:
            raise KeyError(key)
        return value

    def __len__(self):
        """ Return the number of unique keys within the trie """
        return self._cnt


class Indexer:

    """ A thin dict wrapper that maps unique keys to indices,
        and is invertible, i.e. can be converted to a index->key map """

    def __init__(self):
        self._d = dict()

    def add(self, s):
        try:
            return self._d[s]
        except KeyError:
            ix = len(self._d)
            self._d[s] = ix
            return ix

    def invert(self):
        """ Invert the index, so it is index->key instead of key->index """
        self._d = {v: k for k, v in self._d.items()}

    def __len__(self):
        return len(self._d)

    def __getitem__(self, key):
        return self._d[key]

    def get(self, key, default=None):
        return self._d.get(key, default)

    def __str__(self):
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

    """

    VERSION = b"Reynir 001.04.00"
    assert len(VERSION) == 16

    def __init__(self):
        self._forms = Trie()  # ordmynd
        self._stems = Indexer()  # stofn
        self._meanings = Indexer()  # beyging
        self._alphabet = set()
        # map form index -> { (stem, meaning) }
        self._lookup_form = defaultdict(set)
        # map stem index -> { case: { form } }
        self._lookup_stem = defaultdict(lambda: defaultdict(set))
        # Count of stem word categories
        self._stem_cat_count = defaultdict(int)
        # Count of word forms for each case for each stem
        self._canonical_count = defaultdict(int)
        # map declension pattern -> { offset }
        self._case_variants = dict()

    def read(self, fnames):
        """ Read the given .csv text files in turn and add them to the
            compressed data structures """
        cnt = 0
        stem_cnt = -1
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
                    stem, wid, ordfl, fl, form, meaning = t
                    # Skip this if present in _BIN_DELETIONS
                    if (stem, ordfl, fl) in _BIN_DELETIONS or " " in line:
                        print(
                            "Skipping {stem} {wid} {ordfl} {fl} {form} {meaning}"
                            .format(
                                stem=stem,
                                wid=wid,
                                ordfl=ordfl,
                                fl=fl,
                                form=form,
                                meaning=meaning,
                            )
                        )
                        continue
                    # Apply a fix if we have one for this
                    # particular (stem, ordfl) combination
                    fl = _BIN_ERRATA.get((stem, ordfl), fl)
                    stem = stem.encode("latin-1")
                    ordfl = ordfl.encode("latin-1")
                    fl = fl.encode("latin-1")
                    form = form.encode("latin-1")
                    meaning = meaning.encode("latin-1")
                    # Cut off redundant ending of meaning (beyging),
                    # e.g. ÞGF2
                    if meaning and meaning[-1] in {b"2", b"3"}:
                        meaning = meaning[:-1]
                    self._alphabet |= set(form)
                    # Map null (no string) in utg to -1
                    wix = int(wid) if wid else -1
                    six = self._stems.add((stem, wix))
                    if six > stem_cnt:
                        # New stem, not seen before: count its category (ordfl)
                        self._stem_cat_count[t[2]] += 1
                        stem_cnt = six
                    fix = self._forms.add(form)  # Add to a trie
                    mix = self._meanings.add((ordfl, fl, meaning))
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
        self._stems.invert()
        self._meanings.invert()
        # Convert alphabet set to contiguous byte array, sorted by ordinal
        self._alphabet = bytes(sorted(self._alphabet))

    def print_stats(self):
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
        print("Meanings are {0}".format(len(self._meanings)))
        print("The alphabet is '{0}'".format(self._alphabet))
        print("It contains {0} characters".format(len(self._alphabet)))

    def lookup(self, form):
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
                    s[1],  # utg
                    m[0].decode("latin-1"),  # ordfl
                    m[1].decode("latin-1"),  # fl
                    form,  # ordmynd
                    m[2].decode("latin-1"),  # beyging
                )
                for s, m in result
            ]
        except KeyError:
            return []

    def lookup_forms(self, form, case="NF"):
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
                    for can in self._lookup_stem[six][case]:
                        for s, m in self._lookup_form[self._forms[can]]:
                            if s == six:
                                b = self._meanings[m][2]
                                if case_latin in b:
                                    # Nominative
                                    v.append((b, can))
            return [(m.decode("latin-1"), f.decode("latin-1")) for m, f in v]
        except KeyError:
            return []

    def write_forms(self, f, alphabet, lookup_map):
        """ Write the forms trie contents to a packed binary stream """
        # We assume that the alphabet can be represented in 7 bits
        assert len(alphabet) + 1 < 2 ** 7
        todo = []
        node_cnt = 0
        single_char_node_count = 0
        multi_char_node_count = 0
        no_child_node_count = 0

        def write_node(node, parent_loc):
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

    def write_binary(self, fname):
        """ Write the compressed structure to a packed binary file """
        print("Writing file '{0}'...".format(fname))
        # Create a byte buffer stream
        f = io.BytesIO()

        # Version header
        f.write(self.VERSION)

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

        def write_padded(b, n):
            assert len(b) <= n
            f.write(b + b"\x00" * (n - len(b)))

        def write_aligned(s):
            """ Write a string in the latin-1 charset, zero-terminated,
                padded to align on a DWORD (32-bit) boundary """
            f.write(struct.pack("{0}s0I".format(len(s) + 1), s))

        def write_spaced(s):
            """ Write a string in the latin-1 charset, zero-terminated,
                padded to align on a DWORD (32-bit) boundary """
            pad = 4 - (len(s) & 0x03)  # Always add at least one space
            f.write(s + b" " * pad)

        def write_string(s):
            """ Write a string preceded by a length byte, aligned to a
                DWORD (32-bit) boundary """
            f.write(struct.pack("B{0}s0I".format(len(s)), len(s), s))

        def compress_set(s, base=None):
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

        def fixup(ptr):
            """ Go back and fix up a previous pointer to point at the
                current offset in the stream """
            loc = f.tell()
            f.seek(ptr)
            f.write(UINT32.pack(loc))
            f.seek(loc)

        # Write the alphabet
        write_padded(b"[alphabet]", 16)
        fixup(alphabet_offset)
        f.write(UINT32.pack(len(self._alphabet)))
        write_aligned(self._alphabet)

        # Write the form to meaning mapping
        write_padded(b"[mapping]", 16)
        fixup(mapping_offset)
        lookup_map = []
        cnt = 0
        # Loop through word forms
        for fix in range(len(self._forms)):
            lookup_map.append(cnt)
            # Each word form may have multiple meanings:
            # loop through them
            num_meanings = len(self._lookup_form[fix])
            for i, (six, mix) in enumerate(self._lookup_form[fix]):
                # Allocate 20 bits for the stem index
                assert six < 2 ** 20
                # Allocate 11 bits for the meaning index
                assert mix < 2 ** 11
                # Mark the last meaning with the high bit
                last_indicator = 0x80000000 if i == num_meanings - 1 else 0
                f.write(UINT32.pack(last_indicator | (six << 11) | mix))
                cnt += 1

        # Write the the compact radix trie structure that
        # holds the word forms themselves, mapping them
        # to indices
        fixup(forms_offset)
        self.write_forms(f, self._alphabet, lookup_map)

        # Write the stems
        write_padded(b"[stems]", 16)
        lookup_map = []
        f.write(UINT32.pack(len(self._stems)))
        # Keep track of the number of bytes that will be written
        # to the case variant buffer
        num_sets_bytes = 0
        for ix in range(len(self._stems)):
            lookup_map.append(f.tell())
            # Squeeze the word id into the lower 31 bits
            # and a flag for whether a canonical forms list
            # is present into the uppermost bit
            wid = self._stems[ix][1] + 1  # -1 becomes 0
            has_case_variants = False
            if self._lookup_stem.get(ix):
                # We have a set of word forms in four cases
                # for this stem
                wid |= 0x80000000
                has_case_variants = True
            f.write(UINT32.pack(wid))
            # Write the stem
            stem = self._stems[ix][0]
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
        f.write(UINT32.pack(len(self._meanings)))
        for ix in range(len(self._meanings)):
            lookup_map.append(f.tell())
            write_spaced(b" ".join(self._meanings[ix]))  # ordfl, fl, beyging
        f.write(b" " * 24)
        fixup(meanings_offset)

        # Write the index-to-offset mapping table for meanings
        for offset in lookup_map:
            f.write(UINT32.pack(offset))

        # Write the entire byte buffer stream to the compressed file
        with open(fname, "wb") as stream:
            stream.write(f.getvalue())


class BIN_Compressed:

    """ A wrapper for the compressed binary dictionary,
        allowing read-only lookups of word forms """

    if __package__:
        # Make sure that the ord.compressed filename is
        # unpacked and ready for use
        import pkg_resources

        # Note: the resource path below should NOT use os.path.join()
        _FNAME = pkg_resources.resource_filename(__name__, "resources/" + FILENAME)
    else:
        _FNAME = os.path.join(_PATH, "resources", FILENAME)

    # Unique indicator used to signify no utg field
    # (needed since None is a valid utg value)
    NoUtg = object()

    def __init__(self):
        """ We use a memory map, provided by the mmap module, to
            directly map the compressed file into memory without
            having to read it into a byte buffer. This also allows
            the same memory map to be shared between processes. """
        with open(self._FNAME, "rb") as stream:
            self._b = mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ)
        # Check that the file version matches what we expect
        assert (
            self._b[0:16] == BIN_Compressor.VERSION
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
        self._alphabet = bytes(
            self._b[alphabet_offset + 4 : alphabet_offset + 4 + alphabet_length]
        )
        # Create a CFFI buffer object pointing to the memory map
        self._mmap_buffer = ffi.from_buffer(self._b)

    def _UINT(self, offset):
        """ Return the 32-bit UINT at the indicated offset
            in the memory-mapped buffer """
        return self._partial_UINT(offset)[0]

    def close(self):
        """ Close the memory map """
        if self._b is not None:
            self._mappings = None
            self._stems = None
            self._meanings = None
            self._alphabet = None
            self._mmap_buffer = None
            self._b.close()
            self._b = None

    def meaning(self, ix):
        """ Find and decode a meaning (ordfl, fl, beyging) tuple,
            given its index """
        off, = UINT32.unpack_from(self._meanings, ix * 4)
        b = bytes(self._b[off : off + 24])
        s = b.decode("latin-1").split(maxsplit=4)
        return tuple(s[0:3])  # ordfl, fl, beyging

    def stem(self, ix):
        """ Find and decode a stem (utg, stofn) tuple, given its index """
        off, = UINT32.unpack_from(self._stems, ix * 4)
        wid = self._UINT(off)
        # The id (utg) is stored in the lower 31 bits, after adding 1
        wid = (wid & 0x7FFFFFFF) - 1
        p = off + 4
        lw = self._b[p]  # Length byte
        p += 1
        b = bytes(self._b[p : p + lw])
        return b.decode("latin-1"), wid  # stofn, utg

    def case_variants(self, ix, case=b"NF"):
        """ Return all word forms having the given case, that are
            associated with the stem whose index is in ix """

        def read_set(p, base=None):
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

        off, = UINT32.unpack_from(self._stems, ix * 4)
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

    def _mapping_cffi(self, word):
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

    def _raw_lookup(self, word):
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
            stem_meaning, = self._partial_mappings(mapping * 4)
            stem_index = (stem_meaning >> 11) & (2 ** 20 - 1)
            meaning_index = stem_meaning & (2 ** 11 - 1)
            result.append((stem_index, meaning_index))
            if stem_meaning & 0x80000000:
                # Last mapping indicator: we're done
                break
            mapping += 1
        return result

    def contains(self, word):
        """ Returns True if the trie contains the given word form"""
        return self._mapping_cffi(word) is not None

    def __contains__(self, word):
        """ Returns True if the trie contains the given word form"""
        return self._mapping_cffi(word) is not None

    def lookup(self, word, cat=None, stem=None, utg=NoUtg, beyging_func=None):
        """ Returns a list of BÍN meanings for the given word form,
            eventually constrained to the requested word category,
            stem, utg number and/or the given beyging_func filter function,
            which is called with the beyging field as a parameter. """
        # Category set
        if cat is None:
            cats = None
        elif cat == "no":
            # Allow a cat of "no" to mean a noun of any gender
            cats = GENDERS_SET
        else:
            cats = {cat}
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
        self, word, case, *,
        singular=False, indefinite=False,
        cat=None, stem=None, utg=NoUtg,
        beyging_filter=None
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

        result = set()
        case_latin = case.encode("latin-1")
        # Category set
        if cat is None:
            cats = None
        elif cat == "no":
            # Allow a cat of "no" to mean a noun of any gender
            cats = GENDERS_SET
        else:
            cats = {cat}
        wanted_beyging = ""

        def simplify_beyging(beyging):
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

        def beyging_func(beyging):
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

    def raw_nominative(self, word):
        """ Returns a set of all nominative forms of the stems of the given word form.
            Note that the word form is case-sensitive. """
        result = set()
        for stem_index, _ in self._raw_lookup(word):
            for c_latin in self.case_variants(stem_index):
                c = c_latin.decode("latin-1")
                # Make sure we only include each result once
                result.update(m for m in self.lookup(c) if "NF" in m[5])
        return result

    def nominative(self, word, **options):
        """ Returns a set of all nominative forms of the stems of the given word form,
            subject to the constraints in **options.
            Note that the word form is case-sensitive. """
        return self.lookup_case(word, "NF", **options)

    def accusative(self, word, **options):
        """ Returns a set of all accusative forms of the stems of the given word form,
            subject to the given constraints on the beyging field.
            Note that the word form is case-sensitive. """
        return self.lookup_case(word, "ÞF", **options)

    def dative(self, word, **options):
        """ Returns a set of all dative forms of the stems of the given word form,
            subject to the given constraints on the beyging field.
            Note that the word form is case-sensitive. """
        return self.lookup_case(word, "ÞGF", **options)

    def genitive(self, word, **options):
        """ Returns a set of all genitive forms of the stems of the given word form,
            subject to the given constraints on the beyging field.
            Note that the word form is case-sensitive. """
        return self.lookup_case(word, "EF", **options)


if __name__ == "__main__":
    # When run as a main program, generate a compressed binary file
    print("Welcome to the Reynir compressed vocabulary file generator")

    # Read BÍN errata and deletions from BinErrata.conf
    from settings import Settings, BinErrata, BinDeletions  # type: ignore

    Settings.read(os.path.join(_PATH, "config", "BinErrata.conf"))
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

    filename = os.path.join(_PATH, "resources", FILENAME)
    b.write_binary(filename)
    print("Done; the compressed vocabulary was written to {0}".format(filename))

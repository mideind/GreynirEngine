#!/usr/bin/env python
"""

    Reynir: Natural language processing for Icelandic

    BÍN compressor module

    Copyright (C) 2018 Miðeind ehf.
    Author: Vilhjálmur Þorsteinsson

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
from collections import defaultdict


_PATH = os.path.dirname(__file__) or "."

INT32 = struct.Struct("<i")
UINT32 = struct.Struct("<I")


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
                return child.lookup(fragment[len(child.fragment):])
        # No route matches: the key was not found
        return None

    def __str__(self):
        s = "Fragment: '{0}', value '{1}'\n".format(self.fragment, self.value)
        c = ["   {0}".format(child) for child in self.children] if self.children else []
        return s + "\n".join(c)

    def __hash__(self):
        return id(self).__hash__()

    def __eq__(self, other):
        return id(self) == id(other)


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

    VERSION = b'Reynir 001.03.00'
    assert len(VERSION) == 16

    def __init__(self):
        self._forms = Trie()        # ordmynd
        self._stems = Indexer()     # stofn
        self._meanings = Indexer()  # beyging
        self._alphabet = set()
        # map form index -> [ (stem, cat, tcat, meaning) ]
        self._lookup_form = defaultdict(list)
        # map stem index -> { form }
        self._lookup_stem = defaultdict(set)
        # Count of stem word categories
        self._stem_cat_count = defaultdict(int)
        self._canonical_count = 0

    def read(self, fnames):
        cnt = 0
        stem_cnt = -1
        start_time = time.time()
        for fname in fnames:
            print("Reading file '{0}'...\n".format(fname))
            with open(fname, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    t = line.split(";")
                    stem, wid, ordfl, fl, form, meaning = t
                    stem = stem.encode("latin-1")
                    ordfl = ordfl.encode("latin-1")
                    fl = fl.encode("latin-1")
                    form = form.encode("latin-1")
                    m = meaning
                    meaning = meaning.encode("latin-1")
                    # Cut off redundant ending of meaning (beyging),
                    # e.g. ÞGF2
                    if meaning and meaning[-1] in {b'2', b'3'}:
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
                    self._lookup_form[fix].append((six, mix))
                    if "NF" in m:
                        # Nominative case: store with the stem as a canonical form
                        if form not in self._lookup_stem[six]:
                            self._lookup_stem[six].add(form)
                            self._canonical_count += 1
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
        print("Nominative forms associated with stems are {0}".format(self._canonical_count))
        print("Meanings are {0}".format(len(self._meanings)))
        print("The alphabet is '{0}'".format(self._alphabet))
        print("It contains {0} characters".format(len(self._alphabet)))

    def lookup(self, form):
        """ Test lookup from uncompressed data """
        form_latin = form.encode("latin-1")
        try:
            values = self._lookup_form[self._forms[form_latin]]
            # Obtain the stem and meaning tuples corresponding to the word form
            result = [
                (self._stems[six], self._meanings[mix])
                for six, mix in values
            ]
            # Convert to Unicode and return a 5-tuple (stofn, utg, ordfl, fl, ordmynd, beyging)
            return [
                (
                    s[0].decode("latin-1"),     # stofn
                    s[1],                       # utg
                    m[0].decode("latin-1"),     # ordfl
                    m[1].decode("latin-1"),     # fl
                    form,                       # ordmynd
                    m[2].decode("latin-1")      # beyging
                )
                for s, m in result
            ]
        except KeyError:
            return []

    def lookup_forms(self, form):
        """ Test lookup of all forms having the same stem as the given form """
        form_latin = form.encode("latin-1")
        try:
            values = self._lookup_form[self._forms[form_latin]]
            # Obtain the stem and meaning tuples corresponding to the word form
            v = []
            # Go through the distinct stems found for this word form
            for six in set(v[0] for v in values):
                # Look at all forms of this stem that may be canonical
                if six in self._lookup_stem:
                    for can in self._lookup_stem[six]:
                        for s, m in self._lookup_form[self._forms[can]]:
                            if s == six:
                                b = self._meanings[m][2]
                                if b"NF" in b:
                                    # Nominative
                                    v.append((b, can))
            return [
                (m.decode("latin-1"), f.decode("latin-1"))
                for m, f in v
            ]
        except KeyError:
            return []

    def write_forms(self, f, alphabet, lookup_map):
        """ Write the forms trie contents to a packed binary stream """
        # We assume that the alphabet can be represented in 7 bits
        assert len(alphabet) + 1 < 2**7
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
            assert val < 2**23
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
                assert chix < 2**7
                f.write(
                    UINT32.pack(
                        0x80000000
                        | childless_bit
                        | (chix << 23)
                        | (val & 0x007FFFFF)
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
            "Written {0} nodes, thereof {1} single-char nodes and {2} multi-char."
            .format(node_cnt, single_char_node_count, multi_char_node_count)
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
            f.write(s + b' ' * pad)

        def write_string(s):
            """ Write a string preceded by a length byte, aligned to a
                DWORD (32-bit) boundary """
            f.write(struct.pack("B{0}s0I".format(len(s)), len(s), s))

        def write_set(s):
            """ Write a set of strings as a single compressed string """
            # Sort the set for maximum compression
            assert len(s) > 0
            ss = sorted(s)
            b = bytearray()
            last_w = ss[0]
            llast = len(last_w)
            b.append(len(last_w))
            b += last_w
            for w in ss[1:]:
                lw = len(w)
                # Find number of common characters in front
                i = 0
                while i < llast and i < lw and last_w[i] == w[i]:
                    i += 1
                # Write the number of common characters
                b.append(i)
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
            # Append padding to a DWORD (32-bit) boundary, if needed
            pad = 4 - (len(b) & 0x03)
            if 0 < pad < 4:
                b += b'\x00' * pad
            f.write(b)

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
                assert six < 2**20
                # Allocate 11 bits for the meaning index
                assert mix < 2**11
                # Mark the last meaning with the high bit
                last_indicator = 0x80000000 if i == num_meanings - 1 else 0
                f.write(UINT32.pack(last_indicator | (six << 11) | mix))
                cnt += 1

        # Write the the compact radix trie structure
        # that holds the word forms themselves, mapping them
        # to indices
        fixup(forms_offset)
        self.write_forms(f, self._alphabet, lookup_map)

        # Write the stems
        write_padded(b"[stems]", 16)
        lookup_map = []
        f.write(UINT32.pack(len(self._stems)))
        for ix in range(len(self._stems)):
            lookup_map.append(f.tell())
            # Squeeze the word id into the lower 31 bits
            # and a flag for whether a canonical forms list
            # is present into the uppermost bit
            wid = self._stems[ix][1] + 1  # -1 becomes 0
            if ix in self._lookup_stem:
                wid |= 0x80000000
            f.write(UINT32.pack(wid))
            # Write the stem
            write_string(self._stems[ix][0])
            # Write the set of nominative word forms, compressed,
            # if this stem has such a set
            if ix in self._lookup_stem:
                write_set(self._lookup_stem[ix])
        fixup(stems_offset)

        # Write the index-to-offset mapping table for stems
        for offset in lookup_map:
            f.write(UINT32.pack(offset))

        # Write the meanings
        write_padded(b"[meanings]", 16)
        lookup_map = []
        f.write(UINT32.pack(len(self._meanings)))
        for ix in range(len(self._meanings)):
            lookup_map.append(f.tell())
            write_spaced(b' '.join(self._meanings[ix]))  # ordfl, fl, beyging
        f.write(b' ' * 24)
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

    BIN_COMPRESSED_FILE = os.path.join(_PATH, "resources", "ord.compressed")

    def _UINT(self, offset):
        return UINT32.unpack(self._b[offset:offset+4])[0]

    def __init__(self):
        """ We use a memory map, provided by the mmap module, to
            directly map the compressed file into memory without
            having to read it into a byte buffer. This also allows
            the same memory map to be shared between processes. """
        import mmap
        with open(self.BIN_COMPRESSED_FILE, "rb") as stream:
            self._b = mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ)
        assert self._b[0:16] == BIN_Compressor.VERSION
        mappings_offset, forms_offset, stems_offset, meanings_offset, alphabet_offset = (
            struct.unpack("<IIIII", self._b[16:36])
        )
        self._forms_offset = forms_offset
        self._mappings = self._b[mappings_offset:]
        self._stems = self._b[stems_offset:]
        self._meanings = self._b[meanings_offset:]
        # Cache the trie root header
        self._forms_root_hdr = self._UINT(forms_offset)
        # The alphabet header occupies the next 16 bytes
        # Read the alphabet length
        alphabet_length = self._UINT(alphabet_offset)
        self._alphabet = bytes(self._b[alphabet_offset+4:alphabet_offset + 4 + alphabet_length])

    def close(self):
        """ Close the memory map """
        if self._b is not None:
            self._mappings = None
            self._stems = None
            self._meanings = None
            self._alphabet = None
            self._b.close()
            self._b = None

    def meaning(self, ix):
        """ Find and decode a meaning (ordfl, fl, beyging) tuple,
            given its index """
        off, = UINT32.unpack(self._meanings[ix * 4:ix * 4 + 4])
        b = bytes(self._b[off:off+24])
        s = b.decode('latin-1').split(maxsplit=4)
        return tuple(s[0:3])  # ordfl, fl, beyging

    def stem(self, ix):
        """ Find and decode a stem (utg, stofn) tuple, given its index """
        off, = UINT32.unpack(self._stems[ix * 4:ix * 4 + 4])
        wid, = UINT32.unpack(self._b[off:off+4])
        # The id (utg) is stored in the lower 31 bits, after adding 1
        wid = (wid & 0x7FFFFFFF) - 1
        p = off + 4
        lw = self._b[p]  # Length byte
        p += 1
        b = bytes(self._b[p:p + lw])
        return b.decode('latin-1'), wid  # stofn, utg

    def canonicals(self, ix):
        """ Return all canonical word forms, i.e. forms with the nominative
            case, associated with the stem whose index is in ix """

        def read_set(p):
            """ Decompress a set of strings written by write_set() """
            lw = self._b[p]
            p += 1
            last_w = self._b[p: p + lw]
            p += lw
            c = [last_w]
            while True:
                common = self._b[p]
                if common == 255:
                    break
                p += 1
                lw = self._b[p]
                p += 1
                w = last_w[0:common] + self._b[p:p + lw]
                p += lw
                c.append(w)
                last_w = w
            return c

        off, = UINT32.unpack(self._stems[ix * 4:ix * 4 + 4])
        wid, = UINT32.unpack(self._b[off:off+4])
        # The id (utg) is stored in the lower 31 bits, after adding 1
        if wid & 0x80000000 == 0:
            # No canonicals associated with this stem
            return []
        # Skip past the stem itself
        p = off + 4
        lw = self._b[p]  # Length byte
        lw += 1
        if lw & 3:
            lw += 4 - (lw & 3)
        p += lw
        # Read the set of canonicals from the given offset
        return read_set(p)

    def _prepare(self, word):
        """ Return the latin-1 and compact-encoded forms of the word """
        # Map the word to Latin-1 as well as a
        # compact 7-bit-per-character representation
        try:
            word_latin = word.encode('latin-1')
            cword = bytes(self._alphabet.index(c) + 1 for c in word_latin)
        except (UnicodeEncodeError, ValueError):
            # The word contains a letter that is not in the Latin-1
            # or BÍN alphabets: it can't be in BÍN
            return 0, b"", b""
        return len(word), word_latin, cword

    def _raw_lookup(self, word):
        """ Look up the given word form via the radix trie,
            returning a list of stem and meaning indices """
        word_len, word_latin, cword = self._prepare(word)
        if word_len == 0:
            return []

        def _matches(node_offset, hdr, fragment_index):
            """ If the lookup fragment word[fragment_index:] matches the node,
                return the number of characters matched. Otherwise,
                return -1 if the node is lexicographically less than the
                lookup fragment, or 0 if the node is greater than the fragment.
                (The lexicographical ordering here is actually a comparison
                between the Latin-1 ordinal numbers of characters.) """
            if hdr & 0x80000000:
                # Single-character fragment
                chix = (hdr >> 23) & 0x7F
                if chix == cword[fragment_index]:
                    # Match
                    return 1
                return 0 if chix > cword[fragment_index] else -1
            if hdr & 0x40000000:
                # Childless node
                frag = node_offset + 4
            else:
                num_children = self._UINT(node_offset + 4)
                frag = node_offset + 8 + 4 * num_children
            matched = 0
            while (
                self._b[frag] != 0
                and (fragment_index + matched < word_len)
                and self._b[frag] == word_latin[fragment_index + matched]
            ):
                frag += 1
                matched += 1
            if self._b[frag] == 0:
                # Matched the entire fragment: success
                return matched
            if fragment_index + matched >= word_len:
                # The node is longer and thus greater than the fragment
                return 0
            return 0 if self._b[frag] > word_latin[fragment_index + matched] else -1

        def _lookup(node_offset, hdr, fragment_index):
            if fragment_index >= word_len:
                # We've arrived at our destination:
                # return the associated value (unless this is an interim node)
                value = hdr & 0x007FFFFF
                return None if value == 0x007FFFFF else value
            if hdr & 0x40000000:
                # Childless node: nowhere to go
                return None
            num_children = self._UINT(node_offset + 4)
            child_offset = node_offset + 8
            # Binary search for a matching child node
            lo = 0
            hi = num_children
            while hi > lo:
                mid = (lo + hi) // 2
                mid_loc = child_offset + mid * 4
                mid_offset = self._UINT(mid_loc)
                hdr = self._UINT(mid_offset)
                match_len = _matches(mid_offset, hdr, fragment_index)
                if match_len > 0:
                    return _lookup(mid_offset, hdr, fragment_index + match_len)
                if match_len < 0:
                    lo = mid + 1
                else:
                    hi = mid
            # No child route matches
            return None

        mapping = _lookup(self._forms_offset, self._forms_root_hdr, 0)
        if mapping is None:
            # Word not found in trie: return an empty list of meanings
            return []
        # Found the word in the trie; return potentially multiple meanings
        # Fetch the mapping-to-stem/meaning tuples
        result = []
        while True:
            stem_meaning, = UINT32.unpack(self._mappings[mapping * 4:mapping * 4 + 4])
            stem_index = (stem_meaning >> 11) & (2 ** 20 - 1)
            meaning_index = stem_meaning & (2 ** 11 - 1)
            result.append((stem_index, meaning_index))
            if stem_meaning & 0x80000000:
                # Last mapping indicator: we're done
                break
            mapping += 1
        return result

    def lookup(self, word):
        """ Returns a list of BÍN meanings for the given word form """
        result = []
        for stem_index, meaning_index in self._raw_lookup(word):
            stem, meaning = self.stem(stem_index), self.meaning(meaning_index)
            utg = None if stem[1] == -1 else stem[1]
            # stofn, utg, ordfl, fl, ordmynd, beyging
            result.append((stem[0], utg, meaning[0], meaning[1], word, meaning[2]))
        return result

    def nominative(self, word):
        """ Returns a set of all nominative forms of the stems of the given word form.
            Note that the word form is case-sensitive. """
        result = set()
        for stem_index, _ in self._raw_lookup(word):
            for c_latin in self.canonicals(stem_index):
                c = c_latin.decode("latin-1")
                # Make sure we only include each result once
                result.update(m for m in self.lookup(c) if "NF" in m[5])
        return result


if __name__ == "__main__":
    # When run as a main program, generate a compressed binary file
    print("Welcome to the Reynir compressed vocabulary file generator")
    b = BIN_Compressor()
    b.read(
        [
            os.path.join(_PATH, "resources", "ord.csv"),
            os.path.join(_PATH, "resources", "ord.add.csv")
        ]
    )
    b.print_stats()

    # print(b.lookup_forms("aðförin"))
    # print(b.lookup_forms("ekki"))
    # print(b.lookup_forms("fara"))
    # print(b.lookup_forms("bíllinn"))
    # print(b.lookup_forms("stór"))
    # print(b.lookup_forms("stóri"))
    # print(b.lookup_forms("ljótan"))

    # Tests
    # print(f"mín: {b.lookup('mín')}")
    # print(f"að: {b.lookup('að')}")
    # print(f"lama: {b.lookup('lama')}")
    # print(f"búa: {b.lookup('búa')}")
    # print(f"ekki: {b.lookup('ekki')}")
    # print(f"aðförin: {b.lookup('aðförin')}")
    # print(f"einkabílnum: {b.lookup('einkabílnum')}")
    b.write_binary(os.path.join(_PATH, "resources", "ord.compressed"))

"""

    Reynir: Natural language processing for Icelandic

    BIN database access module

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


    This module encapsulates access to the BIN (Beygingarlýsing íslensks nútímamáls)
    database of word forms, including lookup of abbreviations and basic strategies
    for handling missing words.

    The database is assumed to be packed into a compressed binary file,
    which is wrapped inside the bincompress.py module.

    Word meaning lookups are cached in Least Frequently Used (LFU) caches.

    This code must be thread safe.

"""

from functools import lru_cache
from collections import namedtuple

from tokenizer import Abbreviations

from .settings import AdjectiveTemplate, Meanings, StemPreferences, StaticPhrases
from .cache import LFU_Cache
from .dawgdictionary import Wordbase
from .bincompress import BIN_Compressed


# Size of LRU/LFU caches for word lookups
CACHE_SIZE = 512
CACHE_SIZE_MEANINGS = 2048 # Most common lookup function (meanings of a particular word form)
CACHE_SIZE_UNDECLINABLE = 2048

# Named tuple for word meanings fetched from the BÍN database (lexicon)
BIN_Meaning = namedtuple('BIN_Meaning', ['stofn', 'utg', 'ordfl', 'fl', 'ordmynd', 'beyging'])
# Compact string representation
BIN_Meaning.__str__ = BIN_Meaning.__repr__ = lambda self: "(stofn='{0}', {2}/{3}/{1}, ordmynd='{4}' {5})" \
    .format(self.stofn, self.utg, self.ordfl, self.fl, self.ordmynd, self.beyging)


class BIN_Db:

    """ Encapsulates the BÍN database of word forms """

    # Adjective endings
    _ADJECTIVE_TEST = "leg" # Check for adjective if word contains 'leg'

    # Word categories that are allowed to appear capitalized in the middle of sentences,
    # as a result of compound word construction
    _NOUNS = frozenset(("kk", "kvk", "hk"))

    # Singleton LFU caches for word meaning lookup
    _meanings_cache = LFU_Cache(maxsize = CACHE_SIZE_MEANINGS)

    # Singleton instance of BIN_Db, returned by get_db()
    _singleton = None

    @classmethod
    def get_db(cls):
        """ Return a session object that can be used in a with statement """

        class _BIN_Session:

            def __init__(self):
                pass

            def __enter__(self):
                """ Python context manager protocol """
                if cls._singleton is None:
                    cls._singleton = cls()
                return cls._singleton

            def __exit__(self, exc_type, exc_value, traceback):
                """ Python context manager protocol """
                # Return False to re-throw exception from the context, if any
                return False

        return _BIN_Session()

    @classmethod
    def cleanup(cls):
        """ Close singleton instance, if any """
        if cls._singleton:
            cls._singleton.close()
            cls._singleton = None

    def __init__(self):
        """ Initialize BIN database wrapper instance """
        # Cache descriptors for the lookup functions
        self._meanings_func = lambda key: self._meanings_cache.lookup(key, getattr(self, "meanings"))
        # Compressed BÍN wrapper
        # Throws IOError if the compressed file doesn't exist
        self._compressed_bin = BIN_Compressed()

    def close(self):
        """ Close the BIN_Compressed() instance """
        if self._compressed_bin is not None:
            self._compressed_bin.close()
            self._compressed_bin = None

    def _meanings(self, w):
        """ Low-level fetch of the BIN meanings of a given word """
        # Route the lookup request to the compressed binary file
        g = self._compressed_bin.lookup(w)
        # If an error occurs, this returns None.
        # If the lookup doesn't yield any results, [] is returned.
        # Otherwise, map the query results to a BIN_Meaning tuple
        return list(map(BIN_Meaning._make, g)) if g else g

    def meanings(self, w):
        """ Return a list of all possible grammatical meanings of the given word """
        m = self._meanings(w)
        if m is None:
            return None
        if w in Meanings.DICT:
            # There are additional word meanings in the Meanings dictionary,
            # coming from the settings file: append them
            m.extend(map(BIN_Meaning._make, Meanings.DICT[w]))
        if w in StemPreferences.DICT:
            # We have a preferred stem for this word form:
            # cut off meanings based on other stems
            worse, better = StemPreferences.DICT[w]
            m = [ mm for mm in m if mm.stofn not in worse ]
            # The better (preferred) stem should still be there somewhere
            # assert any(mm.stofn in better for mm in m)

        # Order the meanings by priority, so that the most
        # common/likely ones are first in the list and thus
        # matched more readily than the less common ones

        def priority(m):
            # Order "VH" verbs (viðtengingarháttur) after other forms
            # Also order past tense ("ÞT") after present tense
            # plural after singular and 2p after 3p
            if m.ordfl != "so":
                # Prioritize forms with non-NULL utg
                return 1 if m.utg is None else 0
            prio = 4 if "VH" in m.beyging else 0
            prio += 2 if "ÞT" in m.beyging else 0
            prio += 1 if "FT" in m.beyging else 0
            prio += 1 if "2P" in m.beyging else 0
            return prio

        m.sort(key = priority)
        return m

    def forms(self, w):
        """ Return a list of all possible forms of a particular root (stem) """
        assert False, "This feature is not supported in the Reynir module"

    def is_undeclinable(self, stem, fl):
        """ Return True if the given stem, of the given word category,
            is undeclinable, i.e. all word forms are identical.
            This is presently only used in the POS tagger (postagger.py). """
        assert False, "This feature is not supported in the Reynir module"

    def lookup_utg(self, stofn, ordfl, utg, beyging = None):
        """ Return a list of meanings with the given integer id ('utg' column) """
        assert False, "This feature is not supported in the Reynir module"

    @lru_cache(maxsize = CACHE_SIZE)
    def lookup_nominative(self, w):
        """ Return meaning tuples for all word forms in nominative
            case for all { kk, kvk, hk, lo } category stems of the given word """
        return list(map(BIN_Meaning._make, self._compressed_bin.nominative(w)))

    def lookup_word(self, w, at_sentence_start, auto_uppercase = False):
        """ Given a word form, look up all its possible meanings """
        return self._lookup(w, at_sentence_start, auto_uppercase, self._meanings_func)

    def lookup_form(self, w, at_sentence_start):
        """ Given a word root (stem), look up all its forms """
        assert False,  "This feature is not supported in the Reynir module"

    @lru_cache(maxsize = CACHE_SIZE)
    def lookup_name_gender(self, name):
        """ Given a person name, lookup its gender. """
        if not name:
            return "hk"  # Unknown gender
        w = name.split(maxsplit = 1)[0]  # First name
        g = self.meanings(w)
        m = next((x for x in g if x.fl in { "ism", "nafn" }), None)
        if m:
            # Found a meaning with fl='ism' or fl='nafn'
            return m.ordfl
        # The first name was not found: check whether the full name is
        # in the static phrases
        m = StaticPhrases.lookup(name)
        if m is not None:
            m = BIN_Meaning._make(m)
            if m.fl in { "ism", "nafn" }:
                return m.ordfl
        return "hk"  # Unknown gender

    @staticmethod
    def prefix_meanings(mlist, prefix):
        """ Return a meaning list with a prefix added to the stofn and ordmynd attributes """
        return [
            BIN_Meaning(prefix + "-" + r.stofn, r.utg, r.ordfl, r.fl,
                prefix + "-" + r.ordmynd, r.beyging)
            for r in mlist
        ] if prefix else mlist

    @staticmethod
    def _lookup(w, at_sentence_start, auto_uppercase, lookup):
        """ Lookup a simple or compound word in the database and return its meaning(s) """

        def lookup_abbreviation(w):
            """ Lookup abbreviation from abbreviation list """
            # Remove brackets, if any, before lookup
            if w[0] == '[':
                clean_w = w[1:-1]
                # Check for abbreviation that also ended a sentence and
                # therefore had its end period cut off
                if not clean_w.endswith('.'):
                    clean_w += '.'
            else:
                clean_w = w
            # Return a single-entity list with one meaning
            m = Abbreviations.DICT.get(clean_w, None)
            return None if m is None else [ BIN_Meaning._make(m) ]

        # Start with a straightforward lookup of the word

        if auto_uppercase and w.islower():
            if len(w) == 1:
                # Special case for single letter words:
                # if they exist in BÍN, don't convert them
                m = lookup(w)
                if not m:
                    # If they don't exist in BÍN, treat them as uppercase
                    # abbreviations (probably middle names)
                    w = w.upper() + '.'
            else:
                # Check whether this word has an uppercase form in the database
                w_upper = w.capitalize()
                m = lookup(w_upper)
                if m:
                    # Yes: assume it should be uppercase
                    w = w_upper
                    at_sentence_start = False # No need for special case here
                else:
                    # No: go for the regular lookup
                    m = lookup(w)
        else:
            m = lookup(w)

        if at_sentence_start or not m:
            # No meanings found in database, or at sentence start
            # Try a lowercase version of the word, if different
            lower_w = w.lower()
            if lower_w != w:
                # Do another lookup, this time for lowercase only
                if not m:
                    # This is a word that contains uppercase letters
                    # and was not found in BÍN in its original form
                    # Try an abbreviation before doing a lowercase lookup
                    # (since some abbreviations are also words, i.e. LÍN)
                    m = lookup_abbreviation(w)
                    if not m:
                        m = lookup(lower_w)
                    elif w[0] == '[':
                        # Remove brackets from known abbreviations
                        w = w[1:-1]
                else:
                    # Be careful to make a new list here, not extend m
                    # in place, as it may be a cached value from the LFU
                    # cache and we don't want to mess the original up
                    m = m + lookup(lower_w)

        if m:
            # Most common path out of this function
            return (w, m)

        if lower_w != w or w[0] == '[':
            # Still nothing: check abbreviations
            m = lookup_abbreviation(w)
            if not m and w[0] == '[':
                # Could be an abbreviation with periods at the start of a sentence:
                # Lookup a lowercase version
                m = lookup_abbreviation(lower_w)
            if m and w[0] == '[':
                # Remove brackets from known abbreviations
                w = w[1:-1]

        if not m and BIN_Db._ADJECTIVE_TEST in lower_w:
            # Not found: Check whether this might be an adjective
            # ending in 'legur'/'leg'/'legt'/'legir'/'legar' etc.
            llw = len(lower_w)
            m = []
            for aend, beyging in AdjectiveTemplate.ENDINGS:
                if lower_w.endswith(aend) and llw > len(aend):
                    prefix = lower_w[0 : llw - len(aend)]
                    # Construct an adjective descriptor
                    m.append(BIN_Meaning(prefix + "legur", 0, "lo", "alm", lower_w, beyging))
            if lower_w.endswith("lega") and llw > 4:
                # For words ending with "lega", add a possible adverb meaning
                m.append(BIN_Meaning(lower_w, 0, "ao", "ob", lower_w, "-"))

        if not m:
            # Still nothing: check compound words
            cw = Wordbase.dawg().slice_compound_word(w)
            if not cw and lower_w != w:
                # If not able to slice in original case, try lower case
                cw = Wordbase.dawg().slice_compound_word(lower_w)
            if cw:
                # This looks like a compound word:
                # use the meaning of its last part
                prefix = "-".join(cw[0:-1])
                # Lookup the potential meanings of the last part
                m = lookup(cw[-1])
                if lower_w != w and not at_sentence_start:
                    # If this is an uppercase word in the middle of a
                    # sentence, allow only nouns as possible interpretations
                    # (it wouldn't be correct to capitalize verbs, adjectives, etc.)
                    m = [ mm for mm in m if mm.ordfl in BIN_Db._NOUNS ]
                m = BIN_Db.prefix_meanings(m, prefix)

        if not m and lower_w.startswith('ó'):
            # Check whether an adjective without the 'ó' prefix is found in BÍN
            # (i.e. create 'óhefðbundinn' from 'hefðbundinn')
            suffix = lower_w[1:]
            if suffix:
                om = lookup(suffix)
                if om:
                    m = [ BIN_Meaning("ó" + r.stofn, r.utg, r.ordfl, r.fl,
                        "ó" + r.ordmynd, r.beyging)
                        for r in om if r.ordfl == "lo" ]

        if not m and auto_uppercase and w.islower():
            # If no meaning found and we're auto-uppercasing,
            # convert this to upper case (could be an entity name)
            w = w.capitalize()

        # noinspection PyRedundantParentheses
        return (w, m)



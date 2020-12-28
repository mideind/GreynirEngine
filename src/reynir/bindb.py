"""

    Greynir: Natural language processing for Icelandic

    BIN database access module

    Copyright (C) 2020 Miðeind ehf.

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

    This module encapsulates access to the BIN (Beygingarlýsing íslensks nútímamáls)
    database of word forms, including lookup of abbreviations and basic strategies
    for handling missing words.

    The database is assumed to be packed into a compressed binary file,
    which is wrapped inside the bincompress.py module.

    Word meaning lookups are cached in Least Frequently Used (LFU) caches.

    This code must be thread safe.

"""

from typing import (
    NamedTuple,
    Optional,
    Callable,
    List,
    Tuple,
    Iterable,
    Type,
    Dict,
    Any,
)
from typing_extensions import Protocol

from functools import lru_cache

from .settings import AdjectiveTemplate, StemPreferences, StaticPhrases, NounPreferences
from .cache import LFU_Cache
from .dawgdictionary import Wordbase
from .bincompress import BIN_Compressed


# Named tuple for word meanings fetched from the BÍN database (lexicon)
BIN_Meaning = NamedTuple(
    "BIN_Meaning",
    [
        ("stofn", str),
        ("utg", int),
        ("ordfl", str),
        ("fl", str),
        ("ordmynd", str),
        ("beyging", str),
    ],
)
# Type definitions
ResultTuple = Tuple[str, List[BIN_Meaning]]
LookupFunc = Callable[[str], List[BIN_Meaning]]
TupleLookupFunc = Callable[[str], ResultTuple]
MeaningFilterFunc = Callable[[Iterable[BIN_Meaning]], List[BIN_Meaning]]

# Annotate the case-casting function signature via a callback protocol
# See https://www.python.org/dev/peps/pep-0544/#callback-protocols
class CaseFunc(Protocol):
    def __call__(self, w: str, **options) -> List[BIN_Meaning]:
        ...


# Size of LRU/LFU caches for word lookups
CACHE_SIZE = 512
# Most common lookup function (meanings of a particular word form)
CACHE_SIZE_MEANINGS = 2048
CACHE_SIZE_UNDECLINABLE = 2048

# Compact string representation
_meaning_repr = lambda self: (
    "(stofn='{0}', {2}/{3}/{1}, ordmynd='{4}', {5})".format(
        self.stofn, self.utg, self.ordfl, self.fl, self.ordmynd, self.beyging
    )
)

setattr(BIN_Meaning, "__str__", _meaning_repr)
setattr(BIN_Meaning, "__repr__", _meaning_repr)

# The set of word subcategories (fl) for person names
# (i.e. first names or complete names)
PERSON_NAME_FL = frozenset(("ism", "nafn", "gæl", "erm"))


class _BIN_Session:

    """ Encapsulates a BIN_Db singleton instance in a context manager """

    def __init__(self, cls: Type["BIN_Db"]) -> None:
        self._cls = cls

    def __enter__(self) -> "BIN_Db":
        """ Python context manager protocol """
        if self._cls._singleton is None:
            self._cls._singleton = self._cls()
        return self._cls._singleton

    def __exit__(self, exc_type, exc_value, traceback):
        """ Python context manager protocol """
        # Return False to re-throw exception from the context, if any
        return False


class BIN_Db:

    """ Encapsulates the BÍN database of word forms """

    # Adjective endings
    _ADJECTIVE_TEST = "leg"  # Check for adjective if word contains 'leg'

    # Word categories that are allowed to appear capitalized in the middle of sentences,
    # as a result of compound word construction
    _NOUNS = frozenset(("kk", "kvk", "hk"))

    _OPEN_CATS = frozenset(("so", "kk", "hk", "kvk", "lo"))  # Open word categories

    # Singleton LFU caches for word meaning lookup
    _meanings_cache = LFU_Cache(maxsize=CACHE_SIZE_MEANINGS)

    # Singleton instance of BIN_Db, returned by get_db()
    _singleton: Optional["BIN_Db"] = None

    @classmethod
    def get_db(cls) -> _BIN_Session:
        """ Return a session object that can be used in a with statement """
        return _BIN_Session(cls)

    @classmethod
    def cleanup(cls) -> None:
        """ Close singleton instance, if any """
        if cls._singleton:
            cls._singleton.close()
            cls._singleton = None

    def __init__(self) -> None:
        """ Initialize BIN database wrapper instance """
        # Cache descriptors for the lookup functions
        self._meanings_func = lambda key: (
            self._meanings_cache.lookup(key, self.meanings)
        )
        # Compressed BÍN wrapper
        # Raises IOError if the compressed file doesn't exist
        self._compressed_bin: Optional[BIN_Compressed] = BIN_Compressed()

    def close(self) -> None:
        """ Close the BIN_Compressed() instance """
        if self._compressed_bin is not None:
            self._compressed_bin.close()
            self._compressed_bin = None

    def contains(self, w: str) -> bool:
        """ Returns True if the given word form is found in BÍN """
        assert self._compressed_bin is not None
        return self._compressed_bin.contains(w)

    def __contains__(self, w: str) -> bool:
        """ Returns True if the given word form is found in BÍN """
        assert self._compressed_bin is not None
        return self._compressed_bin.contains(w)

    def _meanings(self, w: str) -> List[BIN_Meaning]:
        """ Low-level fetch of the BIN meanings of a given word """
        # Route the lookup request to the compressed binary file
        assert self._compressed_bin is not None
        g = self._compressed_bin.lookup(w)
        # If an error occurs, this returns None.
        # If the lookup doesn't yield any results, [] is returned.
        # Otherwise, map the query results to a BIN_Meaning tuple
        return list(map(BIN_Meaning._make, g)) if g else []

    @staticmethod
    def _priority(m: BIN_Meaning) -> int:
        """ Return a relative priority for the word meaning tuple
            in m. A lower number means more priority, a higher number
            means less priority. """
        # Order "VH" verbs (viðtengingarháttur) after other forms
        # Also order past tense ("ÞT") after present tense
        # plural after singular and 2p after 3p
        if m.ordfl != "so":
            # Prioritize forms with non-NULL utg
            return 1 if (m.utg is None or m.utg < 1) else 0
        prio = 4 if "VH" in m.beyging else 0
        prio += 2 if "ÞT" in m.beyging else 0
        prio += 1 if "FT" in m.beyging else 0
        prio += 1 if "2P" in m.beyging else 0
        return prio

    def meanings(self, w: str) -> List[BIN_Meaning]:
        """ Return a list of all possible grammatical meanings of the given word.
            Note that this is a low-level lookup in BÍN, or rather in ord.compressed,
            meaning that no upper/lower case conversion is applied, no abbreviations
            are recognized, static phrases are not looked up, etc.
            Also note that this is not a cached function. """
        m = self._meanings(w)
        if not m:
            return []
        stem_prefs = StemPreferences.DICT.get(w)
        if stem_prefs is not None:
            # We have a preferred stem for this word form:
            # cut off meanings based on other stems
            worse, _ = stem_prefs
            m = [mm for mm in m if mm.stofn not in worse]
            # The better (preferred) stem should still be there somewhere
            # assert any(mm.stofn in better for mm in m)

        # Order the meanings by priority, so that the most
        # common/likely ones are first in the list and thus
        # matched more readily than the less common ones
        m.sort(key=self._priority)
        return m

    @lru_cache(maxsize=CACHE_SIZE)
    def lookup_raw_nominative(self, w: str) -> List[BIN_Meaning]:
        """ Return a set of meaning tuples for all word forms in nominative case.
            The set is unfiltered except for the presence of 'NF' in the beyging
            field. For new code, lookup_nominative() is likely to be a
            more efficient choice. """
        assert self._compressed_bin is not None
        return list(map(BIN_Meaning._make, self._compressed_bin.raw_nominative(w)))

    def lookup_nominative(self, w: str, **options) -> List[BIN_Meaning]:
        """ Return meaning tuples for all word forms in nominative
            case for all { kk, kvk, hk, lo } category stems of the given word """
        assert self._compressed_bin is not None
        return list(
            map(BIN_Meaning._make, self._compressed_bin.nominative(w, **options))
        )

    def lookup_accusative(self, w: str, **options) -> List[BIN_Meaning]:
        """ Return meaning tuples for all word forms in accusative
            case for all { kk, kvk, hk, lo } category stems of the given word """
        assert self._compressed_bin is not None
        return list(
            map(BIN_Meaning._make, self._compressed_bin.accusative(w, **options))
        )

    def lookup_dative(self, w: str, **options) -> List[BIN_Meaning]:
        """ Return meaning tuples for all word forms in dative
            case for all { kk, kvk, hk, lo } category stems of the given word """
        assert self._compressed_bin is not None
        return list(map(BIN_Meaning._make, self._compressed_bin.dative(w, **options)))

    def lookup_genitive(self, w: str, **options) -> List[BIN_Meaning]:
        """ Return meaning tuples for all word forms in genitive
            case for all { kk, kvk, hk, lo } category stems of the given word """
        assert self._compressed_bin is not None
        return list(map(BIN_Meaning._make, self._compressed_bin.genitive(w, **options)))

    def lookup_word(
        self, w: str, at_sentence_start: bool = False, auto_uppercase: bool = False
    ) -> ResultTuple:
        """ Given a word form, look up all its possible meanings """
        assert self._compressed_bin is not None
        return self._lookup(w, at_sentence_start, auto_uppercase, self._meanings_func)

    # A dictionary of functions, one for each word category, that return
    # True for declension (beyging) strings of canonical/lemma forms
    LEMMA_FILTERS: Dict[str, Callable[[str], bool]] = dict(
        # Nouns: Nominative, singular
        kk=lambda b: b == "NFET",
        kvk=lambda b: b == "NFET",
        hk=lambda b: b == "NFET",
        # Pronouns: Masculine, nominative, singular
        fn=lambda b: b == "KK-NFET" or b == "KK_NFET" or b == "fn_KK_NFET",
        # Personal pronouns: Nominative, singular
        pfn=lambda b: b == "NFET",
        # Definite article: Masculine, nominative, singular
        gr=lambda b: b == "KK-NFET" or b == "KK_NFET",
        # Verbs: infinitive
        so=lambda b: b == "GM-NH",
        # Adjectives: Masculine, singular, first degree, strong declension
        lo=lambda b: b == "FSB-KK-NFET" or b == "KK-NFET",
        # Number words: Masculine, nominative case; or no inflection
        to=lambda b: b.startswith("KK_NF") or b == "-",
    )

    def lookup_lemma(
        self, w: str, at_sentence_start: bool = False, auto_uppercase: bool = False
    ) -> ResultTuple:
        """ Given a word lemma, look up all its possible meanings """
        # Note: we consider middle voice infinitive verbs to be lemmas,
        # i.e. 'eignast' is recognized as a lemma as well as 'eigna'.
        # This is done for consistency, as some middle voice verbs have
        # their own separate lemmas in BÍN, such as 'ábyrgjast'.
        final_w, meanings = self.lookup_word(
            w, at_sentence_start=at_sentence_start, auto_uppercase=auto_uppercase
        )

        def match(m: BIN_Meaning) -> bool:
            """ Return True for meanings that are canonical as lemmas """
            if m.ordfl == "so" and m.beyging == "MM-NH":
                # This is a middle voice verb infinitive meaning
                # ('eignast', 'komast'): accept it as a lemma
                return True
            if m.stofn.replace("-", "") != final_w:
                # This lemma does not agree with the passed-in word
                return False
            # Do a check of the canonical lemma inflection forms
            return self.LEMMA_FILTERS.get(m.ordfl, lambda b: True)(m.beyging)

        return final_w, [m for m in meanings if match(m)]

    @lru_cache(maxsize=CACHE_SIZE)
    def lookup_name_gender(self, name: str) -> str:
        """ Given a person name, lookup its gender """
        if not name:
            return "hk"  # Unknown gender
        w = name.split(maxsplit=1)[0]  # First name
        g = self.meanings(w)
        m = next((x for x in g if x.fl in PERSON_NAME_FL), None)
        if m:
            # Found a name meaning
            return m.ordfl
        # The first name was not found: check whether the full name is
        # in the static phrases
        mm = StaticPhrases.lookup(name)
        if mm is not None:
            m = BIN_Meaning._make(mm)
            if m.fl in PERSON_NAME_FL:
                return m.ordfl
        return "hk"  # Unknown gender

    @staticmethod
    def prefix_meanings(
        mlist: Iterable[BIN_Meaning],
        prefix: str,
        *,
        insert_hyphen: bool = True,
        uppercase: bool = False
    ) -> List[BIN_Meaning]:
        """ Return a meaning list with a prefix added to the
            stofn and ordmynd attributes. If insert_hyphen is True, we
            insert a hyphen between the prefix and the suffix, both in the
            stofn and in the ordmynd fields. If uppercase is additionally True, we
            uppercase the suffix. """
        if insert_hyphen:
            if uppercase:
                concat = lambda w: prefix + "-" + w.capitalize()
            else:
                concat = lambda w: prefix + "-" + w
        else:
            concat = lambda w: prefix + w
        return (
            [
                BIN_Meaning(
                    concat(r.stofn), r.utg, r.ordfl, r.fl, concat(r.ordmynd), r.beyging
                )
                for r in mlist
            ]
            if prefix
            else list(mlist)
        )

    @staticmethod
    def open_cats(mlist: Iterable[BIN_Meaning]) -> List[BIN_Meaning]:
        """ Return a list of meanings filtered down to
            open (extensible) word categories """
        return [mm for mm in mlist if mm.ordfl in BIN_Db._OPEN_CATS]

    @staticmethod
    def nouns(mlist: Iterable[BIN_Meaning]) -> List[BIN_Meaning]:
        """ Return a list of meanings filtered down to noun categories (kk, kvk, hk) """
        return [mm for mm in mlist if mm.ordfl in BIN_Db._NOUNS]

    @staticmethod
    def _compound_meanings(
        w: str, lower_w: str, at_sentence_start: bool, lookup: LookupFunc
    ) -> List[BIN_Meaning]:
        """ Return a list of meanings of this word,
            when interpreted as a compound word """
        if " " in w:
            # The word is a multi-word compound, such as 'félags- og barnamálaráðherra':
            # Look at the last part only
            prefix, suffix = w.rsplit(" ", maxsplit=1)
            uppercase = suffix[0].isupper() and suffix[1:].islower()
            m = BIN_Db._compound_meanings(suffix, suffix.lower(), False, lookup)
            return (
                BIN_Db.prefix_meanings(
                    m, prefix + " ", insert_hyphen=False, uppercase=uppercase
                )
                if m
                else []
            )
        if "-" in w and not w.endswith("-"):
            # The word already contains a hyphen: respect that split and
            # look at the suffix only
            prefix, suffix = w.rsplit("-", maxsplit=1)
            m = BIN_Db._compound_meanings(suffix, suffix.lower(), False, lookup)
            # For words such as 'Ytri-Hnaus', retain the uppercasing of the suffix
            uppercase = suffix[0].isupper() and suffix[1:].islower()
            return BIN_Db.prefix_meanings(m, prefix, uppercase=uppercase) if m else []
        cw = Wordbase.slice_compound_word(w)
        if not cw and lower_w != w:
            # If not able to slice in original case, try lower case
            cw = Wordbase.slice_compound_word(lower_w)
        if not cw:
            # No way to find a compound meaning: give up
            return []
        # This looks like a compound word:
        # use the meaning of its last part
        prefix = "-".join(cw[0:-1])
        # Lookup the potential meanings of the last part
        m = lookup(cw[-1])
        if lower_w != w and not at_sentence_start:
            # If this is an uppercase word in the middle of a
            # sentence, allow only nouns as possible interpretations
            # (it wouldn't be correct to capitalize verbs, adjectives, etc.)
            m = BIN_Db.nouns(m)
        else:
            # Only allows meanings from open word categories
            # (nouns, verbs, adjectives, adverbs)
            m = BIN_Db.open_cats(m)
        # Add the prefix to the remaining word stems
        return BIN_Db.prefix_meanings(m, prefix)

    @staticmethod
    def _lookup(
        w: str, at_sentence_start: bool, auto_uppercase: bool, lookup: LookupFunc
    ) -> ResultTuple:
        """ Lookup a simple or compound word in the database and
            return its meaning(s). This function checks for abbreviations,
            upper/lower case variations, etc. """

        # Start with a straightforward lookup of the word as-is
        lower_w = w
        m = lookup(w)

        if auto_uppercase and w.islower():
            # Lowercase word that was not found in BÍN:
            # If auto_uppercase is True, we attempt to find an
            # uppercase variant of it
            if len(w) == 1 and not m:
                # Special case for single letter words that are not found in BÍN:
                # treat them as uppercase abbreviations
                # (probably middle names)
                w = w.upper() + "."
            else:
                # Check whether this word has an uppercase form in the database
                # capitalize() converts "ABC" and "abc" to "Abc"
                w_upper = w.capitalize()
                m_upper = lookup(w_upper)
                if m_upper:
                    # Uppercase form(s) found
                    w = w_upper
                    if m:
                        # ...in addition to lowercase ones
                        # Note that the uppercase forms are put in front of the
                        # resulting list. This is intentional, inter alia so that
                        # person names are recognized as such in bintokenizer.py.
                        m = m_upper + m
                    else:
                        # No lowercase forms: use the uppercase form and meanings
                        m = m_upper
                    at_sentence_start = False  # No need for special case here

        if at_sentence_start or not m:
            # No meanings found in database, or at sentence start
            # Try a lowercase version of the word, if different
            lower_w = w.lower()
            if lower_w != w:
                # Do another lookup, this time for lowercase only
                if not m:
                    # This is a word that contains uppercase letters
                    # and was not found in BÍN in its original form:
                    # try the all-lowercase version
                    m = lookup(lower_w)
                else:
                    # Be careful to make a new list here, not extend m
                    # in place, as it may be a cached value from the LFU
                    # cache and we don't want to mess the original up
                    # Note: the lowercase lookup result is intentionally put
                    # in front of the uppercase one, as we want go give
                    # 'regular' lowercase meanings priority when matching
                    # tokens to terminals. For example, 'Maður' and 'maður'
                    # are both in BÍN, the former as a place name ('örn'),
                    # but we want to give the regular, common lower case form
                    # priority.
                    m = lookup(lower_w) + m
        if m:
            # Most common path out of this function
            return w, m

        if not m and BIN_Db._ADJECTIVE_TEST in lower_w:
            # Not found: Check whether this might be an adjective
            # ending in 'legur'/'leg'/'legt'/'legir'/'legar' etc.
            llw = len(lower_w)
            m = []
            for aend, beyging in AdjectiveTemplate.ENDINGS:
                if lower_w.endswith(aend) and llw > len(aend):
                    prefix = lower_w[0 : llw - len(aend)]
                    # Construct an adjective descriptor
                    m.append(
                        BIN_Meaning(prefix + "legur", 0, "lo", "alm", lower_w, beyging)
                    )
            if lower_w.endswith("lega") and llw > 4:
                # For words ending with "lega", add a possible adverb meaning
                m.append(BIN_Meaning(lower_w, 0, "ao", "ob", lower_w, "-"))

        if not m:
            # Still nothing: check compound words
            m = BIN_Db._compound_meanings(w, lower_w, at_sentence_start, lookup)

        if not m and lower_w.startswith("ó"):
            # Check whether an adjective without the 'ó' prefix is found in BÍN
            # (i.e. create 'óhefðbundinn' from 'hefðbundinn')
            suffix = lower_w[1:]
            if suffix:
                om = lookup(suffix)
                if om:
                    m = [
                        BIN_Meaning(
                            "ó" + r.stofn,
                            r.utg,
                            r.ordfl,
                            r.fl,
                            "ó" + r.ordmynd,
                            r.beyging,
                        )
                        for r in om
                        if r.ordfl == "lo"
                    ]

        if not m and "z" in w:
            # Special case: the word contains a 'z' and may be using
            # older Icelandic spelling ('lízt', 'íslenzk'). Try to assign
            # a meaning by substituting an 's' instead, or 'st' instead of
            # 'tzt'. Call ourselves recursively to do this.
            # Note: We don't do this for uppercase 'Z' because those are
            # much more likely to indicate a person or entity name
            _, m = BIN_Db._lookup(
                w.replace("tzt", "st").replace("z", "s"),
                at_sentence_start,
                auto_uppercase,
                lookup,
            )

        if auto_uppercase and not m and w.islower():
            # If still no meaning found and we're auto-uppercasing,
            # convert this to upper case (probably an entity name)
            w = w.capitalize()

        return w, m

    @staticmethod
    def _cast_to_case(
        w: str,
        lookup_func: TupleLookupFunc,
        case_func: CaseFunc,
        meaning_filter_func: Optional[MeaningFilterFunc],
    ) -> str:
        """ Return a word after casting it from nominative to another case,
            as returned by the case_func """

        def score(m: BIN_Meaning) -> int:
            """ Return a score for a noun word form, based on the
                [noun_preferences] section in Prefs.conf """
            sc = NounPreferences.DICT.get(m.ordmynd.split("-")[-1])
            return 0 if sc is None else sc.get(m.ordfl, 0)

        # Begin by looking up the word form
        _, mm = lookup_func(w)
        if not mm:
            # Unknown word form: leave it as-is
            return w
        # Check whether this is (or might be) an adjective
        m_word = next((m for m in mm if m.ordfl == "lo" and "NF" in m.beyging), None)
        if m_word is not None:
            # This is an adjective: find its forms
            # in the requested case ("Gul gata", "Stjáni blái")
            mm = case_func(m_word.ordmynd, cat="lo", stem=m_word.stofn)
            if "VB" in m_word.beyging:
                mm = [m for m in mm if "VB" in m.beyging]
            elif "SB" in m_word.beyging:
                mm = [m for m in mm if "SB" in m.beyging]
        else:
            # Sort the possible meanings in reverse order by score
            mm = sorted(mm, key=score, reverse=True)
            m_word = next(
                (
                    m
                    for m in mm
                    if m.ordfl in {"kk", "kvk", "hk", "fn", "pfn", "to", "gr"}
                    and "NF" in m.beyging
                ),
                None,
            )
            if m_word is None:
                # Not a case-inflectable word that we are interested in: leave it
                return w
            if "-" in m_word.ordmynd and "-" not in w:
                # Composite word (and not something like 'Vestur-Þýskaland', which
                # is in BÍN including the hyphen): use the meaning of its last part
                cw = m_word.ordmynd.split("-")
                prefix = "-".join(cw[0:-1])
                # No need to think about upper or lower case here,
                # since the last part of a compound word is always in BÍN as-is
                mm = case_func(
                    cw[-1], cat=m_word.ordfl, stem=m_word.stofn.split("-")[-1]
                )
                # Add the prefix to the remaining word stems
                mm = BIN_Db.prefix_meanings(mm, prefix, insert_hyphen=False)
            else:
                mm = case_func(w, cat=m_word.ordfl, stem=m_word.stofn)
                if not mm and w[0].isupper() and not w.isupper():
                    # Did not find an uppercase version: try a lowercase one
                    mm = case_func(w.lower(), cat=m_word.ordfl, stem=m_word.stofn)
        if mm:
            # Likely successful: return the word after casting it
            if "ET" in m_word.beyging:
                # Restrict to singular
                mm = [m for m in mm if "ET" in m.beyging]
            elif "FT" in m_word.beyging:
                # Restrict to plural
                mm = [m for m in mm if "FT" in m.beyging]
            # Apply further filtering, if desired
            if meaning_filter_func is not None:
                mm = meaning_filter_func(mm)
            if mm:
                o = mm[0].ordmynd
                # Imitate the case of the original word
                if w.isupper():
                    o = o.upper()
                elif w[0].isupper() and not o[0].isupper():
                    o = o[0].upper() + o[1:]
                return o

        # No case casting could be done: return the original word
        return w

    def cast_to_accusative(
        self, w: str, *, meaning_filter_func: Optional[MeaningFilterFunc] = None
    ) -> str:
        """ Cast a word from nominative to accusative case, or return it
            unchanged if it is not inflectable by case. """
        # Note that since this function has no context, the conversion is
        # by necessity simplistic; for instance it does not know whether
        # an adjective is being used with an indefinite or definite noun,
        # or whether a word such as 'við' is actually a preposition.
        return self._cast_to_case(
            w,
            self.lookup_word,
            self.lookup_accusative,
            meaning_filter_func=meaning_filter_func,
        )

    def cast_to_dative(
        self, w: str, *, meaning_filter_func: Optional[MeaningFilterFunc] = None
    ) -> str:
        """ Cast a word from nominative to dative case, or return it
            unchanged if it is not inflectable by case. """
        # Note that since this function has no context, the conversion is
        # by necessity simplistic; for instance it does not know whether
        # an adjective is being used with an indefinite or definite noun,
        # or whether a word such as 'við' is actually a preposition.
        return self._cast_to_case(
            w,
            self.lookup_word,
            self.lookup_dative,
            meaning_filter_func=meaning_filter_func,
        )

    def cast_to_genitive(
        self, w: str, *, meaning_filter_func: Optional[MeaningFilterFunc] = None
    ) -> str:
        """ Cast a word from nominative to genitive case, or return it
            unchanged if it is not inflectable by case. """
        # Note that since this function has no context, the conversion is
        # by necessity simplistic; for instance it does not know whether
        # an adjective is being used with an indefinite or definite noun,
        # or whether a word such as 'við' is actually a preposition.
        return self._cast_to_case(
            w,
            self.lookup_word,
            self.lookup_genitive,
            meaning_filter_func=meaning_filter_func,
        )

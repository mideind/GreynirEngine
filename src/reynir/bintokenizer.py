"""

    Greynir: Natural language processing for Icelandic

    Dictionary-aware tokenization layer

    Copyright (C) 2021 Miðeind ehf.

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

    This module adds layers on top of the "raw" tokenizer in
    tokenizer.py. These layers annotate the token stream with word
    meanings from the BIN lexicon of Icelandic, identify multi-word
    phrases, process person names, etc.

"""

from typing import (
    DefaultDict,
    Dict,
    cast,
    Optional,
    Tuple,
    List,
    Sequence,
    Mapping,
    Union,
    Iterable,
    Iterator,
    Set,
    FrozenSet,
    Callable,
    Type,
    Any,
    TypeVar,
)
from typing_extensions import TypedDict

import sys
import re
from collections import defaultdict

from tokenizer import (
    TOK,
    Tok,
    TokenStream,
    tokenize_without_annotation,
    # The following imports are here in order to be visible in clients
    # (they are not used in this module)
    correct_spaces,  # type: ignore
    paragraphs,  # type: ignore
    parse_tokens,  # type: ignore
)
from tokenizer.definitions import (
    BIN_Tuple,
    BIN_TupleList,
    CurrencyTuple,
    NumberTuple,
    PersonNameList,
    PersonNameTuple,
    ValType,
    DateTimeTuple,
)
from tokenizer.abbrev import Abbreviations

from .settings import StaticPhrases, AmbigPhrases, DisallowedNames, NamePreferences
from .bindb import GreynirBin


class TokenDict(TypedDict, total=False):

    """ The type of a token dictionary returned from describe_token() """

    # Index in original token list
    ix: int
    # Kind
    k: int
    # Terminal
    t: str
    # Augmented terminal (optional)
    a: str
    # Meaning: ordmynd, ordfl, fl, beyging
    m: Tuple[str, str, str, str]
    # Text
    x: str
    # Value
    v: Any
    # Gender (for person tokens only)
    g: str
    # Error marker (optional)
    err: int


class CanonicalTokenDict(TypedDict, total=False):

    """ A token dictionary returned from canonicalize_token().
        This scheme is intended for external consumption,
        such as export in JSON format to clients. """

    # Index in original token list
    ix: int
    # Token kind, as a string (e.g. 'WORD')
    k: str
    # Terminal, normalized (e.g. 'no_kk_et_nf')
    t: str
    # Original terminal (e.g. '"og:st"')
    o: str
    # Augmented terminal (e.g. 'so_1_þf_gm_fh_nt')
    a: str
    # Text
    x: str
    # Lemma
    s: str
    # BÍN category ('kk', 'so', 'fs'...)
    c: str
    # BÍN fl field ('ism', 'ætt'...)
    f: str
    # BÍN inflection (beyging field, e.g. 'GM-FH-NT')
    b: str
    # Additional values, depending on token kind
    v: Union[str, float, Dict[str, Any]]


if "PyPy 7.3.0" in sys.version or "PyPy 7.2." in sys.version:
    # Patch bug in PyPy 7.2/7.3.0, which may raise an erroneous exception on str.rsplit()
    def all_except_suffix(s: str) -> str:  # type: ignore
        try:
            return s[0 : s.rindex(" ")]
        except ValueError:
            # String does not contain a space: return it whole
            return s


else:

    def all_except_suffix(s: str) -> str:
        return s.rsplit(maxsplit=1)[0]


# Generic type variable
T = TypeVar("T")
# The type of a list of tokens
TokenList = List[Tok]
TokenIterable = Iterable[Tok]
# The input argument type for the tokenize() function and derivatives thereof
StringIterable = Union[str, Iterable[str]]
# The type of a stream of tokens
TokenIterator = Iterator[Tok]
# The type of a tokenization pipeline phase
FirstPhaseFunction = Callable[[], TokenIterator]
FollowingPhaseFunction = Callable[[TokenIterator], TokenIterator]
PhaseFunction = Union[FirstPhaseFunction, FollowingPhaseFunction]
StateTuple = Tuple[List[str], int]
StateList = List[StateTuple]
StateDict = DefaultDict[str, StateList]
DisambiguationTuple = Tuple[str, FrozenSet[str]]
TokenConstructor = Type["Bin_TOK"]
FilterFunction = Callable[[BIN_Tuple], bool]

# Person names that are not recognized at the start of sentences
NOT_NAME_AT_SENTENCE_START: FrozenSet[str] = frozenset(
    (
        "Annar",
        "Annars",
        "Kalla",
        "Sanna",
        "Gamli",
        "Gamla",
        "Vinni",
        "Vinna",
        "Vilji",
        "Vilja",
        "Ljótur",
        "Ljót",
        "Ljóti",
        "Ljóts",
        "Mikill",
        "Mikil",
    )
)

# Set of all cases (nominative, accusative, dative, genitive)
ALL_CASES: FrozenSet[str] = frozenset(["nf", "þf", "þgf", "ef"])

# Genders
GENDER_SET: FrozenSet[str] = frozenset(("kk", "kvk", "hk"))
GENDER_DICT: Mapping[str, str] = {"KK": "kk", "KVK": "kvk", "HK": "hk"}

HYPHEN = "-"  # Normal hyphen
EN_DASH = "\u2013"  # "–"
EM_DASH = "\u2014"  # "—"
COMPOSITE_HYPHEN = EN_DASH
COMPOSITE_HYPHENS = HYPHEN + COMPOSITE_HYPHEN
HYPHEN_SPLIT_RE = r"[" + COMPOSITE_HYPHENS + r"]"

# Prefixes that can be applied to adjectives with an intervening hyphen
ADJECTIVE_PREFIXES: FrozenSet[str] = frozenset(["hálf", "marg", "semí", "full"])

# Recognize number abbreviations
NUMBER_ABBREVS: FrozenSet[str] = frozenset(
    (
        "þús.",
        "millj.",
        "ma.",
        "mrð.",
    )
)

# The following must occur as lemmas in BÍN
DECLINABLE_NUMBERS: FrozenSet[str] = frozenset(
    (
        "hundrað",
        "þúsund",
        "milljón",
        "milljarður",
        "billjón",
        "billjarður",
        "trilljón",
        "trilljarður",
        "kvaðrilljón",
        # "kvaðrilljarður",
        # "kvintilljón",
        # "sextilljón",
        # "septilljón",
        # "oktilljón",
    )
)

# Recognize words for percentages
PERCENTAGES: Mapping[str, int] = {
    "prósent": 1,
    "prósenta": 1,
    "hundraðshluti": 1,
    "prósentustig": 1,
}

# Recognize words for nationalities (used for currencies)
NATIONALITIES: Mapping[str, str] = {
    "danskur": "dk",
    "enskur": "uk",
    "breskur": "uk",
    "bandarískur": "us",
    "kanadískur": "ca",
    "svissneskur": "ch",
    "sænskur": "se",
    "norskur": "no",
    "japanskur": "jp",
    "íslenskur": "is",
    "pólskur": "po",
    "kínverskur": "cn",
    "ástralskur": "au",
    "rússneskur": "ru",
    "indverskur": "in",
    "indónesískur": "id",
}

# Valid currency combinations
ISO_CURRENCIES: Mapping[Tuple[str, str], str] = {
    ("dk", "ISK"): "DKK",
    ("is", "ISK"): "ISK",
    ("no", "ISK"): "NOK",
    ("se", "ISK"): "SEK",
    ("uk", "GBP"): "GBP",
    ("us", "USD"): "USD",
    ("ca", "USD"): "CAD",
    ("au", "USD"): "AUD",
    ("ch", "CHF"): "CHF",
    ("jp", "JPY"): "JPY",
    ("po", "PLN"): "PLN",
    ("ru", "RUB"): "RUB",
    ("in", "INR"): "INR",  # Indian rupee
    ("id", "INR"): "IDR",  # Indonesian rupiah
    ("cn", "CNY"): "CNY",
    ("cn", "RMB"): "RMB",
}

# Amount abbreviations including 'kr' for the ISK
# Corresponding abbreviations are found in Abbrev.conf
AMOUNT_ABBREV: Mapping[str, int] = {
    "kr.": 1,
    "kr": 1,
    "þ.kr.": 10 ** 3,
    "þ.kr": 10 ** 3,
    "þús.kr.": 10 ** 3,
    "þús.kr": 10 ** 3,
    "m.kr.": 10 ** 6,
    "m.kr": 10 ** 6,
    "mkr.": 10 ** 6,
    "mkr": 10 ** 6,
    "ma.kr.": 10 ** 9,
    "ma.kr": 10 ** 9,
    "mrð.kr.": 10 ** 9,
    "mrð.kr": 10 ** 9,
}

# Number words can be marked as subjects (any gender) or as numbers
NUMBER_CATEGORIES: FrozenSet[str] = frozenset(["töl", "to", "kk", "kvk", "hk", "lo"])

# Recognize words for currencies
CURRENCIES: Mapping[str, str] = {
    "króna": "ISK",
    "ISK": "ISK",
    "kr.": "ISK",
    "kr": "ISK",
    "DKK": "DKK",
    "NOK": "NOK",
    "SEK": "SEK",
    "pund": "GBP",
    "sterlingspund": "GBP",
    "GBP": "GBP",
    "dollari": "USD",
    "dalur": "USD",
    "bandaríkjadalur": "USD",
    "USD": "USD",
    "franki": "CHF",
    "CHF": "CHF",
    "rúbla": "RUB",
    "RUB": "RUB",
    "rúpía": "INR",
    "INR": "INR",
    "IDR": "IDR",
    "jen": "JPY",
    "yen": "JPY",
    "JPY": "JPY",
    "zloty": "PLN",
    "PLN": "PLN",
    "júan": "CNY",
    "yuan": "CNY",
    "CNY": "CNY",
    "renminbi": "RMB",
    "RMB": "RMB",
    "evra": "EUR",
    "EUR": "EUR",
}

CURRENCY_GENDERS: Mapping[str, str] = {
    "ISK": "kvk",
    "DKK": "kvk",
    "NOK": "kvk",
    "SEK": "kvk",
    "GBP": "hk",
    "USD": "kk",
    "CHF": "kk",
    "RUB": "kvk",
    "INR": "kvk",
    "IDR": "kvk",
    "JPY": "hk",
    "PLN": "hk",
    "CNY": "hk",
    "RMB": "hk",
    "EUR": "kvk",
}

# Set of categories (fl fields in BÍN) that denote
# person names, Icelandic ('ism' or 'gæl') or foreign ('erm')
PERSON_NAME_SET: FrozenSet[str] = frozenset(("ism", "gæl", "erm"))

# Set of categories (fl fields in BÍN) for patronyms
# and matronyms, as well as gender-neutral family names
PATRONYM_SET: FrozenSet[str] = frozenset(("föð", "móð", "ætt"))

# Set of foreign middle names that start with a lower case letter
# ('Louis de Broglie', 'Jan van Eyck')
# 'of' was also here but caused problems
FOREIGN_MIDDLE_NAME_SET: FrozenSet[str] = frozenset(
    ("van", "de", "den", "der", "el", "al", "von", "la")
)

ENTITY_MIDDLE_NAME_SET: FrozenSet[str] = frozenset(
    ("in", "a", "an", "for", "and", "the", "for", "on", "of")
)

# Given names that can also be family names (and thus gender- and caseless as such)
BOTH_GIVEN_AND_FAMILY_NAMES: FrozenSet[str] = frozenset(("Hafstein",))

# Note: these must have a meaning for this to work, so specifying them
# as abbreviations in Abbrev.conf in Tokenizer is recommended
_CORPORATION_ENDINGS: FrozenSet[str] = frozenset(
    [
        "ehf.",
        "ehf",
        "hf.",
        "hses.",
        "hses",
        "hf",
        "bs.",
        "bs",
        "sf.",
        "sf",
        "slhf.",
        "slhf",
        "slf.",
        "slf",
        "svf.",
        "svf",
        "ohf.",
        "ohf",
        "Inc",
        "Inc.",
        "Incorporated",
        "Corp",
        "Corp.",
        "Corporation",
        "Ltd",
        "Ltd.",
        "Limited",
        "Co",
        "Co.",
        "Company",
        "Group",
        "AS",
        "ASA",
        "SA",
        "S.A.",
        "GmbH",
        "AG",
        "SARL",
        "S.à.r.l.",
    ]
)

# Abbreviations that we explicitly accept as a part of
# person names, if we are auto-capitalizing
MIDDLE_NAME_ABBREVS: FrozenSet[str] = frozenset(
    (
        "th",
        "kr",
        "st",
        "fr",
        "a",
        "á",
        "b",
        "c",
        "d",
        "e",
        "é",
        "f",
        "g",
        "h",
        "i",
        "í",
        "j",
        "k",
        "l",
        "m",
        "n",
        "o",
        "ó",
        "p",
        "q",
        "r",
        "s",
        "t",
        "u",
        "ú",
        "v",
        "w",
        "x",
        "y",
        "ý",
        "z",
        "þ",
        "æ",
        "ö",
    )
)

# Not name abbreviations if not followed by period or surname
NOT_NAME_ABBREVS: FrozenSet[str] = frozenset(("á", "í"))

# Words which should probably be lowercase
PREFER_LOWERCASE: FrozenSet[str] = frozenset(("á", "bóndi", "ganga", "hæð"))


def load_token(*args: Any) -> Tuple[int, str, ValType]:
    """ Convert a plain, usually JSON serialized, argument tuple
        to kind, txt, val attributes """
    kind, txt, val = args[:3]
    if kind == TOK.WORD:
        val = [BIN_Tuple(*v) for v in val]
    elif kind == TOK.PERSON:
        val = [PersonNameTuple(*v) for v in val]
    else:
        val = tuple(val)
    return kind, txt, cast(ValType, val)


class Bin_TOK(TOK):

    """ Override the TOK class from tokenizer.py to allow a dummy
        token parameter to be passed into token constructors where
        required. This again allows errtokenizer.py in GreynirCorrect
        to add token error information. """

    @staticmethod
    def Word(
        t: Union[Tok, str],
        m: Optional[BIN_TupleList] = None,
        token: Union[None, Tok, Sequence[Tok]] = None,
    ) -> Tok:
        # Note that the m parameter cannot be easily type annotated,
        # as the Tokenizer package is still using a .pyi (Python 2.7-compatible)
        # type annotation scheme
        r = TOK.Word(t, m)
        if token is not None:
            # We are basing this word token on a previously existing
            # token or list of tokens: copy the original text field(s)
            if isinstance(token, Tok):
                r.original = token.original
            else:
                r.original = "".join(t.original or "" for t in token)
        return r

    @staticmethod
    def Number(
        t: Union[Tok, str],
        n: float,
        cases: Optional[List[str]] = None,
        genders: Optional[List[str]] = None,
        token: Optional[Tok] = None,
    ) -> Tok:
        return TOK.Number(t, n, cases, genders)

    @staticmethod
    def Amount(
        t: Union[Tok, str],
        iso: str,
        n: float,
        cases: Optional[List[str]] = None,
        genders: Optional[List[str]] = None,
        token: Optional[Tok] = None,
    ) -> Tok:
        return TOK.Amount(t, iso, n, cases, genders)

    @staticmethod
    def Person(
        t: Union[Tok, str],
        m: Optional[PersonNameList] = None,
        token: Optional[Tok] = None,
    ) -> Tok:
        return TOK.Person(t, m)


def annotate(
    db: GreynirBin,
    token_ctor: TokenConstructor,
    token_stream: TokenIterator,
    *,
    auto_uppercase: bool = False,
    no_sentence_start: bool = False
):
    """ Look up word forms in the BIN word database. If auto_uppercase
        is True, change lower case words to uppercase if it looks likely
        that they should be uppercase. If no_sentence_start is True,
        don't assume that the token stream starts a sentence. """

    at_sentence_start = False

    # Consume the iterable source in token_stream (which may be a generator)
    for t in token_stream:
        if t.kind != TOK.WORD:
            # Not a word: relay the token unchanged
            yield t
            if t.kind == TOK.S_BEGIN or t.punctuation == ":":
                # After an S_BEGIN, and also after a colon, we consider ourselves
                # to be at a sentence starting point - unless
                # no_sentence_start is set to True
                at_sentence_start = not no_sentence_start
            elif t.kind != TOK.PUNCTUATION and t.kind != TOK.ORDINAL:
                # Wait until we have something other than punctuation or an
                # ordinal number to conclude that the sentence has started
                at_sentence_start = False
            continue
        # This is a word token
        w = t.txt
        if not t.val:
            # Look up word in BIN database
            w, m = db.lookup_g(w, at_sentence_start, auto_uppercase)
            if not m:
                # Check exceptional cases involving hyphens
                w = t.txt
                if w[0] in COMPOSITE_HYPHENS:
                    # Something like '-menn' in 'þingkonur og -menn'
                    _, m = db.lookup_g(w[1:], False, False)
                    if m:
                        m = [
                            BIN_Tuple(
                                # We leave the lemma intact here ('maður' for '-menn')
                                mm.stofn,
                                mm.utg,
                                mm.ordfl,
                                mm.fl,
                                # ...but keep the hyphen in the word form ('-menn')
                                w,
                                mm.beyging,
                            )
                            for mm in m
                        ]
                elif HYPHEN in w or COMPOSITE_HYPHEN in w:
                    # Word with embedded hyphen: 'marg-ítrekaðri',
                    # 'málfræði-greining'
                    parts = re.split(HYPHEN_SPLIT_RE, w)
                    # Start by checking whether it exists in BÍN without hyphens
                    w_new, m = "", []
                    if all(p[0].islower() for p in parts[1:]):
                        # ...but we only do this if all of the suffixes start
                        # with a lowercase character (so, we don't do this for
                        # 'Syðri-Hnaus' or 'Litla-Brekka')
                        w_new, m = db.lookup_g(
                            "".join(parts), at_sentence_start, auto_uppercase
                        )
                    else:
                        w_new = ""  # Included to silence warning about unbound variable
                    if m:
                        # Found without hyphens: use that word form
                        m = [
                            BIN_Tuple(
                                # Leave the lemma intact (but it may already contain
                                # hyphens inserted by the compound word recognizer)
                                mm.stofn,
                                mm.utg,
                                mm.ordfl,
                                mm.fl,
                                # Keep the word form as it originally appeared,
                                # with its hyphens
                                w,
                                mm.beyging,
                            )
                            for mm in m
                        ]
                        # Emulate what auto_uppercase does in this case
                        if auto_uppercase and w_new[0].isupper():
                            w = w[0].upper() + w[1:]
                    else:
                        # Not found without hyphens:
                        # Look up the last part only
                        _, m = db.lookup_g(parts[-1], False, False)
                        if m:
                            m = [
                                BIN_Tuple(
                                    # In this case, keep the hyphens in the lemma,
                                    # imitating the compound word recognizer
                                    "-".join(parts[:-1] + [mm.stofn]),
                                    mm.utg,
                                    mm.ordfl,
                                    mm.fl,
                                    # Keep the word form intact with hyphens
                                    w,
                                    mm.beyging,
                                )
                                for mm in m
                            ]

            # Yield a word tuple with meanings
            yield token_ctor.Word(
                w if auto_uppercase and t.txt not in PREFER_LOWERCASE else t.txt,
                m,
                token=t,
            )
        else:
            # Already have a meaning (most likely from an abbreviation that the
            # tokenizer has recognized)
            meanings = list(t.meanings)
            if not w.isupper() and " " not in w and "." not in w:
                # This token is not in all-caps and does not contain spaces or
                # periods. It is thus possible that it is an abbreviation that
                # could have additional meanings as a word in BÍN.
                w_new, m = db.lookup_g(w, at_sentence_start, auto_uppercase)
                if m:
                    # Additional meanings found: add them to
                    # the front of the meaning list, giving them a bit of
                    # priority over the dubious abbreviation
                    meanings = m + meanings
                    if auto_uppercase:
                        w = w_new
            yield token_ctor.Word(w, meanings, token=t)
        # We have yielded a word token: definitely no longer at sentence start
        at_sentence_start = False


def match_stem_list(
    token: Tok, stems: Mapping[str, T], filter_func: Optional[FilterFunction] = None,
) -> Optional[T]:
    """ Find the stem of a word token in given dict, or return None if not found """
    if token.kind != TOK.WORD:
        return None
    # Go through the meanings with their stems
    if token.val:
        for m in token.meanings:
            # If a filter function is given, pass candidates to it
            lower_stofn = m.stofn.lower()
            if lower_stofn in stems and (filter_func is None or filter_func(m)):
                return stems[lower_stofn]
    # No meanings found: this might be a foreign or unknown word
    # However, if it is still in the stems list we return True
    return stems.get(token.txt.lower(), None)


def case(bin_spec: str, default: str = "nf") -> str:
    """ Return the case specified in the bin_spec string """
    c = default
    if "NF" in bin_spec:
        c = "nf"
    elif "ÞF" in bin_spec:
        c = "þf"
    elif "ÞGF" in bin_spec:
        c = "þgf"
    elif "EF" in bin_spec:
        c = "ef"
    return c


def add_cases(cases: Set[str], bin_spec: str, default: str = "nf") -> None:
    """ Add the case specified in the bin_spec string, if any, to the cases set """
    c = case(bin_spec, default)
    if c:
        cases.add(c)


def all_cases(token: Tok, filter_func: Optional[FilterFunction] = None) -> List[str]:
    """ Return a list of all cases that the token can be in """
    cases: Set[str] = set()
    if token.kind == TOK.WORD and token.val:
        # Roll through the potential meanings and extract the cases therefrom
        for m in token.meanings:
            if filter_func is not None and not filter_func(m):
                continue
            if m.fl == "ob" or m.beyging == "-":
                # One of the meanings is an undeclined word: all cases apply
                cases = set(ALL_CASES)
                break
            add_cases(cases, m.beyging, "")
    return list(cases)


def all_common_cases(
    token1: Tok, token2: Tok, filter_func: Optional[FilterFunction] = None,
):
    """ Compute intersection of case sets for two tokens """
    set1 = set(all_cases(token1, filter_func))
    if not token2.val:
        # Token2 is not found in BÍN (probably an exotic currency name):
        # just return the cases of the first token
        return list(set1)
    set2 = set(all_cases(token2))
    return list(set1 & set2)


def all_genders(token: Tok) -> Optional[List[str]]:
    """ Return a list of the possible genders of the word in the token, if any """
    if token.kind != TOK.WORD:
        return None
    g: Set[str] = set()
    if token.val:

        def find_gender(m: BIN_Tuple) -> Optional[str]:
            if m.ordfl in GENDER_SET:
                return m.ordfl  # Plain noun
            # Probably number word ('töl' or 'to'): look at its spec
            for k, v in GENDER_DICT.items():
                if k in m.beyging:
                    return v
            return None

        for meaning in token.meanings:
            gn = find_gender(meaning)
            if gn is not None:
                g.add(gn)

    return list(g)


def parse_phrases_1(
    db: GreynirBin, token_ctor: TokenConstructor, token_stream: TokenIterator
) -> TokenIterator:
    """ Parse numbers and amounts """

    token: Tok = cast(Tok, None)

    try:

        # Maintain a one-token lookahead
        token = next(token_stream)
        while True:
            next_token: Tok = next(token_stream)

            # Check for [number] [AMOUNT|PERCENT]
            if token.kind == TOK.NUMBER and next_token.kind == TOK.WORD:

                if next_token.txt in AMOUNT_ABBREV:
                    # Abbreviations for ISK amounts
                    num = cast(NumberTuple, token.val)
                    original = (token.original or "") + (next_token.original or "")
                    token = token_ctor.Amount(
                        token.txt + " " + next_token.txt,
                        "ISK",
                        num[0] * AMOUNT_ABBREV[next_token.txt],
                        all_cases(next_token),
                        all_genders(next_token),
                    )
                    token.original = original
                    next_token = next(token_stream)
                else:
                    # Check for [number] [PERCENT]
                    percentage = match_stem_list(next_token, PERCENTAGES)
                    if percentage is not None:
                        # Found a word indicating percentage
                        original = (token.original or "") + (next_token.original or "")
                        token = token_ctor.Percent(
                            token.txt + " " + next_token.txt,
                            token.number,
                            all_cases(next_token),
                            all_genders(next_token),
                        )
                        token.original = original
                        # Eat the percentage token
                        next_token = next(token_stream)

            # Check for currency name doublets, for example
            # 'danish krona' or 'british pound'
            if token.kind == TOK.WORD and next_token.kind == TOK.WORD:
                nat = match_stem_list(token, NATIONALITIES)
                if nat is not None:
                    cur = match_stem_list(next_token, CURRENCIES)
                    if cur is not None:
                        if (nat, cur) in ISO_CURRENCIES:
                            # Match: accumulate the possible cases
                            iso_code = ISO_CURRENCIES[(nat, cur)]
                            # Filter the possible cases by considering adjectives
                            # having the correct form, i.e.
                            # strong inflection for indefinite nouns or
                            # weak inflection for definite nouns
                            if (
                                next_token.has_meanings
                                and "gr" in next_token.meanings[0].beyging
                                and next_token.meanings[0].stofn != "kró"
                            ):
                                # ("krónum" sometimes interpreted as
                                # definite form of word "kró")

                                # Definite form ('pundið', 'dollarinn')
                                form = "VB"
                            else:
                                # Indefinite form ('pund', 'dollari')
                                form = "SB"
                            original = (token.original or "") + (next_token.original or "")
                            token = token_ctor.Currency(
                                token.txt + " " + next_token.txt,
                                iso_code,
                                all_common_cases(
                                    token,
                                    next_token,
                                    lambda m: (m.ordfl == "lo" and form in m.beyging),
                                ),
                                [CURRENCY_GENDERS[cur]],
                            )
                            token.original = original
                            next_token = next(token_stream)

            # Check for composites:
            # 'stjórnskipunar- og eftirlitsnefnd'
            # 'dómsmála-, viðskipta- og iðnaðarráðherra'
            tq: List[Tok] = []
            while (
                token.kind == TOK.WORD or token.kind == TOK.ENTITY
            ) and next_token.punctuation == COMPOSITE_HYPHEN:
                tq.append(token)
                hyphen = TOK.Punctuation(next_token.txt, normalized=HYPHEN)
                hyphen.original = next_token.original
                tq.append(hyphen)
                # Check for optional comma after the prefix
                comma_token: Tok = next(token_stream)
                if comma_token.punctuation == ",":
                    # A comma is present: append it to the queue
                    # and skip to the next token
                    tq.append(comma_token)
                    comma_token = next(token_stream)
                # Reset our two lookahead tokens
                token = comma_token
                next_token = next(token_stream)

            if tq:
                # We have accumulated one or more prefixes
                # ('dómsmála-, viðskipta-')
                if token.kind == TOK.WORD and token.txt in ("og", "eða"):
                    # We have 'viðskipta- og'
                    if next_token.kind != TOK.WORD:
                        # Incorrect: yield the accumulated token
                        # queue and keep the current token and the
                        # next_token lookahead unchanged
                        for t in tq:
                            yield t
                    else:
                        # We have 'viðskipta- og iðnaðarráðherra'
                        # or 'dómsmála-, viðskipta- og iðnaðarráðherra'.
                        # Return a single token with the meanings of
                        # the last word, but an amalgamated token text.
                        # Note: there is no meaning check for the first
                        # part of the composition, so it can be an unknown word.
                        all_tq = tq + [token, next_token]
                        txt = " ".join(t.txt for t in all_tq)
                        txt = txt.replace(" -", "-").replace(" ,", ",")
                        # Create a fresh list of meanings with the full
                        # prefix in the ordmynd field
                        prefix = all_except_suffix(txt)
                        m = [
                            BIN_Tuple(
                                prefix + " " + mm.stofn,
                                mm.utg,
                                mm.ordfl,
                                mm.fl,
                                prefix + " " + mm.ordmynd,
                                mm.beyging,
                            )
                            for mm in cast(Tuple[BIN_Tuple, ...], next_token.val)
                        ]
                        # Copy attributes, such as capitalization status
                        # (cf. GreynirCorrect) from the first token in the queue
                        token = token_ctor.Word(txt, m, token=all_tq)
                        next_token = next(token_stream)
                else:
                    # Incorrect prediction: make amends and continue
                    for t in tq:
                        yield t

            # Yield the current token and advance to the lookahead
            yield token
            token = next_token

    except StopIteration:
        pass

    # Final token (previous lookahead)
    if token:
        yield token


def parse_phrases_2(
    token_stream: TokenIterator, token_ctor: TokenConstructor, auto_uppercase: bool
) -> TokenIterator:
    """ Parse a stream of tokens looking for phrases and making substitutions.
        Second pass: handle conversion of numbers + currencies into amounts,
        and process person names """

    token: Tok = cast(Tok, None)

    try:
        # Use TokenStream wrapper for iterator with lookahead
        token_stream = TokenStream(token_stream)

        token = next(token_stream)
        # Maintain a set of full person names encountered
        names: Set[PersonNameTuple] = set()
        at_sentence_start = False

        while True:
            next_token = next(token_stream)

            # Make the lookahead checks we're interested in
            # Check for [number] [currency] and convert to [amount]
            if token.kind == TOK.NUMBER and (
                next_token.kind == TOK.WORD or next_token.kind == TOK.CURRENCY
            ):
                # Preserve the case of the number, if available
                # (milljónir, milljóna, milljónum)
                num = cast(NumberTuple, token.val)
                cases = all_cases(next_token)
                genders = all_genders(next_token)
                cur = None

                if next_token.kind == TOK.WORD:
                    # Try to find a currency name
                    cur = match_stem_list(next_token, CURRENCIES)
                    if cur is None and next_token.txt.isupper():
                        # Might be an ISO abbrev (which is not in BÍN)
                        cur = CURRENCIES.get(next_token.txt)
                        if not genders:
                            # Try to find a correct gender for the ISO abbrev,
                            # or use neutral as a default
                            genders = [CURRENCY_GENDERS.get(next_token.txt, "hk")]
                            cases = list(ALL_CASES)

                elif next_token.kind == TOK.CURRENCY:
                    # Already have an ISO identifier for a currency
                    ct = cast(CurrencyTuple, next_token.val)
                    cur = ct[0]

                    # Use all cases and try to fetch gender from CURRENCY_GENDERS ("hk" by default)
                    # if no such information was given with the currency token itself
                    cases = ct[1] or list(ALL_CASES)
                    genders = ct[2] or [CURRENCY_GENDERS.get(next_token.txt.rstrip("."), "hk")]

                if cur is not None:
                    # Create an amount
                    # Use the case and gender information from the number, if any
                    original = (token.original or "") + (next_token.original or "")
                    token = token_ctor.Amount(
                        token.txt + " " + next_token.txt, cur, num[0], cases, genders,
                        token=next_token,
                    )
                    token.original = original
                    # Eat the currency token
                    next_token = next(token_stream)

            # Check for [time] [date] (absolute)
            if token.kind == TOK.TIME and next_token.kind == TOK.DATEABS:
                # Create a time stamp
                h, m, s = cast(DateTimeTuple, token.val)
                y, mo, d = cast(DateTimeTuple, next_token.val)
                original = (token.original or "") + (next_token.original or "")
                token = token_ctor.Timestampabs(
                    token.txt + " " + next_token.txt, y=y, mo=mo, d=d, h=h, m=m, s=s
                )
                token.original = original
                # Eat the time token
                next_token = next(token_stream)

            # Check for [time] [date] (relative)
            if token.kind == TOK.TIME and next_token.kind == TOK.DATEREL:
                # Create a time stamp
                h, m, s = cast(DateTimeTuple, token.val)
                y, mo, d = cast(DateTimeTuple, next_token.val)
                original = (token.original or "") + (next_token.original or "")
                token = token_ctor.Timestamprel(
                    token.txt + " " + next_token.txt, y=y, mo=mo, d=d, h=h, m=m, s=s
                )
                token.original = original
                # Eat the time token
                next_token = next(token_stream)

            # Logic for human names

            def stems(
                tok: Tok, categories: FrozenSet[str], given_name: bool = False
            ) -> Optional[List[PersonNameTuple]]:
                """ If the token denotes a given name, return its possible
                    interpretations, as a list of PersonName tuples (name, case, gender).
                    If given_name is True, we omit from the list all name forms that
                    occur in the disallowed_names section in the configuration file. """
                if tok.kind != TOK.WORD or not tok.val:
                    return None
                if at_sentence_start and tok.txt in NOT_NAME_AT_SENTENCE_START:
                    # Disallow certain person names at the start of sentences,
                    # such as 'Annar'
                    return None
                # Set up the names we're not going to allow
                dstems = DisallowedNames.STEMS if given_name else {}
                # Look through the token meanings
                result: List[PersonNameTuple] = []
                for m in tok.meanings:
                    if m.fl in categories and ("ET" in m.beyging or m.beyging == "-"):
                        # If this is a given name, we cut out name forms
                        # that are frequently ambiguous and wrong,
                        # i.e. "Frá" as accusative of the name "Frár",
                        # and "Sigurð" in the nominative.
                        c = case(m.beyging, default="-")
                        if m.stofn not in dstems or c not in dstems[m.stofn]:
                            # Note the stem ('stofn') and the gender from
                            # the word type ('ordfl')
                            result.append(
                                PersonNameTuple(name=m.stofn, gender=m.ordfl, case=c)
                            )
                return result or None

            def has_category(tok: Tok, categories: FrozenSet[str]) -> bool:
                """ Return True if the token matches a meaning
                    with any of the given categories """
                if tok.kind != TOK.WORD or not tok.val:
                    return False
                return any(m.fl in categories for m in tok.meanings)

            def has_other_meaning(tok: Tok, categories: FrozenSet[str]) -> bool:
                """ Return True if the token can denote something
                    besides a given name """
                if tok.kind != TOK.WORD or not tok.val:
                    return True
                # Return True if there is a different meaning, not a given name
                return any(m.fl not in categories for m in tok.meanings)

            # Check for person names
            def given_names(tok: Tok) -> Optional[List[PersonNameTuple]]:
                """ Check for Icelandic or foreign person name
                    (category 'ism', 'gæl' or 'erm') """
                if tok.kind != TOK.WORD or not tok.txt[0].isupper():
                    # Must be a word starting with an uppercase character
                    return None
                return stems(tok, PERSON_NAME_SET, given_name=True)

            # Check for surnames
            def surnames(tok: Tok) -> Optional[List[PersonNameTuple]]:
                """ Check for Icelandic patronym (category 'föð'),
                    matronym (category 'móð') or family names (category 'ætt') """
                if tok.kind != TOK.WORD or not tok.txt[0].isupper():
                    # Must be a word starting with an uppercase character
                    return None
                return stems(tok, PATRONYM_SET)

            # Check for unknown surnames
            def unknown_surname(tok: Tok) -> bool:
                """ Check for unknown (non-Icelandic) surnames """
                # Accept (most) upper case words as a surnames
                if auto_uppercase:
                    if tok.txt and not tok.val:
                        # Looks like an unknown word: accept it as a surname
                        # (might be a foreign name)
                        return True
                if tok.kind != TOK.WORD or not tok.txt[0].isupper():
                    # Must start with capital letter
                    return False
                if has_category(tok, PATRONYM_SET):
                    # This is a known surname, not an unknown one
                    return False
                if tok.txt in _CORPORATION_ENDINGS:
                    return False
                # Allow single-letter abbreviations, but not multi-letter
                # all-caps words (those are probably acronyms)
                return len(tok.txt) == 1 or not tok.txt.isupper()

            def given_names_or_middle_abbrev(
                tok: Tok,
            ) -> Optional[List[PersonNameTuple]]:
                """ Check for given name or middle abbreviation """
                gnames = given_names(tok)
                wrd = tok.txt
                if gnames is not None:
                    if wrd in BOTH_GIVEN_AND_FAMILY_NAMES:
                        # For instance "Hafstein" which can be both a given
                        # name and a family name: prepend the family name as
                        # an genderless and caseless option to the list
                        gnames = [
                            PersonNameTuple(name=wrd, gender=None, case=None)
                        ] + gnames
                    return gnames

                if tok.kind != TOK.WORD:
                    return None

                if auto_uppercase and wrd.rstrip(".") in MIDDLE_NAME_ABBREVS:
                    # Capitalize middle name abbreviations
                    wrd = wrd.capitalize()
                    # Also update token txt
                    tok.txt = wrd

                # If wrd (without following period) is longer than
                # middle name abbrevs such as "th", "kr" or "f"
                # or not a foreign middle name (like "al", "der", "van")
                elif (
                    len(wrd.rstrip(".")) > 2 or wrd[0].islower()
                ) and wrd not in FOREIGN_MIDDLE_NAME_SET:
                    return None

                # Either:
                # - One or two letter middle name abbreviation (possibly with following period)
                # - Lowercase foreign middle name ("Thomas de Broglie", "Ruud van Nistelrooy")
                return [PersonNameTuple(name=wrd, gender=None, case=None)]

            def compatible(pn: PersonNameTuple, npn: PersonNameTuple) -> bool:
                """ Return True if the next PersonNameTuple (npn) is compatible
                    with the one we have (pn) """
                # The neutral gender (hk) is used for family names and is
                # compatible with both masculine and feminine given names
                if npn.gender and npn.gender != "hk" and (npn.gender != pn.gender):
                    return False
                if npn.case and npn.case != "-" and (npn.case != pn.case):
                    return False
                return True

            gn: Optional[List[PersonNameTuple]] = None
            # Accumulated original token text for person name
            namespan: str = ""
            if (
                token.kind == TOK.WORD
                and token.has_meanings
                and token.meanings[0].fl == "nafn"
            ):
                # Convert a WORD with fl="nafn" to a PERSON with the correct gender,
                # in all cases
                namespan = token.original or ""
                gender = token.meanings[0].ordfl
                token = token_ctor.Person(
                    token.txt,
                    m = [PersonNameTuple(token.txt, gender, case) for case in ALL_CASES],
                    token = token,
                )
                token.original = namespan
            else:
                gn = given_names(token)

            if gn:
                # Found at least one given name: look for a sequence of given names
                # having compatible genders and cases
                w = token.txt
                namespan = token.original or ""
                patronym = False

                while True:
                    ntxt = next_token.txt

                    if auto_uppercase:
                        # Auto uppercasing of middle name abbreviations

                        # Interpret "s." as abbreviation of "símanúmer"
                        # when followed by telephone number
                        if ntxt == "s." and token_stream.kind() == TOK.TELNO:
                            # Followed by telephone number
                            # -> not a middle name abbreviation
                            break

                        # Other lowercase middle name abbreviations
                        if ntxt in MIDDLE_NAME_ABBREVS:

                            # Check if next token is a period
                            if token_stream.punctuation() == ".":
                                # Concatenate period token to middle name abbrev
                                # and remove period token
                                next_token = next_token.concatenate(next(token_stream))
                                ntxt = next_token.txt

                            elif (
                                ntxt in NOT_NAME_ABBREVS
                                and token_stream[0]
                                and not surnames(cast(Tok, token_stream[0]))
                            ):
                                # Next token is common word (such as "á", "í")
                                # and should only be considered a middle name
                                # if next word is a surname
                                break

                    # Deal with wrong sentence end/begin (S_END/S_BEGIN) tokens
                    # that sometimes appear in middle of sentence
                    # when middle name abbrevations end with period.
                    # However, if abbrev is last token in sentence, we keep the S_END token
                    if (
                        ntxt.endswith(".")
                        and ntxt.rstrip(".").lower() in MIDDLE_NAME_ABBREVS
                        and token_stream.kind(0) == TOK.S_END
                        and token_stream.kind(1) == TOK.S_BEGIN
                    ):
                        next(token_stream)  # Remove S_END
                        next(token_stream)  # Remove S_BEGIN

                    ngn = given_names_or_middle_abbrev(next_token)
                    if not ngn:
                        break
                    # Look through the stuff we got and see what is compatible
                    r: List[PersonNameTuple] = []
                    # pylint: disable=not-an-iterable
                    for p in gn:
                        # noinspection PyTypeChecker
                        for np in ngn:
                            if compatible(p, np):
                                # Compatible: add to result
                                r.append(
                                    PersonNameTuple(
                                        name=p.name + " " + np.name,
                                        gender=p.gender,
                                        case=p.case,
                                    )
                                )
                    if not r:
                        # This next name is not compatible with what we already
                        # have: break
                        break
                    # Success: switch to new given name list
                    gn = r
                    w += " " + next_token.txt
                    namespan += next_token.original or ""
                    next_token = next(token_stream)

                # Check whether the sequence of given names is followed
                # by one or more surnames (patronym/matronym) of the same gender,
                # for instance 'Dagur Bergþóruson Eggertsson'

                def eat_surnames(
                    gn: List[PersonNameTuple], w: str, patronym: bool, next_token: Tok
                ) -> Tuple[List[PersonNameTuple], str, bool, Tok]:
                    """ Process contiguous known surnames, typically "*dóttir/*son",
                        while they are compatible with the given name
                        we already have """
                    while True:
                        sn = surnames(next_token)
                        if not sn:
                            break
                        r: List[PersonNameTuple] = []
                        # Found surname: append it to the accumulated name,
                        # if compatible
                        for p in gn:
                            # pylint: disable=not-an-iterable
                            for np in sn:
                                if compatible(p, np):
                                    gender = (
                                        np.gender
                                        if (np.gender and np.gender != "hk")
                                        else p.gender
                                    )
                                    case = np.case if np.case != "-" else p.case
                                    r.append(
                                        PersonNameTuple(
                                            name=p.name + " " + np.name,
                                            gender=gender,
                                            case=case,
                                        )
                                    )
                        if not r:
                            break
                        # Compatible: include it and advance to the next token
                        gn = r
                        w += " " + next_token.txt
                        nonlocal namespan
                        namespan += next_token.original or ""
                        patronym = True
                        next_token = next(token_stream)
                    return gn, w, patronym, next_token

                gn, w, patronym, next_token = eat_surnames(gn, w, patronym, next_token)

                # Must have at least one possible name
                assert gn is not None
                assert len(gn) >= 1
                if not patronym:
                    # We stop name parsing after we find one or more Icelandic
                    # patronyms/matronyms. Otherwise, check whether we have an
                    # unknown uppercase word next;
                    # if so, add it to the person names we've already found
                    while unknown_surname(next_token):
                        ntxt = next_token.txt

                        if auto_uppercase and ntxt.islower():
                            ntxt = ntxt.capitalize()

                        for ix, p in enumerate(gn):
                            gn[ix] = PersonNameTuple(
                                name=p.name + " " + ntxt, gender=p.gender, case=p.case,
                            )
                        w += " " + ntxt
                        namespan += next_token.original or ""
                        next_token = next(token_stream)
                        # Assume we now have a patronym
                        patronym = True

                    if patronym:
                        # We still might have surnames coming up:
                        # eat them too, if present
                        gn, w, _, next_token = eat_surnames(gn, w, patronym, next_token)
                        assert gn is not None

                found_name = False
                # If we have a full name with patronym, store it
                if patronym:
                    names |= set(gn)
                else:
                    # Look through earlier full names and see whether this one matches
                    for ix, p in enumerate(gn):
                        gnames = p.name.split(" ")  # Given names
                        for lp in names:
                            match = (not p.gender) or (p.gender == lp.gender)
                            if match:
                                # The gender matches
                                # Leave the patronym off
                                lnames = set(lp.name.split(" ")[0:-1])
                                for n in gnames:
                                    if n not in lnames:
                                        # We have a given name that does not
                                        # match the person
                                        match = False
                                        break
                            if match:
                                # All given names match: assign the previously seen
                                # full name
                                gn[ix] = PersonNameTuple(
                                    name=lp.name, gender=lp.gender, case=p.case
                                )
                                found_name = True
                                break
                # If this is not a "strong" name, backtrack from recognizing it.
                # A "weak" name is (1) at the start of a sentence; (2) only one
                # word; (3) that word has a meaning that is not a name;
                # (4) the name has not been seen in a full form before;
                # (5) not on a 'well known name' list.
                weak = (
                    at_sentence_start
                    and (" " not in w)
                    and not patronym
                    and not found_name
                    and (
                        has_other_meaning(token, PERSON_NAME_SET)
                        and w not in NamePreferences.SET
                    )
                )

                if not weak:
                    # Return a person token with the accumulated name
                    # and the intersected set of possible cases
                    token = token_ctor.Person(w, gn)
                    token.original = namespan

            # Yield the current token and advance to the lookahead
            yield token
            if token.kind == TOK.S_BEGIN or token.punctuation == ":":
                at_sentence_start = True
            elif token.kind != TOK.PUNCTUATION and token.kind != TOK.ORDINAL:
                at_sentence_start = False
            token = next_token

    except StopIteration:
        pass

    # Final token (previous lookahead)
    if token:
        yield token


def parse_phrases_3(
    db: GreynirBin, token_stream: TokenIterator, token_ctor: TokenConstructor
) -> TokenIterator:
    """ Parse a stream of tokens looking for phrases and making substitutions.
        Third pass: coalesce uppercase, otherwise unrecognized words with
        a following person name, if any; also coalesce entity names and
        recognize company names by endings ('hf.', 'Inc.', etc.). """

    def is_interesting(token: Tok) -> bool:
        """ Return True if this token causes us to want to take
            a further look at the following tokens """
        if token.kind != TOK.ENTITY and token.kind != TOK.WORD:
            return False
        return token.txt[0].isupper()

    def can_concat(token: Tok) -> bool:
        """ Return True if the token content can be concatenated onto
            an existing entity name """
        # Non-capitalized function words that can appear within entity names
        if token.txt in ENTITY_MIDDLE_NAME_SET or token.txt in FOREIGN_MIDDLE_NAME_SET:
            return True
        if token.kind != TOK.ENTITY and token.kind != TOK.WORD:
            return False
        if not token.txt[0].isupper():
            return False
        if " " in token.txt:
            return False
        if token.kind == TOK.WORD and token.val:
            if any(m.stofn[0].isupper() for m in token.meanings):
                # This word has an independent uppercase meaning:
                # don't concatenate it
                return False
        return True

    def not_in_bin(token: Tok) -> bool:
        """ Return True if the token is not a normal word found in BÍN """
        if token.kind == TOK.ENTITY:
            return True
        assert token.kind == TOK.WORD
        if token.val:
            if all(m.ordfl != "entity" for m in token.meanings):
                # This word is found in BÍN and has no 'entity' meanings
                return False
        return True

    # The following declaration is a deliberate mypy hack
    token: Tok = cast(Tok, None)
    try:

        # Maintain a one-token lookahead
        token = next(token_stream)
        concatable = False

        while True:

            if not concatable and not is_interesting(token):
                if (
                    token.txt
                    and " " in token.txt
                    and token.txt.split(" ")[-1] in FOREIGN_MIDDLE_NAME_SET
                ):
                    # Combined in parse_phrases_2() but no capitalized word follows
                    # Should be split up
                    split = token.txt.split()
                    first = split[:-1]
                    middle = ""
                    orig = token.original
                    if first[-1] in FOREIGN_MIDDLE_NAME_SET:
                        # Allow one more check, in case of "de la"
                        middle = first[-1]
                        first = first[:-1]
                    if token.kind == TOK.PERSON:
                        token = token_ctor.Person(
                            " ".join(first),
                            [
                                PersonNameTuple(" ".join(first), pn.gender, pn.case)
                                for pn in token.person_names
                            ],
                        )
                    else:
                        token = token_ctor.Entity(" ".join(first))
                    token.original = orig
                    yield token
                    if middle:
                        _, m = db.lookup_g(middle)
                        x = token_ctor.Word(middle, m)
                        x.original = ""  # TODO: This could be made more intelligent
                        yield x
                    _, m = db.lookup_g(split[-1])
                    token = token_ctor.Word(split[-1], m)
                    token.original = ""  # TODO: This could be made more intelligent
                else:
                    yield token
                    # Make sure that token is None if next() raises StopIteration
                    token = cast(Tok, None)
                    token = next(token_stream)
                    continue
            next_token = next(token_stream)
            concatable = False

            if next_token.txt in _CORPORATION_ENDINGS:
                # Allow merging a corporation ending ('ehf.', 'Inc.'). This is fairly
                # open: any prefix consisting of uppercase words is
                # allowed, even if they are found in BÍN.
                original = (token.original or "") + (next_token.original or "")
                token = token_ctor.Company(token.txt + " " + next_token.txt)
                token.original = original
                next_token = next(token_stream)
            elif not_in_bin(token):
                if next_token.kind == TOK.PERSON and token.txt.istitle():
                    # Upper-case word that is either an entity or a word that is
                    # not in BÍN, and the next token is a person: merge the two
                    # tokens into a single person name
                    # 'Jesse' 'John Kelley' -> 'Jesse John Kelley'
                    original = (token.original or "") + (next_token.original or "")
                    token = token_ctor.Person(
                        token.txt + " " + next_token.txt,
                        [
                            PersonNameTuple(
                                token.txt + " " + pn.name, pn.gender, pn.case
                            )
                            for pn in next_token.person_names
                        ],
                    )
                    token.original = original
                    next_token = next(token_stream)
                elif can_concat(next_token):
                    # Concatenate the next token and do another loop round
                    original = (token.original or "") + (next_token.original or "")
                    token = token_ctor.Entity(token.txt + " " + next_token.txt)
                    token.original = original
                    concatable = True
                    continue

            # Yield the current token and advance to the lookahead
            yield token
            token = next_token

    except StopIteration:
        pass

    # Final token (previous lookahead)
    if token is not None:
        yield token


def fix_abbreviations(token_stream: TokenIterator) -> TokenIterator:
    """ Fix sentence splitting that may be wrong due to abbreviations """
    token: Tok = cast(Tok, None)
    try:
        # Maintain a one-token lookahead
        token = next(token_stream)
        while True:
            next_token = next(token_stream)
            # If we have a 'name finisher abbreviation'
            # (such as 'próf.' for 'prófessor') and the next token
            # is a text token but not a person, insert a sentence split
            if (
                token.kind == TOK.WORD
                and token.txt.lower() in Abbreviations.NAME_FINISHERS
                and next_token.kind in TOK.TEXT_EXCL_PERSON
            ):
                yield token
                yield TOK.End_Sentence()
                token = TOK.Begin_Sentence()
            # Yield the current token and advance to the lookahead
            yield token
            token = next_token
    except StopIteration:
        pass
    # Final token (previous lookahead)
    if token is not None:
        yield token


class MatchingStream:

    """ This class parses a stream of tokens while looking for
        multi-token matching sequences described in a phrase dictionary,
        and calling a matching function whenever those sequences
        occur in the stream, providing an opportunity to
        replace or modify these sequences.
    """

    def __init__(self, phrase_dictionary: StateDict) -> None:
        self._pdict = phrase_dictionary

    def key(self, token: Tok) -> Any:
        """ Generate a state key from the given token """
        return token.txt.lower()

    def match_state(self, key: Any, state: StateDict) -> StateList:
        """ Returns an iterable of states that match the key,
            or a falsy value if the key matches no states. """
        return state.get(key, [])

    def match(self, tq: List[Tok], ix: int) -> Iterable[Tok]:
        """ Called when we have found a match for the entire
            token queue tq, using the index ix """
        return tq

    def length(self, ix: int) -> int:
        """ Override this to provide the length of the actual
            phrase that matches at index ix """
        return 0

    def process(self, token_stream: TokenIterator) -> TokenIterator:
        """ Generate an output stream from the input token stream """
        # Token queue
        tq: List[Tok] = []
        # Phrases we're considering
        state: StateDict = defaultdict(list)
        pdict = self._pdict  # The phrase dictionary
        token: Optional[Tok]

        try:

            while True:

                token = next(token_stream)

                if token.txt is None:
                    # Not a word: no match; yield the token queue
                    if tq:
                        yield from tq
                        tq = []
                    # Discard the previous state, if any
                    if state:
                        state = defaultdict(list)
                    # ...and yield the non-matching token
                    yield token
                    continue

                # Look for matches in the current state and build a new state
                newstate: StateDict = defaultdict(list)
                key = self.key(token)

                def add_to_state(slist: List[str], index: int) -> None:
                    """ Add the list of subsequent words to the new parser state """
                    next_key = slist[0]
                    rest = slist[1:]
                    newstate[next_key].append((rest, index))

                def accept(state: List[Tuple[List[str], int]]) -> TokenIterator:
                    """ The current token matches the given state, either as
                        a continuation of a previous state or as an initiation
                        of a new phrase """
                    nonlocal token, newstate, tq
                    if token:
                        tq.append(token)
                        token = cast(Tok, None)
                    # sl is the continuation list (possible next tokens)
                    # for each state
                    for sl, ix in state:
                        if not sl:
                            # No continuation token from this state:
                            # this is a complete match
                            phrase_length = self.length(ix)
                            while len(tq) > phrase_length:
                                # We have extra queued tokens in the token queue
                                # that belong to a previously seen partial phrase
                                # that was not completed: yield them first
                                yield tq.pop(0)
                            if tq:
                                # Let the match function decide what to yield
                                # from this matched state
                                yield from self.match(tq, ix)
                                tq = []
                            # Make sure that we start from a fresh state and
                            # a fresh token queue when processing the next token
                            if newstate:
                                newstate = defaultdict(list)
                            # Note that it is possible to match even longer phrases
                            # by including a starting phrase in its entirety in
                            # the static phrase dictionary
                            break
                        # Nonempty continuation: add it to the next state
                        add_to_state(sl, ix)

                siter = self.match_state(key, state)
                if siter:
                    # This matches an expected token:
                    # go through potential continuations
                    yield from accept(siter)
                else:
                    # This matches no expected token, i.e. is not a
                    # continuation of any previously pushed state
                    if tq:
                        # Yield the accumulated token queue
                        yield from tq
                        tq = []
                    # Check whether this token starts a new phrase.
                    # Note: we cannot allow the last token of a
                    # previous phrase to start a new phrase, since it
                    # has already been consumed and acted upon
                    # (and, indeed, in that case the token variable
                    # would contain None at this point)
                    siter = self.match_state(key, pdict)
                    if siter:
                        # This word potentially starts a new phrase
                        yield from accept(siter)
                    elif token:
                        # Not starting a new phrase: pass the token through
                        yield token

                # Transition to the new state
                state = newstate

        except StopIteration:
            # Token stream is exhausted
            pass

        # Yield any tokens remaining in queue
        yield from tq


class StaticPhraseStream(MatchingStream):

    """ Process a stream of tokens looking for static multiword phrases
        (i.e. phrases that are not affected by inflection).
        The algorithm implements N-token lookahead where N is the
        length of the longest phrase.
    """

    def __init__(self, token_ctor: TokenConstructor, auto_uppercase: bool) -> None:
        super().__init__(StaticPhrases.DICT)
        self._token_ctor = token_ctor
        self._auto_uppercase = auto_uppercase

    def length(self, ix: int) -> int:
        return StaticPhrases.get_length(ix)

    def key(self, token: Tok) -> Tuple[str, str]:
        """ We allow both the original token text and a lowercase
            version of it to match """
        wo = token.txt  # Original word
        w = wo.lower()  # Lower case
        if w is not wo and (w == wo):
            wo = w
        return wo, w

    def match_state(self, key: Tuple[str, str], state: StateDict) -> StateList:
        """ First check for original (uppercase) word in the state, if any;
            if that doesn't match, check the lower case """
        wm = ""
        wo, w = key
        if self._auto_uppercase and len(wo) == 1 and w != wo:
            # If we are auto-uppercasing, leave single-letter lowercase
            # phrases alone, i.e. 'g' for 'gram' and 'm' for 'meter'
            wm = wo
        elif wo is not w and wo in state:
            wm = wo  # Original word
        elif w in state:
            wm = w  # Lowercase version
        return state.get(wm, [])

    def match(self, tq: List[Tok], ix: int) -> Iterable[Tok]:
        w = " ".join([t.txt for t in tq])
        # Add the entire phrase as one 'word' to the token queue.
        # Note that the StaticPhrases meaning list will be converted
        # to BIN_Tuple tuples in the annotate() pass.
        # Also note that the entire token queue is sent in as
        # the token parameter, as any token in the queue may
        # contain error information.
        newtok = self._token_ctor.Word(w, StaticPhrases.get_meaning(ix), token=tq)
        yield newtok


def parse_static_phrases(
    token_stream: TokenIterator, token_ctor: TokenConstructor, auto_uppercase: bool
) -> TokenIterator:
    """ Use the StaticPhraseStream class to process the token stream
        and replace static phrases with single tokens """
    sps = StaticPhraseStream(token_ctor, auto_uppercase)
    return sps.process(token_stream)


class DisambiguationStream(MatchingStream):

    """ Disambiguates a token stream by only retaining word
        meanings that have categories matching those allowed
        in the [disambiguate_phrases] section in config/Phrases.conf """

    def __init__(self, token_ctor: TokenConstructor) -> None:
        super().__init__(AmbigPhrases.DICT)
        self._token_ctor = token_ctor

    def key(self, token: Tok) -> DisambiguationTuple:
        """ Generate a phrase key from the given token """
        # Construct a set of all possible lemmas of this word form
        if token.kind == TOK.WORD:
            return token.txt.lower(), frozenset(m.stofn + "*" for m in token.meanings)
        return token.txt.lower(), frozenset()

    def match_state(self, key: DisambiguationTuple, state: StateDict) -> StateList:
        """ Called to see if the current token's key matches
            the given state. Returns the value that should be
            used to look up the key within the state, or None
            if there is no match. """
        # First, check for a direct text match
        txt, stems = key
        states = list(state.get(txt, []))
        # Then, check whether the stems of the token match any
        # asterisk-marked entry in the state
        for stem in stems:
            if stem in state:
                states.extend(state[stem])
        return states

    def length(self, ix: int) -> int:
        return len(AmbigPhrases.get_cats(ix))

    def match(self, tq: List[Tok], ix: int) -> Iterable[Tok]:
        """ We have a phrase match: return the tokens in the token
            queue, but with their meanings filtered down to only
            the word categories specified in the phrase configration """
        cats = AmbigPhrases.get_cats(ix)
        words = AmbigPhrases.get_words(ix)
        token_ctor = self._token_ctor
        assert len(tq) == len(cats)
        for t, cat_set, word in zip(tq, cats, words):
            # Yield a new token with fewer meanings for each
            # original token in the queue
            if t.kind != TOK.WORD or "*" in cat_set:
                # Not a word or no category constraint:
                # nothing to do
                yield t
                continue
            # Prepare the constrained list of meanings
            if "fs" in cat_set:
                # Handle prepositions specially, since we may have additional
                # preps defined in Main.conf that don't have fs meanings in BÍN
                w = t.txt.lower()
                mm = [BIN_Tuple(w, 0, "fs", "alm", w, "-")]
                cat_set = cat_set - frozenset(("fs",))
                # !!! BUG: constraining the meanings of prepositions (ordfl=fs)
                # !!! isn't currently meaningful, since the matcher in binparser.py
                # !!! for fs terminals doesn't look at the token meanings
            else:
                mm = []
            if cat_set:
                # Eliminate meanings that are not in the allowed category
                # set, or that have stems that don't match a stem specification
                # (i.e. phrase components marked with an asterisk, such as 'eiga*')
                stem = word[:-1] if word[-1] == "*" else None
                mm.extend(
                    m
                    for m in t.meanings
                    if m.ordfl in cat_set and (stem is None or m.stofn == stem)
                )

            yield token_ctor.Word(t.txt, mm, token=t)


def disambiguate_phrases(
    token_stream: TokenIterator, token_ctor: TokenConstructor
) -> TokenIterator:

    """ Parse a stream of tokens looking for common ambiguous multiword phrases
        (i.e. phrases that have a well known very likely interpretation but
        other extremely uncommon ones are also grammatically correct).
    """

    ds = DisambiguationStream(token_ctor)
    yield from ds.process(token_stream)


class DefaultPipeline:

    """ A DefaultPipeline encapsulates a sequence of tokenization
        phases, with each phase being a generator that accepts
        tokens from its input stream and yields tokens on its
        output stream. Individual phases in the sequence can
        easily be overridden in derived classes. """

    _token_ctor: TokenConstructor = Bin_TOK

    def __init__(self, text_or_gen: StringIterable, **options: Any) -> None:
        self._text_or_gen = text_or_gen
        self._auto_uppercase: bool = options.pop("auto_uppercase", False)
        self._no_sentence_start: bool = options.pop("no_sentence_start", False)
        self._options = options
        self._db: Optional[GreynirBin] = None
        # Initialize the default tokenizer pipeline.
        # This sequence of phases can be modified in derived classes.
        self._phases: List[PhaseFunction] = [
            self.tokenize_without_annotation,
            self.correct_tokens,
            self.parse_static_phrases,
            self.annotate,
            self.recognize_entities,
            self.check_spelling,
            self.parse_phrases_1,
            self.parse_phrases_2,
            self.parse_phrases_3,
            self.fix_abbreviations,
            self.disambiguate_phrases,
            self.final_correct,
        ]

    def tokenize_without_annotation(self) -> TokenIterator:
        """ The basic, raw tokenization from the tokenizer package """
        return tokenize_without_annotation(self._text_or_gen, **self._options)

    def parse_static_phrases(self, stream: TokenIterator) -> TokenIterator:
        """ Static multiword phrases """
        return parse_static_phrases(stream, self._token_ctor, self._auto_uppercase)

    def correct_tokens(self, stream: TokenIterator) -> TokenIterator:
        """ Token-level correction can be plugged in here (default stack doesn't do
            any corrections, but this is overridden in GreynirCorrect) """
        return stream

    def annotate(self, stream: TokenIterator) -> TokenIterator:
        """ Lookup meanings from dictionary """
        assert self._db is not None
        return annotate(
            self._db,
            self._token_ctor,
            stream,
            auto_uppercase=self._auto_uppercase,
            no_sentence_start=self._no_sentence_start,
        )

    def recognize_entities(self, stream: TokenIterator) -> TokenIterator:
        """ Recognize named entities. Default stack doesn't do anything,
            but derived classes can override this. """
        return stream

    def check_spelling(self, stream: TokenIterator) -> TokenIterator:
        """ Spelling correction can be plugged in here (default stack doesn't do
            any corrections, but this is overridden in GreynirCorrect) """
        return stream

    def parse_phrases_1(self, stream: TokenIterator) -> TokenIterator:
        """ Numbers and amounts """
        assert self._db is not None
        return parse_phrases_1(self._db, self._token_ctor, stream)

    def parse_phrases_2(self, stream: TokenIterator) -> TokenIterator:
        """ Currencies, person names """
        return parse_phrases_2(stream, self._token_ctor, self._auto_uppercase)

    def parse_phrases_3(self, stream: TokenIterator) -> TokenIterator:
        """ Additional person and entity name logic """
        assert self._db is not None
        return parse_phrases_3(self._db, stream, self._token_ctor)

    def fix_abbreviations(self, stream: TokenIterator) -> TokenIterator:
        """ Fix sentence splitting relating to abbreviations """
        return fix_abbreviations(stream)

    def disambiguate_phrases(self, stream: TokenIterator) -> TokenIterator:
        """ Eliminate very uncommon meanings """
        return disambiguate_phrases(stream, self._token_ctor)

    def final_correct(self, stream: TokenIterator) -> TokenIterator:
        """ Late-stage token correction, overridden in GreynirCorrect """
        return stream

    def tokenize(self) -> TokenIterator:
        """ Tokenize text in several phases, returning a generator of tokens
            that processes the text on-demand. If auto_uppercase is True, the tokenizer
            attempts to correct lowercase words that probably should be uppercase.
            If correction_func is not None, the given generator function is inserted
            into the token chain after processing static phrases but before
            BÍN annotation. This gives an opportunity to perform context-independent
            spelling corrections and the like. """

        if self._db is not None:
            # This should never occur, even in multi-threaded programs, since
            # each tokenize() call creates its own instance of DefaultPipeline
            raise ValueError("DefaultPipeline.tokenize() is not re-entrant")

        # We stack the tokenization phases together. Each generator
        # becomes a consumer of the previous generator.

        # Thank you Python for enabling this programming pattern ;-)

        with GreynirBin.get_db() as db:
            try:
                self._db = db
                # First tokenization phase
                token_stream = cast(FirstPhaseFunction, self._phases[0])()
                # Stack the other phases on top of each other
                for phase in self._phases[1:]:
                    token_stream = cast(FollowingPhaseFunction, phase)(token_stream)
                # ...and return the resulting chained generator
                return token_stream
            finally:
                self._db = None


def tokenize(text: StringIterable, **options: Any) -> TokenIterator:
    """ Tokenize text using the default pipeline """
    pipeline = DefaultPipeline(text, **options)
    return pipeline.tokenize()


def tokens_are_foreign(tokens: TokenIterable, min_icelandic_ratio: float) -> bool:
    """ Return True if the given tokens are probably not in Icelandic """
    words_in_bin = 0
    words_not_in_bin = 0
    # Enumerate through the tokens
    for t in tokens:
        if t.kind == TOK.WORD:
            if t.val:
                # The word has at least one meaning
                words_in_bin += 1
            else:
                # The word has no recognized meaning
                words_not_in_bin += 1
        elif t.kind == TOK.PERSON:
            # Person names count as recognized words
            words_in_bin += 1
        elif t.kind == TOK.ENTITY:
            # Entity names do not count as recognized words;
            # we count each enclosed word in the entity name
            words_not_in_bin += t.txt.count(" ") + 1
    # Return True if the sentence has at least three words
    # but less than 60% of them are found in BÍN
    num_words = words_in_bin + words_not_in_bin
    return num_words > 2 and words_in_bin / num_words < min_icelandic_ratio


def stems_of_token(t: "TokenDict") -> List[Tuple[str, str]]:
    """ Return a list of word stem descriptors associated with the token t.
        This is an empty list if the token is not a word or person or entity name.
    """
    kind = t.get("k", TOK.WORD)
    if kind not in {TOK.WORD, TOK.PERSON, TOK.ENTITY}:
        # No associated stem
        return []
    if kind == TOK.WORD:
        # Obtain the stem and the word category from the 'm' (meaning) field,
        # if present
        m = t.get("m")
        if m:
            stem, cat = m[0], m[1]
            return [(stem, cat)]
        # Entity or unknown word: fall through
    elif kind == TOK.PERSON:
        # The full person name, in nominative case, is stored in the 'v' field
        stem = t["v"]
        if "t" in t:
            # The gender is at the end of the corresponding terminal name
            gender = "_" + t["t"].split("_")[-1]
        elif "g" in t:
            # No terminal: there might be a dedicated gender ('g') field
            gender = "_" + t["g"]
        else:
            # No known gender
            gender = ""
        return [(stem, "person" + gender)]
    # TOK.ENTITY or unknown word
    stem = t["x"]
    return [(stem, "entity")]


def choose_full_name(
    val: PersonNameList, case: Optional[str], gender: Optional[str]
) -> Tuple[str, str]:
    """ From a list of name possibilities in val, and given a case and a gender
        (which may be None), return the best matching full name and gender """
    fn_list = [
        (fn, g, c)
        for fn, g, c in val
        if (gender is None or g == gender) and (case is None or c == case)
    ]
    if not fn_list:
        # Oops - nothing matched this. Might be a foreign, undeclinable name.
        # Try nominative if it wasn't alredy tried
        if case is not None and case != "nf":
            fn_list = [
                (fn, g, c)
                for fn, g, c in val
                if (gender is None or g == gender) and (case == "nf")
            ]
        # If still nothing, try anything with the same gender
        if not fn_list and gender is not None:
            fn_list = [(fn, g, c) for fn, g, c in val if (g == gender)]
        # If still nothing, give up and select the first available meaning
        if not fn_list:
            fn, g, c = val[0]
            fn_list = [(fn, g, c)]
    # If there are many choices, select the nominative case,
    # or the first element as a last resort
    ft = next((fn for fn in fn_list if fn[2] == "nf"), fn_list[0])
    return ft[0], (ft[1] if gender is None else gender) or "hk"

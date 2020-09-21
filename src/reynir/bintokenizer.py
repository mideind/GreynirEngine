"""

    Greynir: Natural language processing for Icelandic

    Dictionary-aware tokenization layer

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

    This module adds layers on top of the "raw" tokenizer in
    tokenizer.py. These layers annotate the token stream with word
    meanings from the BIN lexicon of Icelandic, identify multi-word
    phrases, process person names, etc.

"""

from typing import (
    cast,
    Optional,
    NamedTuple,
    Tuple,
    List,
    Dict,
    Union,
    Iterable,
    Iterator,
    Set,
    FrozenSet,
    Callable,
    Type,
    Any,
)

import sys
import re
from collections import defaultdict

from tokenizer import (
    TOK,
    Tok,
    tokenize_without_annotation,
    normalized_text,
    Abbreviations,
)

# The following imports are here in order to be visible in clients
# (they are not used in this module)
from tokenizer import (
    tokenize as raw_tokenize,
    correct_spaces,
    paragraphs,
    parse_tokens,
)

from .settings import StaticPhrases, AmbigPhrases, DisallowedNames
from .settings import NamePreferences
from .bindb import BIN_Db, BIN_Meaning


if "PyPy 7.3.0" in sys.version or "PyPy 7.2." in sys.version:
    # Patch bug in PyPy 7.2/7.3.0, which may raise an erroneous exception on str.rsplit()
    def all_except_suffix(s):
        try:
            return s[0 : s.rindex(" ")]
        except ValueError:
            # String does not contain a space: return it whole
            return s


else:
    all_except_suffix = lambda s: s.rsplit(maxsplit=1)[0]


# Named tuple for person names, including case and gender
PersonName = NamedTuple(
    "PersonName", [("name", str), ("gender", Optional[str]), ("case", Optional[str])]
)
# The type of a list of tokens
TokenList = List[Tok]
# The input argument type for the tokenize() function and derivatives thereof
StringIterable = Union[str, Iterable[str]]
# The type of a stream of tokens
TokenIterator = Iterator[Tok]
# The type of a token val field
TokenValType = Union[List[BIN_Meaning], List[PersonName], Tuple, None]
# The type of a tokenization pipeline phase
FirstPhaseFunction = Callable[[], TokenIterator]
FollowingPhaseFunction = Callable[[TokenIterator], TokenIterator]
PhaseFunction = Union[FirstPhaseFunction, FollowingPhaseFunction]

# Person names that are not recognized at the start of sentences
NOT_NAME_AT_SENTENCE_START = {
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
}

# Set of all cases (nominative, accusative, dative, genitive)
ALL_CASES = frozenset(["nf", "þf", "þgf", "ef"])

HYPHEN = "-"  # Normal hyphen
EN_DASH = "\u2013"  # "–"
EM_DASH = "\u2014"  # "—"
COMPOSITE_HYPHEN = EN_DASH
COMPOSITE_HYPHENS = HYPHEN + EN_DASH

# Prefixes that can be applied to adjectives with an intervening hyphen
ADJECTIVE_PREFIXES = frozenset(["hálf", "marg", "semí", "full"])

# Recognize words that multiply numbers
MULTIPLIERS = {
    # "núll": 0,
    # "hálfur": 0.5,
    # "helmingur": 0.5,
    # "þriðjungur": 1.0 / 3,
    # "fjórðungur": 1.0 / 4,
    # "fimmtungur": 1.0 / 5,
    "einn": 1,
    "tveir": 2,
    "þrír": 3,
    "fjórir": 4,
    "fimm": 5,
    "sex": 6,
    "sjö": 7,
    "átta": 8,
    "níu": 9,
    "tíu": 10,
    "ellefu": 11,
    "tólf": 12,
    "þrettán": 13,
    "fjórtán": 14,
    "fimmtán": 15,
    "sextán": 16,
    "sautján": 17,
    "seytján": 17,
    "átján": 18,
    "nítján": 19,
    "tuttugu": 20,
    "þrjátíu": 30,
    "fjörutíu": 40,
    "fimmtíu": 50,
    "sextíu": 60,
    "sjötíu": 70,
    "áttatíu": 80,
    "níutíu": 90,
    # "par": 2,
    # "tugur": 10,
    # "tylft": 12,
    "hundrað": 100,
    "þúsund": 1000,  # !!! Bæði hk og kvk!
    "þús.": 1000,
    "milljón": 1e6,
    "milla": 1e6,
    "millj.": 1e6,
    "milljarður": 1e9,
    "miljarður": 1e9,
    "ma.": 1e9,
    "mrð.": 1e9,
}

# The following must occur as lemmas in BÍN
DECLINABLE_MULTIPLIERS = frozenset(("hundrað", "þúsund", "milljón", "milljarður"))

# Recognize words for percentages
PERCENTAGES = {"prósent": 1, "prósenta": 1, "hundraðshluti": 1, "prósentustig": 1}

# Recognize words for nationalities (used for currencies)
NATIONALITIES = {
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
ISO_CURRENCIES = {
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
AMOUNT_ABBREV = {
    "kr.": 1,
    "kr": 1,
    "þ.kr.": 1e3,
    "þ.kr": 1e3,
    "þús.kr.": 1e3,
    "þús.kr": 1e3,
    "m.kr.": 1e6,
    "m.kr": 1e6,
    "mkr.": 1e6,
    "mkr": 1e6,
    "ma.kr.": 1e9,
    "ma.kr": 1e9,
    "mrð.kr.": 1e9,
    "mrð.kr": 1e9,
}

# Number words can be marked as subjects (any gender) or as numbers
NUMBER_CATEGORIES = frozenset(["töl", "to", "kk", "kvk", "hk", "lo"])

# Recognize words for currencies
CURRENCIES = {
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

CURRENCY_GENDERS = {
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
# person names, Icelandic ('ism') or foreign ('erm')
PERSON_NAME_SET = frozenset(("ism", "erm"))

# Set of categories (fl fields in BÍN) for patronyms
# and matronyms, as well as gender-neutral family names
PATRONYM_SET = frozenset(("föð", "móð", "ætt"))

# Set of foreign middle names that start with a lower case letter
# ('Louis de Broglie', 'Jan van Eyck')
# 'of' was also here but caused problems
FOREIGN_MIDDLE_NAME_SET = frozenset(("van", "de", "den", "der", "el", "al"))

# Given names that can also be family names (and thus gender- and caseless as such)
BOTH_GIVEN_AND_FAMILY_NAMES = frozenset(("Hafstein",))

# Note: these must have a meaning for this to work, so specifying them
# as abbreviations to Main.conf is recommended
_CORPORATION_ENDINGS = frozenset(
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


def load_token(*args) -> Tuple[int, str, TokenValType]:
    """ Convert a plain, usually JSON serialized, argument tuple
        to kind, txt, val attributes """
    kind, txt, val = args[0], args[1], args[2]
    if kind == TOK.WORD:
        val = [BIN_Meaning(*v) for v in val]
    elif kind == TOK.PERSON:
        val = [PersonName(*v) for v in val]
    else:
        val = tuple(val)
    return kind, txt, val


def annotate(db, token_ctor, token_stream, auto_uppercase):
    """ Look up word forms in the BIN word database. If auto_uppercase
        is True, change lower case words to uppercase if it looks likely
        that they should be uppercase. """

    at_sentence_start = False

    # Consume the iterable source in token_stream (which may be a generator)
    for t in token_stream:
        if t.kind != TOK.WORD:
            # Not a word: relay the token unchanged
            yield t
            if t.kind == TOK.S_BEGIN or (t.kind == TOK.PUNCTUATION and t.val[1] == ":"):
                # After an S_BEGIN, and also after a colon, we consider ourselves
                # to be at a sentence starting point
                at_sentence_start = True
            elif t.kind != TOK.PUNCTUATION and t.kind != TOK.ORDINAL:
                # Wait until we have something other than punctuation or an
                # ordinal number to conclude that the sentence has started
                at_sentence_start = False
            continue
        w = t.txt
        if not t.val:
            # Look up word in BIN database
            w, m = db.lookup_word(w, at_sentence_start, auto_uppercase)
            if not m:
                # Check exceptional cases involving hyphens
                w = t.txt
                if w[0] in COMPOSITE_HYPHENS:
                    # Something like '-menn' in 'þingkonur og -menn'
                    _, m = db.lookup_word(w[1:], False, False)
                    if m:
                        m = [
                            BIN_Meaning(
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
                elif HYPHEN in w or EN_DASH in w:
                    # Word with embedded hyphen: 'marg-ítrekaðri',
                    # 'málfræði-greining'
                    parts = re.split(r"[" + HYPHEN + EN_DASH + r"]", w)
                    # Start by checking whether it exists in BÍN without hyphens
                    if all(p[0].islower() for p in parts[1:]):
                        # ...but we only do this if all of the suffixes start
                        # with a lowercase character (so, we don't do this for
                        # 'Syðri-Hnaus' or 'Litla-Brekka')
                        w_new, m = db.lookup_word(
                            "".join(parts), at_sentence_start, auto_uppercase
                        )
                    if m:
                        # Found without hyphens: use that word form
                        m = [
                            BIN_Meaning(
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
                        _, m = db.lookup_word(parts[-1], False, False)
                        if m:
                            m = [
                                BIN_Meaning(
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
            yield token_ctor.Word(w, m, token=t)
        else:
            # Already have a meaning (most likely from an abbreviation that the
            # tokenizer has recognized), which probably needs conversion
            # from a bare tuple to a BIN_Meaning
            meanings = list(map(BIN_Meaning._make, t.val))
            if not w.isupper() and " " not in w and "." not in w:
                # This token is not in all-caps and does not contain spaces or
                # periods. It is thus possible that it is an abbreviation that
                # could have additional meanings as a word in BÍN.
                w_new, m = db.lookup_word(w, at_sentence_start, auto_uppercase)
                if m:
                    # Additional meanings found: add them to
                    # the front of the meaning list, giving them a bit of
                    # priority over the dubious abbreviation
                    # !!! TODO: Consider doing list(set(m + meanings)) to
                    # !!! eliminate duplicates
                    meanings = m + meanings
                    w = w_new
            yield token_ctor.Word(w, meanings, token=t)
        # We have yielded a word token: definitely no longer at sentence start
        at_sentence_start = False


def match_stem_list(token, stems, filter_func=None):
    """ Find the stem of a word token in given dict, or return None if not found """
    if token.kind != TOK.WORD:
        return None
    # Go through the meanings with their stems
    if token.val:
        for m in token.val:
            # If a filter function is given, pass candidates to it
            lower_stofn = m.stofn.lower()
            if lower_stofn in stems and (filter_func is None or filter_func(m)):
                return stems[lower_stofn]
    # No meanings found: this might be a foreign or unknown word
    # However, if it is still in the stems list we return True
    return stems.get(token.txt.lower(), None)


def case(bin_spec, default="nf"):
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


def add_cases(cases, bin_spec, default="nf"):
    """ Add the case specified in the bin_spec string, if any, to the cases set """
    c = case(bin_spec, default)
    if c:
        cases.add(c)


def all_cases(token, filter_func=None):
    """ Return a list of all cases that the token can be in """
    cases: Union[FrozenSet[str], Set[str]] = set()
    if token.kind == TOK.WORD and token.val:
        # Roll through the potential meanings and extract the cases therefrom
        for m in token.val:
            if filter_func is not None and not filter_func(m):
                continue
            if m.fl == "ob":
                # One of the meanings is an undeclined word: all cases apply
                cases = ALL_CASES
                break
            add_cases(cases, m.beyging, None)
    return list(cases)


def all_common_cases(token1, token2, filter_func=None):
    """ Compute intersection of case sets for two tokens """
    set1 = set(all_cases(token1, filter_func))
    if not token2.val:
        # Token2 is not found in BÍN (probably an exotic currency name):
        # just return the cases of the first token
        return list(set1)
    set2 = set(all_cases(token2))
    return list(set1 & set2)


_GENDER_SET = {"kk", "kvk", "hk"}
_GENDER_DICT = {"KK": "kk", "KVK": "kvk", "HK": "hk"}


def all_genders(token):
    """ Return a list of the possible genders of the word in the token, if any """
    if token.kind != TOK.WORD:
        return None
    g = set()
    if token.val:

        def find_gender(m):
            if m.ordfl in _GENDER_SET:
                return m.ordfl  # Plain noun
            # Probably number word ('töl' or 'to'): look at its spec
            for k, v in _GENDER_DICT.items():
                if k in m.beyging:
                    return v
            return None

        for meaning in token.val:
            gn = find_gender(meaning)
            if gn is not None:
                g.add(gn)

    return list(g)


def parse_phrases_1(db, token_ctor, token_stream):
    """ Parse numbers and amounts """

    token = None
    try:

        # Maintain a one-token lookahead
        token = next(token_stream)
        while True:
            next_token = next(token_stream)

            # Logic for numbers that are partially or entirely
            # written out in words

            def number(tok):
                """ If the token denotes a number, return that number - or None """
                if tok.txt.lower() == "áttu":
                    # Do not accept 'áttu' (stem='átta', no kvk) as a number
                    return None
                return match_stem_list(
                    tok, MULTIPLIERS, filter_func=lambda m: m.ordfl in NUMBER_CATEGORIES
                )

            # Check whether we have an initial number word
            multiplier = number(token) if token.kind == TOK.WORD else None

            # Check for [number] 'hundred|thousand|million|billion'
            while (
                token.kind == TOK.NUMBER or multiplier is not None
            ) and next_token.kind == TOK.WORD:

                multiplier_next = number(next_token)

                def convert_to_num(token):
                    if multiplier is not None:
                        token = token_ctor.Number(
                            token.txt,
                            multiplier,
                            all_cases(token),
                            all_genders(token),
                            token=token,
                        )
                    return token

                if multiplier_next is not None:
                    # Retain the case of the last multiplier, except
                    # if it is genitive (eignarfall) and the previous
                    # token had a case ('hundruðum milljarða' is dative,
                    # not genitive)
                    next_case = all_cases(next_token)
                    next_gender = all_genders(next_token)
                    if "ef" in next_case:
                        # We may have something like 'hundruðum milljarða':
                        # use the case and gender of 'hundruðum', not 'milljarða'
                        next_case = all_cases(token) or next_case
                        next_gender = all_genders(token) or next_gender
                    token = convert_to_num(token)
                    # We send error information, if any, from the token
                    # into the freshly constructed composite token via
                    # the token parameter. This ensures that "fimmhundruð"
                    # is correctly marked with an error resulting from
                    # a split into "fimm" and "hundruð".
                    token = token_ctor.Number(
                        token.txt + " " + next_token.txt,
                        token.val[0] * multiplier_next,
                        next_case,
                        next_gender,
                        token=token,
                    )
                    # Eat the multiplier token
                    next_token = next(token_stream)
                elif next_token.txt in AMOUNT_ABBREV:
                    # Abbreviations for ISK amounts
                    # For abbreviations, we do not know the case,
                    # but we try to retain the previous case information if any
                    token = convert_to_num(token)
                    token = token_ctor.Amount(
                        token.txt + " " + next_token.txt,
                        "ISK",
                        token.val[0] * AMOUNT_ABBREV[next_token.txt],
                        token.val[1],
                        token.val[2],
                    )
                    next_token = next(token_stream)
                else:
                    # Check for [number] 'percent'
                    percentage = match_stem_list(next_token, PERCENTAGES)
                    if percentage is not None:
                        token = convert_to_num(token)
                        token = token_ctor.Percent(
                            token.txt + " " + next_token.txt,
                            token.val[0],
                            all_cases(next_token),
                            all_genders(next_token),
                        )
                        # Eat the percentage token
                        next_token = next(token_stream)
                    else:
                        break

                multiplier = None

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
                            if next_token.val and "gr" in next_token.val[0].beyging:
                                # Definite form ('pundið', 'dollarinn')
                                form = "VB"
                            else:
                                # Indefinite form ('pund', 'dollari')
                                form = "SB"
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
                            next_token = next(token_stream)

            # Check for composites:
            # 'stjórnskipunar- og eftirlitsnefnd'
            # 'dómsmála-, viðskipta- og iðnaðarráðherra'
            tq = []
            while (
                (token.kind == TOK.WORD or token.kind == TOK.ENTITY)
                and next_token.kind == TOK.PUNCTUATION
                and next_token.val[1] == COMPOSITE_HYPHEN
            ):
                tq.append(token)
                tq.append(TOK.Punctuation(next_token.txt, normalized=HYPHEN))
                # Check for optional comma after the prefix
                comma_token = next(token_stream)
                if comma_token.kind == TOK.PUNCTUATION and comma_token.val[1] == ",":
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
                        txt = " ".join(t.txt for t in tq + [token, next_token])
                        txt = txt.replace(" -", "-").replace(" ,", ",")
                        # Create a fresh list of meanings with the full
                        # prefix in the ordmynd field
                        prefix = all_except_suffix(txt)
                        m = [
                            BIN_Meaning(
                                prefix + " " + mm.stofn,
                                mm.utg,
                                mm.ordfl,
                                mm.fl,
                                prefix + " " + mm.ordmynd,
                                mm.beyging,
                            )
                            for mm in next_token.val
                        ]
                        token = token_ctor.Word(txt, m, token=next_token)
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


def parse_phrases_2(token_stream, token_ctor):
    """ Parse a stream of tokens looking for phrases and making substitutions.
        Second pass: handle conversion of numbers + currencies into amounts,
        and process person names """

    token = None
    try:

        # Maintain a one-token lookahead
        token = next(token_stream)

        # Maintain a set of full person names encountered
        names = set()

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
                cases = token.val[1]
                genders = token.val[2]
                cur = None

                if next_token.kind == TOK.WORD:
                    # Try to find a currency name
                    cur = match_stem_list(next_token, CURRENCIES)
                    if cur is None and next_token.txt.isupper():
                        # Might be an ISO abbrev (which is not in BÍN)
                        cur = CURRENCIES.get(next_token.txt)
                        if not cases:
                            cases = list(ALL_CASES)
                        if not genders:
                            # Try to find a correct gender for the ISO abbrev,
                            # or use neutral as a default
                            genders = [CURRENCY_GENDERS.get(next_token.txt, "hk")]
                    if cur is not None:
                        # Use the case and gender information from the currency name
                        if not cases or "nf" in cases:
                            # No case information from the number, or
                            # it is nominative ('tólf hundruð pundum')
                            # use the case of the currency name only
                            new_cases = all_cases(next_token)
                            # However, for 'sex milljónum punda', we use
                            # the case of 'sex milljónum' and not 'punda'
                            if "ef" not in new_cases:
                                cases = new_cases
                        if not genders:
                            genders = all_genders(next_token)
                elif next_token.kind == TOK.CURRENCY:
                    # Already have an ISO identifier for a currency
                    cur = next_token.val[0]
                    # Use the case and gender information from the currency name
                    # if no such information was given with the number itself
                    cases = cases or next_token.val[1]
                    genders = genders or next_token.val[2]

                if cur is not None:
                    # Create an amount
                    # Use the case and gender information from the number, if any
                    token = token_ctor.Amount(
                        token.txt + " " + next_token.txt,
                        cur,
                        token.val[0],
                        cases,
                        genders,
                    )
                    # Eat the currency token
                    next_token = next(token_stream)

            # Check for [time] [date] (absolute)
            if token.kind == TOK.TIME and next_token.kind == TOK.DATEABS:
                # Create a time stamp
                h, m, s = token.val
                y, mo, d = next_token.val
                token = token_ctor.Timestampabs(
                    token.txt + " " + next_token.txt, y=y, mo=mo, d=d, h=h, m=m, s=s
                )
                # Eat the time token
                next_token = next(token_stream)

            # Check for [time] [date] (relative)
            if token.kind == TOK.TIME and next_token.kind == TOK.DATEREL:
                # Create a time stamp
                h, m, s = token.val
                y, mo, d = next_token.val
                token = token_ctor.Timestamprel(
                    token.txt + " " + next_token.txt, y=y, mo=mo, d=d, h=h, m=m, s=s
                )
                # Eat the time token
                next_token = next(token_stream)

            # Logic for human names

            def stems(tok, categories, given_name=False):
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
                result = []
                for m in tok.val:
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
                                PersonName(name=m.stofn, gender=m.ordfl, case=c)
                            )
                return result or None

            def has_category(tok, categories):
                """ Return True if the token matches a meaning
                    with any of the given categories """
                if tok.kind != TOK.WORD or not tok.val:
                    return False
                return any(m.fl in categories for m in tok.val)

            def has_other_meaning(tok, category_set):
                """ Return True if the token can denote something
                    besides a given name """
                if tok.kind != TOK.WORD or not tok.val:
                    return True
                # Return True if there is a different meaning, not a given name
                return any(m.fl not in category_set for m in tok.val)

            # Check for person names
            def given_names(tok):
                """ Check for Icelandic or foreign person name
                    (category 'ism' or 'erm') """
                if tok.kind != TOK.WORD or not tok.txt[0].isupper():
                    # Must be a word starting with an uppercase character
                    return None
                return stems(tok, PERSON_NAME_SET, given_name=True)

            # Check for surnames
            def surnames(tok):
                """ Check for Icelandic patronym (category 'föð'),
                    matronym (category 'móð') or family names (category 'ætt') """
                if tok.kind != TOK.WORD or not tok.txt[0].isupper():
                    # Must be a word starting with an uppercase character
                    return None
                return stems(tok, PATRONYM_SET)

            # Check for unknown surnames
            def unknown_surname(tok):
                """ Check for unknown (non-Icelandic) surnames """
                # Accept (most) upper case words as a surnames
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

            def given_names_or_middle_abbrev(tok):
                """ Check for given name or middle abbreviation """
                gnames = given_names(tok)
                if gnames is not None:
                    if tok.txt in BOTH_GIVEN_AND_FAMILY_NAMES:
                        # For instance "Hafstein" which can be both a given
                        # name and a family name: prepend the family name as
                        # an genderless and caseless option to the list
                        gnames = [
                            PersonName(name=tok.txt, gender=None, case=None)
                        ] + gnames
                    return gnames
                if tok.kind != TOK.WORD:
                    return None
                wrd = tok.txt
                if len(wrd) > 2 or not wrd[0].isupper():
                    if wrd not in FOREIGN_MIDDLE_NAME_SET:
                        # Accept "Thomas de Broglie", "Ruud van Nistelrooy"
                        return None
                # One or two letters, capitalized: accept as middle name abbrev,
                # all genders and cases possible
                return [PersonName(name=wrd, gender=None, case=None)]

            def compatible(pn, npn):
                """ Return True if the next PersonName (npn) is compatible
                    with the one we have (pn) """
                # The neutral gender (hk) is used for family names and is
                # compatible with both masculine and feminine given names
                if npn.gender and npn.gender != "hk" and (npn.gender != pn.gender):
                    return False
                if npn.case and npn.case != "-" and (npn.case != pn.case):
                    return False
                return True

            gn: Optional[List[PersonName]] = None
            if token.kind == TOK.WORD and token.val and token.val[0].fl == "nafn":
                # Convert a WORD with fl="nafn" to a PERSON with the correct gender,
                # in all cases
                gender = token.val[0].ordfl
                token = token_ctor.Person(
                    token.txt,
                    [PersonName(token.txt, gender, case) for case in ALL_CASES],
                )
            else:
                gn = given_names(token)

            if gn:
                # Found at least one given name: look for a sequence of given names
                # having compatible genders and cases
                w = token.txt
                patronym = False
                while True:
                    ngn = given_names_or_middle_abbrev(next_token)
                    if not ngn:
                        break
                    # Look through the stuff we got and see what is compatible
                    r = []
                    # pylint: disable=not-an-iterable
                    for p in gn:
                        # noinspection PyTypeChecker
                        for np in ngn:
                            if compatible(p, np):
                                # Compatible: add to result
                                r.append(
                                    PersonName(
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
                    next_token = next(token_stream)

                # Check whether the sequence of given names is followed
                # by one or more surnames (patronym/matronym) of the same gender,
                # for instance 'Dagur Bergþóruson Eggertsson'

                def eat_surnames(gn, w, patronym, next_token):
                    """ Process contiguous known surnames, typically "*dóttir/*son",
                        while they are compatible with the given name
                        we already have """
                    while True:
                        sn = surnames(next_token)
                        if not sn:
                            break
                        r = []
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
                                        PersonName(
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
                        for ix, p in enumerate(gn):
                            gn[ix] = PersonName(
                                name=p.name + " " + next_token.txt,
                                gender=p.gender,
                                case=p.case,
                            )
                        w += " " + next_token.txt
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
                                gn[ix] = PersonName(
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

            # Yield the current token and advance to the lookahead
            yield token

            if token.kind == TOK.S_BEGIN or (
                token.kind == TOK.PUNCTUATION and token.val[1] == ":"
            ):
                at_sentence_start = True
            elif token.kind != TOK.PUNCTUATION and token.kind != TOK.ORDINAL:
                at_sentence_start = False
            token = next_token

    except StopIteration:
        pass

    # Final token (previous lookahead)
    if token:
        yield token


def parse_phrases_3(token_stream, token_ctor):
    """ Parse a stream of tokens looking for phrases and making substitutions.
        Third pass: coalesce uppercase, otherwise unrecognized words with
        a following person name, if any; also coalesce entity names and
        recognize company names by endings ('hf.', 'Inc.', etc.). """

    def is_interesting(token) -> bool:
        """ Return True if this token causes us to want to take
            a further look at the following tokens """
        if token.kind != TOK.ENTITY and token.kind != TOK.WORD:
            return False
        return token.txt[0].isupper()

    def can_concat(token) -> bool:
        """ Return True if the token content can be concatenated onto
            an existing entity name """
        if token.kind != TOK.ENTITY and token.kind != TOK.WORD:
            return False
        if not token.txt[0].isupper():
            return False
        if " " in token.txt:
            return False
        if token.kind == TOK.WORD and token.val:
            if not any(m.ordfl == "entity" for m in token.val):
                return False
        return True

    def not_in_bin(token) -> bool:
        """ Return True if the token is not a normal word found in BÍN """
        if token.kind == TOK.ENTITY:
            return True
        assert token.kind == TOK.WORD
        if token.val:
            if all(m.ordfl != "entity" for m in token.val):
                # This word is found in BÍN and has no 'entity' meanings
                return False
        return True

    token = None
    try:

        # Maintain a one-token lookahead
        token = next(token_stream)
        concatable = False

        while True:

            if not concatable and not is_interesting(token):
                yield token
                # Make sure that token is None if next() raises StopIteration
                token = None
                token = next(token_stream)
                continue

            next_token = next(token_stream)
            concatable = False

            if next_token.txt in _CORPORATION_ENDINGS:
                # Allow merging a corporation ending. This is fairly
                # open: any prefix consisting of uppercase words is
                # allowed, even if they are found in BÍN.
                token = token_ctor.Company(token.txt + " " + next_token.txt)
                next_token = next(token_stream)
            elif not_in_bin(token):
                if next_token.kind == TOK.PERSON and token.txt.istitle():
                    # Upper-case word that is either an entity or a word that is
                    # not in BÍN, and the next token is a person: merge the two
                    # tokens into a single person name
                    # 'Jesse' 'John Kelley' -> 'Jesse John Kelley'
                    token = token_ctor.Person(
                        token.txt + " " + next_token.txt,
                        [
                            PersonName(token.txt + " " + pn.name, pn.gender, pn.case)
                            for pn in next_token.val
                        ],
                    )
                    next_token = next(token_stream)
                elif can_concat(next_token):
                    # Concatenate the next token and do another loop round
                    token = token_ctor.Entity(token.txt + " " + next_token.txt)
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


def fix_abbreviations(token_stream):
    """ Fix sentence splitting that may be wrong due to abbreviations """
    token = None
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

    def __init__(self, phrase_dictionary) -> None:
        self._pdict = phrase_dictionary

    def key(self, token: Tok) -> Any:
        """ Generate a state key from the given token """
        return token.txt.lower()

    def match_state(self, key: Any, state: Any) -> Any:
        """ Returns an iterable of states that match the key,
            or a falsy value if the key matches no states. """
        return state.get(key)

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
        state: Dict[str, List[Tuple[List[str], int]]] = defaultdict(list)
        pdict = self._pdict  # The phrase dictionary

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
                newstate = defaultdict(list)
                key = self.key(token)

                def add_to_state(slist, index):
                    """ Add the list of subsequent words to the new parser state """
                    next_key = slist[0]
                    rest = slist[1:]
                    newstate[next_key].append((rest, index))

                def accept(state):
                    """ The current token matches the given state, either as
                        a continuation of a previous state or as an initiation
                        of a new phrase """
                    nonlocal token, newstate, tq
                    if token:
                        tq.append(token)
                        token = None
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

    def __init__(self, token_ctor, auto_uppercase):
        super().__init__(StaticPhrases.DICT)
        self._token_ctor = token_ctor
        self._auto_uppercase = auto_uppercase

    def length(self, ix):
        return StaticPhrases.get_length(ix)

    def key(self, token):
        """ We allow both the original token text and a lowercase
            version of it to match """
        wo = token.txt  # Original word
        w = wo.lower()  # Lower case
        if w is not wo and (w == wo):
            wo = w
        return wo, w

    def match_state(self, key, state):
        """ First check for original (uppercase) word in the state, if any;
            if that doesn't match, check the lower case """
        wm = None
        wo, w = key
        if self._auto_uppercase and len(wo) == 1 and w is wo:
            # If we are auto-uppercasing, leave single-letter lowercase
            # phrases alone, i.e. 'g' for 'gram' and 'm' for 'meter'
            pass
        elif wo is not w and wo in state:
            wm = wo  # Original word
        elif w in state:
            wm = w  # Lowercase version
        return state[wm]

    def match(self, tq, ix):
        w = " ".join([t.txt for t in tq])
        # Add the entire phrase as one 'word' to the token queue.
        # Note that the StaticPhrases meaning list will be converted
        # to BIN_Meaning tuples in the annotate() pass.
        # Also note that the entire token queue is sent in as
        # the token paramter, as any token in the queue may
        # contain error information.
        yield self._token_ctor.Word(w, StaticPhrases.get_meaning(ix), token=tq)


def parse_static_phrases(token_stream, token_ctor, auto_uppercase):
    """ Use the StaticPhraseStream class to process the token stream
        and replace static phrases with single tokens """
    sps = StaticPhraseStream(token_ctor, auto_uppercase)
    return sps.process(token_stream)


class DisambiguationStream(MatchingStream):

    """ Disambiguates a token stream by only retaining word
        meanings that have categories matching those allowed
        in the [disambiguate_phrases] section in config/Phrases.conf """

    def __init__(self, token_ctor):
        super().__init__(AmbigPhrases.DICT)
        self._token_ctor = token_ctor

    def key(self, token):
        """ Generate a phrase key from the given token """
        # Construct a set of all possible lemmas of this word form
        if token.kind == TOK.WORD:
            return token.txt.lower(), frozenset(m.stofn + "*" for m in token.val)
        return token.txt.lower(), frozenset()

    def match_state(self, key, state):
        """ Called to see if the current token's key matches
            the given state. Returns the value that should be
            used to look up the key within the state, or None
            if there is no match. """
        # First, check for a direct text match
        states = []
        if key[0] in state:
            states.extend(state[key[0]])
        # Then, check whether the stems of the token match any
        # asterisk-marked entry in the state
        for stem in key[1]:
            if stem in state:
                states.extend(state[stem])
        return states

    def length(self, ix):
        return len(AmbigPhrases.get_cats(ix))

    def match(self, tq, ix):
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
                mm = [BIN_Meaning(w, 0, "fs", "alm", w, "-")]
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
                    for m in t.val
                    if m.ordfl in cat_set and (stem is None or m.stofn == stem)
                )
            yield token_ctor.Word(t.txt, mm, token=t)


def disambiguate_phrases(token_stream, token_ctor):

    """ Parse a stream of tokens looking for common ambiguous multiword phrases
        (i.e. phrases that have a well known very likely interpretation but
        other extremely uncommon ones are also grammatically correct).
    """

    ds = DisambiguationStream(token_ctor)
    yield from ds.process(token_stream)


class Bin_TOK(TOK):

    """ Override the TOK class from tokenizer.py to allow a dummy
        token parameter to be passed into token constructors where
        required. This again allows errtokenizer.py in GreynirCorrect
        to add token error information."""

    @staticmethod
    def Word(w: str, m=None, token: Optional[Tok] = None) -> Tok:
        return TOK.Word(w, m)

    @staticmethod
    def Number(
        w: str, n: float, cases=None, genders=None, token: Optional[Tok] = None
    ) -> Tok:
        return TOK.Number(w, n, cases, genders)


class DefaultPipeline:

    """ A DefaultPipeline encapsulates a sequence of tokenization
        phases, with each phase being a generator that accepts
        tokens from its input stream and yields tokens on its
        output stream. Individual phases in the sequence can
        easily be overridden in derived classes. """

    _token_ctor: Type[Bin_TOK] = Bin_TOK

    def __init__(self, text_or_gen: StringIterable, **options) -> None:
        self._text_or_gen = text_or_gen
        self._auto_uppercase = options.pop("auto_uppercase", False)
        self._options = options
        self._db: Optional[BIN_Db] = None
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
        return annotate(self._db, self._token_ctor, stream, self._auto_uppercase)

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
        return parse_phrases_1(self._db, self._token_ctor, stream)

    def parse_phrases_2(self, stream: TokenIterator) -> TokenIterator:
        """ Currencies, person names """
        return parse_phrases_2(stream, self._token_ctor)

    def parse_phrases_3(self, stream: TokenIterator) -> TokenIterator:
        """ Additional person and entity name logic """
        return parse_phrases_3(stream, self._token_ctor)

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

        with BIN_Db.get_db() as db:
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


def tokenize(text: StringIterable, **options) -> Iterable[Tok]:
    """ Tokenize text using the default pipeline """
    pipeline = DefaultPipeline(text, **options)
    return pipeline.tokenize()


def tokens_are_foreign(tokens: TokenList, min_icelandic_ratio: float) -> bool:
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
    # Return True if the sentence has at least three words
    # but less than 60% of them are found in BÍN
    num_words = words_in_bin + words_not_in_bin
    return num_words > 2 and words_in_bin / num_words < min_icelandic_ratio


def stems_of_token(t):
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


def choose_full_name(val, case, gender):
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
    fn = next((fn for fn in fn_list if fn[2] == "nf"), fn_list[0])
    return fn[0], fn[1] if gender is None else gender


def describe_token(index, t, terminal, meaning):
    """ Return a compact dictionary describing the token t,
        at the given index within its sentence,
        which matches the given terminal with the given meaning """
    txt = normalized_text(t)
    d = dict(x=txt, ix=index)
    if terminal is not None:
        # There is a token-terminal match
        if t.kind == TOK.PUNCTUATION:
            if txt == HYPHEN:
                # Hyphen: check whether it is matching an em or en-dash terminal
                if terminal.colon_cat == "em":
                    # Substitute em dash (will be displayed with surrounding space)
                    d["x"] = EM_DASH
                elif terminal.colon_cat == "en":
                    # Substitute en dash
                    d["x"] = EN_DASH
        else:
            # Annotate with terminal name and BÍN meaning
            # (no need to do this for punctuation)
            d["t"] = terminal.name
            if meaning is not None:
                if terminal.first == "fs":
                    # Special case for prepositions since they're really
                    # resolved from the preposition list in Main.conf, not from BÍN
                    m = (meaning.ordmynd, "fs", "alm", terminal.variant(0).upper())
                else:
                    m = (meaning.stofn, meaning.ordfl, meaning.fl, meaning.beyging)
                d["m"] = m
    if t.kind != TOK.WORD:
        # Optimize by only storing the k field for non-word tokens
        d["k"] = t.kind
    if t.val is not None and t.kind not in {TOK.WORD, TOK.ENTITY, TOK.PUNCTUATION}:
        # For tokens except words, entities and punctuation, include the val field
        if t.kind == TOK.PERSON:
            case = None
            gender = None
            if terminal is not None and terminal.num_variants >= 1:
                gender = terminal.variant(-1)
                if gender in {"nf", "þf", "þgf", "ef"}:
                    # Oops, mistaken identity
                    case = gender
                    gender = None
                if terminal.num_variants >= 2:
                    case = terminal.variant(-2)
            d["v"], gender = choose_full_name(t.val, case, gender)
            # Make sure the terminal field has a gender indicator
            if terminal is not None:
                if not terminal.name.endswith("_" + gender):
                    d["t"] = terminal.name + "_" + gender
            else:
                # No terminal field: create it
                d["t"] = "person_" + gender
            # In any case, add a separate gender indicator field for convenience
            d["g"] = gender
        else:
            d["v"] = t.val
    return d

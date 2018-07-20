"""

    Reynir: Natural language processing for Icelandic

    Dictionary-aware tokenization layer

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


    This module adds layers on top of the "raw" tokenizer in
    tokenizer.py. These layers annotate the token stream with word
    meanings from the BIN lexicon of Icelandic, identify multi-word
    phrases, process person names, etc.

"""

from collections import namedtuple, defaultdict

from tokenizer import tokenize_without_annotation, TOK, parse_tokens

# The following imports are here in order to be visible in clients
# (they are not used in this module)
from tokenizer import correct_spaces, paragraphs, tokenize as raw_tokenize

from .settings import StaticPhrases, AmbigPhrases, DisallowedNames
from .settings import NamePreferences
from .bindb import BIN_Db, BIN_Meaning


# Person names that are not recognized at the start of sentences
NOT_NAME_AT_SENTENCE_START = { "Annar" }

# Set of all cases (nominative, accusative, dative, possessive)
ALL_CASES = frozenset(["nf", "þf", "þgf", "ef"])

# Named tuple for person names, including case and gender
PersonName = namedtuple('PersonName', ['name', 'gender', 'case'])

COMPOSITE_HYPHEN = '–' # en dash
HYPHEN = '-' # Normal hyphen

# Prefixes that can be applied to adjectives with an intervening hyphen
ADJECTIVE_PREFIXES = frozenset(["hálf", "marg", "semí"])

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
DECLINABLE_MULTIPLIERS = frozenset((
    'hundrað', 'þúsund', 'milljón', 'milljarður'
))

# Recognize words for percentages
PERCENTAGES = {
    "prósent": 1,
    "prósenta": 1,
    "hundraðshluti": 1,
    "prósentustig": 1
}

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
    "indónesískur": "id"
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
    ("in", "INR"): "INR", # Indian rupee
    ("id", "INR"): "IDR", # Indonesian rupiah
    ("cn", "CNY"): "CNY",
    ("cn", "RMB"): "RMB"
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
    "[kr.]": "ISK",
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
    "EUR": "kvk"
}


def annotate(token_stream, auto_uppercase):
    """ Look up word forms in the BIN word database. If auto_uppercase
        is True, change lower case words to uppercase if it looks likely
        that they should be uppercase. """

    at_sentence_start = False

    with BIN_Db.get_db() as db:

        # Consume the iterable source in wlist (which may be a generator)
        for t in token_stream:
            if t.kind != TOK.WORD:
                # Not a word: relay the token unchanged
                yield t
                if t.kind == TOK.S_BEGIN or (t.kind == TOK.PUNCTUATION and t.txt == ':'):
                    at_sentence_start = True
                elif t.kind != TOK.PUNCTUATION and t.kind != TOK.ORDINAL:
                    at_sentence_start = False
                continue
            if t.val is None:
                # Look up word in BIN database
                w, m = db.lookup_word(t.txt, at_sentence_start, auto_uppercase)
                # Yield a word tuple with meanings
                yield TOK.Word(w, m)
            else:
                # Already have a meaning, which probably needs conversion
                # from a bare tuple to a BIN_Meaning
                yield TOK.Word(t.txt, list(map(BIN_Meaning._make, t.val)))
            # No longer at sentence start
            at_sentence_start = False


def match_stem_list(token, stems, filter_func=None):
    """ Find the stem of a word token in given dict, or return None if not found """
    if token.kind != TOK.WORD:
        return None
    # Go through the meanings with their stems
    if token.val:
        for m in token.val:
            # If a filter function is given, pass candidates to it
            try:
                lower_stofn = m.stofn.lower()
                if lower_stofn in stems and (filter_func is None or filter_func(m)):
                    return stems[lower_stofn]
            except Exception as e:
                print("Exception {0} in match_stem_list\nToken: {1}\nStems: {2}".format(e, token, stems))
                raise
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


def all_cases(token, filter_func = None):
    """ Return a list of all cases that the token can be in """
    cases = set()
    if token.kind == TOK.WORD:
        # Roll through the potential meanings and extract the cases therefrom
        if token.val:
            for m in token.val:
                if filter_func is not None and not filter_func(m):
                    continue
                if m.fl == "ob":
                    # One of the meanings is an undeclined word: all cases apply
                    cases = ALL_CASES
                    break
                add_cases(cases, m.beyging, None)
    return list(cases)


def all_common_cases(token1, token2, filter_func = None):
    """ Compute intersection of case sets for two tokens """
    set1 = set(all_cases(token1, filter_func))
    if not token2.val:
        # Token2 is not found in BÍN (probably an exotic currency name):
        # just return the cases of the first token
        return list(set1)
    set2 = set(all_cases(token2))
    return list(set1 & set2)


_GENDER_SET = { "kk", "kvk", "hk" }
_GENDER_DICT = { "KK": "kk", "KVK": "kvk", "HK": "hk" }


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


def parse_phrases_1(token_stream):

    """ Parse numbers and amounts """

    with BIN_Db.get_db() as db:

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
                    return match_stem_list(tok, MULTIPLIERS,
                        filter_func = lambda m: m.ordfl in NUMBER_CATEGORIES)

                # Check whether we have an initial number word
                multiplier = number(token) if token.kind == TOK.WORD else None

                # Check for [number] 'hundred|thousand|million|billion'
                while (token.kind == TOK.NUMBER or multiplier is not None) \
                    and next_token.kind == TOK.WORD:

                    multiplier_next = number(next_token)

                    def convert_to_num(token):
                        if multiplier is not None:
                            token = TOK.Number(token.txt, multiplier,
                                all_cases(token), all_genders(token))
                        return token

                    if multiplier_next is not None:
                        # Retain the case of the last multiplier, except
                        # if it is possessive (eignarfall) and the previous
                        # token had a case ('hundruðum milljarða' is dative,
                        # not possessive)
                        next_case = all_cases(next_token)
                        next_gender = all_genders(next_token)
                        if "ef" in next_case:
                            # We may have something like 'hundruðum milljarða':
                            # use the case and gender of 'hundruðum', not 'milljarða'
                            next_case = all_cases(token) or next_case
                            next_gender = all_genders(token) or next_gender
                        token = convert_to_num(token)
                        token = TOK.Number(token.txt + " " + next_token.txt,
                            token.val[0] * multiplier_next,
                            next_case, next_gender)
                        # Eat the multiplier token
                        next_token = next(token_stream)
                    elif next_token.txt in AMOUNT_ABBREV:
                        # Abbreviations for ISK amounts
                        # For abbreviations, we do not know the case,
                        # but we try to retain the previous case information if any
                        token = convert_to_num(token)
                        token = TOK.Amount(token.txt + " " + next_token.txt, "ISK",
                            token.val[0] * AMOUNT_ABBREV[next_token.txt], # Number
                            token.val[1], token.val[2]) # Cases and gender
                        next_token = next(token_stream)
                    else:
                        # Check for [number] 'percent'
                        percentage = match_stem_list(next_token, PERCENTAGES)
                        if percentage is not None:
                            token = convert_to_num(token)
                            token = TOK.Percent(token.txt + " " + next_token.txt, token.val[0],
                                all_cases(next_token), all_genders(next_token))
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
                                # having a strong declination (indefinite form) only
                                token = TOK.Currency(token.txt + " "  + next_token.txt,
                                    iso_code,
                                    all_common_cases(token, next_token,
                                        lambda m: (m.ordfl == "lo" and "SB" in m.beyging)),
                                    [ CURRENCY_GENDERS[cur] ])
                                next_token = next(token_stream)

                # Check for composites:
                # 'stjórnskipunar- og eftirlitsnefnd'
                # 'viðskipta- og iðnaðarráðherra'
                # 'marg-ítrekaðri'
                if token.kind == TOK.WORD and \
                    next_token.kind == TOK.PUNCTUATION and next_token.txt == COMPOSITE_HYPHEN:

                    og_token = next(token_stream)
                    if og_token.kind != TOK.WORD or (og_token.txt != "og" and og_token.txt != "eða"):
                        # Incorrect prediction: make amends and continue
                        handled = False
                        if og_token.kind == TOK.WORD:
                            composite = token.txt + "-" + og_token.txt
                            if token.txt.lower() in ADJECTIVE_PREFIXES:
                                # hálf-opinberri, marg-ítrekaðri
                                token = TOK.Word(composite,
                                    [m for m in og_token.val if m.ordfl == "lo" or m.ordfl == "ao"])
                                next_token = next(token_stream)
                                handled = True
                            else:
                                # Check for Vestur-Þýskaland, Suður-Múlasýsla (which are in BÍN in their entirety)
                                m = db.meanings(composite)
                                if m:
                                    # Found composite in BÍN: return it as a single token
                                    token = TOK.Word(composite, m)
                                    next_token = next(token_stream)
                                    handled = True
                        if not handled:
                            yield token
                            # Put a normal hyphen instead of the composite one
                            token = TOK.Punctuation(HYPHEN)
                            next_token = og_token
                    else:
                        # We have 'viðskipta- og'
                        final_token = next(token_stream)
                        if final_token.kind != TOK.WORD:
                            # Incorrect: unwind
                            yield token
                            yield TOK.Punctuation(HYPHEN) # Normal hyphen
                            token = og_token
                            next_token = final_token
                        else:
                            # We have 'viðskipta- og iðnaðarráðherra'
                            # Return a single token with the meanings of
                            # the last word, but an amalgamated token text.
                            # Note: there is no meaning check for the first
                            # part of the composition, so it can be an unknown word.
                            txt = token.txt + "- " + og_token.txt + \
                                " " + final_token.txt
                            token = TOK.Word(txt, final_token.val)
                            next_token = next(token_stream)

                # Yield the current token and advance to the lookahead
                yield token
                token = next_token

        except StopIteration:
            pass

        # Final token (previous lookahead)
        if token:
            yield token


def parse_phrases_2(token_stream):

    """ Parse a stream of tokens looking for phrases and making substitutions.
        Second pass
    """

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
            if token.kind == TOK.NUMBER and (next_token.kind == TOK.WORD or
                next_token.kind == TOK.CURRENCY):

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
                            genders = [ CURRENCY_GENDERS.get(next_token.txt, "hk") ]
                    if cur is not None:
                        # Use the case and gender information from the currency name
                        if not cases:
                            cases = all_cases(next_token)
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
                    token = TOK.Amount(token.txt + " " + next_token.txt,
                        cur, token.val[0], cases, genders)
                    # Eat the currency token
                    next_token = next(token_stream)

            # Logic for human names

            def stems(tok, categories, given_name = False):
                """ If the token denotes a given name, return its possible
                    interpretations, as a list of PersonName tuples (name, case, gender).
                    If first_name is True, we omit from the list all name forms that
                    occur in the disallowed_names section in the configuration file. """
                if tok.kind != TOK.WORD or not tok.val:
                    return None
                if at_sentence_start and tok.txt in NOT_NAME_AT_SENTENCE_START:
                    # Disallow certain person names at the start of sentences,
                    # such as 'Annar'
                    return None
                # Set up the names we're not going to allow
                dstems = DisallowedNames.STEMS if given_name else { }
                # Look through the token meanings
                result = []
                for m in tok.val:
                    if m.fl in categories and "ET" in m.beyging:
                        # If this is a given name, we cut out name forms
                        # that are frequently ambiguous and wrong, i.e. "Frá" as accusative
                        # of the name "Frár", and "Sigurð" in the nominative.
                        c = case(m.beyging)
                        if m.stofn not in dstems or c not in dstems[m.stofn]:
                            # Note the stem ('stofn') and the gender from the word type ('ordfl')
                            result.append(PersonName(name = m.stofn, gender = m.ordfl, case = c))
                return result if result else None

            def has_category(tok, categories):
                """ Return True if the token matches a meaning with any of the given categories """
                if tok.kind != TOK.WORD or not tok.val:
                    return False
                return any(m.fl in categories for m in tok.val)

            def has_other_meaning(tok, category):
                """ Return True if the token can denote something besides a given name """
                if tok.kind != TOK.WORD or not tok.val:
                    return True
                # Return True if there is a different meaning, not a given name
                return any(m.fl != category for m in tok.val)

            # Check for person names
            def given_names(tok):
                """ Check for Icelandic person name (category 'ism') """
                if tok.kind != TOK.WORD or not tok.txt[0].isupper():
                    # Must be a word starting with an uppercase character
                    return None
                return stems(tok, {"ism"}, given_name = True)

            # Check for surnames
            def surnames(tok):
                """ Check for Icelandic patronym (category 'föð') or matronym (category 'móð') """
                if tok.kind != TOK.WORD or not tok.txt[0].isupper():
                    # Must be a word starting with an uppercase character
                    return None
                return stems(tok, {"föð", "móð"})

            # Check for unknown surnames
            def unknown_surname(tok):
                """ Check for unknown (non-Icelandic) surnames """
                # Accept (most) upper case words as a surnames
                if tok.kind != TOK.WORD:
                    return False
                if not tok.txt[0].isupper():
                    # Must start with capital letter
                    return False
                if has_category(tok, {"föð", "móð"}):
                    # This is a known surname, not an unknown one
                    return False
                # Allow single-letter abbreviations, but not multi-letter
                # all-caps words (those are probably acronyms)
                return len(tok.txt) == 1 or not tok.txt.isupper()

            def given_names_or_middle_abbrev(tok):
                """ Check for given name or middle abbreviation """
                gnames = given_names(tok)
                if gnames is not None:
                    return gnames
                if tok.kind != TOK.WORD:
                    return None
                wrd = tok.txt
                if wrd.startswith('['):
                    # Abbreviation: Cut off the brackets & trailing period, if present
                    if wrd.endswith('.]'):
                        wrd = wrd[1:-2]
                    else:
                        # This is probably a C. which had its period cut off as a sentence ending...
                        wrd = wrd[1:-1]
                if len(wrd) > 2 or not wrd[0].isupper():
                    if wrd not in { "van", "de", "den", "der", "el", "al" }: # "of" was here
                        # Accept "Thomas de Broglie", "Ruud van Nistelroy"
                        return None
                # One or two letters, capitalized: accept as middle name abbrev,
                # all genders and cases possible
                return [ PersonName(name = wrd, gender = None, case = None) ]

            def compatible(pn, npn):
                """ Return True if the next PersonName (np) is compatible with the one we have (p) """
                if npn.gender and (npn.gender != pn.gender):
                    return False
                if npn.case and (npn.case != pn.case):
                    return False
                return True

            if token.kind == TOK.WORD and token.val and token.val[0].fl == "nafn":
                # Convert a WORD with fl="nafn" to a PERSON with the correct gender, in all cases
                gender = token.val[0].ordfl
                token = TOK.Person(token.txt, [ PersonName(token.txt, gender, case) for case in ALL_CASES ])
                gn = None
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
                    for p in gn:
                        # noinspection PyTypeChecker
                        for np in ngn:
                            if compatible(p, np):
                                # Compatible: add to result
                                r.append(PersonName(name = p.name + " " + np.name, gender = p.gender, case = p.case))
                    if not r:
                        # This next name is not compatible with what we already
                        # have: break
                        break
                    # Success: switch to new given name list
                    gn = r
                    w += " " + (ngn[0].name if next_token.txt[0] == '[' else next_token.txt)
                    next_token = next(token_stream)

                # Check whether the sequence of given names is followed
                # by one or more surnames (patronym/matronym) of the same gender,
                # for instance 'Dagur Bergþóruson Eggertsson'

                def eat_surnames(gn, w, patronym, next_token):
                    """ Process contiguous known surnames, typically "*dóttir/*son", while they are
                        compatible with the given name we already have """
                    while True:
                        sn = surnames(next_token)
                        if not sn:
                            break
                        r = []
                        # Found surname: append it to the accumulated name, if compatible
                        for p in gn:
                            for np in sn:
                                if compatible(p, np):
                                    r.append(PersonName(name = p.name + " " + np.name, gender = np.gender, case = np.case))
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
                assert len(gn) >= 1

                if not patronym:
                    # We stop name parsing after we find one or more Icelandic
                    # patronyms/matronyms. Otherwise, check whether we have an
                    # unknown uppercase word next;
                    # if so, add it to the person names we've already found
                    while unknown_surname(next_token):
                        for ix, p in enumerate(gn):
                            gn[ix] = PersonName(name = p.name + " " + next_token.txt, gender = p.gender, case = p.case)
                        w += " " + next_token.txt
                        next_token = next(token_stream)
                        # Assume we now have a patronym
                        patronym = True

                    if patronym:
                        # We still might have surnames coming up: eat them too, if present
                        gn, w, _, next_token = eat_surnames(gn, w, patronym, next_token)

                found_name = False
                # If we have a full name with patronym, store it
                if patronym:
                    names |= set(gn)
                else:
                    # Look through earlier full names and see whether this one matches
                    for ix, p in enumerate(gn):
                        gnames = p.name.split(' ') # Given names
                        for lp in names:
                            match = (not p.gender) or (p.gender == lp.gender)
                            if match:
                                # The gender matches
                                lnames = set(lp.name.split(' ')[0:-1]) # Leave the patronym off
                                for n in gnames:
                                    if n not in lnames:
                                        # We have a given name that does not match the person
                                        match = False
                                        break
                            if match:
                                # All given names match: assign the previously seen full name
                                gn[ix] = PersonName(name = lp.name, gender = lp.gender, case = p.case)
                                found_name = True
                                break

                # If this is not a "strong" name, backtrack from recognizing it.
                # A "weak" name is (1) at the start of a sentence; (2) only one
                # word; (3) that word has a meaning that is not a name;
                # (4) the name has not been seen in a full form before;
                # (5) not on a 'well known name' list.

                weak = at_sentence_start and (' ' not in w) and not patronym and \
                    not found_name and (has_other_meaning(token, "ism") and w not in NamePreferences.SET)

                if not weak:
                    # Return a person token with the accumulated name
                    # and the intersected set of possible cases
                    token = TOK.Person(w, gn)

            # Yield the current token and advance to the lookahead
            yield token

            if token.kind == TOK.S_BEGIN or (token.kind == TOK.PUNCTUATION and token.txt == ':'):
                at_sentence_start = True
            elif token.kind != TOK.PUNCTUATION and token.kind != TOK.ORDINAL:
                at_sentence_start = False
            token = next_token

    except StopIteration:
        pass

    # Final token (previous lookahead)
    if token:
        yield token


def parse_static_phrases(token_stream, auto_uppercase):

    """ Parse a stream of tokens looking for static multiword phrases
        (i.e. phrases that are not affected by inflection).
        The algorithm implements N-token lookahead where N is the
        length of the longest phrase.
    """
    tq = [] # Token queue
    state = defaultdict(list) # Phrases we're considering
    pdict = StaticPhrases.DICT # The phrase dictionary
    try:

        while True:

            token = next(token_stream)
            if token.txt is None: # token.kind != TOK.WORD:
                # Not a word: no match; discard state
                if tq:
                    yield from tq
                    tq = []
                if state:
                    state = defaultdict(list)
                yield token
                continue

            # Look for matches in the current state and build a new state
            newstate = defaultdict(list)
            wo = token.txt # Original word
            w = wo.lower() # Lower case
            if wo == w:
                wo = w

            def add_to_state(slist, index):
                """ Add the list of subsequent words to the new parser state """
                wrd = slist[0]
                rest = slist[1:]
                newstate[wrd].append((rest, index))

            # First check for original (uppercase) word in the state, if any;
            # if that doesn't match, check the lower case
            wm = None
            if wo is not w and wo in state:
                wm = wo
            elif w in state:
                wm = w

            if wm:
                # This matches an expected token:
                # go through potential continuations
                tq.append(token) # Add to lookahead token queue
                token = None
                for sl, ix in state[wm]:
                    if not sl:
                        # No subsequent word: this is a complete match
                        # Reconstruct original text behind phrase
                        plen = StaticPhrases.get_length(ix)
                        while len(tq) > plen:
                            # We have extra queued tokens in the token queue
                            # that belong to a previously seen partial phrase
                            # that was not completed: yield them first
                            yield tq.pop(0)
                        w = " ".join([ t.txt for t in tq ])
                        # Add the entire phrase as one 'word' to the token queue
                        yield TOK.Word(w, map(BIN_Meaning._make, StaticPhrases.get_meaning(ix)))
                        # Discard the state and start afresh
                        newstate = defaultdict(list)
                        w = wo = ""
                        tq = []
                        # Note that it is possible to match even longer phrases
                        # by including a starting phrase in its entirety in
                        # the static phrase dictionary
                        break
                    add_to_state(sl, ix)
            elif tq:
                yield from tq
                tq = []

            wm = None
            if auto_uppercase and len(wo) == 1 and w is wo:
                # If we are auto-uppercasing, leave single-letter lowercase
                # phrases alone, i.e. 'g' for 'gram' and 'm' for 'meter'
                pass
            elif wo is not w and wo in pdict:
                wm = wo
            elif w in pdict:
                wm = w

            # Add all possible new states for phrases that could be starting
            if wm:
                # This word potentially starts a phrase
                for sl, ix in pdict[wm]:
                    if not sl:
                        # Simple replace of a single word
                        if tq:
                            yield from tq
                            tq = []
                        # Yield the replacement token
                        yield TOK.Word(token.txt, map(BIN_Meaning._make, StaticPhrases.get_meaning(ix)))
                        newstate = defaultdict(list)
                        token = None
                        break
                    add_to_state(sl, ix)
                if token:
                    tq.append(token)
            elif token:
                yield token

            # Transition to the new state
            state = newstate

    except StopIteration:
        # Token stream is exhausted
        pass

    # Yield any tokens remaining in queue
    yield from tq


def disambiguate_phrases(token_stream):

    """ Parse a stream of tokens looking for common ambiguous multiword phrases
        (i.e. phrases that have a well known very likely interpretation but
        other extremely uncommon ones are also grammatically correct).
        The algorithm implements N-token lookahead where N is the
        length of the longest phrase.
    """

    tq = [] # Token queue
    state = defaultdict(list) # Phrases we're considering
    pdict = AmbigPhrases.DICT # The phrase dictionary

    try:

        while True:

            token = next(token_stream)

            if token.kind != TOK.WORD:
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
            w = token.txt.lower()

            def add_to_state(slist, index):
                """ Add the list of subsequent words to the new parser state """
                wrd = slist[0]
                rest = slist[1:]
                newstate[wrd].append((rest, index))

            if w in state:
                # This matches an expected token:
                # go through potential continuations
                tq.append(token) # Add to lookahead token queue
                token = None
                for sl, ix in state[w]:
                    if not sl:
                        # No subsequent word: this is a complete match
                        # Discard meanings of words in the token queue that are not
                        # compatible with the category list specified
                        cats = AmbigPhrases.get_cats(ix)
                        for t, cat in zip(tq, cats):
                            # Yield a new token with fewer meanings for each original token in the queue
                            if cat == "fs":
                                # Handle prepositions specially, since we may have additional
                                # preps defined in Main.conf that don't have fs meanings in BÍN
                                w = t.txt.lower()
                                yield TOK.Word(t.txt, [ BIN_Meaning(w, 0, "fs", "alm", w, "-") ])
                            else:
                                yield TOK.Word(t.txt, [m for m in t.val if m.ordfl == cat])

                        # Discard the state and start afresh
                        if newstate:
                            newstate = defaultdict(list)
                        w = ""
                        tq = []
                        # Note that it is possible to match even longer phrases
                        # by including a starting phrase in its entirety in
                        # the static phrase dictionary
                        break
                    add_to_state(sl, ix)
            elif tq:
                # This does not continue a started phrase:
                # yield the accumulated token queue
                yield from tq
                tq = []

            if w in pdict:
                # This word potentially starts a new phrase
                for sl, ix in pdict[w]:
                    # assert sl
                    add_to_state(sl, ix)
                if token:
                    tq.append(token) # Start a lookahead queue with this token
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


def tokenize(text, auto_uppercase = False):
    """ Tokenize text in several phases, returning a generator (iterable sequence) of tokens
        that processes tokens on-demand. If auto_uppercase is True, the tokenizer
        attempts to correct lowercase words that probably should be uppercase. """

    # Thank you Python for enabling this programming pattern ;-)

    token_stream = tokenize_without_annotation(text)

    # Static multiword phrases
    token_stream = parse_static_phrases(token_stream, auto_uppercase)

    # Lookup meanings from dictionary
    token_stream = annotate(token_stream, auto_uppercase)

    # Numbers and amounts
    token_stream = parse_phrases_1(token_stream)

    # Currencies, person names
    token_stream = parse_phrases_2(token_stream)

    # Eliminate very uncommon meanings
    token_stream = disambiguate_phrases(token_stream)

    return token_stream


def stems_of_token(t):
    """ Return a list of word stem descriptors associated with the token t.
        This is an empty list if the token is not a word or person or entity name.
        The list can contain multiple stems, for instance in the case
        of composite words ('sjómannadagur' -> ['sjómannadagur/kk', sjómaður/kk', 'dagur/kk']).
        If name_emphasis is > 1, any person and entity names will be repeated correspondingly
        in the list. """
    kind = t.get("k", TOK.WORD)
    if kind not in { TOK.WORD, TOK.PERSON, TOK.ENTITY }:
        # No associated stem
        return []
    if kind == TOK.WORD:
        if "m" in t:
            # Obtain the stem and the word category from the 'm' (meaning) field
            stem = t["m"][0]
            cat = t["m"][1]
            return [ (stem, cat) ]
        else:
            # Sérnafn
            stem = t["x"]
            return [ (stem, "entity") ]
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
        return [ (stem, "person" + gender) ]
    else:
        # TOK.ENTITY
        stem = t["x"]
        return [ (stem, "entity") ]


def choose_full_name(val, case, gender):
    """ From a list of name possibilities in val, and given a case and a gender
        (which may be None), return the best matching full name and gender """
    fn_list = [ (fn, g, c) for fn, g, c in val
        if (gender is None or g == gender) and (case is None or c == case) ]
    if not fn_list:
        # Oops - nothing matched this. Might be a foreign, undeclinable name.
        # Try nominative if it wasn't alredy tried
        if case is not None and case != "nf":
            fn_list = [ (fn, g, c) for fn, g, c in val
                if (gender is None or g == gender) and (case == "nf") ]
        # If still nothing, try anything with the same gender
        if not fn_list and gender is not None:
            fn_list = [ (fn, g, c) for fn, g, c in val if (g == gender) ]
        # If still nothing, give up and select the first available meaning
        if not fn_list:
            fn, g, c = val[0]
            fn_list = [ (fn, g, c) ]
    # If there are many choices, select the nominative case, or the first element as a last resort
    fn = next((fn for fn in fn_list if fn[2] == "nf"), fn_list[0])
    return fn[0], fn[1] if gender is None else gender


def describe_token(t, terminal, meaning):
    """ Return a compact dictionary describing the token t,
        which matches the given terminal with the given meaning """
    d = dict(x=t.txt)
    if terminal is not None:
        # There is a token-terminal match
        if t.kind == TOK.PUNCTUATION:
            if t.txt == "-":
                # Hyphen: check whether it is matching an em or en-dash terminal
                if terminal.colon_cat == "em":
                    d["x"] = "—"  # Substitute em dash (will be displayed with surrounding space)
                elif terminal.colon_cat == "en":
                    d["x"] = "–"  # Substitute en dash
        else:
            # Annotate with terminal name and BÍN meaning (no need to do this for punctuation)
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



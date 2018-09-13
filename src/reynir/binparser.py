"""

    Reynir: Natural language processing for Icelandic

    BIN parser module

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


    This module implements the BIN_Token class, deriving from Token,
    and BIN_Parser class, deriving from Parser.
    BIN_Parser parses sentences in Icelandic according to the grammar
    in the file Reynir.grammar.

    BIN refers to 'Beygingarlýsing íslensks nútímamáls', the database of
    word forms in modern Icelandic.

"""

import os
import time

from datetime import datetime
from functools import reduce
import json

from tokenizer import TOK

from .settings import Settings, VerbObjects, VerbSubjects, Prepositions
from .grammar import (
    Terminal,
    LiteralTerminal,
    Nonterminal,
    Token,
    Grammar,
    GrammarError,
)
from .baseparser import Base_Parser


# This is the base path where we expect to find the Reynir.grammar file
_PATH = os.path.dirname(__file__)


class BIN_Token(Token):

    """
        Wrapper class for a token to be processed by the parser

        The layout of a token tuple coming from the tokenizer is
        as follows:

        t[0] Token type (TOK.WORD, etc.)
        t[1] Token text
        t[2] For TOK.WORD: Meaning list, where each item is a tuple:
            m[0] Word stem
            m[1] BIN index (integer)
            m[2] Word type (kk/kvk/hk (=noun), so, lo, ao, fs, etc.)
            m[3] Word category (alm/fyr/ism etc.)
            m[4] Word form (in most cases identical to t[1])
            m[5] Grammatical form (case, gender, number, etc.)

    """

    # Map the BÍN category (ordfl) to terminal names used in the grammar
    KIND = {
        "kk": "no",
        "kvk": "no",
        "hk": "no",
        "so": "so",
        "ao": "ao",
        "tao": "tao",  # Never appears in BÍN
        "spao": "spao",  # Never appears in BÍN
        "fs": "fs",
        "lo": "lo",
        "fn": "fn",
        "pfn": "pfn",
        "gr": "gr",
        "to": "to",
        "töl": "töl",
        "uh": "uh",
        "st": "st",
        "stt": "stt",  # Never appears in BÍN
        "abfn": "abfn",
        "nhm": "nhm",
    }

    # Strings that must be present in the grammatical form for variants
    VARIANT = {
        "nf": "NF",  # Nefnifall / nominative
        "þf": "ÞF",  # Þolfall / accusative
        "þgf": "ÞGF",  # Þágufall / dative
        "ef": "EF",  # Eignarfall / possessive
        "kk": "KK",  # Karlkyn / masculine
        "kvk": "KVK",  # Kvenkyn / feminine
        "hk": "HK",  # Hvorugkyn / neutral
        "et": "ET",  # Eintala / singular
        "ft": "FT",  # Fleirtala / plural
        "mst": "MST",  # Miðstig / comparative
        "est": "EST",  # Efsta stig / superlative
        "esb": "ESB",  # Efsta stig, sterk beyging / superlative
        "evb": "EVB",  # Efsta stig, veik beyging / superlative
        "p1": "1P",  # Fyrsta persóna / first person
        "p2": "2P",  # Önnur persóna / second person
        "p3": "3P",  # Þriðja persóna / third person
        "op": "OP",  # Ópersónuleg sögn
        "gm": "GM",  # Germynd
        "mm": "MM",  # Miðmynd
        "sb": "SB",  # Sterk beyging
        "vb": "VB",  # Veik beyging
        "nh": "NH",  # Nafnháttur
        "fh": "FH",  # Framsöguháttur
        "bh": "BH",  # Boðháttur
        "lh": "LH",  # Lýsingarháttur (nútíðar)
        "vh": "VH",  # Viðtengingarháttur
        "nt": "NT",  # Nútíð
        "sagnb": "SAGNB",  # Sagnbót ('vera' -> 'hefur verið')
        "lhþt": "LHÞT",  # Lýsingarháttur þátíðar ('var lentur')
        "gr": "gr",  # Greinir
        # Variants that do not have a corresponding BIN meaning
        "abbrev": None,
        "subj": None,
    }

    # Make a copy of VARIANT with the past tense (þt) added
    VARIANT_EX = {key: val for key, val in VARIANT.items() if val is not None}
    VARIANT_EX["þt"] = "ÞT"

    # Bit mapping for all known variants
    VBIT = {key: 1 << i for i, key in enumerate(VARIANT.keys())}
    # Bit mapping for all variants that have a corresponding BIN meaning
    FBIT = {val: 1 << i for i, val in enumerate(VARIANT.values()) if val}

    VBIT_ET = VBIT["et"]
    VBIT_FT = VBIT["ft"]
    VBIT_KK = VBIT["kk"]
    VBIT_KVK = VBIT["kvk"]
    VBIT_HK = VBIT["hk"]
    VBIT_NH = VBIT["nh"]
    VBIT_VH = VBIT["vh"]
    VBIT_LH = VBIT["lhþt"]
    VBIT_MM = VBIT["mm"]
    VBIT_GM = VBIT["gm"]
    VBIT_GR = VBIT["gr"]
    VBIT_SUBJ = VBIT["subj"]
    VBIT_SAGNB = VBIT["sagnb"]
    VBIT_ABBREV = VBIT["abbrev"]
    VBIT_LHNT = VBIT["lh"] | VBIT["nt"]

    # Mask the following bits off a VBIT set to get an FBIT set
    FBIT_MASK = VBIT_ABBREV | VBIT_SUBJ

    CASES = ["nf", "þf", "þgf", "ef"]
    GENDERS = ["kk", "kvk", "hk"]
    GENDERS_SET = frozenset(GENDERS)
    GENDERS_MAP = {"kk": "KK", "kvk": "KVK", "hk": "HK"}

    VBIT_CASES = VBIT["nf"] | VBIT["þf"] | VBIT["þgf"] | VBIT["ef"]
    VBIT_GENDERS = VBIT["kk"] | VBIT["kvk"] | VBIT["hk"]
    VBIT_NUMBER = VBIT["et"] | VBIT["ft"]

    # Variants to be checked for verbs
    VERB_VARIANTS = [
        "p1",
        "p2",
        "p3",
        "nh",
        "vh",
        "lh",
        "bh",
        "fh",
        "sagnb",
        "lhþt",
        "nt",
        "kk",
        "kvk",
        "hk",
        "sb",
        "vb",
        "gm",
        "mm",
    ]
    # Pre-calculate a dictionary of associated BIN forms
    _VERB_FORMS = None  # Initialized later

    # Set of adverbs that cannot be an "eo" (prepositions and pronouns are already excluded)
    _NOT_EO = frozenset(["og", "eða", "sem", "ekkert"])

    # Prepositions that nevertheless must be allowed as adverbs
    # 'Fyrirtækið hefur skilað inn ársreikningi'
    # 'Þá er kannski eftir klukkutími'
    # '... verður ekki til nægur jarðvarmi'
    # '... séu um 20 kaupendur'
    # '... varpaði fram þeirri spurningu'
    # '... samið við nær öll félögin'
    # '... kom út skýrsla'
    # '... að meðal hitastig', "Jón var þar á meðal"
    # '... það á jafnframt dótturfélag'
    # '... afsalaði sér samt launum'
    # '... lifði af nútímalega meðferð'
    # '... nú liggur fyrir skýrsla'
    # '... það flæddi að'
    # '... var að austan'
    # '... ferðaðist austur'
    # '... ók framhjá án þess að veifa'
    # '... hitnaði innan frá', '... stökk aðeins frá'
    # '... hitnaði að innan', '... var holt að innan'
    # '... að neðan'
    # '... styrkurinn datt niður'
    # '... kom að norðan'
    # '... kom norður'
    # '... tók ofan', '... að neðan'
    # '... var að sunnan'
    # '... fór austur'
    # '... hafði varla undan'
    # '... lagði allt undir'
    # '... kom að utan'
    # '... bjó fyrir vestan'
    # '... fór vestur'
    # '... hefur því áhrif'

    _NOT_NOT_EO = frozenset(
        [
            "inn",
            "eftir",
            "til",
            "upp",
            "um",
            "fram",
            "nær",
            "nærri",
            "út",
            "meðal",
            "neðan",
            "jafnframt",
            "samt",
            "af",
            "fyrir",
            "því",
        ]
    )

    # Words that are not eligible for interpretation as proper names, even if they are capitalized
    _NOT_PROPER_NAME = frozenset(
        [
            "ég",
            "þú",
            "hann",
            "hún",
            "það",
            "við",
            "þið",
            "þau",
            "þeir",
            "þær",
            "mér",
            "mig",
            "mín",
            "þig",
            "þér",
            "þín",
            "þeim",
            "þeirra",
            "þetta",
            "þessi",
            "í",
            "á",
            "af",
            "um",
            "að",
            "með",
            "til",
            "frá",
            "búist",
            "annars",
            "samkvæmt",
            "en",
            "og",
            "sem",
            "ekkert",
            "hæð",
            "svo",
            "veggir",
            "þarna",
            "allt",
        ]
    )

    # Numbers that can be used in the singular even if they are nominally plural.
    # This applies to the media company 365, where it is OK to say "365 skuldaði 389 milljónir",
    # as it would be incorrect to say "365 skulduðu 389 milljónir".
    _SINGULAR_SPECIAL_CASES = frozenset([365])

    # Note: these must have a meaning for this to work, so specifying them
    # as abbreviations to Main.conf is recommended
    _CORPORATION_ENDINGS = frozenset(
        [
            "ehf.",
            "ehf",
            "hf.",
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

    # Interrogative adverbs
    _SPAO = frozenset(
        ["hvar", "hvenær", "hvernig", "hvaðan", "hvert", "hví", "hve", "hversu"]
    )

    # Temporal sentential adverbs
    _TAO = frozenset(
        [
            "daglega",
            "dagsdaglega",
            "alltaf",
            "aldrei",
            "fyrr",
            "fyrrum",
            "loks",
            "loksins",
            "mánaðarlega",
            "nú",
            "núna",
            "næst",
            "oft",
            "reglulega",
            "seint",
            "snemma",
            "sjaldan",
            "stundum",
            "síðar",
            "síðla",
            "títt",
            "undanfarið",
            "vikulega",
            "árla",
            "árlega",
            "áður",
            "þá",
        ]
    )

    _UNDERSTOOD_PUNCTUATION = ".?!,:;–-()[]"

    _MEANING_CACHE = {}
    _VARIANT_CACHE = {}

    def __init__(self, t, original_index):

        Token.__init__(self, TOK.descr[t[0]], t[1])
        self.t0 = t[0]  # Token type (TOK.WORD, etc.)
        self.t1 = t[1]  # Token text
        self.t1_lower = t[1].lower()  # Token text, lower case
        # t2 contains auxiliary token information, such as part-of-speech annotation, numbers, etc.
        if isinstance(t[2], list):
            self.t2 = tuple(t[2])
        else:
            self.t2 = t[2]
        self.is_upper = self.t1[0] != self.t1_lower[0]  # True if starts with upper case
        self._hash = None  # Cached hash
        self._index = original_index  # Index of original token within sentence

        # We store a cached check of whether this is an "eo". An "eo" is an adverb (atviksorð)
        # that cannot also be a preposition ("fs") and is therefore a possible non-ambiguous
        # prefix to a noun ("einkunn")
        self._is_eo = None

        # Cache the matching function to use with this token
        self._matching_func = BIN_Token._MATCHING_FUNC[self.t0]

    @property
    def is_word(self):
        return self.t0 == TOK.WORD

    @property
    def lower(self):
        """ Return the text for this property, in lower case """
        return self.t1_lower

    @property
    def index(self):
        """ Return the original index of the corresponding token within the sentence """
        return self._index

    @property
    def dump(self):
        """ Serialize the token as required for text dumping of trees """
        if self.t0 == TOK.WORD:
            # Simple case; no token kind or auxiliary information dumped
            return '"' + self.t1 + '"'
        if self.t2 is None:
            return '"{0}" {1}'.format(self.t1, self._kind)
        return '"{0}" {1} {2}'.format(
            self.t1, self._kind, json.dumps(self.t2, ensure_ascii=False)
        )

    @classmethod
    def fbits(cls, beyging):
        """ Convert a 'beyging' field from BIN to a set of fbits """
        bit = cls.FBIT
        return reduce(
            lambda x, y: x | y, (b for key, b in bit.items() if key in beyging), 0
        )

    @classmethod
    def get_fbits(cls, beyging):
        """ Get the (cached) fbits for a BIN 'beyging' field """
        fbits = cls._MEANING_CACHE.get(beyging)
        if fbits is None:
            # Calculate a set of bits that represent the variants
            # present in m.beyging
            fbits = cls.fbits(beyging)
            cls._MEANING_CACHE[beyging] = fbits
        return fbits

    @classmethod
    def bin_variants(cls, beyging):
        """ Return the set of variants coded in the given BÍN beyging string """
        if not beyging:
            return set()
        vset = cls._VARIANT_CACHE.get(beyging)
        if vset is None:
            vset = set(k for k, v in cls.VARIANT_EX.items() if v in beyging)
            if "lhþt" in vset:
                # Special case, since 'þt' is a substring of 'lhþt'
                vset.remove("þt")
                vset.remove("lh")
            elif "esb" in vset:
                vset.remove("sb")
            elif "evb" in vset:
                vset.remove("vb")
            elif "op" in vset:
                # For impersonal verbs, all three persons are identical
                # and not required
                vset -= {"p1", "p2", "p3"}
            cls._VARIANT_CACHE[beyging] = vset
        return vset

    @staticmethod
    def mm_verb_stem(verb):
        """ Lookup a verb stem for a 'miðmynd' verb,
            i.e. "eignast" for "eigna" (which may have appeared
            as "eignaðist" in the text) """
        # This used to be done via a database lookup but it turns
        # out this is unnecessary, since the middle voice verb stems
        # are always formed by adding "st" at the end of the regular
        # nominal form (unless it already ends with "st").
        return verb if verb.endswith("st") else verb + "st"

    @staticmethod
    def verb_matches(verb, terminal, form):
        """ Return True if the verb stem in question matches the verb category,
            where the category is one of so_0, so_1, so_2 depending on
            the allowable number of noun phrase arguments """

        # If this is an unknown but potentially composite verb,
        # it will contain one or more hyphens. In this case, use only
        # the last part in lookups in the internal verb lexicons.
        if "-" in verb:
            verb = verb.split("-")[-1]

        if terminal.is_subj:
            # Verb subject in non-nominative case
            # Examples:
            # 'Mig langar að fara til Frakklands'
            # 'Páli þykir þetta vera tóm vitleysa'
            if terminal.is_nh:
                if "NH" not in form:
                    # Nominative mode (nafnháttur)
                    return False
            if terminal.is_mm:
                # Central form of verb ('miðmynd')
                # For subj_mm, we don't care about anything but MM
                return "MM" in form
            if terminal.is_gm:
                # Central form of verb ('miðmynd')
                if "GM" not in form:
                    return False
            if terminal.is_singular and "ET" not in form:
                # Require singular
                return False
            if terminal.is_plural and "FT" not in form:
                # Require plural
                return False

            def subject_matches(subj):
                """ Look up the verb in the subjects list loaded from Verbs.conf """
                return subj in VerbSubjects.VERBS.get(verb, set())

            form_lh = "LHÞT" in form
            if terminal.is_lh:
                return form_lh and subject_matches("lhþt")
            # Don't allow lhþt unless explicitly requested in terminal
            if form_lh:
                return False
            form_sagnb = "SAGNB" in form
            if terminal.has_variant("none"):
                # subj_none: Check that the verb is listed in the 'none'
                # subject list in Verbs.conf
                if terminal.is_sagnb != form_sagnb:
                    return False
                return subject_matches("none")
            if form_sagnb and not terminal.is_sagnb:
                # For regular subj, we don't allow SAGNB form
                # ('langað', 'þótt')
                return False
            if terminal.has_variant("op") and "OP" not in form:
                return False
            # Make sure that the subject case (last variant) matches the terminal
            return subject_matches(terminal.variant(-1))

        if terminal.is_singular and "FT" in form:
            # Can't use plural verb if singular terminal
            return False
        if terminal.is_plural and "ET" in form:
            # Can't use singular verb if plural terminal
            return False
        # Check that person (1st, 2nd, 3rd) and other variant requirements match
        for v in terminal.variants:
            # Lookup variant to see if it is one of the required ones for verbs
            rq = BIN_Token._VERB_FORMS.get(v)
            if rq is not None and rq not in form:
                # If this is required variant that is not found in the form we have,
                # return False
                return False
        # Check restrictive variants, i.e. we don't accept meanings
        # that have those unless they are explicitly present in the terminal
        for v in ("sagnb", "lhþt", "bh"):  # Be careful with "lh" here - !!! add mm?
            if BIN_Token.VARIANT[v] in form and not terminal.has_variant(v):
                return False
        if terminal.is_lh:
            if "VB" in form and not terminal.has_variant("vb"):
                # We want only the strong declinations ("SB") of lhþt, not the weak ones,
                # unless explicitly requested
                return False
        if terminal.has_variant("bh") and "ST" in form:
            # We only want the explicit request forms (boðháttur), i.e. "bónaðu"/"bónið",
            # not 'stýfður boðháttur' ("bóna") which causes ambiguity vs.
            # the nominal mode (nafnháttur)
            return False
        # Check whether the verb token can potentially match the argument number
        # of the terminal in question. If the verb is known to take fewer
        # arguments than the terminal wants, this is not a match.
        if terminal.num_variants == 0 or terminal.variant(0) not in "012":
            # No argument number: all verbs match, except...
            if terminal.is_lh:
                # Special check for lhþt: may specify a case without it being an argument case
                if any(
                    terminal.has_variant(c) and BIN_Token.VARIANT[c] not in form
                    for c in BIN_Token.CASES
                ):
                    # Terminal specified a non-argument case but the token doesn't have it:
                    # no match
                    return False
            return True
        is_mm = "MM" in form
        nargs = int(terminal.variant(0))
        if is_mm:
            # For MM forms, do not use the normal stem of the verb
            # for lookup in the VerbObjects.VERBS collection;
            # instead, use the MM-NH stem.
            # This means that for instance "eignaðist hest" is not resolved
            # to "eigna" but to "eignast"
            verb = BIN_Token.mm_verb_stem(verb)
        if verb in VerbObjects.VERBS[nargs]:
            # Seems to take the correct number of arguments:
            # do a further check on the supported cases
            if nargs == 0:
                # Zero arguments: that's simple
                return True
            # Does this terminal require argument cases?
            if terminal.num_variants < 2:
                # No: we don't need to check further
                return True
            # The following is not consistent as some verbs take
            # legitimate arguments in 'miðmynd', such as 'krefjast', 'ábyrgjast'
            # 'undirgangast', 'minnast'. They are also not consistently
            # annotated in BIN; some of them are marked as MM and some not.
            if nargs > 1 and is_mm:
                # Temporary compromise: Don't accept verbs in 'miðmynd'
                # if taking >1 arguments
                return False
            # Check whether the parameters of this verb
            # match up with the requirements of the terminal
            # as specified in its variants at indices 1 and onward
            for argspec in VerbObjects.VERBS[nargs][verb]:
                if all(terminal.variant(1 + ix) == c for ix, c in enumerate(argspec)):
                    # All variants match this spec: we're fine
                    return True
            # No match: return False
            return False
        # It's not there with the correct number of arguments:
        # see if it definitely has fewer ones
        for i in range(0, nargs):
            if verb in VerbObjects.VERBS[i]:
                # Prevent verb from matching a terminal if it
                # doesn't have all the arguments that the terminal requires
                return False
        return True

    def matches_PERSON(self, terminal):
        """ Handle a person name token, matching it with a person_[case]_[gender] terminal """
        if terminal.startswith("sérnafn"):
            # We allow a simple person name to match an entity name (sérnafn)
            if not self.is_upper or " " in self.lower:
                # Must be capitalized and a single name
                return False
            if not terminal.num_variants:
                return True
            case = terminal.variant(0)
            return any(m.case == case for m in self.t2)
        if not terminal.startswith("person"):
            return False
        if not terminal.num_variants:
            # No variant specified on terminal: we're done
            return True
        # Check each PersonName tuple in the t2 list
        case = terminal.variant(0)
        gender = terminal.variant(1) if terminal.num_variants > 1 else None
        return any(
            case == m.case and (gender is None or gender == m.gender)
            for m in self.t2
        )

    def matches_ENTITY(self, terminal):
        """ Handle an entity name token, matching it with an entity terminal """
        return terminal.startswith("entity")
        # !!! TBD !!!
        # Allow person terminals to match entity names that look like person names,
        # i.e. are composed of more than one uppercase words
        # if not terminal.startswith("person"):
        #    return False
        # a = self.t1.split()
        # if len(a) < 2:
        #    return False
        # return all(n[0].isupper() for n in a)

    def matches_PUNCTUATION(self, terminal):
        """ Match a literal terminal with the same content as the punctuation token """
        return terminal.matches("punctuation", self.t1, self.t1)

    def matches_CURRENCY(self, terminal):
        """ A currency name token matches a noun terminal """
        if not terminal.startswith("no"):
            return False
        if terminal.is_abbrev:
            # A currency does not match an abbreviation
            return False
        if self.t2[1]:
            # See whether any of the allowed cases match the terminal
            for c in BIN_Token.CASES:
                if terminal.has_variant(c) and c not in self.t2[1]:
                    return False
        if self.t2[2]:
            # See whether any of the allowed genders match the terminal
            for g in BIN_Token.GENDERS:
                if terminal.has_variant(g) and g not in self.t2[2]:
                    return False
        else:
            # Match only the neutral gender if no gender given
            # return not (terminal.has_variant("kk") or terminal.has_variant("kvk"))
            return not terminal.has_any_vbits(BIN_Token.VBIT_KK | BIN_Token.VBIT_KVK)
        return True

    def is_correct_singular_or_plural(self, terminal):
        """ Match a number with a singular or plural noun (terminal).
            In Icelandic, all integers whose modulo 100 ends in 1 are
            singular, except 11. """
        singular = False
        orig_i = i = int(self.t2[0])
        if float(i) == float(self.t2[0]):
            # Whole number (integer): may be singular
            i = abs(i) % 100
            singular = (i != 11) and (i % 10) == 1
        if terminal.is_singular and not singular:
            # Terminal is singular but number is plural
            return True if orig_i in BIN_Token._SINGULAR_SPECIAL_CASES else False
        if terminal.is_plural and singular:
            # Terminal is plural but number is singular
            return False
        return True

    def matches_NUMBER(self, terminal):
        """ A number token matches a number (töl) or noun terminal """

        if terminal.startswith("tala"):
            # A 'tala' terminal matches a number regardless of any
            # case and gender variants that it may have. Those are
            # for informational purposes only.
            return self.is_correct_singular_or_plural(terminal)

        if terminal.first not in {"töl", "to"}:
            return False

        if not self.t2[1] and not self.t2[2]:
            # If no case and gender info, we only match "tala",
            # not nouns or "töl" terminals
            return False

        if not self.is_correct_singular_or_plural(terminal):
            return False
        if terminal.startswith("to"):
            # Allow a match with "to" if we have BOTH case and gender info
            if not self.t2[1] or not self.t2[2]:
                return False
            # Only check gender for "to", not "töl"
            for g in BIN_Token.GENDERS:
                if terminal.has_variant(g) and g not in self.t2[2]:
                    return False
        if self.t2[1]:
            # See whether any of the allowed cases match the terminal
            for c in BIN_Token.CASES:
                if terminal.has_variant(c) and c not in self.t2[1]:
                    return False
        return True

    def matches_AMOUNT(self, terminal):
        """ An amount token matches a noun terminal """
        if not terminal.startswith("no"):
            return False
        if terminal.has_any_vbits(BIN_Token.VBIT_ABBREV | BIN_Token.VBIT_GR):
            # An amount does not match an abbreviation or
            # a definite article
            return False
        if not self.is_correct_singular_or_plural(terminal):
            return False
        if self.t2[2]:
            # See whether any of the allowed cases match the terminal
            for c in BIN_Token.CASES:
                if terminal.has_variant(c) and c not in self.t2[2]:
                    return False
        if self.t2[3] is None:
            # No gender: match neutral gender only
            if terminal.has_any_vbits(BIN_Token.VBIT_KK | BIN_Token.VBIT_KVK):
                return False
        else:
            # Associated gender
            for g in BIN_Token.GENDERS:
                if terminal.has_variant(g) and g not in self.t2[3]:
                    return False
        return True

    def matches_PERCENT(self, terminal):
        """ A percent token matches a number (töl) or noun terminal """
        if terminal.startswith("töl") or terminal.startswith("prósenta"):
            return True
        # Matches number and noun terminals only
        if not terminal.startswith("no"):
            return False
        if terminal.is_abbrev:
            return False
        # If we are recognizing this as a noun, do so only with neutral gender
        if not terminal.has_variant("hk"):
            return False
        if terminal.has_variant("gr"):
            return False
        if self.t2[1]:
            # See whether any of the allowed cases match the terminal
            for c in BIN_Token.CASES:
                if terminal.has_variant(c) and c not in self.t2[1]:
                    return False
        # We do not check singular or plural here since phrases such as
        # '35% skattur' and '1% allra blóma' are valid
        return True

    def matches_YEAR(self, terminal):
        """ A year token matches a number (töl) or year (ártal) terminal """
        if terminal.first not in {"töl", "ártal", "tala"}:
            return False
        # Only singular match ('2014 var gott ár', not '2014 voru góð ár')
        # Years only match the neutral gender
        if terminal.has_any_vbits(
            BIN_Token.VBIT_FT | BIN_Token.VBIT_KK | BIN_Token.VBIT_KVK
        ):
            return False
        # No case associated with year numbers: match all
        return True

    def matches_DATE(self, terminal):
        """ A date token matches a date (dags) terminal """
        return terminal.startswith("dags")

    def matches_DATEABS(self, terminal):
        """ An absolute date token matches an absolute date (dagsföst) terminal """
        return terminal.startswith("dagsföst")

    def matches_DATEREL(self, terminal):
        """ A relative date token matches a relative date (dagsafs) terminal """
        return terminal.startswith("dagsafs")

    def matches_TIME(self, terminal):
        """ A time token matches a time (tími) terminal """
        return terminal.startswith("tími")

    def matches_TIMESTAMP(self, terminal):
        """ A timestamp token matches a timestamp (tímapunktur) terminal """
        return terminal.startswith("tímapunktur")

    def matches_TIMESTAMPABS(self, terminal):
        """ An absolute timestamp token matches an absolute timestamp (tímapunkturfast) terminal """
        return terminal.startswith("tímapunkturfast")

    def matches_TIMESTAMPREL(self, terminal):
        """ A relative timestamp token matches a relative timestamp (tímapunkturafs) terminal """
        return terminal.startswith("tímapunkturafs")

    def matches_ORDINAL(self, terminal):
        """ An ordinal token matches an ordinal (raðnr) terminal """
        return terminal.startswith("raðnr")

    def matches_MEASUREMENT(self, terminal):
        """ A measurement token matches a measurement (mælieining) terminal """
        return terminal.startswith("mælieining")

    def matches_WORD(self, terminal):
        """ Match a word token, having the potential part-of-speech meanings
            from the BIN database, with the terminal """

        def matcher_so(m):
            """ Check verb """
            if m.ordfl != "so":
                return False
            # Special case for verbs: match only the appropriate
            # argument number, i.e. so_0 for verbs having no noun argument,
            # so_1 for verbs having a single noun argument, and
            # so_2 for verbs with two noun arguments. A verb may
            # match more than one argument number category.
            return self.verb_matches(m.stofn, terminal, m.beyging)

        def matcher_no(m):
            """ Check noun """
            if BIN_Token.KIND[m.ordfl] != "no":
                return False
            no_info = m.beyging == "-"
            if terminal.is_abbrev:
                # Only match abbreviations; gender, case and number do not matter
                return no_info
            if m.fl == "nafn":
                # Names are only matched by person terminals
                return False
            for v in terminal.variants:
                if v in BIN_Token.GENDERS_SET:
                    if m.ordfl != v:
                        # Mismatched gender
                        return False
                elif no_info:
                    # No case and number info: probably a foreign word
                    # Match all cases and numbers
                    # if v == "ft":
                    #    return False
                    if v == "gr":
                        # Do not match a demand for the definitive article ('greinir')
                        return False
                elif BIN_Token.VARIANT[v] not in m.beyging:
                    # Required case or number not found: no match
                    return False
            return True

        def matcher_gata(m):
            """ Check street name """
            if m.fl != "göt":  # Götuheiti
                return False
            if BIN_Token.KIND[m.ordfl] != "no":
                return False
            for v in terminal.variants:
                if v in BIN_Token.GENDERS_SET:
                    if m.ordfl != v:
                        # Mismatched gender
                        return False
                elif BIN_Token.VARIANT[v] not in m.beyging:
                    # Required case or number not found: no match
                    return False
            return True

        def matcher_abfn(m):
            """ Check reflexive pronoun (afturbeygt fornafn) """
            if m.ordfl != "abfn":
                return False
            fbits = BIN_Token.get_fbits(m.beyging)
            # Check the case only
            # (don't check the gender, even if present, since it isn't found in BÍN)
            return terminal.fbits_match_mask(BIN_Token.VBIT_CASES, fbits)

        def matcher_pfn(m):
            """ Personal pronoun """
            if m.ordfl != "pfn":
                return False
            fbits = BIN_Token.get_fbits(m.beyging)
            # Check the case and number only
            # (don't check the gender, even if present, since it isn't found in BÍN)
            return terminal.fbits_match_mask(
                BIN_Token.VBIT_CASES | BIN_Token.VBIT_NUMBER, fbits
            )

        def matcher_stt(m):
            """ Check connective conjunction ('sem', 'er') """
            # This is actually never used by the current grammar,
            # since all instances of stt are of the form "sem:stt"
            # which is handled in matcher_default() / terminal.matches_first()
            return m.ordfl == "st" and m.stofn in {"sem", "er"}

        def matcher_spao(m):
            """ Interrogative adverbs, 'spurnaratviksorð' """
            return m.ordfl.endswith("ao") and m.stofn in BIN_Token._SPAO

        def matcher_tao(m):
            """ Temporal adverbs, 'tímaatviksorð' """
            return m.ordfl.endswith("ao") and m.stofn in BIN_Token._TAO

        def matcher_eo(m):
            """ 'Einkunnarorð': adverb (atviksorð) that is not the same
                as a preposition (forsetning) or pronoun (fornafn).
                Note that temporal adverbs (tao) are explicitly excluded
                since we want them marked as such in the result tree.
                Also, interrogative adverbs (spao) do not match. """
            if not m.ordfl.endswith("ao"):
                # Do not delete this check or move it inside the if below.
                # It is necessary to ensure that other word categories do not match,
                # and to find the correct m that actually matches.
                return False
            if self._is_eo is None:
                txt = self.t1_lower
                if txt in BIN_Token._TAO or txt in BIN_Token._SPAO:
                    self._is_eo = False
                # This token can match an adverb:
                # Cache whether it can also match a preposition
                elif txt in BIN_Token._NOT_EO:
                    # Explicitly forbidden, no need to check further
                    self._is_eo = False
                elif txt in BIN_Token._NOT_NOT_EO:
                    # Explicitly allowed, no need to check further
                    self._is_eo = True
                else:
                    # Check whether also a preposition or pronoun and return False in that case
                    self._is_eo = not (
                        txt in Prepositions.PP or
                        any(mm.ordfl == "fn" for mm in self.t2)
                    )
            # Return True if this token cannot also match a preposition
            return self._is_eo

        def matcher_ao(m):
            """ Adverbs, excluding spao and tao (and meanings explicitly marked as eo) """
            if m.ordfl != "ao" or matcher_spao(m) or matcher_tao(m):
                return False
            fbits = BIN_Token.get_fbits(m.beyging)
            return terminal.fbits_match(fbits)

        def matcher_fs(m):
            """ Check preposition. Note that in this exceptional case, we
                do not use the BÍN annotation of the token at all. Instead
                we look up the token text in Prepositions.PP which is read
                from the Main.conf file. """
            if not terminal.num_variants:
                return False
            # Note that in the case of abbreviated prepositions,
            # such as 'skv.' for 'samkvæmt', the full expanded form
            # is found in m.stofn - not self.t1_lower or m.ordmynd
            fs = self.t1_lower
            if "." in fs:
                fs = m.stofn
            # !!! Note that this will match a word and return True even if the
            # meanings of the token (the list in self.t2) do not include
            # the fs category. This effectively makes the prepositions
            # exempt from the ambiguous_phrases optimization.
            if fs not in Prepositions.PP:
                # Not a preposition
                return False
            var0 = terminal.variant(0)
            if var0 == "nh":
                # Only prepositions marked as nh can match
                return fs in Prepositions.PP_NH
            return var0 in Prepositions.PP[fs]

        def matcher_person(m):
            """ Check name from static phrases, coming from the Reynir.conf file """
            if m.fl != "nafn":
                return False
            if terminal.has_vbits(BIN_Token.VBIT_HK):
                # Never match neutral terminals
                return False
            # Check case, if present
            if m.beyging != "-":
                if any(
                    BIN_Token.VARIANT[c] in m.beyging and
                    not terminal.has_variant(c)
                    for c in BIN_Token.CASES
                ):
                    # The name has an associated case, but this is not it: quit
                    return False
            if terminal.has_vbits(BIN_Token.VBIT_KK) and m.ordfl != "kk":
                # Masculine specified but the name is feminine: no match
                return False
            if terminal.has_vbits(BIN_Token.VBIT_KVK) and m.ordfl != "kvk":
                # Feminine specified but the name is masculine: no match
                return False
            return True

        def matcher_fyrirtæki(m):
            """ Check whether the token text matches a set of corporation identfiers """
            # Note: these must have a meaning for this to work, so specifying them
            # as abbreviations to Main.conf is recommended
            return self.t1 in BIN_Token._CORPORATION_ENDINGS

        def matcher_töl(m):
            """ Undeclinable number word ('fimm', 'sex', 'tuttugu'...) """
            # In this case, the terminal may have variants but they are only used
            # to signal the context in which the terminal stands. We don't use
            # the variants to disqualify meanings, since the word is undeclinable
            # anyway.
            return terminal.matches_first(m.ordfl, m.stofn, self.t1_lower)

        def matcher_default(m):
            """ Check other word categories """
            if m.beyging == "-":
                if m.ordfl == "lo":
                    # If we have an adjective (lo) with no declination info,
                    # assume it's an abbreviation ("hæstv." for "hæstvirtur")
                    # and thus it matches any lo_X terminal irrespective of variants
                    return terminal.matches_first(m.ordfl, m.stofn, self.t1_lower)
                fbits = 0
            else:
                # If the meaning is a noun, its gender is coded in the ordfl attribute
                # In that case, add it to the beyging field so that the relevant fbits
                # are included and can be matched against the terminal if it requires
                # a gender
                fbits = BIN_Token.get_fbits(
                    m.beyging + BIN_Token.GENDERS_MAP.get(m.ordfl, "")
                )
            # Check whether variants required by the terminal are present
            # in the meaning string
            if not terminal.fbits_match(fbits):
                return False
            return terminal.matches_first(m.ordfl, m.stofn, self.t1_lower)

        def matcher_sérnafn(m):
            # Proper name?
            # Only allow a potential interpretation as a proper name if
            # the token is uppercase but there is no uppercase meaning of
            # the word in BÍN. This excludes for instance "Ísland" which
            # should be treated purely as a noun, not as a proper name.
            if not self.is_upper:
                return False
            if self.t1_lower in BIN_Token._NOT_PROPER_NAME:
                return False
            if " " in self.t1_lower:
                return False
            if terminal.num_variants == 0:
                return True
            # The terminal is sérnafn_case: We only accept nouns or adjectives
            # that match the given case
            fbits = BIN_Token.get_fbits(m.beyging) & BIN_Token.VBIT_CASES
            return (
                BIN_Token.KIND[m.ordfl] in {"no", "lo"} and
                terminal.fbits_match(fbits)
            )

        # We have a match if any of the possible part-of-speech meanings
        # of this token match the terminal
        if self.t2:
            # The dispatch table has to be constructed each time because
            # the calls will have a wrong self pointer otherwise
            matcher = locals().get("matcher_" + terminal.first, matcher_default)
            # Return the first matching meaning, or False if none
            return next((m for m in self.t2 if matcher(m)), False)

        # Unknown word, i.e. no meanings in BÍN (might be foreign, unknown name, etc.)
        if self.is_upper:
            # Starts in upper case: We allow this to match a named entity terminal ('sérnafn')
            if (
                terminal.startswith("sérnafn")
                and terminal.num_variants == 0
                and " " not in self.t1_lower
            ):
                return True

        # Not upper case: allow it to match a singular, neutral noun in all cases,
        # but without the definite article ('greinir')
        return (
            terminal.startswith("no")
            and terminal.has_vbits(BIN_Token.VBIT_ET | BIN_Token.VBIT_HK)
            and not terminal.has_vbits(BIN_Token.VBIT_GR)
        )

    # Dispatch table for the token matching functions
    _MATCHING_FUNC = {
        TOK.PERSON: matches_PERSON,
        TOK.ENTITY: matches_ENTITY,
        TOK.PUNCTUATION: matches_PUNCTUATION,
        TOK.CURRENCY: matches_CURRENCY,
        TOK.AMOUNT: matches_AMOUNT,
        TOK.NUMBER: matches_NUMBER,
        TOK.PERCENT: matches_PERCENT,
        TOK.ORDINAL: matches_ORDINAL,
        TOK.YEAR: matches_YEAR,
        TOK.DATE: matches_DATE,
        TOK.DATEREL: matches_DATEREL,
        TOK.DATEABS: matches_DATEABS,
        TOK.TIME: matches_TIME,
        TOK.TIMESTAMP: matches_TIMESTAMP,
        TOK.TIMESTAMPREL: matches_TIMESTAMPREL,
        TOK.TIMESTAMPABS: matches_TIMESTAMPABS,
        TOK.MEASUREMENT: matches_MEASUREMENT,
        TOK.WORD: matches_WORD,
    }

    @classmethod
    def is_understood(cls, t):
        """ Return True if the token type is understood by the BIN Parser """
        if t[0] == TOK.PUNCTUATION:
            # A limited number of punctuation symbols is currently understood
            return t[1] in cls._UNDERSTOOD_PUNCTUATION
        return t[0] in cls._MATCHING_FUNC

    def matches(self, terminal):
        """ Return True if this token matches the given terminal """
        # If the terminal already knows it doesn't match this token,
        # bail out quickly
        if (
            terminal.shortcut_match is not None
            and terminal.shortcut_match(self.t1_lower)
        ):
            return False
        # Otherwise, dispatch the token matching according to the dispatch table in _MATCHING_FUNC
        return self._matching_func(self, terminal) is not False

    def match_with_meaning(self, terminal):
        """ Return False if this token does not match the given terminal;
            otherwise True or the actual meaning tuple that matched """
        # If the terminal already knows it doesn't match this token,
        # bail out quickly
        if (
            terminal.shortcut_match is not None
            and terminal.shortcut_match(self.t1_lower)
        ):
            # Strong literal terminals (those in double quotes) implement this feature
            return False
        # Dispatch the token matching according to the dispatch table in _MATCHING_FUNC
        return self._matching_func(self, terminal)

    def __repr__(self):
        return "[" + TOK.descr[self.t0] + ": " + self.t1 + "]"

    def __str__(self):
        return "'" + self.t1 + "'"

    @property
    def key(self):
        """ Return a hashable key that partitions tokens based on
            effective identity, i.e. tokens with the same hash can be considered
            equivalent for parsing purposes. This hash is inter alia used by the
            alloc_cache() function in fastparser.py to optimize token/terminal
            matching calls. """
        if self.t0 == TOK.WORD:
            # For words, the t2 tuple is significant because it may have been
            # cut down by the tokenizer due to the word's context, cf. the
            # [ambiguous_phrases] section in Main.conf
            return self.t0, self.t1, self.t2
        # Otherwise, the t0 and t1 fields are enough
        return self.t0, self.t1

    def __hash__(self):
        """ Calculate and cache a hash for this token """
        if self._hash is None:
            self._hash = hash(self.key)
        return self._hash

    @classmethod
    def init(cls):
        # Initialize cached dictionary of verb variant forms in BIN
        cls._VERB_FORMS = {v: cls.VARIANT[v] for v in cls.VERB_VARIANTS}


BIN_Token.init()


class VariantHandler:

    """ Mix-in class used in BIN_Terminal and BIN_LiteralTerminal to add
        querying of terminal variants as well as mapping of variants to
        bit arrays for speed """

    def __init__(self, name):
        super().__init__(name)
        # Do a bit of pre-calculation to speed up various
        # checks against this terminal
        parts = self._name.split("_")
        self._first = parts[0]
        # The variant set for this terminal, i.e.
        # tname_var1_var2_var3 -> { 'var1', 'var2', 'var3' }
        self._vparts = parts[1:]
        self._vcount = len(self._vparts)
        self._vset = set(self._vparts)
        # Also map variant names to bits in self._vbits
        bit = BIN_Token.VBIT
        self._vbits = reduce(
            lambda x, y: (x | y),
            (bit[v] for v in self._vset if v in bit),
            0
        )
        # fbits are like vbits but leave out variants that have no BIN meaning
        self._fbits = self._vbits & (~BIN_Token.FBIT_MASK)
        # For speed, store the cases associated with a verb
        # so_0 -> self._cases = ""
        # so_1_þgf -> self._cases = "þgf"
        # so_2_þf_þgf -> self._cases = "þf_þgf"
        if self._vcount >= 1 and self._vparts[0] in "012":
            ncases = int(self._vparts[0])
            self._cases = "".join("_" + self._vparts[1 + i] for i in range(ncases))
        else:
            self._cases = ""

    def startswith(self, part):
        """ Returns True if the terminal name starts with the given string """
        return self._first == part

    def matches_category(self, cat):
        """ Returns True if the terminal matches a particular category
            (overridden in BIN_LiteralTerminal) """
        return self._first == cat

    def matches_first(self, t_kind, t_val, t_lit):
        """ Returns True if the first part of the terminal name matches the
            given word category """
        # Convert 'kk', 'kvk', 'hk' to 'no' before doing the compare
        return self._first == BIN_Token.KIND[t_kind]

    @property
    def first(self):
        """ Return the first part of the terminal name (without variants) """
        return self._first

    @property
    def category(self):
        """ Return the word category matched by the terminal """
        return self._first

    @property
    def colon_cat(self):
        """ Return the string specified after a colon in the terminal name, if any """
        # This is overridden in LiteralTerminal
        return None

    @property
    def num_variants(self):
        """ Return the number of variants in the terminal name """
        return self._vcount

    @property
    def variants(self):
        """ Returns the variants contained in this terminal name as a list """
        return self._vparts

    def variant(self, index):
        """ Return the variant with the given index """
        return self._vparts[index]

    @property
    def verb_cases(self):
        """ Return the verb cases associated with a so_ terminal, or empty string """
        return self._cases

    def has_variant(self, v):
        """ Returns True if the terminal name has the given variant """
        return v in self._vset

    def has_vbits(self, vbits):
        """ Return True if this terminal has (all) the variant(s) corresponding to the given bit(s) """
        return (self._vbits & vbits) == vbits

    def has_any_vbits(self, vbits):
        """ Return True if this terminal has any of the variant(s) corresponding to the given bit(s) """
        return (self._vbits & vbits) != 0

    def cut_fbits(self, fbits):
        """ Mask off the given fbits, making them irrelevant in matches """
        self._fbits &= ~fbits

    def fbits_match(self, fbits):
        """ Return True if the given fbits meet all variant criteria """
        # That is: for every bit in self._fbits, there must be a corresponding bit
        # in the given fbits. We test this by turning off all the bits given in the
        # parameter fbits and checking whether there are any bits left.
        return (self._fbits & ~fbits) == 0

    def fbits_match_mask(self, mask, fbits):
        """ Return True if the given fbits meet the variant criteria after masking """
        return (self._fbits & mask & ~fbits) == 0

    @property
    def gender(self):
        """ Return a gender string corresponding to a variant of this terminal, if any """
        if self._vbits & BIN_Token.VBIT_KK:
            return "kk"
        if self._vbits & BIN_Token.VBIT_KVK:
            return "kvk"
        if self._vbits & BIN_Token.VBIT_HK:
            return "hk"
        return None

    @property
    def is_singular(self):
        return (self._vbits & BIN_Token.VBIT_ET) != 0

    @property
    def is_plural(self):
        return (self._vbits & BIN_Token.VBIT_FT) != 0

    @property
    def is_abbrev(self):
        return (self._vbits & BIN_Token.VBIT_ABBREV) != 0

    @property
    def is_nh(self):
        return (self._vbits & BIN_Token.VBIT_NH) != 0

    @property
    def is_mm(self):
        return (self._vbits & BIN_Token.VBIT_MM) != 0

    @property
    def is_gm(self):
        return (self._vbits & BIN_Token.VBIT_GM) != 0

    @property
    def is_subj(self):
        return (self._vbits & BIN_Token.VBIT_SUBJ) != 0

    @property
    def is_sagnb(self):
        return (self._vbits & BIN_Token.VBIT_SAGNB) != 0

    @property
    def is_lh(self):
        # Lýsingarháttur þátíðar ("LHÞT")
        return (self._vbits & BIN_Token.VBIT_LH) != 0

    @property
    def is_lh_nt(self):
        # Lýsingarháttur nútíðar ("LH-NT")
        return (self._vbits & BIN_Token.VBIT_LHNT) == BIN_Token.VBIT_LHNT

    @property
    def is_vh(self):
        return (self._vbits & BIN_Token.VBIT_VH) != 0


class BIN_Terminal(VariantHandler, Terminal):

    """ Subclass of Terminal that mixes in support from VariantHandler
        for variants in terminal names, including optimizations of variant
        checks and lookups """

    def __init__(self, name):
        super().__init__(name)
        # By default, there is not shortcut function for matching
        self.shortcut_match = None


class BIN_LiteralTerminal(VariantHandler, LiteralTerminal):

    """ Subclass of LiteralTerminal that mixes in support from VariantHandler
        for variants in terminal names """

    def __init__(self, name):
        super().__init__(name)
        # Peel off the quotes from the first part
        assert len(self._first) >= 2  # The string can be ""
        assert self._first[0] == self._first[-1]
        self._first = self._first[1:-1]
        self._cat = None
        self._match_cat = None
        if len(self._first) > 1:
            # Check for a word category specification,
            # i.e. "sem:st", "að:fs", 'vera:so'_gm_nt
            a = self._first.split(":")
            if len(a) > 2:
                raise GrammarError(
                    "A literal terminal can only have one word category specification"
                )
            elif len(a) == 2:
                # We have a word category specification
                self._first = a[0]
                self._cat = self._match_cat = a[1]
                if self._cat == "stt":
                    # Hack to make 'stt' terminals match with the BÍN 'st' category
                    # (stt is only there to mark 'sem' and 'er' specially in particular contexts)
                    self._match_cat = "st"
                elif self._cat == "pfn":
                    # Hack to allow genders to be specified on pfn literal terminals
                    # without having them affect the matching (since genders
                    # are not included on pfn's in BÍN)
                    self.cut_fbits(BIN_Token.VBIT_GENDERS)
                elif self._cat == "fs" or self._cat == "so":
                    # Hack to allow cases to be specified on fs and so literal terminals
                    # (like so: 'í:fs'_þgf) without having them affect the matching
                    self.cut_fbits(BIN_Token.VBIT_CASES)
        # Check whether we have variants on an exact literal
        if self._strong and self.num_variants > 0:
            # It doesn't make sense to have variants on exact literals
            # since they are constant and cannot vary
            raise GrammarError(
                "An exact literal terminal with double quotes cannot have variants"
            )
        if self._match_cat is None:
            # In the simple case where there is no associated category,
            # override matches_first with a simple comparison
            if self._strong:
                self.matches_first = lambda t_kind, t_val, t_lit: self._first == t_lit
            else:
                self.matches_first = lambda t_kind, t_val, t_lit: self._first == t_val
        # For strong literal terminals, provide a fast shortcut so that a token
        # is not considered further if its text does not match the literal
        if self._strong:
            self.shortcut_match = lambda t_lit: self._first != t_lit
        else:
            self.shortcut_match = None

    @property
    def colon_cat(self):
        """ Return the string occurring after a colon in the terminal name """
        return self._cat

    @property
    def category(self):
        """ Return the word category matched by the terminal """
        return self._match_cat

    def startswith(self, part):
        """ Override VariantHandler.startswith() """
        return False

    def matches_category(self, cat):
        """ Returns True if the terminal matches a particular category
            (overrides VariantHandler) """
        return self._match_cat == cat

    def matches_first(self, t_kind, t_val, t_lit):
        """ A literal terminal matches a token if the token text is identical to the literal """
        # Note that this function is overridden in __init__ if self._cat is None
        if t_kind != self._match_cat:
            # Match only the word category that was specified
            return False
        return (self._first == t_lit) if self._strong else (self._first == t_val)

    def matches(self, t_kind, t_val, t_lit):
        """ A literal terminal matches a token if the token text is
            canonically or absolutely identical to the literal """
        return (self._first == t_lit) if self._strong else (self._first == t_val)


class BIN_Nonterminal(Nonterminal):

    """ Subclass of Nonterminal with BÍN-specific convenience functions """

    def __init__(self, name, fname, line):
        super().__init__(name, fname, line)
        # Optimized check for whether this is a noun phrase nonterminal
        self._is_noun_phrase = name.startswith("Nl")

    @property
    def is_noun_phrase(self):
        """ Return True if this nonterminal denotes a noun phrase """
        return self._is_noun_phrase

    @property
    def first(self):
        """ Return the initial part (before any underscores) of the nonterminal name """
        # Do this on demand
        try:
            return self._parts[0]
        except AttributeError:
            self._parts = self.name.split("_")
            return self._parts[0]


class BIN_Grammar(Grammar):

    """ Subclass of Grammar that creates BIN-specific Terminals and LiteralTerminals
        when parsing a grammar, with support for variants in terminal names """

    def __init__(self):
        super().__init__()

    @staticmethod
    def _make_terminal(name):
        """ Make BIN_Terminal instances instead of plain-vanilla Terminals """
        return BIN_Terminal(name)

    @staticmethod
    def _make_literal_terminal(name):
        """ Make BIN_LiteralTerminal instances instead of plain-vanilla LiteralTerminals """
        return BIN_LiteralTerminal(name)

    @staticmethod
    def _make_nonterminal(name, fname, line):
        """ Make BIN_Terminal instances instead of plain-vanilla Terminals """
        return BIN_Nonterminal(name, fname, line)


class BIN_Parser(Base_Parser):

    """ BIN_Parser parses sentences according to the Icelandic
        grammar in the Reynir.grammar file. It subclasses Parser
        and wraps the interface between the BIN grammatical
        data on one hand and the tokens and grammar terminals on
        the other. """

    # A singleton instance of the parsed Reynir.grammar
    _grammar = None
    _grammar_ts = None

    # BIN_Parser version - change when logic is modified so that it
    # affects the parse tree
    _VERSION = "1.0"
    _GRAMMAR_FILE = os.path.join(_PATH, "Reynir.grammar")

    def __init__(self, verbose=False):
        """ Load the shared BIN grammar if not already there, then initialize
            the Base_Parser parent class """
        g = BIN_Parser._grammar
        ts = os.path.getmtime(BIN_Parser._GRAMMAR_FILE)
        if g is None or BIN_Parser._grammar_ts != ts:
            # Grammar not loaded, or its timestamp has changed: load it
            t0 = time.time()
            g = BIN_Grammar()
            if Settings.DEBUG:
                print(
                    "Loading grammar file {0} with timestamp {1}"
                    .format(
                        BIN_Parser._GRAMMAR_FILE, datetime.fromtimestamp(ts)
                    )
                )
            g.read(BIN_Parser._GRAMMAR_FILE, verbose=verbose)
            BIN_Parser._grammar = g
            BIN_Parser._grammar_ts = ts
            if Settings.DEBUG:
                print(
                    "Grammar parsed and loaded in {0:.2f} seconds"
                    .format(time.time() - t0)
                )
        super().__init__(g)

    @property
    def grammar(self):
        """ Return the grammar loaded from Reynir.grammar """
        return BIN_Parser._grammar

    @property
    def version(self):
        """ Return a composite version string from BIN_Parser and Parser """
        ftime = str(self.grammar.file_time)[0:19]  # YYYY-MM-DD HH:MM:SS
        return ftime + "/" + BIN_Parser._VERSION + "/" + super()._VERSION

    @staticmethod
    def _wrap(tokens):
        """ Sanitize the 'raw' tokens and wrap them in BIN_Token() wrappers """
        return wrap_tokens(tokens, wrap_func=lambda t, ix: BIN_Token(t, ix))

    def go(self, tokens):
        """ Parse the token list after wrapping each understood token in the BIN_Token class """
        raise NotImplementedError  # This should never be called - is overridden in Fast_Parser


# Abbreviations and stuff that we ignore inside parentheses
_UNKNOWN = frozenset(("e.", "d.", "þ.", "t.d.", "þ.e.", "m.a."))
_SKIP_PARENTHESIS = frozenset(("e.", "d.", "þ."))


def wrap_tokens(tokens, wrap_func=None):
    """ Pre-process a token stream, removing tokens that will not be looked at
        during parsing - for instance insignificant punctuation and non-Icelandic
        text within parentheses. The function returns a fresh token list, with
        each token eventually processed through the wrap_func given, if any. """

    # Remove stuff that won't be understood in any case
    # Start with runs of unknown words inside parentheses
    tlist = list(tokens)
    tlen = len(tlist)

    def scan_par(left):
        """ Scan tokens inside parentheses and remove'em all
            if they are only unknown words - perhaps starting with
            an abbreviation """
        right = left + 1
        while right < tlen:
            tok = tlist[right]
            if tok[0] == TOK.PUNCTUATION and tok[1] == ")":
                # Check the contents of the token list from left+1 to right-1

                # Skip parentheses starting with "e." (English), "þ." (German) or "d." (Danish)
                foreign = right > left + 1 and tlist[left + 1][1] in _SKIP_PARENTHESIS

                def is_unknown(t):
                    """ A token is unknown if it is a TOK.UNKNOWN or if it is a
                        TOK.WORD with no meanings """
                    return (
                        t[0] == TOK.UNKNOWN
                        or (t[0] == TOK.WORD and not t[2])
                        or t[1] in _UNKNOWN
                    )

                if foreign or all(is_unknown(t) for t in tlist[left + 1 : right]):
                    # Only unknown tokens: erase'em, including the parentheses
                    for i in range(left, right + 1):
                        tlist[i] = None

                return right + 1

            right += 1
        # No match: we're done
        return right

    ix = 0
    while ix < tlen:
        tok = tlist[ix]
        if tok[0] == TOK.PUNCTUATION and tok[1] == "(":
            ix = scan_par(ix)  # Jumps to the right parenthesis, if found
        else:
            ix += 1

    # Wrap the sanitized token list using wrap_func, if given,
    # while keeping a back index to the original token
    wrapped_tokens = []
    for ix, t in enumerate(tlist):
        if t is not None and BIN_Token.is_understood(t):
            wrapped_tokens.append(t if wrap_func is None else wrap_func(t, ix))
    return wrapped_tokens


def simplify_terminal(terminal, cat=None):
    """ Return a simplified terminal name where literal specifications of
        the form 'literal:cat'_var1 and "literal:cat" have been converted
        to cat_var1, with the further complication that kk/kvk/hk are
        converted to no_kk/no_kvk/no_hk. If the cat parameter is given,
        it is the fallback if no category is specified in the literal. """
    if terminal[0] not in "\"'":
        # Not a literal terminal: no need to do anything
        return terminal
    # Change "literal:category" to category,
    # or 'stem'_var1_var2 to category_var1_var2
    # Convert 'literal'_var1_var2 to cat_var1_var2
    # Note that the literal can contain underscores!
    endq = terminal.rindex(terminal[0])
    first = terminal[0 : endq + 1]
    rest = terminal[endq + 1 :]
    if ":" in first:
        # The word category was given in the literal: use it
        # (In almost all cases this matches the meaning, but
        # 'stt' is an exception)
        first = first.split(":")[-1][:-1]
    elif cat is not None:
        # Get the word category from the meaning
        first = cat
    if first in {"kk", "kvk", "hk"}:
        first = "no_" + first
    return first + rest


# Missing variants for personal pronouns
_PFN_VARIANTS = {
    "ég": {"p1"},
    "mig": {"p1"},
    "mér": {"p1"},
    "mín": {"p1"},
    "við": {"p1"},
    "okkur": {"p1"},
    "okkar": {"p1"},
    "vér": {"p1"},
    "oss": {"p1"},
    "vor": {"p1"},
    "þú": {"p2"},
    "þig": {"p2"},
    "þér": {"p2"},
    "þín": {"p2"},
    "þið": {"p2"},
    "ykkur": {"p2"},
    "ykkar": {"p2"},
    "yður": {"p2"},
    "yðar": {"p2"},
    "hann": {"p3", "kk"},
    "honum": {"p3", "kk"},
    "hans": {"p3", "kk"},
    "þeir": {"p3", "kk"},
    "þá": {"p3", "kk"},
    "hún": {"p3", "kvk"},
    "hana": {"p3", "kvk"},
    "henni": {"p3", "kvk"},
    "hennar": {"p3", "kvk"},
    "þær": {"p3", "kvk"},
    "það": {"p3", "hk"},
    "því": {"p3", "hk"},
    "þess": {"p3", "hk"},
    "þau": {"p3", "hk"},
    "þeim": {"p3"},  # Gender unknown
    "þeirra": {"p3"},  # Gender unknown
}


def augment_terminal(terminal, text_lower, beyging):
    """ Augment a terminal name string with additional variants from BÍN,
        extracted from the 'beyging' string """
    a = terminal.split("_")
    cases = []
    vstart = 1
    if a[0] == "so" and len(a) > 1:
        # Special case for verb arguments: keep them in order
        if a[1] in "012":
            args = int(a[1])
            cases = a[1 : 2 + args]
            vstart = 2 + args
        elif a[1] == "subj":
            cases = a[1:2]
            vstart = 2
    vset = set(a[vstart:])
    if a[0] == "pfn":
        # For personal pronouns, BÍN is missing gender and person information
        # Add it here for completeness
        vset |= _PFN_VARIANTS.get(text_lower, set())
    # Collect the variants from the terminal and from the BÍN 'beyging' string
    vset |= BIN_Token.bin_variants(beyging)
    # Additional hygiene to make sure we don't have both _esb and _sb / _evb and _vb
    if "esb" in vset and "sb" in vset:
        vset.remove("sb")
    elif "evb" in vset and "vb" in vset:
        vset.remove("vb")
    elif "op" in vset:
        # For impersonal verbs, all three persons are identical
        # and not required
        vset -= {"p1", "p2", "p3"}
    return "_".join(a[0:1] + cases + sorted(list(vset)))


def canonicalize_token(t):
    """ Convert a token in-situ from a compact dictionary representation
        (typically created by TreeUtility._describe_token()) to a normalized,
        verbose form that is appropriate for external consumption """

    # Set the token kind to a readable string
    kind = t.get("k", TOK.WORD)
    t["k"] = TOK.descr[kind]
    if "t" in t:
        t["t"] = simplify_terminal(
            t["t"], t["m"][1] if "m" in t else None
        )  # Fallback category
    if "m" in t:
        # Flatten the meaning from a tuple/list
        m = t["m"]
        del t["m"]
        # s = stofn (lemma)
        # c = ordfl (category)
        # f = fl (class)
        # b = beyging (declination)
        # For abbreviations (fl='skst'), we include the original token text as the
        # lemma, instead of the abbreviation meaning (which is stored in m[0])
        fl = m[2]
        lemma = t["x"] if fl == "skst" else m[0]
        t.update(dict(s=lemma, c=m[1], f=fl, b=m[3]))
    if "t" in t and "b" in t:
        # This is a terminal that may have additional information
        # about itself in the 'b' (beyging) field from BÍN.
        # Add an 'a' field with a terminal name including all
        # variants, in a canonical form that lists verb arguments
        # first, followed by other variants in alphabetical order.
        t["a"] = augment_terminal(t["t"], t["x"].lower(), t["b"])
    if "v" in t:
        # Flatten and simplify the val field, if present
        val = t["v"]
        if kind == TOK.AMOUNT:
            # Flatten and simplify amounts
            t["v"] = dict(amount=val[0], currency=val[1])
        elif kind == TOK.MEASUREMENT:
            # Flatten and simplify measurements
            t["v"] = dict(unit=val[0], value=val[1])
        elif kind in {TOK.NUMBER, TOK.CURRENCY, TOK.PERCENT}:
            # Number, ISO currency code, percentage
            t["v"] = val[0]
        elif kind in {TOK.DATE, TOK.DATEREL, TOK.DATEABS}:
            t["v"] = dict(y=val[0], mo=val[1], d=val[2])
        elif kind == TOK.TIME:
            t["v"] = dict(h=val[0], m=val[1], s=val[2])
        elif kind in {TOK.TIMESTAMP, TOK.TIMESTAMPREL, TOK.TIMESTAMPABS}:
            t["v"] = dict(y=val[0], mo=val[1], d=val[2], h=val[3], m=val[4], s=val[5])
        elif kind == TOK.PERSON:
            # Move the nominal form of the name to the "s" (stem) field
            t["s"] = t["v"]
            del t["v"]
            # Move the gender to the "c" (category) field
            if "g" in t:
                t["c"] = t["g"]
                del t["g"]
    if kind in (TOK.ENTITY, TOK.WORD) and "s" not in t:
        # Put in a stem for entities and proper names
        t["s"] = t["x"]

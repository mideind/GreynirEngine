"""
    Reynir: Natural language processing for Icelandic

    Matcher module

    Copyright (c) 2018 Miðeind ehf.
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


    This module contains a wrapper class for "simple trees" with
    tree pattern matching operations.

    The match patterns are as follows:
    ----------------------------------

    `.` matches any tree node

    `"literal"` matches a subtree covering exactly the given literal text,
        albeit case-neutral

    `'lemma'` matches a subtree covering exactly the given word lemma(s)

    `NONTERMINAL` matches the given nonterminal

    `terminal` matches the given terminal
    `terminal_var1_var2` matches a terminal having at least the given variants

    `Any1 Any2 Any3` matches the given sequence as-is, in-order

    `Any+` matches one or more sequential instances of Any

    `Any*` matches zero or more sequential instances of Any

    `Any?` matches zero or one sequential instances of Any

    `.*` matches any number of any nodes (as an example)

    `(Any1 | Any2 | ...)` matches if anything within the parentheses matches

    `Any1 > { Any2 Any3 ... }` matches if Any1 matches and has immediate children
        that include Any2, Any3 *and* other given arguments (irrespective of order).
        This is a set-like operator.

    `Any1 >> { Any2 Any3 ... }` matches if Any1 matches and has children at any
        sublevel that include Any2, Any3 *and* other given arguments
        (irrespective of order). This is a set-like operator.

    `Any1 > [ Any2 Any3 ...]` matches if Any1 matches and has immediate children
        that include Any2, Any3 *and* other given arguments in the order specified.
        This is a list-like operator.

    `Any1 >> [ Any2 Any3 ...]` matches if Any1 matches and has children at any sublevel
        that include Any2, Any3 *and* other given arguments in the order specified.
        This is a list-like operator.

    `[ Any1 Any2 ]` matches any node sequence that starts with the two given items.
        It does not matter whether the sequence contains more items.

    `[ Ant1 Any2 $ ]` matches only sequences where Any1 and Any2 match and there are
        no further nodes in the sequence

    `[ Any1 .* Any2 $ ]` matches only sequences that start with Any1 and end with Any2

    NOTE: The repeating operators * + ? are meaningless within { sets }; their
        presence will cause an exception.


    Examples:
    ---------

    All sentences having verb phrases that refer to a person as an argument:

    `S >> { VP >> { NP >> person }}`

    All sentences having verb phrases that refer to a male person as an argument:

    `S >> { VP >> { NP >> person_kk }}`

"""


import re
from pprint import pformat
from itertools import chain

from .cache import cached_property
from .settings import StaticPhrases
from .binparser import BIN_Token, augment_terminal
from .bintokenizer import (
    CURRENCIES,
    CURRENCY_GENDERS,
    MULTIPLIERS,
    DECLINABLE_MULTIPLIERS,
)
from .bindb import BIN_Db
from .ifdtagger import IFD_Tagset


# Default tree simplifier configuration maps

_DEFAULT_NT_MAP = {
    "S0": "P",
    "HreinYfirsetning": "S-MAIN",
    "Setning": "S",
    "SetningLo": "S",
    "SetningÁnF": "S",
    "SetningAukafall": ("S", "IP"),  # Push two headers: S and IP
    "SetningAukafallForgangur": ("S", "IP"),
    "SetningSkilyrði": "S",
    "SetningUmAðRæða": "S",
    "StViðtenging": "S",
    "Tilvísunarsetning": "S-REF",
    "Skilyrði": "S-COND",
    "Afleiðing": "S-CONS",
    "NlSkýring": "S-EXPLAIN",
    "Útskýring": "S-EXPLAIN",
    "FrumlagsInnskot": "S-EXPLAIN",
    "Tilvitnun": "S-QUOTE",
    "Forskeyti": "S-PREFIX",
    # "EfÞegar" : "S-PREFIX",
    "Tíðarsetning": "S-ADV-TEMP",
    "Tilgangssetning": "S-ADV-PURP",
    "Viðurkenningarsetning": "S-ADV-ACK",
    "Afleiðingarsetning": "S-ADV-CONS",
    "Orsakarsetning": "S-ADV-CAUSE",
    "Skilyrðissetning": "S-ADV-COND",
    "Skýringarsetning": "S-THT",
    "Spurnaraukasetning": "S-QUE",
    "Spurnarsetning": "S-QUE",
    "BeygingarliðurÁnF": "IP",
    "BeygingarliðurÁnUmröðunar": "IP",
    "BeygingarliðurMeðUmröðun": "IP",
    "Nl": "NP",
    "EfLiður": "NP-POSS",
    "EfLiðurForskeyti": "NP-POSS",
    "OkkarFramhald": "NP-POSS",
    "LoEftirNlMeðÞgf": "NP-DAT",
    "Heimilisfang": "NP-ADDR",
    "Magn": "NP-MEASURE",
    "Titill": "NP-TITLE",
    "Frumlag": "NP-SUBJ",
    "NlFrumlag": "NP-SUBJ",
    "NlBeintAndlag": "NP-OBJ",
    "NlÓbeintAndlag": "NP-IOBJ",
    "NlSagnfylling": "NP-PRD",
    "SögnErLoBotn": "NP-PRD",  # Show '(Hann er) góður / 18 ára' as a predicate argument
    "Aldur": "NP-AGE",
    "Sagnliður": "VP",
    "SagnliðurMeðF": "VP",
    "So": "VP",
    # "SagnFramhald" : "VP",
    "NhLiðir": "VP",
    "SagnliðurÁnF": "VP",
    "ÖfugurSagnliður": "VP",
    "SagnliðurVh": "VP",
    "SögnLhNt": "VP-PP",  # Present participle, lýsingarháttur nútíðar
    "SagnHluti": "VP-SEQ",
    "SagnRuna": "VP-SEQ",
    "SetningSo": "VP-SEQ",
    "FsMeðFallstjórn": "PP",
    "LoTengtSögn": "ADJP",
    "SagnInnskot": "ADVP",
    "FsAtv": "ADVP",
    "AtvFs": "ADVP",
    "Atviksliður": "ADVP",
    "LoAtviksliðir": "ADVP",
    "Dagsetning": "ADVP-DATE",
    "Tímasetning": "ADVP-DATE",
    # Adverbial time phrases
    "FöstDagsetning": "ADVP-DATE-ABS",
    "AfstæðDagsetning": "ADVP-DATE-REL",
    "FasturTímapunktur": "ADVP-TIMESTAMP-ABS",
    "AfstæðurTímapunktur": "ADVP-TIMESTAMP-REL",
    "Tíðni": "ADVP-TMP-SET",
    "Tímabil": "ADVP-DUR",
    "FastTímabil": "ADVP-DUR-ABS",
    "AfstættTímabil": "ADVP-DUR-REL",
    "TímabilTími": "ADVP-DUR-TIME",
}

# subject_to: don't push an instance of this if the
# immediate parent is already the subject_to nonterminal

# overrides: we cut off a parent node in favor of this one
# if there are no intermediate nodes

_DEFAULT_ID_MAP = {
    "P": dict(name="Málsgrein"),
    "S-MAIN": dict(name="Setning", overrides="S", subject_to={"S-MAIN"}),
    "S": dict(name="Setning", subject_to={"S", "S-EXPLAIN", "S-REF", "IP"}),
    # Condition
    "S-COND": dict(name="Skilyrði", overrides="S"),
    # Consequence
    "S-CONS": dict(name="Afleiðing", overrides="S"),
    # Reference
    "S-REF": dict(
        name="Tilvísunarsetning", overrides="S", subject_to={"S-REF"}
    ),
    "S-EXPLAIN": dict(name="Skýring"),  # Explanation
    "S-QUOTE": dict(name="Tilvitnun"),  # Quote at end of sentence
    "S-PREFIX": dict(name="Forskeyti"),  # Prefix in front of sentence
    "S-ADV-TEMP": dict(name="Tíðarsetning"),  # Adverbial temporal phrase
    "S-ADV-PURP": dict(name="Tilgangssetning"),  # Adverbial purpose phrase
    "S-ADV-ACK": dict(name="Viðurkenningarsetning"),  # Adverbial acknowledgement phrase
    "S-ADV-CONS": dict(name="Afleiðingarsetning"),  # Adverbial consequence phrase
    "S-ADV-CAUSE": dict(name="Orsakarsetning"),  # Adverbial causal phrase
    "S-ADV-COND": dict(name="Skilyrðissetning"),  # Adverbial conditional phrase
    "S-THT": dict(name="Skýringarsetning"),  # Complement clause
    "S-QUE": dict(name="Spurnarsetning"),  # Question clause
    "VP-SEQ": dict(name="Sagnliður"),
    "VP": dict(name="Sögn", overrides="VP-SEQ", subject_to={"VP"}),
    "VP-PP": dict(name="Sögn", overrides="PP"),
    "NP": dict(name="Nafnliður", subject_to={"NP-SUBJ", "NP-OBJ", "NP-IOBJ", "NP-PRD"}),
    "NP-POSS": dict(name="Eignarfallsliður", overrides="NP"),
    "NP-DAT": dict(name="Þágufallsliður", overrides="NP"),
    "NP-ADDR": dict(name="Heimilisfang", overrides="NP"),
    "NP-TITLE": dict(name="Titill", overrides="NP"),
    "NP-AGE": dict(name="Aldur"),
    "NP-MEASURE": dict(name="Mæling", overrides="NP"),
    "NP-SUBJ": dict(name="Frumlag", subject_to={"NP-SUBJ"}),
    "NP-OBJ": dict(name="Beint andlag"),
    "NP-IOBJ": dict(name="Óbeint andlag"),
    "NP-PRD": dict(name="Sagnfylling"),
    "ADVP": dict(name="Atviksliður", subject_to={"ADVP"}),
    "ADVP-DATE": dict(name="Dagsetning"),
    "ADVP-DATE-ABS": dict(name="Föst dagsetning"),
    "ADVP-DATE-REL": dict(name="Afstæð dagsetning"),
    "ADVP-TIMESTAMP": dict(name="Tímapunktur"),
    "ADVP-TIMESTAMP-ABS": dict(name="Fastur tímapunktur"),
    "ADVP-TIMESTAMP-REL": dict(name="Afstæður tímapunktur"),
    "ADVP-TMP-SET": dict(name="Tíðni"),
    "ADVP-DUR": dict(name="Tímabil"),
    "ADVP-DUR-ABS": dict(name="Fast tímabil", overrides="ADVP-DUR"),
    "ADVP-DUR-REL": dict(name="Afstætt tímabil", overrides="ADVP-DUR"),
    "ADVP-DUR-TIME": dict(name="Tímabil", overrides="ADVP-DUR"),
    "PP": dict(name="Forsetningarliður", overrides="ADVP"),
    "ADJP": dict(name="Lýsingarliður", subject_to={"ADJP"}),
    "IP": dict(name="Beygingarliður"),  # Inflectional phrase
}

_DEFAULT_TERMINAL_MAP = {
    # Empty
}

# The following list was obtained using this SQL query:
# select distinct ordmynd from ord
# where ((stofn='sá') or (stofn='þessi') or (stofn='hinn')) and (ordfl='fn');

_DEFINITE_PRONOUNS = frozenset(
    [
        "þau",
        "þeirri",
        "það",
        "þessi",
        "hinnar",
        "þessu",
        "hinar",
        "þeirra",
        "því",
        "hinn",
        "þennan",
        "hins",
        "þetta",
        "þessara",
        "hin",
        "hinu",
        "sá",
        "þessari",
        "hinni",
        "þeim",
        "þessa",
        "þess",
        "þessir",
        "sú",
        "þessar",
        "þær",
        "þessarar",
        "hinna",
        "hinum",
        "þeir",
        "hinir",
        "þessum",
        "þeirrar",
        "hina",
        "hitt",
        "þá",
        "þann",
    ]
)

# _CUT_LEADING_ADVERBS = frozenset(("því", "út", "fram", "þó"))

_MULTIWORD_TOKENS = frozenset(
    (
        "AMOUNT",
        "MEASUREMENT",
        "TIME",
        "TIMESTAMPABS",
        "TIMESTAMPREL",
        "DATEABS",
        "DATEREL",
    )
)

_MONTH_NAMES = frozenset(
    (
        "janúar",
        "febrúar",
        "mars",
        "apríl",
        "maí",
        "júní",
        "júlí",
        "ágúst",
        "september",
        "október",
        "nóvember",
        "desember",
        "jan.",
        "feb.",
        "mar.",
        "apr.",
        "jún.",
        "júl.",
        "ágú.",
        "ág.",
        "sep.",
        "sept.",
        "okt.",
        "nóv.",
        "des.",
    )
)

_CLOCK = frozenset(("klukkan", "kl."))

_CE_BCE = frozenset(("e.kr.", "e.kr", "f.kr.", "f.kr"))  # Lowercase here is deliberate

_CASES = frozenset(("nf", "þf", "þgf", "ef"))

_GENDERS = frozenset(("kk", "kvk", "hk"))

_DECLINABLE_CATEGORIES = frozenset(("kvk", "kk", "hk", "lo", "to", "fn", "pfn", "gr"))

_CONJUNCTIONS = frozenset(("og", "eða"))


def cut_definite_pronouns(txt):
    """ Removes definite pronouns from the front of txt and returns the result.
        However, if the text consists of only definite pronouns, it is returned
        as-is. """
    lower_txt = txt.lower()
    if lower_txt.startswith("það að"):
        # Make an exception for 'það að X sé Y' - this is OK to return,
        # even as an indefinite form
        return txt
    # 'Stefna Norður-Kóreu hefur ávallt verið sú að Bandaríkin setjist við samningaborðið'
    # -> 'það að Bandaríkin setjist við samningaborðið'
    for prefix in ("sá að ", "sú að "):
        if lower_txt.startswith(prefix):
            return "það að " + txt[len(prefix) :]
    a = lower_txt.split()
    len_a = len(a)
    if not len_a:
        return txt
    len_txt = len(txt)
    i = 0
    n = 0
    while n < len_txt and txt[n].isspace():
        n += 1
    while i < len_a and a[i] in _DEFINITE_PRONOUNS:
        n += len(a[i])
        # Roll past any trailing whitespace (there should be only one space character,
        # but one is never too careful these days)
        while n < len_txt and txt[n].isspace():
            n += 1
        i += 1
    if n >= len_txt:
        # Only pronouns: return the original text
        return txt
    return txt[n:]


class MultiReplacer:

    """ Utility class to do multiple replacements on a string
        in a single pass. The replacements are defined in a dict,
        i.e. { "toReplace" : "byString" }
    """

    def __init__(self, replacements):
        self._replacements = replacements
        substrs = sorted(replacements, key=len, reverse=True)
        # Create a big OR regex that matches any of the substrings to replace
        self._regexp = re.compile("|".join(map(re.escape, substrs)))

    def replace(self, string):
        # For each match, look up the new string in the replacements
        return self._regexp.sub(
            lambda match: self._replacements[match.group(0)], string
        )


class SimpleTree:

    """ A wrapper for a simple parse tree, returned from the
        TreeUtils.simple_parse() function """

    _NEST = {"(": ")", "[": "]", "{": "}"}
    _FINISHERS = frozenset(_NEST.values())
    _NOT_ITEMS = frozenset((">", "*", "+", "?", "[", "(", "{", "]", ")", "}", "$"))

    _pattern_cache = dict()

    def __init__(self, pgs, stats=None, register=None, parent=None):
        # Keep a link to the original parent SimpleTree
        self._parent = parent
        if parent is not None:
            assert stats is None
            assert register is None
        self._stats = stats
        self._register = register
        # Flatten the paragraphs into a sentence array
        sents = []
        if pgs:
            for pg in pgs:
                sents.extend(pg)
        self._sents = sents
        self._len = len(sents)
        self._head = sents[0] if self._len == 1 else {}
        self._children = self._head.get("p")
        self._children_cache = None
        self._tag_cache = None

    def __str__(self):
        """ Return a pretty-printed representation of the contained trees """
        return pformat(self._sents)

    def __repr__(self):
        """ Return a compact representation of this subtree """
        len_self = len(self)
        if len_self == 0:
            if self._head.get("k") == "PUNCTUATION":
                x = self._head.get("x")
                return "<SimpleTree object for punctuation '{0}'>".format(x)
            return "<SimpleTree object for terminal {0}>".format(self.terminal)
        return "<SimpleTree object with tag {0} and length {1}>".format(
            self.tag, len_self
        )

    @property
    def parent(self):
        """ The original topmost parent of this subtree """
        return self if self._parent is None else self._parent

    @property
    def stats(self):
        return self.parent._stats

    @property
    def register(self):
        return self.parent._register

    @property
    def tag(self):
        """ The simplified tag of this subtree, i.e. P, S, NP, VP, ADVP... """
        return self._head.get("i")

    @property
    def ifd_tags(self):
        """ Return a list of the Icelandic Frequency Dictionary
            (IFD) tag(s) for this token """
        if not self.is_terminal:
            return []
        x = self.text
        if " " in x:
            # Multi-word phrase
            lower_x = x.lower()
            if StaticPhrases.has_details(lower_x):
                # This is a static multi-word phrase:
                # return its tags, which are defined in the Phrases.conf file
                return StaticPhrases.tags(lower_x)
            # This may potentially be an entity or person name,
            # an amount, a date, or a measurement unit
            tag = str(IFD_Tagset(self._head))
            result = []
            for part in lower_x.split():
                # Unknown multi-token phrase:
                # deal with it, simplistically
                if part in _CONJUNCTIONS:
                    result.append("c")  # Conjunction
                elif part[0] in "0123456789":
                    if tag[0] == "n":
                        # Use the case, number, and gender info from the noun
                        result.append("tf" + tag[1:4])
                    else:
                        result.append("ta")  # Year or other undeclinable number
                elif tag == "to" or tag == "ta":
                    # Word inside an amount or a date
                    # !!! TODO: Handle currency names and measurement units
                    if part == "árið":
                        result.append("nheo")
                    elif part in _CE_BCE:
                        # Abbreviation 'f.Kr.' or 'e.Kr.': handle as adverbial phrase
                        result.append("aa")
                    elif part in _CLOCK:
                        # Feminine, singular, nominative case
                        result.append("nven")
                    elif part in _MONTH_NAMES:
                        result.append("nkeo")  # Assume accusative case
                    else:
                        result.append("x")  # Unknown
                else:
                    result.append(tag)
            return result
        # Single word, single tag
        return [str(IFD_Tagset(self._head))]

    def match_tag(self, item):
        """ Return True if the given item matches the tag of this subtree
            either fully or partially """
        tag = self.tag
        if tag is None:
            return False
        if self._tag_cache is None:
            tags = self._tag_cache = tag.split("-")
        else:
            tags = self._tag_cache
        if isinstance(item, str):
            item = re.split(r"[_\-]", item)  # Split on both _ and -
        if not isinstance(item, list):
            raise ValueError("Argument to match_tag() must be a string or a list")
        return tags[0 : len(item)] == item

    @property
    def terminal(self):
        """ The terminal matched by this subtree """
        return self._head.get("t")

    @property
    def terminal_with_all_variants(self):
        """ The terminal matched by this subtree, with all applicable variants
            in canonical form (in alphabetical order, except for verb argument cases) """
        terminal = self._head.get("a")
        if terminal is not None:
            # All variants already available in canonical form: we're done
            return terminal
        terminal = self._head.get("t")
        if terminal is None:
            return None
        # Reshape the terminal string to the canonical form where
        # the variants are in alphabetical order, except
        # for verb arguments, which are always first, immediately
        # following the terminal category.
        return augment_terminal(terminal, self._text.lower(), self._head.get("b"))

    @cached_property
    def variants(self):
        """ Returns a list of the variants associated with
            this subtree's terminal, if any """
        t = self.terminal
        return [] if t is None else t.split("_")[1:]

    @cached_property
    def all_variants(self):
        """ Returns a list of all variants associated with
            this subtree's terminal, if any, augmented also by BÍN variants """
        # First, check whether an 'a' field is present
        a = self._head.get("a")
        if a is not None:
            # The 'a' field contains the entire variant set, canonically ordered
            return a.split("_")[1:]
        vlist = self.variants
        bin_variants = BIN_Token.bin_variants(self._head.get("b"))
        return vlist + list(bin_variants - set(vlist))  # Add any missing variants

    @cached_property
    def _vset(self):
        """ Return a set of the variants associated with this subtree's terminal,
            if any. Note that this set is undordered, so it is not intended for
            retrieving the cases of verb subjects. """
        return set(self.all_variants)

    @cached_property
    def tcat(self):
        """ The word category associated with this subtree's terminal, if any """
        t = self.terminal
        return "" if t is None else t.split("_")[0]

    @cached_property
    def sentences(self):
        """ A list of the contained sentences """
        return [SimpleTree([[sent]], parent=self.parent) for sent in self._sents]

    @property
    def has_children(self):
        """ Does this subtree have (proper) children? """
        return bool(self._children)

    @property
    def is_terminal(self):
        """ Is this a terminal node? """
        return self._len == 1 and not self._children

    @property
    def _gen_children(self):
        """ Generator for children of this tree """
        if self._len > 1:
            # More than one sentence: yield'em
            yield from self.sentences
        elif self._children:
            # Proper children: yield'em
            for child in self._children:
                yield SimpleTree([[child]], parent=self.parent)

    @property
    def children(self):
        """ Cached generator for children of this tree """
        if self._children_cache is None:
            self._children_cache = tuple(self._gen_children)
        yield from self._children_cache

    @property
    def descendants(self):
        """ Generator for all descendants of this tree, in-order """
        for child in self.children:
            yield child
            yield from child.descendants

    @property
    def deep_children(self):
        """ Generator of generators of children of this tree and its subtrees """
        yield self.children
        for ch in self.children:
            yield from ch.deep_children

    def _view(self, level):
        """ Return a string containing an indented map of this subtree """
        if level == 0:
            indent = ""
        else:
            indent = "  " * (level - 1) + "+-"
        if self._len > 1 or self._children:
            # Children present: Array or nonterminal
            return (
                indent
                + (self.tag or "[]")
                + "".join("\n" + child._view(level + 1) for child in self.children)
            )
        # No children
        if self._head.get("k") == "PUNCTUATION":
            # Punctuation
            return "{0}'{1}'".format(indent, self.text)
        # Terminal
        return "{0}{1}: '{2}'".format(indent, self.terminal, self.text)

    @property
    def view(self):
        """ Return a nicely formatted string showing this subtree """
        return self._view(0)

    # Convert literal terminals that did not have word category specifiers
    # in the grammar (now corrected)
    _replacer = MultiReplacer(
        {
            '"hans"': "pfn_kk_et_ef",
            '"hennar"': "pfn_kvk_et_ef",
            '"einnig"': "ao",
            '"hinn"': "gr_kk_et_þf",
            "'það'_nf_et": "pfn_hk_et_nf",
            "'hafa'_nh": "so_nh",
        }
    )

    @staticmethod
    def _make_terminal_with_case(cat, variants, terminal, default_case="nf"):
        """ Return a terminal identifier with the given category and
            variants, plus the case indicated in the terminal, if any """
        tcase = set(terminal.split("_")[1:]) & _CASES
        if len(tcase) == 0:
            # If no case given, assume nominative rather than nothing
            tcase = {default_case}
        return "_".join([cat] + sorted(list(variants | tcase)))

    @staticmethod
    def _multiword_token(txt, tokentype, terminal):
        """ Return a sequence of terminals corresponding to a multi-word token
            whose source text is in txt """
        # Multi-word tokens can be dates and timestamps, amounts and measurements.
        # We need to jump through several hoops to reconstruct a sequence of
        # terminals that correspond to the source token atoms.
        # A trick is employed here: the source tokens are processed in reverse
        # order, so that we can note the case and gender of a finishing noun
        # (typically a currency name such as 'króna') and use it to qualify
        # a subsequent (but textually preceding) adjective (such as 'danskra').
        result = []
        case = None
        gender = None
        terminal_case = None
        # Token atoms (components of a multiword token)
        a = list(reversed(txt.split()))
        for tok in a:
            if re.match(r"^\d{1,2}:\d\d(:\d\d)?$", tok):
                # 12:34 or 11:34:50
                result.append("tími")
                continue
            if (
                re.match(r"^\d{1,2}\.\d{1,2}(\.\d{2,4})?$", tok)
                or re.match(r"^\d{1,2}/\d{1,2}(/\d{2,4})?$", tok)
            ):
                # 17.6, 30.12.1965, 17/6 or 30/12/65
                result.append("dags")
                continue
            if re.match(r"^\d+\.$", tok):
                # 12.
                result.append("raðnr")
                continue
            if re.match(r"^\d\d\d\d$", tok) and 1776 <= int(tok) <= 2100:
                # 1981
                result.append("ártal")
                continue
            if re.match(r"^[\+\-]?\d+(\.\d\d\d)*(,\d+)?$", tok):
                # 12, 1.234 or 1.234,56
                result.append("tala")
                continue
            tok_lower = tok.lower()
            if tok_lower == "árið":
                result.append("no_et_gr_hk_þf")
                continue
            if tok_lower in _MONTH_NAMES:
                # For month names, return a noun terminal with singular,
                # masculine variants plus the case from the original terminal, if any
                result.append(
                    SimpleTree._make_terminal_with_case(
                        "no", {"et", "kk"}, terminal, "þf"
                    )
                )
                continue
            if tok_lower in _CLOCK:
                # klukkan, kl.
                result.append("no_et_gr_kvk_nf")
                continue
            if tok_lower in _CE_BCE:
                # e.Kr./e.Kr, f.Kr./f.Kr
                result.append("ao")
                continue
            if tokentype == "AMOUNT":
                if tok_lower.endswith("."):
                    if tok_lower in MULTIPLIERS:
                        # Abbreviations such as 'þús.', 'mrð.': treat as
                        # undeclinable 'töl' tokens
                        result.append("töl")
                        continue
                # For spelled-out amounts, we look up contained words in BÍN
                # These may be number prefixes ('sautján'), adjectives ('norskar'),
                # and nouns ('krónur')
                with BIN_Db.get_db() as db:
                    _, m = db.lookup_word(tok_lower, at_sentence_start=False)
                    # We only consider to, töl, lo, currency names or
                    # declinable multipliers ('þúsund', 'milljónir', 'milljarðar')
                    m = list(
                        filter(
                            lambda mm: (
                                (
                                    mm.stofn in CURRENCIES
                                    or mm.stofn in DECLINABLE_MULTIPLIERS
                                )
                                if mm.ordfl in _GENDERS
                                else mm.ordfl in {"to", "töl", "lo"}
                            ),
                            m
                        )
                    )
                    if not m:
                        if tok in CURRENCY_GENDERS:
                            # This is a three-letter currency abbreviation:
                            # put the right gender on it
                            result.append(
                                SimpleTree._make_terminal_with_case(
                                    "no", {"ft", CURRENCY_GENDERS[tok]}, terminal, "þf"
                                )
                            )
                            continue
                    else:
                        # Make sure plural forms are chosen rather than singular ones
                        m.sort(key=lambda mm: 0 if "FT" in mm.beyging else 1)
                        # Make sure that the case of the terminal is preferred
                        # over other cases
                        if terminal_case is None:
                            # Only calculate the terminal case once, on-demand
                            terminal_case = next(
                                iter(set(terminal.split("_")[1:]) & _CASES), ""
                            ).upper()
                        if terminal_case:
                            # The terminal actually specifies a case: sort on it
                            m.sort(
                                key=lambda mm: 0 if terminal_case in mm.beyging else 1
                            )
                        # If we can get away with just a 'töl', do it
                        mm = next((mm for mm in m if mm.ordfl == "töl"), m[0])
                        if mm.ordfl == "lo" and case is not None and gender is not None:
                            # Looks like this is an adjective: filter down to those that
                            # match the previously seen noun
                            m = [
                                mm
                                for mm in m
                                if case in mm.beyging and gender in mm.beyging
                            ]
                            mm = next(iter(m), mm)
                        variants = BIN_Token.bin_variants(mm.beyging)
                        if mm.ordfl in _GENDERS:
                            # The word is a noun
                            ordfl = mm.ordfl
                            result.append(
                                "no_" + "_".join(sorted(list(variants | {ordfl})))
                            )
                            # Note the gender and case of the noun, so we can restrict our
                            # set of adjective forms, if an adjective is attached
                            gender = ordfl.upper()
                            case = next(iter(variants & _CASES), "nf").upper()
                            continue
                        # Something besides a noun: return the category and the variants
                        result.append(
                            mm.ordfl + "".join("_" + v for v in sorted(list(variants)))
                        )
                        continue

            # No special case for this atom: return the terminal
            result.append(terminal)
        # Fix the last terminal if it denotes a currency abbreviation
        # that should be in the possessive case
        if tokentype == "AMOUNT":
            # Note that the terminal list is reversed, so a[0] is the last terminal
            if a[0] in CURRENCY_GENDERS:
                # ISO currency abbreviation
                if result[1].startswith("no_"):
                    # Following a noun (we're assuming that it's a multiplier
                    # such as 'þúsund', 'milljónir', 'milljarðar'):
                    # assemble a terminal identifier with plural, possessive
                    # and the correct gender
                    result[0] = "no_" + "_".join(
                        sorted(["ft", "ef", CURRENCY_GENDERS[a[0]]])
                    )
        return " ".join(reversed(result))

    def _flat(self, func):
        """ Return a string containing an a flat representation of this subtree """
        if self._len > 1 or self._children:
            # Children present: Array or nonterminal
            tag = self.tag or "X"  # Unknown tag (should not occur)
            return (
                tag
                + " "
                + " ".join(child._flat(func) for child in self.children)
                + " /"
                + tag
            )
        # No children
        tokentype = self._head.get("k")
        if tokentype == "PUNCTUATION":
            # Punctuation
            return "p"
        # Terminal
        terminal = func(self)  # Get the terminal representation
        numwords = self._text.count(" ")
        if not numwords:
            return self._replacer.replace(terminal)
        # Multi-word phrase
        if self.tcat == "fs":
            # fs phrase:
            # Return a sequence of ao prefixes before the terminal itself
            return " ".join(["ao"] * numwords + [terminal])
        if tokentype in _MULTIWORD_TOKENS:
            # Use a special handler for these multiword tokens
            return self._multiword_token(self._text, tokentype, terminal)
        # Fallback: Repeat the terminal name for each component word
        words = self._text.split()
        return " ".join("st" if word in _CONJUNCTIONS else terminal for word in words)

    @property
    def flat(self):
        """ Return a flat representation of this subtree """
        return self._flat(lambda tree: tree.terminal)

    @property
    def flat_with_all_variants(self):
        """ Return a flat representation of this subtree, where terminals
            include all applicable variants """
        return self._flat(lambda tree: tree.terminal_with_all_variants)

    def __getattr__(self, name):
        """ Return the first child of this subtree having the given tag """
        name = name.replace("_", "-")  # Convert NP_POSS to NP-POSS
        index = 1
        # Check for NP1, NP2 etc., i.e. a tag identifier followed by a number
        s = re.match(r"^(\D+)(\d+)$", name)
        if s:
            name = s.group(1)
            index = int(s.group(2))  # Should never fail
            if index < 1:
                raise AttributeError("Subtree indices start at 1")
        multi = index
        # NP matches NP-POSS, NP-OBJ, etc.
        # NP-OBJ matches NP-OBJ-PRIMARY, NP-OBJ-SECONDARY, etc.
        names = name.split("-")
        for ch in self.children:
            if ch.match_tag(names):
                # Match: check whether it's the requested index
                index -= 1
                if index == 0:
                    # Yes, it is
                    return ch
        # No match
        if multi > index:
            raise AttributeError(
                "Subtree has {0} {1} but index {2} was requested"
                .format(multi - index, name, multi)
            )
        raise AttributeError("Subtree has no child named '{0}'".format(name))

    def __getitem__(self, index):
        """ Return the appropriate child subtree """
        if isinstance(index, str):
            # Handle tree['NP']
            try:
                return self.__getattr__(index)
            except AttributeError:
                raise KeyError("Subtree has no {0} child".format(index))
        # Handle tree[1]
        if self._children_cache is not None:
            return self._children_cache[index]
        if self._len > 1:
            return SimpleTree([[self._sents[index]]], parent=self.parent)
        if self._children:
            return SimpleTree([[self._children[index]]], parent=self.parent)
        raise IndexError("Subtree has no children")

    def __len__(self):
        """ Return the length of this subtree, i.e. the last usable child index + 1 """
        if self._len > 1:
            return self._len
        return len(self._children) if self._children else 0

    @property
    def _text(self):
        """ Return the original text within this node only, if any """
        return self._head.get("x", "")

    @cached_property
    def _lemma(self):
        """ Return the lemma of this node only, if any """
        lemma = self._head.get("s", self._text)
        if isinstance(lemma, tuple):
            # We have a lazy-evaluation function tuple:
            # call it to obtain the lemma
            f, args = lemma
            lemma = f(*args)
        return lemma

    def _nominative_form(self, form):
        """ Return a nominative form of the text within this node only, if any.
            The form can be 'nominative' for the nominative case only,
            'indefinite' for the indefinite nominative form,
            or 'canonical' for the singular, indefinite, nominative. """
        if self._cat not in _DECLINABLE_CATEGORIES:
            # This is not a potentially declined terminal node: return the original text
            return self._text
        txt = self._text
        prefix = ""
        with BIN_Db.get_db() as db:

            if self.tcat == "person":
                # Special case for person names as they may have embedded spaces
                result = []
                gender = self._cat
                for name in txt.split():
                    meanings = db.lookup_nominative(name)
                    try:
                        # Try to find an 'ism', 'föð' or 'móð' nominative form
                        # of the correct gender
                        result.append(
                            next(
                                filter(
                                    lambda m: (
                                        m.ordfl == gender
                                        and "FT" not in m.beyging
                                        and m.fl in {"ism", "föð", "móð"}
                                    ),
                                    meanings
                                )
                            ).ordmynd
                        )
                    except StopIteration:
                        # No 'ism', 'föð' or 'móð' nominative form
                        try:
                            # Try the first available nominative form,
                            # regardless of what it is
                            result.append(next(iter(meanings)).ordmynd)
                        except StopIteration:
                            # No such thing: use the part as-is
                            result.append(name)
                return " ".join(result)

            # Find the composite word prefix, if any
            lemma = self._lemma
            if "-" in lemma and "abbrev" not in self._vset:
                # This is a composite word ("bakgrunns-upplýsingar")
                a = lemma.rsplit("-", maxsplit=1)
                prefix = a[0].replace("-", "")
                lemma = a[1]
                # Cut the prefix off the front of the word form
                txt = txt[len(prefix) :]
                if txt and txt[0] == "-":
                    # The original word may have been hyphenated
                    # ('Norður-Kóreu'), in which case we want
                    # to lookup 'Kóreu', not '-Kóreu'
                    txt = txt[1:]
                    prefix += "-"

            meanings = db.lookup_nominative(txt)
            if not meanings and not txt.islower():
                # We don't find this form in BÍN:
                # if upper case, try a lower case version of it
                meanings = db.lookup_nominative(txt.lower())

            # The following functions filter the nominative list down
            # to those desired forms that match our lemma and category

            def filter_func_no(m):
                """ Filter function for nouns """
                if m.stofn != lemma or m.ordfl != self._cat:
                    return False
                if form == "canonical":
                    # Only return singular forms
                    if "FT" in m.beyging:
                        return False
                else:
                    # Match the original word in terms of number (singular/plural)
                    number = next(iter(self._vset & {"et", "ft"}), "et")
                    if number.upper() not in m.beyging:
                        return False
                if form == "nominative":
                    # Match the original word in terms of definite/indefinite
                    if ("gr" in self._vset) != ("gr" in m.beyging):
                        return False
                elif "gr" in m.beyging:
                    # Only return indefinite forms
                    return False
                return True

            def filter_func_without_gender(m):
                """ Filter function for personal pronouns """
                if m.stofn != lemma or m.ordfl != self._cat:
                    return False
                if form == "canonical":
                    # Only return singular forms
                    if "FT" in m.beyging:
                        return False
                else:
                    # Match the original word in terms of number (singular/plural)
                    number = next(iter(self._vset & {"et", "ft"}), "et")
                    if number.upper() not in m.beyging:
                        return False
                return True

            def filter_func_with_gender(m):
                """ Filter function for nonpersonal pronouns
                    and declinable number words """
                if m.stofn != lemma or m.ordfl != self._cat:
                    return False
                # Match the original word in terms of gender
                gender = next(iter(self._vset & _GENDERS), "kk")
                if gender.upper() not in m.beyging:
                    return False
                if form == "canonical":
                    # Only return singular forms
                    if "FT" in m.beyging:
                        return False
                else:
                    # Match the original word in terms of number (singular/plural)
                    number = next(iter(self._vset & {"et", "ft"}), "et")
                    if number.upper() not in m.beyging:
                        return False
                return True

            def filter_func_lo(m):
                """ Filter function for adjectives """
                if m.stofn != lemma or m.ordfl != "lo":
                    return False
                # Match the original word in terms of gender
                gender = next(iter(self._vset & _GENDERS), "kk")
                if gender.upper() not in m.beyging:
                    return False
                if form == "canonical":
                    # Only return singular forms
                    if "FT" in m.beyging:
                        return False
                else:
                    # Match the original word in terms of number (singular/plural)
                    number = next(iter(self._vset & {"et", "ft"}), "et")
                    if number.upper() not in m.beyging:
                        return False
                if form == "nominative":
                    if "est" in self._vset:
                        if not ("EVB" in m.beyging or "ESB" in m.beyging):
                            return False
                    elif "evb" in self._vset:
                        if "EVB" not in m.beyging:
                            return False
                    elif "esb" in self._vset:
                        if "ESB" not in m.beyging:
                            return False
                    elif "mst" in self._vset:
                        if "MST" not in m.beyging:
                            return False
                    elif "vb" in self._vset or "fvb" in self._vset:
                        # We are satisfied with any adjective that has
                        # 'FVB', or no degree indicator
                        if any(
                            degree in m.beyging
                            for degree in ("FSB", "MST", "EVB", "ESB")
                        ):
                            return False
                    elif "sb" in self._vset or "fsb" in self._vset:
                        # We are satisfied with any adjective that has
                        # 'FSB', or no degree indicator
                        if any(
                            degree in m.beyging
                            for degree in ("FVB", "MST", "EVB", "ESB")
                        ):
                            return False
                else:
                    # 'indefinite' or 'canonical':
                    # Only return strong declinations since we only want
                    # indefinite forms
                    if "mst" in self._vset:
                        # For comparative degree, no change is required
                        if "MST" not in m.beyging:
                            return False
                    elif "evb" in self._vset or "esb" in self._vset:
                        # Superlative degree
                        if "ESB" not in m.beyging:
                            return False
                    else:
                        # Normal degree
                        # Note that some adjectives (ordfl='lo') have
                        # no degree indication in BÍN. It's therefore not
                        # correct to simply check for the presence of FSB here.
                        if any(
                            degree in m.beyging
                            for degree in ("FVB", "MST", "EVB", "ESB")
                        ):
                            return False
                return True

            # Select and apply the appropriate filter function
            FILTERS = {
                "lo": filter_func_lo,
                "to": filter_func_with_gender,
                "fn": filter_func_with_gender,
                "gr": filter_func_with_gender,
                "pfn": filter_func_without_gender,
            }
            meanings = filter(FILTERS.get(self._cat, filter_func_no), meanings)
            try:
                # Choose the first nominative form that got past the filter
                w = next(meanings).ordmynd
                # Try to match the capitalization of the original word
                if prefix and prefix[-1] != "-":
                    txt = w.lower()
                elif txt[0].isupper():
                    if txt.isupper():
                        txt = w.upper()
                    else:
                        txt = w.capitalize()
                else:
                    txt = w.lower()
            except StopIteration:
                if self._cat == "to" and "ft" in self._vset and form == "canonical":
                    # Declinable number, for which there is no singular form available,
                    # such as "tveir": return an empty string
                    txt = prefix = ""
        return prefix + txt

    @cached_property
    def nominative(self):
        """ Return the nominative form of this node only, if any """
        return self._nominative_form("nominative")

    @cached_property
    def indefinite(self):
        """ Return the indefinite nominative form of this node only, if any """
        return self._nominative_form("indefinite")

    @cached_property
    def canonical(self):
        """ Return the singular indefinite nominative form of this node only, if any """
        return self._nominative_form("canonical")

    @property
    def _cat(self):
        """ Return the word category of this node only, if any """
        # This is the category that is picked up from BÍN, not the terminal
        # category. The terminal category is available in the .tcat property)
        return self._head.get("c")

    @cached_property
    def text(self):
        """ Return the original text contained within this subtree """
        if self.is_terminal:
            # Terminal node: return own text
            return self._text
        # Concatenate the text from the children
        return " ".join([ch.text for ch in self.children if ch.text])

    def _np_form(self, prop_func):
        """ Return a nominative form of the noun phrase (or noun/adjective terminal)
            contained within this subtree. Prop is a property accessor that returns
            either x.nominative, x.indefinite or x.canonical. """
        if self.is_terminal:
            # Terminal node: return its nominative form
            return prop_func(self)
        if self.match_tag("NP"):
            # Noun phrase:
            # Concatenate the nominative forms of the child terminals,
            # and the literal text of nested nonterminals (such as NP-POSS and S-THT)
            result = []
            children = list(self.children)
            # If the noun phrase has an adjective, we keep any leading adverbs
            # ('stórkostlega fallegu blómin', 'ekki vingjarnlegu mennirnir',
            # 'strax fáanlegu vörurnar').
            # Otherwise, they probably belong to a previous verb and we
            # cut them away.
            has_adjective = any(ch.is_terminal and ch.tcat == "lo" for ch in children)
            if not has_adjective:
                # Cut away certain leading adverbs (einkunnarorð, "eo")
                for i, ch in enumerate(children):
                    if ch.is_terminal and ch.tcat == "eo":
                        continue
                    else:
                        if i > 0:
                            children = children[i:]
                        break
            if len(children) == 1 and children[0].tag == "S-THT":
                # If the noun phrase consists only of a S-THT nonterminal
                # ('skýringarsetning'), add 'það' to the front so the
                # result is something like 'það að fjöldi dæmdra glæpamanna hafi aukist'
                np = prop_func(children[0])
                if np:
                    np = "það " + np
                else:
                    np = ""
            else:
                for ch in children:
                    np = prop_func(ch)
                    if np:
                        result.append(np)
                np = " ".join(result)
            # Cut off trailing punctuation
            while len(np) >= 2 and np[-1] in {",", ":", ";", "!", "-", "."}:
                np = np[0:-2]
            return np
        # This is not a noun phrase: return its text as-is
        return self.text

    @cached_property
    def nominative_np(self):
        """ Return the nominative form of the noun phrase (or noun/adjective terminal)
            contained within this subtree """
        return self._np_form(
            lambda node: node.nominative if node.is_terminal else node.text
        )

    @cached_property
    def indefinite_np(self):
        """ Return the indefinite nominative form of the noun phrase (or noun/adjective terminal)
            contained within this subtree """

        def prop_func(node):
            if node.is_terminal:
                if node._cat == "gr":
                    # Cut away the definite article, if present
                    # ('hinir ungu alþingismenn' -> 'ungir alþingismenn')
                    return ""
                return node.indefinite
            return node.text

        return cut_definite_pronouns(self._np_form(prop_func))

    @cached_property
    def canonical_np(self):
        """ Return the singular indefinite nominative form of the noun phrase
            (or noun/adjective terminal) contained within this subtree """

        def prop_func(node):
            """ For canonical noun phrases, cut off S-REF and S-THT subtrees since they probably
                don't make sense any more, with the noun phrase having been converted to singular and all.
                The same applies to NP-POSS. """
            if node.is_terminal:
                if node.tcat == "töl" or (node.tcat == "tala" and "ft" in node._vset):
                    # If we are asking for the canonical (singular) form, cut away undeclinable numbers
                    # so that 'sautján góðglaða alþingismenn' -> 'góðglaður alþingismaður',
                    # not 'sautján góðglaður alþingismaður'; and also cut away declinable plural numbers
                    return ""
                if node._cat == "gr":
                    # Cut away the definite article, if present
                    # ('hinir ungu alþingismenn' -> 'ungur alþingismaður')
                    return ""
                return node.canonical
            # Cut off connected explanatory sentences, possessive phrases, and prepositional phrases
            if any(node.match_tag(tag) for tag in ("S", "NP-POSS", "PP", "ADVP")):
                return None
            return node.text

        return cut_definite_pronouns(self._np_form(prop_func))

    @property
    def own_text(self):
        return self._text

    def _list(self, filter_func):
        """ Return a list of word lemmas that meet the filter criteria within this subtree """
        if self._len > 1 or self._children:
            # Concatenate the text from the children
            t = []
            for ch in self.children:
                t.extend(ch._list(filter_func))
            return t
        # Terminal node: return own lemma if it matches the given category
        if filter_func(self):
            lemma = self._lemma
            return [lemma] if lemma else []
        return []

    @property
    def nouns(self):
        """ Returns the lemmas of all nouns in the subtree """
        return self._list(lambda t: t._cat in _GENDERS)

    @property
    def verbs(self):
        """ Returns the lemmas of all verbs in the subtree """
        return self._list(lambda t: t._cat == "so")

    @property
    def persons(self):
        """ Returns all person names occurring in the subtree """
        return self._list(lambda t: t.tcat == "person")

    @property
    def entities(self):
        """ Returns all entity names occurring in the subtree """
        return self._list(lambda t: t.tcat == "entity")

    @property
    def proper_names(self):
        """ Returns all proper names occurring in the subtree """
        return self._list(lambda t: t.tcat == "sérnafn")

    @property
    def lemmas(self):
        """ Returns the lemmas of all words in the subtree """
        return self._list(lambda t: True)

    @property
    def lemma(self):
        """ Return the lemmas of this subtree as a string """
        if self.is_terminal:
            # Shortcut for terminal node
            return self._lemma
        return " ".join(self.lemmas)

    @property
    def own_lemma(self):
        return self._lemma if self.is_terminal else ""

    def _all_matches(self, items):
        """ Return all subtree roots, including self, that match the given items,
            compiled from a pattern """
        for subtree in chain([self], self.descendants):
            if subtree._match(items):
                yield subtree

    def all_matches(self, pattern):
        """ Return all subtree roots, including self, that match the given pattern """
        items = self._compile(pattern)
        return self._all_matches(items)  # Returns a generator

    def first_match(self, pattern):
        """ Return the first subtree root, including self, that matches the given
            pattern. If no subtree matches, return None. """
        try:
            return next(self.all_matches(pattern))
        except StopIteration:
            return None

    def top_matches(self, pattern):
        """ Return all subtree roots, including self, that match the given pattern,
            but not recursively, i.e. we don't include matches within matches """
        items = self._compile(pattern)
        return self._top_matches(items)  # Returns a generator

    def _top_matches(self, items):
        """ If this subtree matches the items, return it. Otherwise, recurse into
            its children in a left-first traversal. """
        if self._match(items):
            yield self
        else:
            for child in self.children:
                yield from child._top_matches(items)

    class _NestedList(list):
        def __init__(self, kind, content):
            self._kind = kind
            super().__init__()
            if kind == "(":
                # Validate a ( x | y | z ...) construct
                if any(content[i] != "|" for i in range(1, len(content), 2)):
                    raise ValueError("Missing '|' in pattern")
            super().extend(content)

        @property
        def kind(self):
            return self._kind

        def __repr__(self):
            return "<Nested('{0}') ".format(self._kind) + super().__repr__() + ">"

    @classmethod
    def _compile(cls, pattern):
        def nest(items):
            """ Convert any embedded subpatterns, delimited by NEST entries,
                into nested lists """
            len_items = len(items)
            i = 0
            while i < len_items:
                item1 = items[i]
                if item1 in cls._NEST:
                    finisher = cls._NEST[item1]
                    j = i + 1
                    stack = 0
                    while j < len_items:
                        item2 = items[j]
                        if item2 == finisher:
                            if stack > 0:
                                stack -= 1
                            else:
                                nested = cls._NestedList(item1, nest(items[i + 1 : j]))
                                for n in nested:
                                    if isinstance(n, str) and n in cls._FINISHERS:
                                        raise ValueError(
                                            "Mismatched '{0}' in pattern"
                                            .format(n)
                                        )
                                items = items[0:i] + [nested] + items[j + 1 :]
                                len_items = len(items)
                                break
                        elif item2 == item1:
                            stack += 1
                        j += 1
                    else:
                        # Did not find the starting symbol again
                        raise ValueError("Mismatched '{0}' in pattern".format(item1))
                i += 1
            return items

        # Check whether we've parsed this pattern before, and if so,
        # re-use the result
        if pattern in cls._pattern_cache:
            return cls._pattern_cache[pattern]

        # Not parsed before: do it and cache the result

        def gen1():
            """ First generator: yield non-null strings from a regex split of the pattern """
            for item in re.split(r"\s+|([\.\|\(\)\{\}\[\]\*\+\?\>\$])", pattern):
                if item:
                    yield item

        def gen2():
            gen = gen1()
            while True:
                item = next(gen)
                if item.startswith("'") or item.startswith('"'):
                    # String literal item: merge with subsequent items
                    # until we encounter a matching end quote
                    q = item[0]
                    s = item
                    while not item.endswith(q):
                        item = next(gen)
                        s += " " + item
                    yield s
                else:
                    yield item

        items = nest(list(gen2()))
        # !!! TODO: Limit the cache size, for example by LRU or a periodic purge
        cls._pattern_cache[pattern] = items
        return items

    def match(self, pattern):
        """ Return True if this subtree matches the given pattern """
        return self._match(self._compile(pattern))

    def _match(self, items):
        """ Returns True if this subtree matchs the given items,
            compiled from a string pattern """

        def single_match(item, tree):
            """ Does the subtree match with item, in and of itself? """
            if isinstance(item, self._NestedList):
                if item.kind == "(":
                    # A list of choices separated by '|': OR
                    for i in range(0, len(item), 2):
                        if single_match(item[i], tree):
                            return True
                return False
            assert isinstance(item, str)
            assert item
            if item in self._NOT_ITEMS:
                raise ValueError("Spurious '{0}' in pattern".format(item))
            if item == ".":
                # Wildcard: always matches
                return True
            if item.startswith('"'):
                # Literal string
                if not tree.is_terminal:
                    return False
                if not item.endswith('"'):
                    raise ValueError("Missing double quote at end of literal")
                # Case-neutral compare
                return item[1:-1].lower() == tree.own_text.lower()
            if item.startswith("'"):
                # Word lemma(s)
                if not tree.is_terminal:
                    return False
                if not item.endswith("'"):
                    raise ValueError("Missing single quote at end of word lemma")
                # !!! Note: the following will also match nonterminal
                # !!! nodes that contain exactly the given lemma
                return item[1:-1] == tree.own_lemma
            if tree.terminal:
                if tree.terminal == item:
                    return True
                ilist = item.split("_")
                # First parts must match (i.e., no_xxx != so_xxx)
                if ilist[0] != tree.tcat:
                    return False
                # Remaining variants must be a subset of those in the terminal
                return set(ilist[1:]) <= set(tree.variants)
            # Check nonterminal tag
            # NP matches NP as well as NP-POSS, etc.,
            # while NP-POSS only matches NP-POSS
            return tree.match_tag(item)

        def unpack(items, ix):
            """ Unpack an argument for the '>' or '>>' containment operators.
                These are usually lists or sets but may be single items, in
                which case they are interpreted as a set having
                that single item only. """
            item = items[ix]
            if isinstance(item, self._NestedList) and item.kind in {"[", "{"}:
                return item, item.kind
            return items[ix : ix + 1], "{"  # Single item: assume set

        # noinspection PyUnreachableCode
        def contained(tree, items, pc, deep):
            """ Returns True if the tree has children that match the subsequence
                in items[pc], either directly (deep = False) or at any deeper
                level (deep = True) """

            subseq, kind = unpack(items, pc)
            # noinspection PyUnreachableCode
            if not deep:
                if kind == "[":
                    return run_sequence(tree.children, subseq)
                if kind == "{":
                    return run_set(tree.children, subseq)
                assert False
                return False

            # Deep containment: iterate through deep_children, which is
            # a generator of children generators(!)
            if kind == "[":
                return any(
                    run_sequence(gen_children, subseq)
                    for gen_children in tree.deep_children
                )
            if kind == "{":
                return any(
                    run_set(gen_children, subseq)
                    for gen_children in tree.deep_children
                )
            assert False
            return False

        def run_sequence(gen, items):
            """ Match the child nodes of gen with the items, in sequence """
            len_items = len(items)
            # Program counter (index into items)
            pc = 0
            try:
                tree = next(gen)
                while pc < len_items:
                    item = items[pc]
                    pc += 1
                    repeat = None
                    stopper = None
                    if pc < len_items:
                        if items[pc] in {"*", "+", "?", ">"}:
                            # Repeat specifier
                            repeat = items[pc]
                            pc += 1
                            if item == "." and repeat in {"*", "+", "?"}:
                                # Limit wildcard repeats if the following item
                                # is concrete, i.e. non-wildcard and non-end
                                if pc < len_items:
                                    if isinstance(items[pc], self._NestedList):
                                        if items[pc].kind == "(":
                                            stopper = items[pc]
                                    elif items[pc] not in {".", "$"}:
                                        stopper = items[pc]
                    if item == "$":
                        # Only matches at the end of the list
                        result = pc >= len_items
                    else:
                        result = single_match(item, tree)
                    if repeat is None:
                        # Plan item-for-item match
                        if not result:
                            return False
                        tree = next(gen)
                    elif repeat == "+":
                        if not result:
                            return False
                        while result:
                            tree = next(gen)
                            if stopper is not None:
                                result = not single_match(stopper, tree)
                            else:
                                result = single_match(item, tree)
                    elif repeat == "*":
                        if stopper is not None:
                            result = not single_match(stopper, tree)
                        while result:
                            tree = next(gen)
                            if stopper is not None:
                                result = not single_match(stopper, tree)
                            else:
                                result = single_match(item, tree)
                    elif repeat == "?":
                        if stopper is not None:
                            result = not single_match(stopper, tree)
                        if result:
                            tree = next(gen)
                    elif repeat == ">":
                        if not result:
                            # No containment if the head item does not match
                            return False
                        op = ">"
                        if pc < len_items and items[pc] == ">":
                            # '>>' operator: arbitrary depth containment
                            pc += 1
                            op = ">>"
                        if pc >= len_items:
                            raise ValueError(
                                "Missing argument to '{0}' operator"
                                .format(op)
                            )
                        result = contained(tree, items, pc, op == ">>")
                        if not result:
                            return False
                        pc += 1
                        tree = next(gen)
            except StopIteration:
                # Skip any nullable items
                while pc + 1 < len_items and items[pc + 1] in {"*", "?"}:
                    item = items[pc]
                    # Do error checking while we're at it
                    if isinstance(item, str) and item in self._NOT_ITEMS:
                        raise ValueError("Spurious '{0}' in pattern".format(item))
                    pc += 2
                if pc < len_items:
                    if items[pc] == "$":
                        # Iteration done: move past the end-of-list marker, if any
                        pc += 1
                else:
                    if pc > 0 and items[pc - 1] == "$":
                        # Gone too far: back up
                        pc -= 1
            else:
                if len_items and items[-1] == "$":
                    # Found end marker but the child iterator is not
                    # complete: return False
                    return False
            return pc >= len_items

        def run_set(gen, items):
            """ Run through the subtrees (children) yielded by gen,
                matching them set-wise (unordered) with the items.
                If all items are eventually matched, return True,
                otherwise False. """
            len_items = len(items)
            # Keep a set of items that have not yet been matched
            # by one or more tree nodes
            unmatched = set(range(len_items))
            for tree in gen:
                pc = 0
                while pc < len_items:
                    item_pc = pc
                    item = items[pc]
                    pc += 1
                    result = single_match(item, tree)
                    if pc < len_items and items[pc] == ">":
                        # Containment: Not a match unless the children match as well
                        pc += 1
                        op = ">"
                        if pc < len_items and items[pc] == ">":
                            # Deep match
                            op = ">>"
                            pc += 1
                        if pc >= len_items:
                            raise ValueError(
                                "Missing argument to '{0}' operator"
                                .format(op)
                            )
                        if result:
                            # Further constrained by containment
                            result = contained(tree, items, pc, op == ">>")
                        pc += 1
                        # Always cut away the 'dummy' extra items corresponding
                        # to the '>' (or '>>') and its argument
                        unmatched -= {pc - 1, pc - 2}
                        if op == ">>":
                            unmatched -= {pc - 3}
                    if result:
                        # We have a match
                        unmatched -= {item_pc}
                    if not unmatched:
                        # We have a complete match already: Short-circuit
                        return True
            # Return True if all items got matched at some point
            # by a tree node, otherwise False
            return False

        return run_set(iter([self]), items)


class SimpleTreeBuilder:

    """ A class for building a simplified tree from a full
        parse tree. The simplification is done according to the
        maps provided in the constructor. """

    def __init__(self, nt_map=None, id_map=None, terminal_map=None):
        self._nt_map = nt_map or _DEFAULT_NT_MAP
        self._id_map = id_map or _DEFAULT_ID_MAP
        self._terminal_map = terminal_map or _DEFAULT_TERMINAL_MAP
        self._result = []
        self._stack = [self._result]
        self._scope = [NotImplemented]  # Sentinel value
        self._pushed = []

    def push_terminal(self, d):
        """ At a terminal (token) node. The d parameter is normally a dict
            containing a canonicalized token. """
        # Check whether this terminal should be pushed as a nonterminal
        # with a single child
        cat = d["t"].split("_")[0] if "t" in d else None
        mapped_t = self._terminal_map.get(cat)
        if mapped_t is None:
            # No: add as a child of the current node in the condensed tree
            self._stack[-1].append(d)
        else:
            # Yes: create an intermediate nonterminal with this terminal
            # as its only child
            self._stack[-1].append(dict(k="NONTERMINAL", n=mapped_t, i=mapped_t, p=[d]))

    def push_nonterminal(self, nt_base):
        """ Entering a nonterminal node. Pass None if the nonterminal is
            not significant, e.g. an interior or optional node. """
        self._pushed.append(0)  # Number of items pushed
        if not nt_base:
            return
        mapped_nts = self._nt_map.get(nt_base)
        if not mapped_nts:
            return
        # Allow a single nonterminal, or a list of nonterminals, to be pushed
        if isinstance(mapped_nts, str):
            mapped_nts = [mapped_nts]
        for mapped_nt in mapped_nts:
            # We want this nonterminal in the simplified tree:
            # push it (unless it is subject to a scope we're already in)
            mapped_id = self._id_map[mapped_nt]
            subject_to = mapped_id.get("subject_to")
            if subject_to is not None and self._scope[-1] in subject_to:
                # We are already within a nonterminal to which this one is subject:
                # don't bother pushing it
                continue
            # This is a significant and noteworthy nonterminal
            children = []
            self._stack[-1].append(
                dict(k="NONTERMINAL", n=mapped_id["name"], i=mapped_nt, p=children)
            )
            self._stack.append(children)
            self._scope.append(mapped_nt)
            self._pushed[-1] += 1  # Add to number of items pushed

    def pop_nonterminal(self):
        """ Exiting a nonterminal node. Calls to pop_nonterminal() must correspond
            to calls to push_nonterminal(). """
        # Pop the same number of entries as push_nonterminal() pushed
        to_pop = self._pushed.pop()
        for _ in range(to_pop):
            self._pop_nonterminal()

    def _pop_nonterminal(self):
        """ Do the actual popping of a single level pushed by push_nonterminal() """
        children = self._stack.pop()
        mapped_nt = self._scope.pop()
        # Check whether this nonterminal has only one child, which is again
        # the same nonterminal - or a nonterminal which the parent overrides
        if len(children) == 1:

            ch0 = children[0]

            def collapse_child(d):
                """ Determine whether to cut off a child and connect directly
                    from this node to its children """
                if ch0["i"] == d:
                    # Same nonterminal category: do the cut
                    return True
                # If the child is a nonterminal that this one 'overrides',
                # cut off the child
                override = self._id_map[d].get("overrides")
                return ch0["i"] == override

            def replace_parent(d):
                """ Determine whether to replace the parent with the child """
                # If the child overrides the parent, replace the parent
                override = self._id_map[ch0["i"]].get("overrides")
                return d == override

            if ch0["k"] == "NONTERMINAL":
                if collapse_child(mapped_nt):
                    # If so, we eliminate one level and move the children of the child
                    # up to be children of this node
                    self._stack[-1][-1]["p"] = ch0["p"]
                elif replace_parent(mapped_nt):
                    # The child subsumes the parent: replace
                    # the parent by the child
                    self._stack[-1][-1] = ch0

    @property
    def result(self):
        return self._result[0]

    @property
    def tree(self):
        return SimpleTree([[self.result]])

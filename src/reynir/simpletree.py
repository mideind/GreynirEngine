"""

    Greynir: Natural language processing for Icelandic

    SimpleTree module

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

    This module implements SimpleTree, a wrapper class for simplified,
    normalized parse trees. It also implements SimpleTreeBuilder,
    a class that maps detailed parse trees corresponding to the CFG
    in Greynir.grammar to the simplified, normalized tree schema.

    SimpleTree instances can be queried for pattern matches. The pattern
    matching functionality is implemented in matcher.py.

"""

from typing import (
    Dict,
    FrozenSet,
    List,
    Mapping,
    Sequence,
    Tuple,
    Iterable,
    Iterator,
    Set,
    Union,
    Any,
    Optional,
    Callable,
    cast,
)

import re
from pprint import pformat
from itertools import chain

from tokenizer import TOK, Tok, correct_spaces

from .cache import cached_property
from .settings import StaticPhrases
from .binparser import (
    BIN_Nonterminal,
    BIN_Token,
    BIN_Terminal,
    CanonicalTokenDict,
    augment_terminal,
    canonicalize_token,
)
from .fastparser import ParseForestNavigator, Node
from .bintokenizer import (
    CURRENCIES,
    CURRENCY_GENDERS,
    MULTIPLIERS,
    DECLINABLE_MULTIPLIERS,
)
from .binparser import describe_token
from .bindb import BIN_Db, BIN_Meaning
from .ifdtagger import IFD_Tagset
from .matcher import match_pattern, ContextDict


# Type for map from token index to (terminal, meaning) tuple
TerminalMap = Dict[int, Tuple[BIN_Terminal, Optional[BIN_Meaning]]]
NonterminalMap = Mapping[str, Union[str, Tuple[str, ...]]]
IdMap = Mapping[str, Dict[str, Union[str, Set[str]]]]
StatsDict = Dict[str, Union[int, float]]


class SimpleTreeNode(CanonicalTokenDict, total=False):

    """ A dictionary representing a node in a SimpleTree.
        This scheme is intended for external consumption,
        such as export in JSON format to clients. """

    # Node kind, e.g. 'NONTERMINAL'
    # Note: since k is also present in CanonicalTokenDict as an int,
    # we resort to a hack here by using type:ignore to silence mypy's
    # understandable complaints
    k: str  # type: ignore
    # Human-readable name of the nonterminal
    n: str
    # Nonterminal name, from the grammar
    i: str
    # Child nodes
    p: List[CanonicalTokenDict]


# Default tree simplifier configuration maps

_DEFAULT_NT_MAP: NonterminalMap = {
    "S0": "S0",
    "HreinYfirsetning": "S-MAIN",
    "Setning": "S-MAIN",
    "SetningLo": "S-MAIN",
    "SetningÁnF": "S-MAIN",
    "SetningAukafall": ("S-MAIN", "IP"),  # Push two headers: S and IP
    "SetningAukafallForgangur": ("S-MAIN", "IP"),
    "SetningSkilyrði": "S-MAIN",
    "SetningUmAðRæða": "S-MAIN",
    "StViðtenging": "S-MAIN",
    "Fyrirsögn": "S-HEADING",
    "Staðhæfing": "S-QUOTE",  # "Þetta er svona, segir Páll"
    "Tilvísunarsetning": "CP-REL",
    "KommaTilvísunarsetning": "CP-REL",
    "AðÞvíErSegir": "CP-REL",
    "Skilyrði": "CP-COND",
    "Afleiðing": "S-CONS",
    "Spurnarsetning": "S-QUE",
    "Sagt": "CP-QUOTE",
    "Segjandi": "CP-SOURCE",
    "Forskeyti": "S-PREFIX",
    "Tíðarsetning": "CP-ADV-TEMP",
    "Tilgangssetning": "CP-ADV-PURP",
    "Viðurkenningarsetning": "CP-ADV-ACK",
    "Þó": "CP-ADV-ACK",
    "Afleiðingarsetning": "CP-ADV-CONS",
    "Orsakarsetning": "CP-ADV-CAUSE",
    "Skilyrðissetning": "CP-ADV-COND",
    "Samanburðarsetning": "CP-ADV-CMP",
    "SamanburðurSemSetning": "CP-ADV-CMP",
    "SamanburðarNafnliður": "CP-ADV-CMP",
    "StakViðhengi": "CP-ADV-CMP",
    "SamanburðarForskeyti": "CP-ADV-CMP",
    "EnSamanb": "CP-ADV-CMP",
    # Note: CP-THT is used in code logic below; if modifying this,
    # be careful to change all instances where it is referred to
    "Skýringarsetning": "CP-THT",
    "SkýringarsetningFramhald": "CP-THT",
    "AtviksAðSetning": "CP-THT",
    "Spurnaraukasetning": "CP-QUE",
    "BeygingarliðurÁnF": "IP",
    "BeygingarliðurÁnUmröðunar": "IP",
    "BeygingarliðurMeðUmröðun": "IP",
    "BeygingarliðurSögnFremst": "IP",
    "BeygingarliðurLoÞgf": "IP",  # Mér er frjálst (að fara ferða minna)
    "BeygingarliðurTími": ("IP", "VP"),  # (Þegar) líða fer að jólum
    "SagnarBotn": "IP",
    "ÞóBotn": "IP",
    "SkýringarBotn": "IP",
    "SegirÍ": "IP",
    "BeygingarliðurStýftAndlag": "IP",
    "BlTagl": "IP",
    "NhLiður": "IP-INF",
    "SetningÞað": "IP-INF",
    "ÞaðTenging": "IP-INF",
    "ViðurkenningarNh": "IP-INF",
    "ViðurkenningarNhKomma": "IP-INF",
    "Nl": "NP",
    "NlRunaEða": "NP",
    "SpurnarNafnliður": "NP",
    "EfLiður": "NP-POSS",
    "EfLiðurForskeyti": "NP-POSS",
    "OkkarFramhald": "NP-POSS",
    "Allra": "NP-POSS",
    # "LoEftirNlMeðÞgf": "NP-DAT",
    "LoViðhengi": "NP-ADP",  # Adjective predicate
    "Heimilisfang": "NP-ADDR",
    "Fyrirtæki": "NP-COMPANY",
    "SérnafnFyrirtæki": "NP-COMPANY",
    "Magn": "NP-MEASURE",
    # Note: NP-TITLE is referred to in the program logic below,
    # so be careful when changing it
    "Titill": "NP-TITLE",
    "FæðingarOgDánardægur": "NP-LIFESPAN",
    "Frumlag": "NP-SUBJ",
    "NlFrumlag": "NP-SUBJ",
    "NlFrumlagÞað": "NP-SUBJ",
    "NlFrumlagLeppur": "NP-ES",
    "NlBeintAndlag": "NP-OBJ",
    "NlEnginnAndlag": "NP-OBJ",  # 'hann getur enga samninga gert'
    "NlAnnar": "NP-OBJ",  # '[Jón hefur] aðra sögu [að segja]'
    "NlAndlagÞað": "NP-OBJ",  # (Jón lét) þess (getið að Guðrún væri falleg)
    "NlNema": "NP-EXCEPT",  # '(söknuðu einskis) nema hestsins'
    "NlÓbeintAndlag": "NP-IOBJ",
    "NlSagnfylling": "NP-PRD",
    "SögnErLoBotn": "NP-PRD",  # Show '(Hann er) góður / 18 ára' as a predicate argument
    "LoTengtSögn": "NP-PRD",
    "LoÞgfNh": "NP-PRD",  # '(Mér er) frjálst (að reykja utandyra)'
    "Aldur": "NP-AGE",
    "TímaNafnliðurStærri": "NP",
    "TímaNafnliðurMinni": "NP",
    "TímaMagnNafnliðurStærri": "NP",
    "TímaMagnNafnliðurMinni": "NP",
    "Heimild": "NP-SOURCE",
    "NlFjárhæð": "NP",
    "Skst": "NP-PREFIX",  # Noun phrase prefix, such as 'COVID-19 smitið'
    "Sagnliður": "VP",
    "SagnliðurMeðF": "VP",
    "So": "VP",
    "NhSögnAtv": "VP",
    "NhLiðir": "VP",
    "NhSögn": "VP",
    "NhEinfaldur": "VP",
    "SagnliðurÁnF": "VP",
    "ÖfugurSagnliður": "VP",
    "SagnliðurVh": "VP",
    "HjSögnLhÞt": "VP",  # Auxiliary verb, hjálparsögn
    "SögnLhNt": "VP",  # Present participle, lýsingarháttur nútíðar
    "SögnSagnbBreyting": "VP",  # 'hefur versnað'
    "SögnLhNtBreyting": "VP",  # 'hefur farið fækkandi'
    "SögnNhBreyting": "VP",  # 'mun fækka'
    "SögnÞað": "VP",  # '(það) verður að segjast að...'
    "SögnÓp": "VP",  # '(mig) þraut örendið'
    "SögnAðRæða": "VP",
    "SögnAukafallÞgf": "VP",
    "SögnAukafallEf": "VP",
    "SögnÞessGetið": "VP",
    "HreinSögn": "VP",
    "EinSögn": "VP",
    "SögnUmAðRæða": "VP",
    "SögnVarUmAðRæða": "VP",
    "SagnHluti": "VP",
    "SagnRuna": "VP",
    "SagnRunaStýfð": "VP",
    "Andlagssagnliður": "VP",
    "ÓpSagnliður": "VP",
    "HjSögn": "VP-AUX",
    "HjSögnNh": "VP-AUX",
    "SetningSo": "IP",  # Removed "VP" from here - it creates duplicate IP>VP chains
    "SetningSoÞað": "IP",  # Removed "VP" from here - it creates duplicate IP>VP chains
    "FsLiður": "PP",
    "FsMeðFallstjórn": "PP",
    "FsFyrirEftir": "PP",
    "FsUmAðRæða": "PP",
    "FsVarUmAðRæða": "PP",
    "FsRunaEftirSögn": "PP",
    "AðSögn": "PP",
    "ÍNl": "PP",
    "SpurnarForsetningarliður": "PP",
    "MagnAfLiður": "PP",
    "AfLiður": "PP",
    "Atviksliður": "ADVP",
    "AlHvortSemUmErAðRæða": "ADVP",
    "LoAtviksliðir": "ADVP",
    "EinnAl": "ADVP",
    "AlTilv": "ADVP",
    "StefnuAtv": "ADVP-DIR",
    "SpurnarAtviksorð": "ADVP",
    "FöstDagsetning": "ADVP-DATE-ABS",
    "AfstæðDagsetning": "ADVP-DATE-REL",
    "FasturTímapunktur": "ADVP-TIMESTAMP-ABS",
    "AfstæðurTímapunktur": "ADVP-TIMESTAMP-REL",
    "Tíðni": "ADVP-TMP-SET",
    "FastTímabil": "ADVP-DUR-ABS",
    "AfstættTímabil": "ADVP-DUR-REL",
    "TímabilTími": "ADVP-DUR-TIME",
    "Aðaltenging": "C",
    "Samtenging": "C",
    "Skýringartenging": "C",
    "Tíðartenging": "C",
    "Tilgangstenging": "C",
    "Viðurkenningartenging": "C",
    "Enda": "C",
    "Afleiðingartenging": "C",
    "Orsakartenging": "C",
    "OrsakartengingUmröðun": "C",
    "Skilyrðistenging": "C",
    "Samanburðartenging": "C",
    "Tilvísunartenging": "C",
    "InnskotsSamtenging": "C",
    "Sem": "C",
    "EnOgEða": "C",
    "Nema": "C",
    "OgSem": "C",
    "AðÞvíEr": "C",
    "AnnaðhvortSt": "C",
    "VillaHeldur": "C",
    "OgEða": "C",
    "Bæði": "C",
    "Ýmist": "C",
    "Og": "C",
    "Eða": "C",
    "Né": "C",
    "Hvorki": "C",
    "HeldurEn": "C",
    "Til": "C",
    "En": "C",
    "HvortSem": "C",
    "Nhm": "TO",
}

# subject_to: don't push an instance of this if the
# immediate parent is already the subject_to nonterminal

# overrides: we cut off a parent node in favor of this one
# if there are no intermediate nodes

_DEFAULT_ID_MAP: IdMap = {
    "S0": dict(name="Málsgrein"),
    "S0-X": dict(name="Rangt mynduð setning"),
    "S-MAIN": dict(name="Setning", subject_to={"S-MAIN", "S-QUE", "CP-QUOTE", "IP"}),
    "S-QUOTE": dict(name="Staðhæfing", overrides="S-MAIN"),
    "S-HEADING": dict(name="Fyrirsögn"),
    "S-PREFIX": dict(name="Forskeyti"),  # Prefix in front of sentence
    "S-QUE": dict(name="Spurnaraðalsetning", overrides="S-MAIN"),  # Question clause
    "CP-THT": dict(name="Skýringarsetning", overrides="IP-INF"),  # Complement clause
    "CP-QUE": dict(name="Spurnaraukasetning", overrides="NP-OBJ"),  # Question subclause
    "CP-REL": dict(
        name="Tilvísunarsetning", overrides="S", subject_to={"CP-REL"}
    ),  # Relative clause
    "CP-ADV-TEMP": dict(name="Tíðarsetning"),  # Adverbial temporal phrase
    "CP-ADV-PURP": dict(name="Tilgangssetning"),  # Adverbial purpose phrase
    # Adverbial acknowledgement phrase
    "CP-ADV-ACK": dict(name="Viðurkenningarsetning"),
    "CP-ADV-CONS": dict(name="Afleiðingarsetning"),  # Adverbial consequence phrase
    "CP-ADV-CAUSE": dict(name="Orsakarsetning"),  # Adverbial causal phrase
    "CP-ADV-COND": dict(name="Skilyrðissetning"),  # Adverbial conditional phrase
    "CP-ADV-CMP": dict(name="Samanburðarsetning"),  # Adverbial comparative phrase
    "CP-QUOTE": dict(name="Tilvitnun"),  # Direct quote
    "CP-SOURCE": dict(name="Segjandi"),  # Quote source
    "IP": dict(name="Beygingarliður"),  # Inflectional phrase
    # Infinitival inflectional phrase
    "IP-INF": dict(name="Beygingarliður", overrides="VP"),
    "VP": dict(name="Sagnliður", overrides={"VP"}),
    "VP-AUX": dict(name="Hjálparsögn", overrides="VP"),
    "NP": dict(
        name="Nafnliður",
        subject_to={
            "NP-SUBJ",
            "NP-ES",
            "NP-OBJ",
            "NP-IOBJ",
            "NP-PRD",
            "NP-ADP",
            "NP-EXCEPT",
        },
    ),
    "NP-POSS": dict(name="Eignarfallsliður", overrides="NP"),
    "NP-DAT": dict(name="Þágufallsliður", overrides="NP"),
    "NP-ADDR": dict(name="Heimilisfang", overrides="NP"),
    "NP-COMPANY": dict(name="Fyrirtæki", overrides="NP"),
    "NP-TITLE": dict(name="Titill", overrides="NP"),
    "NP-LIFESPAN": dict(name="Ævidægur", overrides="NP-TITLE"),
    "NP-SOURCE": dict(name="Heimild"),
    "NP-PREFIX": dict(name="Forskeyti"),
    "NP-AGE": dict(name="Aldur"),
    "NP-MEASURE": dict(name="Magnliður", overrides="NP"),
    "NP-EXCEPT": dict(name="Nema"),
    "NP-SUBJ": dict(name="Frumlag", subject_to={"NP-SUBJ"}),
    "NP-ES": dict(name="Frumlagsleppur"),
    "NP-OBJ": dict(name="Beint andlag"),
    "NP-IOBJ": dict(name="Óbeint andlag"),
    "NP-PRD": dict(name="Sagnfylling"),
    "NP-ADP": dict(name="Andlag lýsingarorðs"),
    "ADVP": dict(name="Atviksliður", subject_to={"ADVP"}),
    "ADVP-DIR": dict(name="Áttaratviksliður"),
    "ADVP-DATE-ABS": dict(name="Föst dagsetning", overrides="ADVP"),
    "ADVP-DATE-REL": dict(name="Afstæð dagsetning", overrides="ADVP"),
    "ADVP-TIMESTAMP-ABS": dict(name="Fastur tímapunktur", overrides="ADVP"),
    "ADVP-TIMESTAMP-REL": dict(
        name="Afstæður tímapunktur", overrides="ADVP", subject_to={"ADVP-TIMESTAMP-REL"}
    ),
    "ADVP-TMP-SET": dict(name="Tíðni", overrides="ADVP"),
    "ADVP-DUR-ABS": dict(name="Fast tímabil"),
    "ADVP-DUR-REL": dict(name="Afstætt tímabil", overrides="ADVP"),
    "ADVP-DUR-TIME": dict(name="Tímabil"),
    "ADVP-PCL": dict(name="Ögn"),
    "PP": dict(
        name="Forsetningarliður",
        overrides="ADVP",
        subject_to={"ADVP-DUR-REL", "ADVP-DUR-ABS"},
    ),
    # Hausar
    "P": dict(name="Forsetning"),
    "TO": dict(name="Nafnháttarmerki"),
    "C": dict(name="Samtenging"),
    "FOREIGN": dict(name="Erlendur texti"),
}

_DEFAULT_TERMINAL_MAP: Mapping[str, str] = {
    # "no": "N",
    # "hk": "N",
    # "kk": "N",
    # "kvk": "N",
    # "fyrirtæki": "N",
    # "sérnafn": "N",
    # "person": "N",
    # "entity": "N",
    # "fn": "PRON",
    # "pfn": "PRON",
    # "abfn": "PRON",
    "so": "VP",
    # "ao": "ADV",
    # "eo": "ADV",
    "fs": "P",
    # "lo": "ADJ",
    # "raðnr": "ADJ",  # Raðtölur
    # "töl": "NUM",
    # "tala": "NUM",
    # "to": "NUM",
    # "ártal": "NUM",
    # "st": "C",
    # "stt": "C",
    # "nhm": "TO",  # Nafnháttarmerki
    # "gr": "DET",
    # "dagsafs": "DATEREL",
    # "dagsfast": "DATEABS",
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


def cut_definite_pronouns(txt: str) -> str:
    """ Removes definite pronouns from the front of txt and returns the result.
        However, if the text consists of only definite pronouns, it is returned
        as-is. """
    lower_txt = txt.lower()
    if lower_txt.startswith("það að"):
        # Make an exception for 'það að X sé Y' - this is OK to return,
        # even as an indefinite form
        return txt
    # 'Stefna hans hefur ávallt verið sú að Bandaríkin setjist við samningaborðið'
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

    def __init__(self, replacements: Dict[str, str]) -> None:
        self._replacements = replacements
        substrs = sorted(replacements.keys(), key=len, reverse=True)
        # Create a big OR regex that matches any of the substrings to replace
        # Note that this is done in two steps to satisfy Pylance,
        # which currently seems to be unable to infer the type of
        # map(re.escape, Iterable[str])
        re_escape: Callable[[str], str] = re.escape
        escaped = [cast(str, s) for s in map(re_escape, substrs)]
        self._regexp = re.compile("|".join(escaped))

    def replace(self, string: str) -> str:
        # For each match, look up the new string in the replacements
        return self._regexp.sub(
            lambda match: self._replacements[match.group(0)], string
        )


class SimpleTree:

    """ A wrapper for a simple parse tree """

    def __init__(
        self,
        pgs: Iterable[Sequence[CanonicalTokenDict]],
        stats: Optional[StatsDict] = None,
        register=None,
        parent: Optional["SimpleTree"] = None,
        root: Optional["SimpleTree"] = None,
    ) -> None:
        # Keep a link to the original root SimpleTree
        self._root = root
        if root is not None:
            assert stats is None
            assert register is None
        else:
            # Only store stats and register in root nodes
            self._stats = stats
            self._register = register
        self._parent = parent
        # Flatten the paragraphs into a sentence array
        sents: List[CanonicalTokenDict] = []
        if pgs:
            for pg in pgs:
                sents.extend(pg)
        self._sents = sents
        self._len = len(sents)
        self._head = cast(SimpleTreeNode, sents[0] if self._len == 1 else {})
        self._children = cast(Optional[List[CanonicalTokenDict]], self._head.get("p"))
        self._children_cache: Optional[Tuple["SimpleTree", ...]] = None
        self._tag_cache: Optional[List[str]] = None

    def __str__(self) -> str:
        """ Return a pretty-printed representation of the contained trees """
        return pformat(self._head if self.is_terminal else self._sents)

    def __repr__(self) -> str:
        """ Return a compact representation of this subtree """
        len_self = len(self)
        if len_self == 0:
            if self._head.get("k") == "PUNCTUATION":
                x = self._head.get("x")
                return "<SimpleTree for punctuation '{0}'>".format(x)
            return "<SimpleTree for terminal {0}>".format(self.terminal)
        return "<SimpleTree with tag {0} and length {1}>".format(self.tag, len_self)

    @classmethod
    def from_deep_tree(
        cls, deep_tree, toklist: List[Tok], first_token_index: int = 0
    ) -> Optional["SimpleTree"]:
        """ Construct a SimpleTree from a deep (detailed) parse tree """
        # If the deep_tree has nodes referring to tokens with a different
        # index range than the given toklist, pass the difference in the
        # first_token_index parameter. For instance, if the toklist spans
        # tokens 5..10 within the original toklist that was used to construct
        # deep_tree, first_token_index would be 5.
        if deep_tree is None or not toklist:
            return None
        s = Simplifier(toklist, first_token_index=first_token_index)
        s.go(deep_tree)
        return s.tree

    @property
    def root(self) -> "SimpleTree":
        """ The original topmost root of this subtree """
        return self if self._root is None else self._root

    @property
    def parent(self) -> Optional["SimpleTree"]:
        """ Return the parent of this subtree, or None if it is a root """
        return self._parent

    @property
    def stats(self):
        """ Return the parse statistics, if any, for the root of this subtree """
        return self.root._stats

    @property
    def register(self):
        """ Return the name register, if any, for the root of this subtree """
        return self.root._register

    @property
    def tag(self) -> Optional[str]:
        """ The simplified tag of this subtree, i.e. P, S, NP, VP, ADVP... """
        return cast(Optional[str], self._head.get("i"))

    @property
    def kind(self) -> Optional[str]:
        """ The kind of token associated with this subtree, for example
            'WORD', 'MEASUREMENT' or 'PUNCTUATION', if the subtree is
            a terminal node, or None otherwise """
        return cast(Optional[str], self._head.get("k"))

    @property
    def ifd_tags(self) -> List[str]:
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
                return StaticPhrases.tags(lower_x) or []
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

    def match_tag(self, item: Union[str, List[str]]) -> bool:
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
        return tags[0 : len(item)] == item

    def enclosing_tag(self, item: Union[str, List[str]]) -> Optional["SimpleTree"]:
        """ Return the closest parent node having a tag
            that matches the given item, if such a node exists,
            or None otherwise """
        p = self.parent
        while p is not None and not p.match_tag(item):
            p = p.parent
        return p

    @property
    def terminal(self) -> Optional[str]:
        """ The terminal matched by this subtree. Note that this is a
            'canonicalized' version of the terminal name, where literal
            specifications have been simplified
            (e.g., 'orð:hk'_x_y becomes 'no_hk_x_y') """
        return cast(Optional[str], self._head.get("t"))

    @property
    def original_terminal(self) -> Optional[str]:
        """ The terminal matched by this subtree, as originally specified
            in the grammar """
        return cast(Optional[str], self._head.get("o", self._head.get("t")))

    @property
    def terminal_with_all_variants(self) -> Optional[str]:
        """ The terminal matched by this subtree, with all applicable
            variants in canonical form (in alphabetical order, except for
            verb argument cases) """
        terminal = cast(Optional[str], self._head.get("a"))
        if terminal is not None:
            # All variants already available in canonical form: we're done
            return terminal
        terminal = cast(Optional[str], self._head.get("t"))
        if terminal is None:
            return None
        # Reshape the terminal string to the canonical form where
        # the variants are in alphabetical order, except
        # for verb arguments, which are always first, immediately
        # following the terminal category.
        beyging = cast(Optional[str], self._head.get("b")) or ""
        return augment_terminal(terminal, self._text.lower(), beyging)

    @cached_property
    def variants(self) -> List[str]:
        """ Returns a list of the variants associated with
            this subtree's terminal, if any """
        t = self.terminal
        return [] if t is None else t.split("_")[1:]

    @cached_property
    def all_variants(self) -> List[str]:
        """ Returns a list of all variants associated with
            this subtree's terminal, if any, augmented also by BÍN variants """
        # First, check whether an 'a' field is present
        a = cast(Optional[str], self._head.get("a"))
        if a is not None:
            # The 'a' field contains the entire variant set, canonically ordered
            return a.split("_")[1:]
        vlist = self.variants
        if self.terminal in {"sérnafn", "fyrirtæki"}:
            # Don't attempt to augment proper names or company abbreviations
            return vlist
        beyging = cast(Optional[str], self._head.get("b")) or ""
        bin_variants = BIN_Token.bin_variants(beyging)
        return vlist + list(bin_variants - set(vlist))  # Add any missing variants

    @cached_property
    def _vset(self) -> Set[str]:
        """ Return a set of the variants associated with this subtree's terminal,
            if any. Note that this set is undordered, so it is not intended for
            retrieving the cases of verb subjects. """
        return set(self.all_variants)

    @cached_property
    def tcat(self) -> str:
        """ The word category associated with this subtree's terminal, if any """
        t = self.terminal
        return "" if t is None else t.split("_")[0]

    @property
    def index(self) -> Optional[int]:
        """ Return the associated token index, if this is a terminal,
            otherwise None """
        return cast(Optional[int], self._head.get("ix")) if self.is_terminal else None

    @cached_property
    def sentences(self) -> List["SimpleTree"]:
        """ A list of the contained sentences """
        return [
            SimpleTree([[sent]], root=self.root, parent=self) for sent in self._sents
        ]

    @property
    def has_children(self) -> bool:
        """ Does this subtree have (proper) children? """
        return bool(self._children)

    @property
    def is_terminal(self) -> bool:
        """ Is this a terminal node? """
        return self._len == 1 and not self._children

    @property
    def _gen_children(self) -> Iterator["SimpleTree"]:
        """ Generator for children of this tree """
        if self._len > 1:
            # More than one sentence: yield'em
            yield from self.sentences
        elif self._children:
            # Proper children: yield'em
            for child in self._children:
                yield SimpleTree([[child]], root=self.root, parent=self)

    @property
    def children(self) -> Iterator["SimpleTree"]:
        """ Cached generator for children of this tree """
        if self._children_cache is None:
            self._children_cache = tuple(self._gen_children)
        yield from self._children_cache

    @property
    def descendants(self) -> Iterator["SimpleTree"]:
        """ Generator for all descendants of this tree, in-order """
        for child in self.children:
            yield child
            yield from child.descendants

    @property
    def deep_children(self) -> Iterator[Iterator["SimpleTree"]]:
        """ Generator of generators of children of this tree and its subtrees """
        yield self.children
        for ch in self.children:
            yield from ch.deep_children

    def _view(self, level: int) -> str:
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
    def view(self) -> str:
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
    def _make_terminal_with_case(
        cat: str, variants: Set[str], terminal: str, default_case: str = "nf"
    ) -> str:
        """ Return a terminal identifier with the given category and
            variants, plus the case indicated in the terminal, if any """
        tcase: Set[str] = set(terminal.split("_")[1:]) & _CASES
        if len(tcase) == 0:
            # If no case given, assume nominative rather than nothing
            tcase = {default_case}
        return "_".join([cat] + sorted(list(variants | tcase)))

    @staticmethod
    def _multiword_token(txt: str, tokentype: str, terminal: str) -> str:
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
        terminal_case: Optional[str] = None
        # Token atoms (components of a multiword token)
        a = list(reversed(txt.split()))
        for tok in a:
            if re.match(r"^\d{1,2}:\d\d(:\d\d)?$", tok):
                # 12:34 or 11:34:50
                result.append("tími")
                continue
            if re.match(r"^[+\-]?\d+(\.\d\d\d)*(,\d+)?$", tok):
                # 12, 1.234 or 1.234,56
                result.append("tala")
                continue
            if re.match(r"^[+\-]?\d+(\,\d\d\d)+(\.\d+)+$", tok):
                # English-format number: must have both a thousands separator
                # and a decimal part
                # 1,234.56
                result.append("tala")
                continue
            if re.match(r"^\d{1,2}\.\d{1,2}(\.\d{2,4})?$", tok) or re.match(
                r"^\d{1,2}/\d{1,2}(/\d{2,4})?$", tok
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
                            m,
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
                            tc: str = terminal_case  # Make mypy happy
                            m.sort(key=lambda mm: 0 if tc in mm.beyging else 1)
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
                            # Note the gender and case of the noun, so we can restrict
                            # our set of adjective forms, if an adjective is attached
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
        # that should be in the genitive case
        if tokentype == "AMOUNT":
            # Note that the terminal list is reversed, so a[0] is the last terminal
            if a[0] in CURRENCY_GENDERS:
                # ISO currency abbreviation
                if result[1].startswith("no_"):
                    # Following a noun (we're assuming that it's a multiplier
                    # such as 'þúsund', 'milljónir', 'milljarðar'):
                    # assemble a terminal identifier with plural, genitive
                    # and the correct gender
                    result[0] = "no_" + "_".join(
                        sorted(["ft", "ef", CURRENCY_GENDERS[a[0]]])
                    )
        return " ".join(reversed(result))

    def _flat(self, func: Callable[["SimpleTree"], str]) -> str:
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
        tokentype: str = cast(Optional[str], self._head.get("k")) or ""
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
        # Fallback: Repeat the terminal name for each component word,
        # except that we use 'st' for conjunctions. Note that the component
        # words may have trailing hyphens and commas, as in
        # 'dómsmála-, ferðamála- og nýsköpunarráðherra'
        words = self._text.split()
        return " ".join("st" if word in _CONJUNCTIONS else terminal for word in words)

    @property
    def flat(self) -> str:
        """ Return a flat representation of this subtree """
        return self._flat(lambda tree: cast(str, tree.terminal))

    @property
    def flat_with_all_variants(self) -> str:
        """ Return a flat representation of this subtree, where terminals
            include all applicable variants """
        return self._flat(lambda tree: cast(str, tree.terminal_with_all_variants))

    def _bracket_form(self) -> str:
        """ Return a bracketed representation of the tree """
        result: List[str] = []
        puncts = frozenset((".", ",", ";", ":", "-", "—", "–"))

        def push(node: Optional["SimpleTree"]) -> None:
            """ Append information about a node to the result list """
            if node is None:
                return
            nonlocal result
            node_head = node._head
            node_kind = node_head.get("k")
            if node_kind == "NONTERMINAL":
                result.append("(" + cast(str, node_head.get("i", "")))
                # Recursively add the children of this nonterminal
                for child in node.children:
                    result.append(" ")
                    push(child)
                result.append(")")
            elif node_kind == "PUNCTUATION" and node_head.get("x") in puncts:
                result.append("(PUNCT {})".format(node_head.get("x")))
            else:
                # Terminal: append the text
                result.append(node.text.replace(" ", "_"))

        push(self)
        return "".join(result)

    @property
    def bracket_form(self) -> str:
        """ Return a bracketed representation of the tree """
        return self._bracket_form()

    def __getattr__(self, name: str) -> "SimpleTree":
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
                "Subtree has {0} {1} but index {2} was requested".format(
                    multi - index, name, multi
                )
            )
        raise AttributeError("Subtree has no child named '{0}'".format(name))

    def __getitem__(self, index: Union[str, int]) -> "SimpleTree":
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
            return SimpleTree([[self._sents[index]]], root=self.root, parent=self)
        if self._children:
            return SimpleTree([[self._children[index]]], root=self.root, parent=self)
        raise IndexError("Subtree has no children")

    def __len__(self) -> int:
        """ Return the length of this subtree, i.e. the last usable child index + 1 """
        if self._len > 1:
            return self._len
        return len(self._children) if self._children else 0

    @property
    def _text(self) -> str:
        """ Return the original text within this node only, if any """
        return cast(str, self._head.get("x", ""))

    @cached_property
    def _lemma(self) -> str:
        """ Return the lemma of this node only, if any """
        lemma = cast(
            Union[str, Tuple[Callable[..., str], Tuple]],
            self._head.get("s", self._text),
        )
        if isinstance(lemma, tuple):
            # We have a lazy-evaluation function tuple:
            # call it to obtain the lemma
            f, args = lemma
            lemma = f(*args)
        return lemma

    def _alternative_form(self, form: str) -> str:
        """ Return a nominative form of the text within this node only, if any.
            The form can be 'nominative' for the nominative case only,
            'indefinite' for the indefinite nominative form,
            or 'canonical' for the singular, indefinite, nominative. """
        if self._cat not in _DECLINABLE_CATEGORIES:
            # This is not a potentially declined terminal node:
            # return the original text
            # !!! TODO: self._cat may be None, for instance for TOK.AMOUNT tokens
            # !!! ('25.000 krónum' or '100 breskum pundum').
            # !!! In that case, self.tcat is 'no'. Inflection to be implemented.
            return self._text
        txt = self._text
        indefinite = form == "indefinite"
        canonical = form == "canonical"
        prefix = ""
        with BIN_Db.get_db() as db:

            # A bit convoluted, but so it goes
            lookup_functions = {
                "accusative": db.lookup_accusative,
                "dative": db.lookup_dative,
                "genitive": db.lookup_genitive,
            }
            lookup_func = lookup_functions.get(form, db.lookup_nominative)

            if self.tcat == "person":
                # Special case for person names as they may have embedded spaces
                result = []
                gender = self._cat
                for name in txt.split():
                    meanings = lookup_func(name, singular=True, cat=gender)
                    try:
                        # Try to find an 'ism', 'erm', 'gæl', 'föð' or 'móð'
                        # nominative form of the correct gender
                        result.append(
                            next(
                                filter(
                                    lambda m: m.fl
                                    in {"ism", "gæl", "erm", "föð", "móð"},
                                    meanings,
                                )
                            ).ordmynd
                        )
                    except StopIteration:
                        # No nominative form
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

            options: Dict[str, Any] = dict(
                cat=self._cat,
                stem=lemma,
                singular=canonical,
                indefinite=indefinite or canonical,
                # We don't want second or third optional forms of
                # word declensions; we just stick with the first form
                beyging_filter=lambda b: "2" not in b and "3" not in b,
            )
            meanings = lookup_func(txt, **options)
            if not meanings and not txt.islower():
                # We don't find this form in BÍN:
                # if upper case, try a lower case version of it
                meanings = lookup_func(txt.lower(), **options)

            if not meanings and canonical and self._cat in _GENDERS:
                # Might be a noun that only exists in plural, such as
                # 'landsteinar': retry
                options["singular"] = False
                meanings = lookup_func(txt, **options)
                if not meanings and not txt.islower():
                    # Try the lower case version as well, for good measure
                    meanings = lookup_func(txt.lower(), **options)

            # The following functions filter the nominative list in a
            # final step that is required because some word forms can
            # have more than one gender and can even be valid both as
            # singular and plural

            def filter_func_no(m: BIN_Meaning) -> bool:
                """ Filter function for nouns """
                if not canonical and self.tcat != "gata":
                    # Match the original word in terms of number (singular/plural)
                    # We don't do this for street names ('gata' terminals)
                    # since they don't have number variants (_et/_ft)
                    number_set = self._vset & {"et", "ft"}
                    number = next(iter(number_set), "et")
                    if number.upper() not in m.beyging:
                        return False
                if not (canonical or indefinite):
                    # Match the original word in terms of definite/indefinite
                    # (This is probably redundant since definite and indefinite
                    # forms are (almost?) always disjoint sets, but one can
                    # never be too careful)
                    if ("gr" in self._vset) != ("gr" in m.beyging):
                        return False
                elif "gr" in m.beyging:
                    # Only return indefinite forms
                    return False
                return True

            def filter_func_without_gender(m: BIN_Meaning) -> bool:
                """ Filter function for personal pronouns """
                if not canonical:
                    # Match the original word in terms of number (singular/plural)
                    number = next(iter(self._vset & {"et", "ft"}), "et")
                    if number.upper() not in m.beyging:
                        return False
                return True

            def filter_func_with_gender(m: BIN_Meaning) -> bool:
                """ Filter function for nonpersonal pronouns
                    and declinable number words """
                # Match the original word in terms of gender
                gender = next(iter(self._vset & _GENDERS), "kk")
                if gender.upper() not in m.beyging:
                    return False
                if not canonical:
                    # Match the original word in terms of number (singular/plural)
                    number = next(iter(self._vset & {"et", "ft"}), "et")
                    if number.upper() not in m.beyging:
                        return False
                return True

            def filter_func_lo(m: BIN_Meaning) -> bool:
                """ Filter function for adjectives """
                # Match the original word in terms of gender
                gender = next(iter(self._vset & _GENDERS), "kk")
                if gender.upper() not in m.beyging:
                    return False
                if not canonical:
                    # Match the original word in terms of number (singular/plural)
                    number = next(iter(self._vset & {"et", "ft"}), "et")
                    if number.upper() not in m.beyging:
                        return False
                if not (canonical or indefinite):
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
                    # Only return strong declension since we only want
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
            filters: Dict[Union[None, str], Callable[[BIN_Meaning], bool]] = {
                "lo": filter_func_lo,
                "to": filter_func_with_gender,
                "fn": filter_func_with_gender,
                "gr": filter_func_with_gender,
                "pfn": filter_func_without_gender,
            }
            meanings_iter = filter(filters.get(self._cat, filter_func_no), meanings)
            try:
                # Choose the first nominative form that got past the filter
                w = next(meanings_iter).ordmynd
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
                if self._cat == "to" and "ft" in self._vset and canonical:
                    # Declinable number, for which there is no singular form available,
                    # such as "tveir": return an empty string
                    txt = prefix = ""
        return prefix + txt

    @property
    def nominative(self) -> str:
        """ Return the nominative form of this node only, if any """
        return self._alternative_form("nominative")

    @property
    def accusative(self) -> str:
        """ Return the accusative form of this node only, if any """
        return self._alternative_form("accusative")

    @property
    def dative(self) -> str:
        """ Return the dative form of this node only, if any """
        return self._alternative_form("dative")

    @property
    def genitive(self) -> str:
        """ Return the genitive form of this node only, if any """
        return self._alternative_form("genitive")

    @cached_property
    def indefinite(self) -> str:
        """ Return the indefinite nominative form of this node only, if any """
        return self._alternative_form("indefinite")

    @cached_property
    def canonical(self) -> str:
        """ Return the singular indefinite nominative form of this node only, if any """
        return self._alternative_form("canonical")

    @property
    def _cat(self) -> Optional[str]:
        """ Return the word category of this node only, if any """
        # This is the category that is picked up from BÍN, not the terminal
        # category. The terminal category is available in the .tcat property)
        return cast(Optional[str], self._head.get("c"))

    # Set of token kind description strings for tokens that contain text
    _TEXT_TOKEN_DESC = frozenset(TOK.descr[kind] for kind in TOK.TEXT)

    @property
    def cat(self) -> str:
        """ Return the word category of this node, if it is a terminal,
            or an empty string otherwise """
        cat = cast(str, self._head.get("c", ""))
        if cat:
            return cat
        if self.terminal is not None and self.kind in self._TEXT_TOKEN_DESC:
            # For unknown words, we return a category of 'entity'
            return "entity"
        return ""

    @property
    def lemma_cat(self) -> str:
        """ Return the word category of this node, to be paired with a lemma.
            This is different from cat in the case of unknown words, where
            there is no BÍN category, and we return "entity". For non-text
            tokens/terminals, we return "". """
        if self.terminal is None:
            return ""
        k = self.kind
        if k not in self._TEXT_TOKEN_DESC:
            # For non-text token types, we return "" for the category
            return ""
        if k == "PERSON":
            # Return person_kk, person_kvk or person_hk for person names
            return "person_" + (cast(Optional[str], self._head.get("c")) or "hk")
        # Unknown words by convention get a category of 'entity'
        return cast(str, self._head.get("c", "entity"))

    @property
    def categories(self) -> List[str]:
        """ Return a list of word categories within this subtree """
        if self._len > 1 or self._children:
            # Concatenate the categories from the children
            t = []
            for ch in self.children:
                t.extend(ch.categories)
            return t
        # Terminal node: return the associated word category
        c = cast(Optional[str], self._head.get("c"))
        if c:
            return [c]
        # If we have a lemma, we must return a corresponding category
        # to ensure that zip(t.lemmas, t.categories) always works
        return [""] if self._lemma else []

    @property
    def fl(self) -> str:
        """ Return the BÍN 'fl' field of this node, if it is a terminal,
            or an empty string otherwise """
        return cast(str, self._head.get("f", ""))

    @cached_property
    def text(self) -> str:
        """ Return the original text contained within this subtree """
        if self.is_terminal:
            # Terminal node: return own text
            return self._text
        # Concatenate the text from the children
        return " ".join([ch.text for ch in self.children if ch.text])

    @cached_property
    def tidy_text(self) -> str:
        """ Return the text contained within this subtree
            after correcting its spacing """
        if self.is_terminal:
            # Terminal node: return own text
            return self._text
        # Correct the spaced text coming from the self.text attribute
        return correct_spaces(self.text)

    def _np_form(self, prop_func: Callable[["SimpleTree"], str]) -> str:
        """ Return a nominative form of the noun phrase (or noun/adjective terminal)
            contained within this subtree. Prop is a property accessor that returns
            either x.nominative, x.indefinite or x.canonical. """
        if self.is_terminal:
            # Terminal node: return its nominative form
            return prop_func(self)
        if not self.match_tag("NP"):
            # This is not a noun phrase: return its text as-is
            return self.text
        # Noun phrase:
        # Concatenate the nominative forms of the child terminals,
        # and the literal text of nested nonterminals (such as NP-POSS and CP-THT)
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
        if len(children) == 1 and children[0].tag == "CP-THT":
            # If the noun phrase consists only of a CP-THT nonterminal
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

    def _case_np(self, case_property) -> str:
        """ Return the noun phrase contained within this subtree
            after casting it to the given case """

        def prop_func(node: "SimpleTree") -> str:
            if node.is_terminal:
                return case_property.fget(node)
            if node.tag in {"NP-TITLE", "NP-MEASURE", "NP-ADDR"}:
                # For these NP types, recurse into them, since we
                # also want to cast them to the requested case
                return node._np_form(prop_func)
            return node.text

        return self._np_form(prop_func)

    @property
    def nominative_np(self) -> str:
        """ Return the nominative form of the noun phrase (or noun/adjective terminal)
            contained within this subtree """
        return self._case_np(SimpleTree.nominative)

    @property
    def accusative_np(self) -> str:
        """ Return the accusative form of the noun phrase (or noun/adjective terminal)
            contained within this subtree """
        return self._case_np(SimpleTree.accusative)

    @property
    def dative_np(self) -> str:
        """ Return the dative form of the noun phrase (or noun/adjective terminal)
            contained within this subtree """
        return self._case_np(SimpleTree.dative)

    @property
    def genitive_np(self) -> str:
        """ Return the genitive form of the noun phrase (or noun/adjective terminal)
            contained within this subtree """
        return self._case_np(SimpleTree.genitive)

    @cached_property
    def indefinite_np(self) -> str:
        """ Return the indefinite nominative form of the noun phrase
            (or noun/adjective terminal) contained within this subtree """

        def prop_func(node: "SimpleTree") -> str:
            if node.is_terminal:
                if node._cat == "gr":
                    # Cut away the definite article, if present
                    # ('hinir ungu alþingismenn' -> 'ungir alþingismenn')
                    return ""
                return node.indefinite
            return node.text

        return cut_definite_pronouns(self._np_form(prop_func))

    @cached_property
    def canonical_np(self) -> str:
        """ Return the singular indefinite nominative form of the noun phrase
            (or noun/adjective terminal) contained within this subtree """

        def prop_func(node: SimpleTree) -> str:
            """ For canonical noun phrases, cut off CP subtrees
                since they probably don't make sense any more, with the noun
                phrase having been converted to singular and all.
                The same applies to NP-POSS. """
            if node.is_terminal:
                if node.tcat == "töl" or (node.tcat == "tala" and "ft" in node._vset):
                    # If we are asking for the canonical (singular) form,
                    # cut away undeclinable numbers so that
                    # 'sautján góðglaða alþingismenn' -> 'góðglaður alþingismaður',
                    # not 'sautján góðglaður alþingismaður'; and also cut away
                    # declinable plural numbers
                    return ""
                if node._cat == "gr":
                    # Cut away the definite article, if present
                    # ('hinir ungu alþingismenn' -> 'ungur alþingismaður')
                    return ""
                return node.canonical

            if node.tag == "NP-MEASURE":
                # For these NP types, recurse into them, since we
                # want their canonical form
                return node._np_form(prop_func)

            # Cut off connected explanatory sentences, possessive noun phrases,
            # and prepositional phrases
            if any(
                node.match_tag(tag)
                for tag in ("S", "NP-POSS", "PP", "ADVP", "CP", "NP-TITLE")
            ):
                return ""

            return node.text

        return cut_definite_pronouns(self._np_form(prop_func))

    @property
    def own_text(self):
        return self._text

    def _list(self, filter_func: Callable[["SimpleTree"], bool]) -> List[str]:
        """ Return a list of word lemmas that meet the filter criteria
            within this subtree """
        if self._len > 1 or self._children:
            # Concatenate the text from the children
            t: List[str] = []
            for ch in self.children:
                t.extend(ch._list(filter_func))
            return t
        # Terminal node: return own lemma if it matches the given category
        if self._lemma and filter_func(self):
            return [self._lemma]
        return []

    @property
    def leaves(self) -> Iterator["SimpleTree"]:
        """ Generate all descendant leaf (terminal) nodes of this node,
            returning a dict with the canonical representation of
            each token/terminal match """
        for ch in self.descendants:
            if ch.is_terminal:
                yield ch

    @property
    def span(self) -> Tuple[int, int]:
        """ Returns a (start, end) tuple of token indices pointing
            to the first and the last token spanned by this subtree """
        ix = self.index
        if ix is not None:
            # This is a terminal: return its token index
            return (ix, ix)
        # Nonterminal: navigate its leaves and retrieve token indices
        start = end = None
        for t in self.leaves:
            ix = t.index or 0
            if start is None or ix < start:
                start = ix
            if end is None or ix > end:
                end = ix
        assert start is not None and end is not None
        return (start, end)

    @property
    def nouns(self):
        """ Returns the lemmas of all nouns in the subtree """
        return self._list(
            lambda t: t.tcat == "no" or t.tcat == "entity" or t._cat in _GENDERS
        )

    @property
    def verbs(self) -> List[str]:
        """ Returns the lemmas of all verbs in the subtree """
        return self._list(lambda t: t.tcat == "so")

    @property
    def persons(self) -> List[str]:
        """ Returns all person names occurring in the subtree """
        return self._list(lambda t: t.tcat == "person")

    @property
    def entities(self) -> List[str]:
        """ Returns all entity names occurring in the subtree """
        return self._list(lambda t: t.tcat == "entity")

    @property
    def proper_names(self) -> List[str]:
        """ Returns all proper names occurring in the subtree """
        return self._list(lambda t: t.tcat == "sérnafn")

    @property
    def lemmas(self) -> List[str]:
        """ Returns the lemmas of all words in the subtree """
        return self._list(lambda t: True)

    @property
    def lemmas_and_cats(self) -> List[Tuple[str, str]]:
        """ Return a list of (lemma, category) tuples for words within this subtree """
        if self._len > 1 or self._children:
            # Concatenate the categories from the children
            t = []
            for ch in self.children:
                t.extend(ch.lemmas_and_cats)
            return t
        # Terminal node: return its (lemma, category) tuple
        if not self._lemma:
            return []
        return [(self._lemma, self.lemma_cat)]

    @property
    def lemma(self) -> str:
        """ Return the lemmas of this subtree as a string """
        if self.is_terminal:
            # Shortcut for terminal node
            return self._lemma
        return " ".join(self.lemmas)

    @property
    def own_lemma(self) -> str:
        """ Return the lemma of the word token matching this terminal,
            or an empty string if this is not a terminal """
        return self._lemma if self.is_terminal else ""

    @property
    def own_lemma_mm(self) -> str:
        """ Return the middle voice lemma of the word token matching
            this terminal, or an empty string if this is not a terminal """
        # A middle voice lemma is the same as the ordinary lemma except
        # in the case of middle voice verbs; there the lemma is the
        # MM-NH form ('eignast' instead of 'eiga' for a word form
        # such as 'eignaðist'; 'dást' instead of 'dá' for a word form
        # such as 'dáðst').
        if not self.is_terminal:
            return ""
        if self.tcat != "so" or "mm" not in self.all_variants:
            # Not a middle voice verb
            return self._lemma
        # Construct and return the "-st" middle voice stem
        return BIN_Token.mm_verb_stem(self._lemma)

    def all_matches(self, pattern: str, context: ContextDict=None) -> Iterator["SimpleTree"]:
        """ Return all subtree roots, including self, that match the given pattern """
        for subtree in chain([self], self.descendants):
            if match_pattern(subtree, pattern, context):
                yield subtree

    def first_match(self, pattern: str, context: ContextDict=None) -> Optional["SimpleTree"]:
        """ Return the first subtree root, including self, that matches the given
            pattern. If no subtree matches, return None. """
        try:
            return next(self.all_matches(pattern, context))
        except StopIteration:
            return None

    def top_matches(self, pattern: str, context: ContextDict=None) -> Iterator["SimpleTree"]:
        """ Return all subtree roots, including self, that match the given pattern,
            but not recursively, i.e. we don't include matches within matches """
        if match_pattern(self, pattern, context):
            yield self
        else:
            for child in self.children:
                yield from child.top_matches(pattern, context)

    def match(self, pattern: str, context: ContextDict=None) -> bool:
        """ Return True if this subtree matches the given pattern """
        return match_pattern(self, pattern, context)


class SimpleTreeBuilder:

    """ A class for building a simplified tree from a full
        parse tree. The simplification is done according to the
        maps provided in the constructor. """

    def __init__(
        self,
        nt_map: Optional[NonterminalMap] = None,
        id_map: Optional[IdMap] = None,
        terminal_map: Optional[Mapping[str, str]] = None,
    ):
        self._nt_map: NonterminalMap = nt_map or _DEFAULT_NT_MAP
        self._id_map: IdMap = id_map or _DEFAULT_ID_MAP
        self._terminal_map: Mapping[str, str] = terminal_map or _DEFAULT_TERMINAL_MAP
        self._result: List[CanonicalTokenDict] = []
        self._stack = [self._result]
        self._scope: List[str] = [""]  # Sentinel value
        self._pushed: List[int] = []
        # The state property is a placeholder for client data
        self.state: Any = None

    def push_terminal(self, d: CanonicalTokenDict) -> None:
        """ At a terminal (token) node. The d parameter is normally a dict
            containing a canonicalized token. """
        # Check whether this terminal should be pushed as a nonterminal
        # with a single child
        cat = d["t"].split("_")[0] if "t" in d else None
        mapped_t = None if cat is None else self._terminal_map.get(cat)
        if mapped_t is None:
            # No: add as a child of the current node in the condensed tree
            self._stack[-1].append(d)
        else:
            # Yes: create an intermediate nonterminal with this terminal
            # as its only child
            # Look up the corresponding nonterminal from the id map
            mapped_id = self._id_map[mapped_t]
            # Use the human-readable name of the nonterminal
            self._stack[-1].append(
                SimpleTreeNode(
                    k="NONTERMINAL", n=cast(str, mapped_id["name"]), i=mapped_t, p=[d]
                )
            )

    def push_nonterminal(self, nt_base: str) -> None:
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
            mapped_nts = (mapped_nts,)
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
            children: List[CanonicalTokenDict] = []
            self._stack[-1].append(
                SimpleTreeNode(
                    k="NONTERMINAL",
                    n=cast(str, mapped_id["name"]),
                    i=mapped_nt,
                    p=children,
                )
            )
            self._stack.append(children)
            self._scope.append(mapped_nt)
            self._pushed[-1] += 1  # Add to number of items pushed

    def pop_nonterminal(self) -> None:
        """ Exiting a nonterminal node. Calls to pop_nonterminal() must correspond
            to calls to push_nonterminal(). """
        # Pop the same number of entries as push_nonterminal() pushed
        to_pop = self._pushed.pop()
        for _ in range(to_pop):
            self._pop_nonterminal()

    def _pop_nonterminal(self) -> None:
        """ Do the actual popping of a single level pushed by push_nonterminal() """
        children = self._stack.pop()
        mapped_nt = self._scope.pop()
        # Check whether this nonterminal has only one child, which is again
        # the same nonterminal - or a nonterminal which the parent overrides
        if len(children) == 1:

            ch0 = cast(SimpleTreeNode, children[0])

            def collapse_child(d: str) -> bool:
                """ Determine whether to cut off a child and connect directly
                    from this node to its children """
                if ch0["i"] == d:
                    # Same nonterminal category: do the cut
                    return True
                # If the child is a nonterminal that this one 'overrides',
                # cut off the child
                override = self._id_map[d].get("overrides")
                return ch0["i"] == override

            def replace_parent(d: str) -> bool:
                """ Determine whether to replace the parent with the child """
                # If the child overrides the parent, replace the parent
                override = self._id_map[ch0["i"]].get("overrides")
                return d == override

            if ch0["k"] == "NONTERMINAL":
                if collapse_child(mapped_nt):
                    # If so, we eliminate one level and move the children of the child
                    # up to be children of this node
                    stn = cast(SimpleTreeNode, self._stack[-1][-1])
                    stn["p"] = ch0["p"]
                elif replace_parent(mapped_nt):
                    # The child subsumes the parent: replace
                    # the parent by the child
                    self._stack[-1][-1] = ch0

    @property
    def result(self) -> CanonicalTokenDict:
        return self._result[0]

    @property
    def tree(self) -> SimpleTree:
        """ Create and return a SimpleTree instance rooted with the
            result of this builder """
        return SimpleTree([[self.result]])


class Annotator(ParseForestNavigator):

    """ Utility class to navigate a parse forest and annotate the
        original token list with the corresponding terminal matches """

    def __init__(self, tmap: TerminalMap) -> None:
        super().__init__()
        self._tmap = tmap

    def visit_token(self, level: int, w: Node) -> Any:
        """ At token node """
        assert w is not None
        assert w.token is not None
        ix = w.token.index  # Index into original sentence
        assert ix not in self._tmap
        t = cast(BIN_Terminal, w.terminal)
        meaning = w.token.match_with_meaning(t)
        # Map from original token to matched terminal
        self._tmap[ix] = (t, None if isinstance(meaning, bool) else meaning)
        return None


class Simplifier(ParseForestNavigator):

    """ Utility class to construct a simplified, condensed representation of
        a parse tree in a nested dictionary structure """

    def __init__(
        self,
        tokens: List[Tok],
        *,
        nt_map: Optional[NonterminalMap] = None,
        id_map: Optional[IdMap] = None,
        terminal_map: Optional[Mapping[str, str]] = None,
        first_token_index: int = 0,
    ) -> None:
        super().__init__(visit_all=True)
        self._tokens = tokens
        self._builder = SimpleTreeBuilder(nt_map, id_map, terminal_map)
        self._first_token_index = first_token_index

    def visit_token(self, level: int, w: Node) -> Any:
        """ At terminal node, matching a token """
        assert w.token is not None
        t = cast(BIN_Terminal, w.terminal)
        meaning = w.token.match_with_meaning(t)
        token_index = (w.token.index or 0) - self._first_token_index
        d = describe_token(
            token_index,
            self._tokens[token_index],
            t,
            None if isinstance(meaning, bool) else meaning,
        )
        # Convert from compact form to external (more verbose and descriptive) form
        ct = canonicalize_token(d)
        self._builder.push_terminal(ct)
        return None

    def visit_nonterminal(self, level: int, node: Node) -> Any:
        """ Entering a nonterminal node """
        assert node.nonterminal is not None
        nt = cast(BIN_Nonterminal, node.nonterminal)
        if node.is_interior or nt.is_optional:
            nt_base = ""
        else:
            nt_base = nt.first
        self._builder.push_nonterminal(nt_base)
        return None

    def process_results(self, results, node: Node) -> None:
        """ Exiting a nonterminal node """
        self._builder.pop_nonterminal()

    @property
    def tree(self) -> SimpleTree:
        """ Return a SimpleTree object """
        return self._builder.tree

    @property
    def result(self) -> CanonicalTokenDict:
        """ Return nested dictionaries """
        return self._builder.result


class AnnoTree:

    """ Encapsulates an Annotald-formatted (bracketed) parse tree.

        An Annotald-formatted string looks as follows:

        (META
            (ID-CORPUS 43bf66f3-51c4-11e6-8438-04014c605401.10)
            (ID-LOCAL greynir_corpus_00003.psd,.1)
            (URL http://www.mbl.is/sport/efstadeild/2016/07/24/ia_ibv_stadan_er_1_0/)
        )
        (S0 (S-HEADING
            (IP
                (NP-SUBJ
                    (fn_ft_kk_nf Engir (lemma enginn))
                    (no_ft_kk_nf atburðir (lemma atburður))
                )
                (NP-PRD
                    (VP
                        (so_ft_kk_lhþt_nf_sb skráðir (lemma skrá))
                    )
                )
                (ADVP (ao enn (lemma enn)))
            )
        ))

    """

    def __init__(self, txt: str) -> None:
        """ Initializes an AnnoTree from its string representation """
        self._head: Optional[CanonicalTokenDict] = None
        self._id_corpus = ""
        self._id_local = ""
        self._url = ""
        self.parse(txt)

    def as_simple_tree(self) -> Optional[SimpleTree]:
        """ Return the AnnoTree as a SimpleTree structure """
        if self._head is None:
            return None
        return SimpleTree([[self._head]])

    @property
    def id_corpus(self) -> str:
        """ Return the META ID-CORPUS field, if present """
        return self._id_corpus

    @property
    def id_local(self) -> str:
        """ Return the META ID-LOCAL field, if present """
        return self._id_local

    @property
    def url(self) -> str:
        """ Return the META URL field, if present """
        return self._url

    def parse(self, txt: str) -> None:
        """ Parse an Annotald-formatted string """
        self._head = None
        self._id_corpus = ""
        self._id_local = ""
        self._url = ""
        if not txt:
            return
        # Current character pointer
        p: int = 0
        end: int = len(txt)
        terminators: FrozenSet[str] = frozenset(("(", ")"))

        def skipspace() -> None:
            """ Advance the p index past any whitespace """
            nonlocal p
            while p < end and txt[p].isspace():
                p += 1

        def skipleft() -> bool:
            """ Advance the p index past a left parenthesis, if found """
            # Since skipright() is always called before skipleft(),
            # we don't need skipspace() here - it's already been called
            nonlocal p
            if p < end and txt[p] == "(":
                p += 1
                return True
            return False

        def skipright() -> bool:
            """ Advance the p index past a right parenthesis, if found """
            nonlocal p
            skipspace()
            if p < end and txt[p] == ")":
                p += 1
                return True
            return False

        def skipstring() -> str:
            """ Advance the p index until a parenthesis is encountered,
                and return the underlying string """
            nonlocal p
            skipspace()
            start = p
            while p < end and txt[p] not in terminators:
                # !!! TODO: There should be an escape character
                # !!! for parentheses here
                p += 1
            return txt[start:p].rstrip()

        # A stack of nested nonterminal dictionaries,
        # each having a list of children (nonterminals or terminals)
        stack: List[List[CanonicalTokenDict]] = [[]]

        while True:
            if skipright():
                # Right parenthesis
                # The enclosing nonterminal is done; pop up to the next level above
                stack.pop()
            elif skipleft():
                # Left parenthesis
                s = skipstring()
                a = s.split(maxsplit=1)
                # Extract the node identifier
                t = a[0]
                if t[0].isupper():
                    # Nonterminal node, or meta tag
                    if t == "ID-CORPUS":
                        self._id_corpus = a[1]
                        if not skipright():
                            raise ValueError("Expected right parenthesis")
                        continue
                    elif t == "ID-LOCAL":
                        self._id_local = a[1]
                        if not skipright():
                            raise ValueError("Expected right parenthesis")
                        continue
                    elif t == "URL":
                        self._url = a[1]
                        if not skipright():
                            raise ValueError("Expected right parenthesis")
                        continue
                    # Treat this node as a nonterminal with a list of children
                    children: List[CanonicalTokenDict] = []
                    if t == "META":
                        # Meta tag
                        stack[-1].append(SimpleTreeNode(k=t, i=t, p=children))
                    else:
                        # Regular nonterminal tag
                        stack[-1].append(
                            SimpleTreeNode(
                                k="NONTERMINAL",
                                i=t,
                                n=cast(str, _DEFAULT_ID_MAP[t]["name"]),
                                p=children,
                            )
                        )
                    # Push a new level
                    stack.append(children)
                else:
                    # Nonterminal node, or lemma
                    assert t[0].islower()
                    if t == "lemma":
                        # Hack: Set the lemma of the last terminal
                        assert len(stack) >= 2
                        assert len(stack[-1]) == 0
                        assert len(stack[-2]) >= 1
                        assert stack[-2][-1]["k"] != "NONTERMINAL"
                        stack[-2][-1]["s"] = a[1]
                        if not skipright():
                            raise ValueError("Expected right parenthesis")
                    else:
                        # Regular terminal node
                        v = t.split("_")
                        cat = v[0]
                        if cat == "no":
                            # Obtain the BÍN category for nouns
                            cat = (set(v) & {"kk", "kvk", "hk"}).pop()
                        # !!! TODO: The k field should, strictly speaking, reflect
                        # !!! the token type, i.e. NUMBER, AMOUNT, EMAIL, etc.
                        # The dictionary fields for terminals are as follows:
                        # k is the token type
                        # t is the terminal
                        # c is the word/terminal category
                        # x is the original token text
                        # s is the lemma, which is assigned by the "lemma" handler above
                        stack[-1].append(SimpleTreeNode(k="WORD", t=t, c=cat, x=a[1]))
                        # The terminal node might have a child (a lemma spec),
                        # so we push a dummy children list
                        stack.append([])
            else:
                # Not a left or right parenthesis:
                # either we're done or there is an error
                break

        if p < end:
            raise ValueError("String is unbalanced or not properly terminated")

        # Skip past the META tag, if present
        assert len(stack) == 1
        top = cast(List[SimpleTreeNode], stack[0])
        p = 0
        while top[p]["i"] == "META":
            p += 1
        assert p < len(top)
        # Store the first tag after META
        self._head = top[p]

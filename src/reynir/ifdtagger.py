"""

    Reynir: Natural language processing for Icelandic

    IFD tagger module

    Copyright (C) 2018 Miðeind ehf.

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


    This module implements a class that handles conversion from Reynir's
    terminal variants to the Icelandic Frequency Dictionary (IFD) tagset.

    The tagset is described here: http://www.malfong.is/files/ot_tagset_files_is.pdf

"""

from .settings import (
    UndeclinableAdjectives,
    StaticPhrases,
)
from .binparser import canonicalize_token
from .bintokenizer import TOK


class IFD_Tagset:

    """ Utility class to generate POS tags compatible with
        the Icelandic Frequency Dictionary (IFD) tagset
        (cf. http://www.malfong.is/files/ot_tagset_book_is.pdf) """

    # Strings that must be present in the grammatical form for variants
    BIN_TO_VARIANT = {
        "NF": "nf",  # Nefnifall / nominative
        "ÞF": "þf",  # Þolfall / accusative
        "ÞGF": "þgf",  # Þágufall / dative
        "EF": "ef",  # Eignarfall / possessive
        "KK": "kk",  # Karlkyn / masculine
        "KVK": "kvk",  # Kvenkyn / feminine
        "HK": "hk",  # Hvorugkyn / neutral
        "ET": "et",  # Eintala / singular
        "ET2": "et",  # Eintala / singular
        "ET3": "et",  # Eintala / singular
        "FT": "ft",  # Fleirtala / plural
        "FT2": "ft",  # Fleirtala / plural
        "FT3": "ft",  # Fleirtala / plural
        "FSB": "fsb",  # Frumstig, sterk beyging
        "FVB": "fvb",  # Frumstig, veik beyging
        "MST": "mst",  # Miðstig / comparative
        "MST2": "mst",  # Miðstig / comparative
        "ESB": "esb",  # Efsta stig, sterk beyging / superlative
        "EVB": "evb",  # Efsta stig, veik beyging / superlative
        "EST": "est",  # Efsta stig / superlative
        "EST2": "est",  # Efsta stig / superlative
        "1P": "p1",  # Fyrsta persóna / first person
        "2P": "p2",  # Önnur persóna / second person
        "3P": "p3",  # Þriðja persóna / third person
        "OP": "op",  # Ópersónuleg sögn
        "GM": "gm",  # Germynd
        "MM": "mm",  # Miðmynd
        "SB": "sb",  # Sterk beyging
        "VB": "vb",  # Veik beyging
        "NH": "nh",  # Nafnháttur
        "FH": "fh",  # Framsöguháttur
        "BH": "bh",  # Boðháttur
        "LH": "lh",  # Lýsingarháttur (nútíðar)
        "VH": "vh",  # Viðtengingarháttur
        "NT": "nt",  # Nútíð
        "ÞT": "þt",  # Þátíð
        "SAGNB": "sagnb",  # Sagnbót ('vera' -> 'hefur verið')
        "SAGNB2": "sagnb",
        "LHÞT": "lhþt",  # Lýsingarháttur þátíðar ('var lentur')
        "gr": "gr",  # Greinir
        "gr2": "gr",  # Greinir
    }

    # Create a list of BIN tags in descending order by length
    BIN_TAG_LIST = sorted(BIN_TO_VARIANT.keys(), key=lambda x: len(x), reverse=True)

    KIND_TO_TAG = {
        # !!! TBD: put in more precise tags
        "DATE": "to",
        "DATEREL": "to",
        "DATEABS": "to",
        "TIME": "to",
        "TIMESTAMP": "to",
        "TIMESTAMPREL": "to",
        "TIMESTAMPABS": "to",
        "PERCENT": "tp",
        "MEASUREMENT": "to",
    }

    CAT_TO_SCHEME = {
        "no": "_n",
        "kk": "_n",
        "kvk": "_n",
        "hk": "_n",
        "fn": "_f",
        "abfn": "_f",
        "pfn": "_f",
        "gr": "_g",
        "to": "_t",
        "töl": "_t",
        "tala": "_number",
        "raðnr": "_raðnr",
        "ártal": "_year",
        "so": "_s",
        "lo": "_l",
        "ao": "_a",
        "eo": "_a",
        "spao": "_a",
        "tao": "_a",
        "fs": "_a",
        "uh": "_a",
        "st": "_c",
        "stt": "_c",
        "nhm": "_c",
        "entity": "_e",
        "prósenta": "_t",
        "sérnafn": "_n",
        "fyrirtæki": "_n",
        "person": "_n",
        "gata": "_n",
    }

    FN_FL = {
        "sá": "a",
        "þessi": "a",
        "hinn": "a",
        "slíkur": "b",
        "sjálfur": "b",
        "samur": "b",
        "sami": "b",  # ætti að vera samur
        "þvílíkur": "b",
        "minn": "e",
        "þinn": "e",
        "sinn": "e",
        "vor": "e",
        "einhver": "o",
        "sérhver": "o",
        "nokkur": "o",
        "allnokkur": "o",
        "hvorugur": "o",
        "allur": "o",
        "mestallur": "o",
        "flestallur": "o",
        "sumur": "o",
        "enginn": "o",
        "margur": "o",
        "flestir": "o",  # ætti að vera margur
        "einn": "o",
        "annar": "o",
        "neinn": "o",
        "sitthvað": "o",
        "ýmis": "o",
        "fáeinir": "o",
        "báðir": "o",
        "hver": "s",
        "hvor": "s",
        "hvaða": "s",
        "hvílíkur": "s",
    }
    FN_SAMFALL = {  # Beygingarmyndir sem tilheyra bæði 'sá' og pfn.
        "það",
        "því",
        "þess",
        "þau",
        "þeir",
        "þá",
        "þær",
        "þeim",
        "þeirra",
    }
    FN_BÆÐI = {"sá", "það"}
    FN_PK = {
        "ég": "1",
        "þú": "2",
        "hann": "k",
        "hún": "v",
        "það": "h",
        "þér": "2",
        "vér": "1",
    }
    # Sjálfgefin fallstjórn forsetninga
    FS_FALL = {
        "af": "þ",
        "andspænis": "þ",
        "auk": "e",
        "austan": "e",
        "austur": "o",
        "að": "þ",
        "eftir": "o",  # þ kemur líka til greina
        "fjarri": "þ",
        "fram": "o",
        "framhjá": "þ",
        "frá": "þ",
        "fyrir": "o",  # þ kemur líka til greina
        "gagnvart": "þ",
        "gegn": "þ",
        "gegnt": "þ",
        "gegnum": "o",
        "handa": "þ",
        "handan": "e",
        "heim": "o",
        "hjá": "þ",
        "inn": "o",
        "innan": "o",  # e kemur líka til greina
        "innanundir": "þ",  # o kemur líka til greina (til skoðunar)
        "jafnfætis": "þ",
        "kringum": "o",
        "lengi": "e",
        "megin": "e",
        "með": "þ",  # o kemur líka til greina
        "meðal": "e",
        "meðfram": "þ",
        "milli": "e",
        "millum": "e",
        "mót": "þ",
        "móti": "þ",
        "neðan": "e",
        "niður": "o",
        "norðan": "e",
        "norður": "o",
        "nálægt": "þ",
        "nær": "þ",
        "ofan": "e",
        "sakir": "e",
        "samkvæmt": "þ",
        "samtímis": "þ",
        "snemma": "e",
        "sunnan": "e",
        "suður": "o",
        "síðla": "e",
        "sökum": "e",
        "til": "e",
        "um": "o",  # n kemur líka til greina (til skoðunar)
        "umfram": "o",
        "umhverfis": "o",
        "undan": "þ",
        "undir": "þ",  # o kemur líka til greina
        "upp": "o",
        "utan": "o",  # e kemur líka til greina
        "vegna": "e",
        "vestan": "e",
        "vestur": "o",
        "við": "o",  # þ kemur líka til greina
        "yfir": "o",  # þ kemur líka til greina
        "á": "o",  # þ kemur líka til greina
        "án": "e",
        "árla": "e",
        "ásamt": "þ",
        "í": "þ",  # o kemur líka til greina
        "öndvert": "þ",
        "úr": "þ",
        "út": "o",
    }
    # Raðtölur
    ORDINALS = frozenset(
        [
            "fyrstur",
            "annar",
            "þriðji",
            "fjórði",
            "fimmti",
            "sjötti",
            "sjöundi",
            "áttundi",
            "níundi",
            "tíundi",
            "ellefti",
            "tólfti",
            "þrettándi",
            "fjórtándi",
            "fimmtándi",
            "sextándi",
            "sautjándi",
            "átjándi",
            "nítjándi",
            "tuttugasti",
            "þrítugasti",
            "fertugasti",
            "fimmtugasti",
            "sextugasti",
            "sjötugasti",
            "átttugasti",
            "nítugasti",
            "hundraðasti",
            "tvöhundraðasti",
            "þrjúhundraðasti",
            "fjögurhundraðasti",
            "fimmhundraðasti",
            "sexhundraðasti",
            "sjöhundraðasti",
            "áttahundraðasti",
            "níuhundraðasti",
            "þúsundasti",
            "tvöþúsundasti",
            "þrjúþúsundasti",
            "fjögurþúsundasti",
            "fimmþúsundasti",
            "sexþúsundasti",
            "sjöþúsundasti",
            "áttaþúsundasti",
            "níuþúsundasti",
            "tíuþúsundasti",
            "milljónasti",
            "milljarðasti",
        ]
    )

    def __init__(self, *args, **kwargs):
        # Initialize the tagset from a token or from keyword parameters
        if len(args) == 1 and len(kwargs) == 0:
            # Single positional parameter: assume it's a token dict
            self._init_from(args[0])
        elif len(args) == 0:
            # Relay keyword parameters onwards
            self._init_from(kwargs)
        else:
            raise ValueError("Unsupported parameter list")

    def _init_from(self, t):
        """ Initialize the tagset parameters from a dict """
        self._cache = None
        self._kind = t.get("k")
        self._cat = t.get("c")
        self._fl = t.get("f")
        self._txt = t.get("x")
        if self._txt:
            self._txt = self._txt.lower()
        self._stem = t.get("s")
        self._v = t.get("v")
        if "t" in t:
            # Terminal: assemble the variants
            a = t["t"].split("_")
            self._first = a[0]
            self._tagset = set(a[1:])
        else:
            self._first = None
            self._tagset = set()
        if self._cat in {"kk", "kvk", "hk"}:
            self._tagset.add(self._cat)
        if "b" in t:
            # Mix the BIN tags into the set
            beyging = t["b"]
            for bin_tag in self.BIN_TAG_LIST:
                # This loop proceeds in descending order by tag length
                if bin_tag in beyging:
                    self._tagset.add(self.BIN_TO_VARIANT[bin_tag])
                    beyging = beyging.replace(bin_tag, "").replace("--", "")
                    if not beyging:
                        break

    def _tagstring(self):
        """ Calculate the IFD tagstring from the tagset """
        if self._kind == "PUNCTUATION":
            return self._txt
        if self._kind in self.KIND_TO_TAG:
            return self.KIND_TO_TAG[self._kind]
        key = self._first or self._cat or self._kind
        scheme = self.CAT_TO_SCHEME.get(key)
        if scheme is None:
            return "[" + key + "]"  # !!! TODO
        func = getattr(self, scheme)
        return scheme[1:] if func is None else func()

    def has_tag(self, tag):
        """ Returns True if the tagset contains the given feature,
            i.e. kk, kvk, þgf, nh, p3, vb, etc. """
        return tag in self._tagset

    def __str__(self):
        """ Return the tags formatted as an IFD compatible string """
        if self._cache is None:
            self._cache = self._tagstring()
        return self._cache

    def _n(self):
        return (
            "n"
            + self._kyn()
            + self._tala()
            + self._fall()
            + self._greinir()
            + self._sérnöfn()
        )

    def _l(self):
        return (
            "l"
            + self._kyn()
            + self._tala()
            + self._fall()
            + self._beyging()
            + self._stig()
        )

    def _f(self):
        return (
            "f" + self._flokkur_f() + self._kyn_persóna() + self._tala() + self._fall()
        )

    def _g(self):
        return "g" + self._kyn() + self._tala() + self._fall()

    def _t(self):
        # if self._cat == "töl" and self._fl == "ob":
        # Tekið út eftir að mörkun var bætt við í Reynir.grammar
        # Óbeygt töluorð
        #    return "ta"
        return (
            "t"
            + self._flokkur_t()
            + self._kyn()
            + self._tala(default="f")
            + self._fall()
        )

    def _s(self):
        if "lh" in self._tagset and "nt" in self._tagset:
            # Lýsingarháttur nútíðar
            return "slg"  # Alltaf germynd - gæti hugsanlega verið miðmynd
        if "lhþt" in self._tagset:
            # Lýsingarháttur þátíðar
            return "sþ" + self._mynd() + self._kyn() + self._tala() + self._fall()
        if "nh" in self._tagset:
            # Nafnháttur
            if "þt" in self._tagset:
                return "sn" + self._mynd() + "--þ"
            return "sn" + self._mynd()
        if "bh" in self._tagset:
            # Boðháttur
            return "sb" + self._mynd() + "2" + self._tala() + "n"  # Alltaf 2.p. nútíð
        if "sagnb" in self._tagset:
            # Sagnbót
            return "ss" + self._mynd()
        return (
            "s"
            + self._háttur()
            + self._mynd()
            + self._persóna()
            + self._tala()
            + self._tíð()
        )

    def _a(self):
        return "a" + self._flokkur_a() + self._stig_a()

    def _c(self):
        return "c" + self._flokkur_c()

    def _e(self):
        if self._txt[0].isupper():
            return "nxex-s"  # Sérnafn, óþekkt kyn, óþekkt fall
        return "e"

    def _x(self):
        return "x"

    def _number(self):
        return "tfkfn" if self._v == 11 or self._v % 10 != 1 else "tfken"

    def _raðnr(self):
        if self._tagset:
            return "l" + self._kyn() + "e" + self._fall() + "vf"
        # Lýsingarorð, eintala, veik beyging, frumstig. Kyn og fall óþekkt
        return "lxexvf"

    def _year(self):
        return "ta"

    def _kyn(self):
        if "kk" in self._tagset:
            return "k"
        if "kvk" in self._tagset:
            return "v"
        if "hk" in self._tagset:
            return "h"
        return "x"

    def _tala(self, default="e"):
        if "ft" in self._tagset:
            return "f"
        elif "et" in self._tagset:
            return "e"
        return default

    def _fall(self, default="n"):
        if "nf" in self._tagset:
            return "n"
        if "þf" in self._tagset:
            return "o"
        if "þgf" in self._tagset:
            return "þ"
        if "ef" in self._tagset:
            return "e"
        return default

    def _greinir(self):
        return "g" if "gr" in self._tagset else ""

    def _sérnöfn(self):
        if not self._stem:
            return ""
        if self._fl in {"örn", "göt", "lönd"}:
            return "ö" if "gr" in self._tagset else "-ö"
        if self._kind == "PERSON":
            return "-m"
        if self._kind == "CURRENCY":
            # !!! TBD
            return "e" if "gr" in self._tagset else "-e"
        if self._stem[0].isupper():
            # Sérnafn
            return "s" if "gr" in self._tagset else "-s"
        return ""

    def _stig(self):
        if "esb" in self._tagset or "evb" in self._tagset:
            return "e"
        if "mst" in self._tagset:
            return "m"
        return "f"

    def _beyging(self):
        if self._stem in UndeclinableAdjectives.ADJECTIVES:
            return "o"
        if "fsb" in self._tagset or "esb" in self._tagset:
            return "s"
        if "fvb" in self._tagset or "evb" in self._tagset or "mst" in self._tagset:
            return "v"
        if self._stem in self.ORDINALS:
            return "v"
        return "o"

    def _flokkur_f(self):
        if self._cat == "abfn":
            return "p"  # OTB flokkar abfn. með pfn.
        if self._cat == "pfn":
            return "p"
        if self._txt in self.FN_SAMFALL and self._stem in self.FN_BÆÐI:
            return "p"
        return self.FN_FL.get(self._stem, "x")

    def _kyn_persóna(self):
        if self._stem in self.FN_PK:
            return self.FN_PK[self._stem]
        if "kk" in self._tagset:
            return "k"
        if "kvk" in self._tagset:
            return "v"
        if "hk" in self._tagset:
            return "h"
        if "p1" in self._tagset:
            return "1"
        if "p2" in self._tagset:
            return "2"
        return "x"

    def _flokkur_t(self):
        if self._kind == "PERCENT":
            return "p"
        return "f"

    def _mynd(self):
        return "m" if "mm" in self._tagset else "g"

    def _háttur(self):
        # if "nh" in self._tagset:
        #    return "n"
        if "bh" in self._tagset:
            return "b"
        if "vh" in self._tagset:
            return "v"
        # if "sagnb" in self._tagset:
        #    return "s"
        if "lh" in self._tagset and "nt" in self._tagset:
            return "l"
        return "f"

    def _tíð(self):
        return "þ" if "þt" in self._tagset else "n"

    def _persóna(self):
        if "op" in self._tagset:
            return "3"
        if "p1" in self._tagset:
            return "1"
        if "p2" in self._tagset:
            return "2"
        return "3"

    def _stig_a(self):
        if "mst" in self._tagset:
            return "m"
        if "est" in self._tagset:
            return "e"
        return ""

    def _flokkur_a(self):
        if self._cat == "uh":
            return "u"
        if self._cat == "fs":
            return self._fall(default=self.FS_FALL.get(self._stem, "o"))
        return "a"

    def _flokkur_c(self):
        if self._first == "stt":
            # 'sem', 'er' as connective conjunctions
            return "t"
        if self._cat == "nhm":
            return "n"
        return ""

    @classmethod
    def word_tag_stream(cls, sentence_stream):
        """ Generator of a (word, tag) stream from a raw token stream.
            Both the input and the output streams are segmented into
            sentences. """
        for sent in sentence_stream:
            if not sent:
                continue
            output = []
            for t in sent:
                x = t.get("x")
                if not x:
                    continue
                if t.get("k", TOK.WORD) == TOK.PUNCTUATION:
                    output.append((x, x))
                    continue
                canonicalize_token(t)
                if " " in x:
                    lower_x = x.lower()
                    if StaticPhrases.has_details(lower_x):
                        # This is a static multi-word phrase
                        tags = StaticPhrases.tags(lower_x)
                        output.extend(zip(x.split(), tags))
                    else:
                        tag = str(cls(t))
                        for part in x.split():
                            # !!! TODO: this needs to be made more intelligent and detailed
                            if part in {"og", "eða"}:
                                output.append((part, "c"))
                            else:
                                output.append((part, tag or "Unk"))
                else:
                    tag = str(cls(t))
                    output.append((x, tag or "Unk"))
            if output:
                yield output

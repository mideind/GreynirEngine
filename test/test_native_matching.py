"""

    test_native_matching.py

    Tests for the native (C++) token/terminal matching fast path
    (build_matching_table()/encode_token_matching_data() in binparser.py
    and evalMatch() in eparser.cpp). Verifies that the fast path is
    enabled by default, produces results identical to Python matching,
    reports zero discrepancies in parity mode, and is automatically
    disabled for parser subclasses whose tokens may match terminals
    in ways that the fast path does not replicate.

"""

import os
import random
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional, Tuple

from tokenizer import TOK
from tokenizer.definitions import BIN_Tuple

from reynir import Greynir
from reynir._eparser import lib as eparser, ffi  # type: ignore
from reynir.binparser import BIN_Token, encode_token_matching_data
from reynir.fastparser import Fast_Parser, ParseJob

# A corpus exercising all producible token kinds and all families of
# token/terminal matching: strong and lemma literal terminals, category
# terminals (nouns with/without the definite article, adjectives with
# degrees and subject cases, adverbs, pronouns, number words), verb
# terminals (argument frames, impersonal/oblique subjects, middle voice,
# past participle, supine, expletives), prepositions, person and street
# names, abbreviations, unknown/foreign words, and the various
# non-word token kinds (numbers, amounts, percentages, dates, times,
# timestamps, measurements, e-mail addresses, URLs, domains, hashtags,
# usernames, telephone numbers, molecules, companies and entities).
# Sentences that do not parse still exercise matching and are valuable
# here; the corpus is also used for token kind coverage checks below.
SENTENCES = [
    "Ása sá sól.",
    "Konan sem kom í heimsókn í gær ætlar að kaupa nýja íbúð í miðbænum.",
    "Hr. Jón Jónsson býr á Laugavegi 26 og á 3,4 milljónir króna í banka.",
    "Verðbólgan hefur aukist verulega, þ.e.a.s. um 5,6%, á síðustu mánuðum.",
    "Xylofonn og Kwerty eru ekki íslensk orð.",
    "Hinn 17. júní 2011 var lýðveldið Ísland 67 ára gamalt.",
    "Þórunn Ólafsdóttir varð sér úti um brimsalta poka af poppi.",
    "Það rignir sjaldan í Reykjavík í júlí en þó gerist það stundum.",
    "Bandaríkin og Evrópusambandið gerðu með sér nýjan viðskiptasamning.",
    "Kötturinn, sem heitir Brandur, veiddi þrjár mýs í nótt.",
    # Person names, titles
    "Guðrún Helgadóttir forsætisráðherra hitti Pál Ólafsson og frú Sigríði í gær.",
    # Currency amounts, percentages, numbers
    "Bíllinn kostaði 4,5 milljónir króna og lækkaði um 12,5% í verði.",
    "Fyrirtækið greiddi 1.200 USD fyrir hugbúnaðinn og 45 EUR fyrir þjónustuna.",
    # Time, absolute and relative dates
    "Fundurinn hefst klukkan 14:30 þriðjudaginn 5. mars 2024 í aðalbyggingunni.",
    "Árið 1944 varð Ísland lýðveldi og 17. júní er þjóðhátíðardagurinn.",
    # Timestamps, absolute and relative
    "Tölvupósturinn barst 2024-03-05 14:30 og var lesinn strax.",
    "Afmælið er 17. júní kl. 15:00 í sumar.",
    # Ordinals
    "Hún varð í 2. sæti í keppninni um helgina.",
    # Measurements
    "Vegalengdin er 42,2 km og hitinn fór í 15,5 gráður í morgun.",
    # E-mail, telephone, domain, hashtag, URL, username
    "Sendu póst á jon@example.is eða hringdu í síma 581-2345 fyrir hádegi.",
    "Umræðan um #veðrið á vefnum visir.is var fjörug í gærkvöldi.",
    "Nánari upplýsingar má finna á https://greynir.is um helgina.",
    "Hún merkti @jonjons og @gudrun í færslunni á miðlinum.",
    # Number with letter, street names
    "Fjölskyldan flutti af Laugavegi 12 á Skólavörðustíg 4b.",
    # Abbreviations, meanings without declension info
    "Hr. Jón og dr. Páll komu ásamt fleiri gestum á fundinn.",
    # Personal and reflexive pronouns
    "Hann meiddi sig illa og hún skammaði sjálfa sig fyrir það.",
    # Impersonal verbs, oblique subjects
    "Mig langar að fara heim því að mér leiðist svo hérna.",
    # Middle voice verbs
    "Þeir hittust í bænum og ræddust lengi við um málið.",
    # Past participle, supine
    "Verkinu er löngu lokið og húsið hefur verið málað að utan.",
    # Adjectives with subject case, comparatives, superlatives
    "Hún er samþykk tillögunni en þetta er samt besta lausnin og miklu skemmtilegri en hinar.",
    # Unknown/foreign words, proper name terminals
    "Forritið TensorFlow og tólið grep eru notuð í verkefninu.",
    # Companies and entities
    "Microsoft Word er vinsælt forrit frá Microsoft Corporation.",
    "Össur hf. og Marel seldu vörur til útlanda í fyrra.",
    # Molecules
    "Losun CO2 jókst um fimm prósent milli ára.",
    # Quotes and punctuation variety (does not currently parse,
    # but exercises punctuation and literal terminal matching)
    "„Komdu sæll,“ sagði hún — og hann svaraði: „Sömuleiðis!“",
    # Undeclinable and declinable number words
    "Tuttugu og þrír hestar, fimm kýr og tólf kindur voru á bænum.",
    # Expletive verbs
    "Það snjóaði mikið í nótt og það verður kalt á morgun.",
    # Question words, interrogative form
    "Hvenær kemur þú og hverjir verða með þér í ferðinni?",
    # Roman ordinal, year range
    "Elísabet II. Bretadrottning ríkti frá 1952 til 2022.",
]

# Token kinds that the corpus above must produce, so that native
# matching is exercised (or correctly bypassed) for all of them
REQUIRED_TOKEN_KINDS = frozenset(
    (
        TOK.WORD,
        TOK.PERSON,
        TOK.ENTITY,
        TOK.COMPANY,
        TOK.PUNCTUATION,
        TOK.NUMBER,
        TOK.NUMWLETTER,
        TOK.ORDINAL,
        TOK.PERCENT,
        TOK.AMOUNT,
        TOK.YEAR,
        TOK.DATEABS,
        TOK.DATEREL,
        TOK.TIME,
        TOK.TIMESTAMPABS,
        TOK.TIMESTAMPREL,
        TOK.MEASUREMENT,
        TOK.DOMAIN,
        TOK.HASHTAG,
        TOK.EMAIL,
        TOK.TELNO,
        TOK.URL,
        TOK.MOLECULE,
        TOK.USERNAME,
    )
)


# Sentences with verbs in all sorts of forms, for the tests of native
# matching of verb terminals: impersonal verbs with subjects in oblique
# cases, middle voice, past participles in various cases, supine,
# imperative (also clipped), subjunctive, question forms with a clitic,
# expletives, abbreviated and unknown verbs, verbs with zero to two
# arguments, and adjectives that take a subject in an oblique case
VERB_SENTENCES = [
    "Mig langar að fara heim en mér þykir það samt leitt.",
    "Hana dreymdi illa og hún hafði ekki sofið vel.",
    "Það rignir og það snjóar og hann blæs á móti.",
    "Farðu út og kom þú aftur, far vel og gakktu hægt.",
    "Ertu kominn, viltu kaffi, áttu bíl og gerðirðu þetta?",
    "Bókin var lesin, húsin voru byggð og mennirnir voru handteknir.",
    "Hann sagðist hafa eignast barn og þau kynntust í skólanum.",
    "Henni var gefin bókin og honum voru sagðar sögurnar.",
    "Ég hefði viljað að hann kæmi fyrr og færi seinna.",
    "Mér líkar þetta, hann vantar peninga og okkur sárnaði framkoman.",
    "Þess gætir víða og misskilnings gætti í málinu.",
    "Hann gaf henni blóm, sýndi þeim húsið og rændi þá aleigunni.",
    "Hún kenndi börnunum íslensku og spurði manninn spurningar.",
    "Þeir veipuðu og gúggluðu þetta en dílaði hún við það?",
    "Ath. að fundurinn hefst kl. 10 og honum lýkur um hádegi.",
    "Sofandi maðurinn var vakinn af hlæjandi börnum.",
    "Hann er samþykkur tillögunni, líkur föður sínum og fullur efasemda.",
    "Við höfum verið beðin um að láta vita ef eitthvað breytist.",
    "Skipið hefur sokkið, ísinn hefur bráðnað og sólin er sest.",
    "Honum tókst að opna dyrnar og henni leiddist biðin.",
    "Sástu hann, vissirðu þetta og hélstu að hún kæmi?",
    "Hún lét sig hverfa, þau gerðu sér dagamun og hann dreif sig af stað.",
    "Því var haldið fram að honum hefði verið sagt upp.",
    "Stjórnin kvaðst myndu endurskoða ákvörðunina og óskaði eftir fresti.",
]


def _token_records(
    fp: Fast_Parser, sentences: List[str]
) -> Iterator[Tuple[BIN_Token, Any]]:
    """Generate the distinct tokens of the sentences, as wrapped by the
    parser, with their packed matching data"""
    g = Greynir()
    table = fp._matching_table
    assert table is not None
    seen = set()
    for sentence in sentences:
        for tok in fp._wrap(list(g.tokenize(sentence))):
            if tok.key in seen:
                continue
            seen.add(tok.key)
            data = encode_token_matching_data(tok, table, fp._verb_profiles)
            yield tok, ffi.new("BYTE[]", data)


def _compare_native_with_python(
    fp: Fast_Parser, sentences: List[str], *, verbs_only: bool = False
) -> Dict[str, int]:
    """For the distinct tokens of the sentences and (nearly) all terminals
    of the grammar, check that every match that the C++ core would decide
    by itself is decided the way that BIN_Token.matches() decides it.
    The parser only asks about the terminals that its predictions lead
    to; here, they are all asked about. Literal terminals, which are four
    out of five and are simple, are only checked for every sixth token,
    to keep the running time down. Returns counts of what was seen."""
    count = dict(native=0, python=0, verb_native=0, verb_true=0, tokens=0)
    terminals = fp._terminals
    for tok, rec in _token_records(fp, sentences):
        count["tokens"] += 1
        with_literals = count["tokens"] % 6 == 0 and not verbs_only
        for ix, t in terminals.items():
            first = getattr(t, "first", "")
            if verbs_only and first != "so":
                continue
            if t.is_literal and not with_literals:
                continue
            answer = eparser.nativeMatch(fp._c_parser, rec, ix)
            if answer < 0:
                # Python is asked
                count["python"] += 1
                continue
            expected = tok.matches(t)
            assert bool(answer) == expected, (tok, t)
            count["native"] += 1
            if first == "so" and not t.is_literal:
                count["verb_native"] += 1
                count["verb_true"] += expected
    return count


_MODES = {
    # Native matching, the default
    "native": {},
    # Native matching checked against Python matching for every evaluation;
    # the Python result is the one used, so the forest is that of Python matching
    "parity": {"GREYNIR_MATCHING_PARITY": "1"},
    # Python matching only
    "python": {"GREYNIR_DISABLE_CPP_MATCHING": "1"},
}


@contextmanager
def _matching_mode(mode: str) -> Iterator[Greynir]:
    """Yield a fresh Greynir instance whose parser uses the given matching mode"""
    env = _MODES[mode]
    keys = {k for m in _MODES.values() for k in m}
    old = {k: os.environ.get(k) for k in keys}
    try:
        for k in keys:
            os.environ.pop(k, None)
        os.environ.update(env)
        # Discard the cached parser so that a fresh one is constructed
        # under the current environment settings
        Greynir.cleanup()
        yield Greynir()
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        Greynir.cleanup()


def _parse_results(g: Greynir) -> List[Optional[int]]:
    """Parse the corpus. Returns, per sentence, the number of parse tree
    combinations in the forest (or None if the sentence did not parse).
    We compare forest sizes since they are fully determined by the
    token/terminal match results, which is exactly what this module tests.
    (Reduced trees are nowadays deterministic as well; see test_parse.py::
    test_deterministic_reduction.)"""
    results: List[Optional[int]] = []
    for s in SENTENCES:
        r = g.parse_single(s)
        results.append(None if r is None or r.tree is None else r.combinations)
    return results


def test_native_matching_enabled_by_default():
    fp = Fast_Parser()
    try:
        assert fp.uses_native_matching
    finally:
        fp.cleanup()


def test_corpus_token_coverage():
    """The corpus must produce all required token kinds, so that the
    other tests in this module exercise the full matching surface"""
    g = Greynir()
    kinds = set()
    for s in SENTENCES:
        for t in g.tokenize(s):
            kinds.add(t.kind)
    missing = REQUIRED_TOKEN_KINDS - kinds
    assert not missing, "Corpus does not produce token kinds: {0}".format(
        ", ".join(sorted(TOK.descr[k] for k in missing))
    )


def test_native_python_equivalence():
    """The native fast path must produce exactly the same parse forests as
    Python matching, with no discrepancy in any single match evaluation.
    The parity mode run supplies the Python matching forests, since it uses
    the Python result for every evaluation, so this doesn't need a separate
    Python-only pass over the corpus."""
    with _matching_mode("native") as g:
        native = _parse_results(g)
        assert g.parser.uses_native_matching
    with _matching_mode("parity") as g:
        python = _parse_results(g)
        fp = g.parser
        assert fp.uses_native_matching
        assert fp.parity_mismatches == 0
    assert native == python
    # Sanity check: nearly all of the corpus should actually parse
    assert sum(1 for r in native if r is not None) >= len(SENTENCES) - 2


def test_python_matching_switch():
    """GREYNIR_DISABLE_CPP_MATCHING must switch the parser to Python matching,
    which must give the same forest as native matching"""
    sentence = SENTENCES[2]
    with _matching_mode("native") as g:
        native = g.parse_single(sentence).combinations
    with _matching_mode("python") as g:
        assert not g.parser.uses_native_matching
        assert g.parse_single(sentence).combinations == native


def _combinations(fp: Fast_Parser) -> List[Optional[int]]:
    """Parse the corpus with the given parser. Returns, per sentence, the
    number of parse trees in the forest, or None if there is no parse."""
    g = Greynir()
    results: List[Optional[int]] = []
    for s in SENTENCES:
        forest = fp.go_no_exc(list(g.tokenize(s)))
        results.append(
            None if forest is None else Fast_Parser.num_combinations(forest)
        )
    return results


def test_gate_token_subclass_with_verb_hooks():
    """A parser whose tokens are of a class derived from BIN_Token, which
    only overrides the hooks that BIN_Token.verb_matches() calls (as the
    tokens of GreynirCorrect do), uses native matching. Verb terminals are
    matched with verbs in Python, so the overrides are in effect."""

    class StrictToken(BIN_Token):
        def __init__(self, t, original_index):
            super().__init__(t, original_index)
            self.extra = 1

        @classmethod
        def verb_matches_arguments(cls, key):
            # Don't allow verbs to have two arguments
            return key.count("_") < 2 and super().verb_matches_arguments(key)

    class StrictParser(Fast_Parser):
        @staticmethod
        def wrap_token(t, ix):
            return StrictToken(t, ix)

    class PythonStrictParser(StrictParser):
        _USE_CPP_MATCHING = False

    assert StrictParser._native_token_class() is StrictToken
    fp = Fast_Parser()
    sfp = StrictParser()
    pfp = PythonStrictParser()
    try:
        assert sfp.uses_native_matching
        assert not pfp.uses_native_matching
        strict = _combinations(sfp)
        # The same results as with Python matching throughout
        assert strict == _combinations(pfp)
        # ...and not the same as with normal tokens
        assert strict != _combinations(fp)
    finally:
        fp.cleanup()
        sfp.cleanup()
        pfp.cleanup()


def test_gate_token_subclass_parity(monkeypatch):
    """Native matching of tokens of a derived class agrees with
    Python matching in every single evaluation"""

    class MyToken(BIN_Token):
        @classmethod
        def verb_is_strictly_impersonal(cls, verb, form):
            return False

    class MyParser(Fast_Parser):
        @staticmethod
        def wrap_token(t, ix):
            return MyToken(t, ix)

    monkeypatch.setenv("GREYNIR_MATCHING_PARITY", "1")
    fp = MyParser()
    try:
        assert fp.uses_native_matching
        results = _combinations(fp)
        assert fp.parity_mismatches == 0
        assert sum(1 for r in results if r is not None) >= len(SENTENCES) - 2
    finally:
        fp.cleanup()


def test_gate_token_subclass_with_other_overrides():
    """A parser whose tokens may match terminals differently from
    BIN_Token in ways that the native fast path does not know about
    automatically falls back to Python matching"""

    class WordToken(BIN_Token):
        def matches_WORD(self, terminal):
            return super().matches_WORD(terminal)

    class KeyToken(BIN_Token):
        @property
        def key(self):
            return super().key

    class HashToken(BIN_Token):
        def __hash__(self):
            return 1

    class GrandchildToken(WordToken):
        pass

    class NotAToken:
        def __init__(self, t, ix):
            pass

    for token_class in (WordToken, KeyToken, HashToken, GrandchildToken, NotAToken):

        class MyParser(Fast_Parser):
            @staticmethod
            def wrap_token(t, ix, token_class=token_class):
                return token_class(t, ix)

        assert MyParser._native_token_class() is None, token_class.__name__

    class WordParser(Fast_Parser):
        @staticmethod
        def wrap_token(t, ix):
            return WordToken(t, ix)

    fp = WordParser()
    try:
        assert not fp.uses_native_matching
    finally:
        fp.cleanup()

    class WrappingParser(Fast_Parser):
        def _wrap(self, tokens):
            return super()._wrap(tokens)

    assert WrappingParser._native_token_class() is None

    # A parser that wraps its tokens in plain BIN_Token objects, in
    # its own way, does use native matching
    class PlainParser(Fast_Parser):
        @staticmethod
        def wrap_token(t, ix):
            return BIN_Token(t, ix)

    assert PlainParser._native_token_class() is BIN_Token


def test_all_terminals_against_python():
    """Every match that the core decides natively, for any terminal of the
    grammar and any token of the test sentences, is what Python decides"""
    fp = Fast_Parser()
    try:
        assert fp.uses_native_matching
        count = _compare_native_with_python(fp, SENTENCES + VERB_SENTENCES)
        assert count["tokens"] > 300
        # Nearly everything is decided natively...
        assert count["native"] > 30 * count["python"]
        # ...verb terminals included, and they do match some verbs
        assert count["verb_native"] > 50_000
        assert count["verb_true"] > 1000
    finally:
        fp.cleanup()


def test_verb_terminals_with_random_forms():
    """Verb terminals against verbs with pseudo-random inflection strings:
    combinations of grammatical features that are rare or absent in BÍN,
    but which BIN_Token.verb_matches() has an opinion on all the same"""
    rnd = random.Random(1904)
    lemmas = [
        # With zero, one and two arguments, impersonal, middle voice only,
        # with subjects in oblique cases, composite and unknown
        "vera", "hafa", "fara", "gefa", "segja", "kenna", "spyrja", "ræna",
        "langa", "þykja", "dreyma", "vanta", "líka", "gæta", "rigna", "snjóa",
        "eignast", "eigna", "kynnast", "kynna", "takast", "leiðast", "sárna",
        "frá-segja", "endur-skoða", "gúggla", "veipa", "xyzzyja",
    ]

    def random_form() -> str:
        parts = []
        if rnd.random() < 0.15:
            parts.append("OP")
        if rnd.random() < 0.15:
            parts.append("það")
        parts.append(rnd.choice(("GM", "GM", "MM")))
        mood = rnd.choice(("FH", "FH", "VH", "NH", "BH", "LHÞT", "LH-NT", "SAGNB"))
        parts.append(mood)
        if mood == "LHÞT":
            parts.append(rnd.choice(("SB", "VB")))
            parts.append(rnd.choice(("KK", "KVK", "HK")))
            parts.append(rnd.choice(("NF", "ÞF", "ÞGF", "EF")) + rnd.choice(("ET", "FT")))
        elif mood in ("FH", "VH"):
            parts.append(rnd.choice(("NT", "ÞT")))
            parts.append(rnd.choice(("1P", "2P", "3P")))
            parts.append(rnd.choice(("ET", "FT")))
        elif mood == "BH":
            if rnd.random() < 0.5:
                parts.append("ST")
            parts.append(rnd.choice(("ET", "FT")))
        if rnd.random() < 0.1:
            parts.append("SP")
        return "-".join(parts)

    fp = Fast_Parser()
    try:
        table = fp._matching_table
        assert table is not None
        so = [
            (ix, t)
            for ix, t in fp._terminals.items()
            if getattr(t, "first", "") == "so" and not t.is_literal
        ]
        num_true = num_subj_true = 0
        for _ in range(500):
            lemma = rnd.choice(lemmas)
            form = "-" if rnd.random() < 0.03 else random_form()
            meanings = [BIN_Tuple(lemma, 0, "so", "alm", "orðið", form)]
            tok = BIN_Token(TOK.Word("orðið", meanings), 0)
            rec = ffi.new(
                "BYTE[]", encode_token_matching_data(tok, table, fp._verb_profiles)
            )
            for ix, t in so:
                answer = eparser.nativeMatch(fp._c_parser, rec, ix)
                assert answer >= 0
                expected = tok.matches(t)
                assert bool(answer) == expected, (lemma, form, t)
                num_true += expected
                num_subj_true += expected and t.is_subj
        assert num_true > 2000
        assert num_subj_true > 100
    finally:
        fp.cleanup()


def test_verb_terminals_with_hooks():
    """Verb terminals are matched natively for tokens of a class that
    overrides the methods that BIN_Token.verb_matches() calls, with those
    methods being respected (this is what the tokens of GreynirCorrect do)"""

    class HookToken(BIN_Token):
        _RESTRICTIVE_VARIANTS = ("sagnb", "lhþt", "bh")

        @classmethod
        def verb_is_strictly_impersonal(cls, verb, form):
            return verb.startswith("d")

        @classmethod
        def verb_cannot_be_impersonal(cls, verb, form):
            return any(f in form for f in ("BH", "NH", "FT"))

        @classmethod
        def verb_subject_matches(cls, verb, subj):
            return super().verb_subject_matches(verb, subj) or verb.startswith("l")

        @classmethod
        def verb_matches_arguments(cls, key):
            return super().verb_matches_arguments(key) or key.endswith("a_þgf")

    class HookParser(Fast_Parser):
        @staticmethod
        def wrap_token(t, ix):
            return HookToken(t, ix)

    fp = Fast_Parser()
    hfp = HookParser()
    try:
        assert hfp.uses_native_matching
        count = _compare_native_with_python(
            hfp, SENTENCES + VERB_SENTENCES, verbs_only=True
        )
        plain = _compare_native_with_python(
            fp, SENTENCES + VERB_SENTENCES, verbs_only=True
        )
        assert count["python"] == 0
        assert count["verb_native"] == plain["verb_native"] > 50_000
        # The hooks make a difference
        assert count["verb_true"] != plain["verb_true"]
    finally:
        fp.cleanup()
        hfp.cleanup()


def test_verb_terminals_with_own_verb_matches():
    """If the class of the tokens has its own verb_matches() method, verb
    terminals are matched with verbs in Python, and everything else
    natively as usual"""

    class OwnToken(BIN_Token):
        @classmethod
        def verb_matches(cls, verb, terminal, form):
            return "NH" in form

    class OwnParser(Fast_Parser):
        @staticmethod
        def wrap_token(t, ix):
            return OwnToken(t, ix)

    fp = OwnParser()
    try:
        assert fp.uses_native_matching
        assert fp._verb_profiles is None
        count = _compare_native_with_python(fp, VERB_SENTENCES, verbs_only=True)
        # Verb terminals are decided natively for the tokens that have
        # no verb meanings, and in Python for those that do
        assert count["native"] > 0 and count["python"] > 0
        assert count["verb_true"] == 0
        # The method is in effect: any infinitive matches any verb terminal
        g = Greynir()
        tok = fp._wrap(list(g.tokenize("fara")))[0]
        so = [t for t in fp._terminals.values() if getattr(t, "first", "") == "so"]
        assert all(tok.matches(t) for t in so if not t.is_literal)
    finally:
        fp.cleanup()


def test_prefilled_matching_cache(monkeypatch):
    """When a token is seen for the first time, most terminals are marked
    as not matching it without being evaluated one by one. None of
    those may match the token."""
    # Nothing is prefilled in parity mode, where every match is evaluated
    monkeypatch.delenv("GREYNIR_MATCHING_PARITY", raising=False)
    fp = Fast_Parser()
    try:
        size = (fp.grammar.num_terminals + 1 + 3) // 4
        num_prefilled = num_tokens = num_nonwords = 0
        for tok, rec in _token_records(fp, SENTENCES + VERB_SENTENCES[0:6]):
            num_tokens += 1
            if tok.t0 != TOK.WORD:
                num_nonwords += 1
            elif num_tokens % 5:
                # All tokens that are not words, and every fifth word
                continue
            cache = ffi.new("BYTE[]", size)
            eparser.prefillMatchCache(fp._c_parser, cache, rec)
            # Terminal 0 does not exist; its entry marks a prefilled cache
            assert cache[0] & 3 == 3
            for ix, t in fp._terminals.items():
                value = (cache[ix >> 2] >> ((ix & 3) << 1)) & 3
                if value:
                    # 2 means that the terminal is known not to match
                    assert value == 2
                    assert not tok.matches(t), (tok, t)
                    num_prefilled += 1
        assert num_nonwords > 30
        # Most terminals are prefilled, for most tokens
        assert num_prefilled > 4000 * num_nonwords
    finally:
        fp.cleanup()


def test_buffer_handover(monkeypatch):
    """The parser hands the buffers of the tokens that have been seen
    before - the matching cache and the packed matching data - over to
    the C++ core when it calls it, so the core only calls back to ask
    for the buffers of tokens that are new. The results must not
    depend on which way the core gets a buffer."""
    calls = {"alloc": 0, "data": 0}
    alloc_cache = ParseJob.alloc_cache
    token_matching_data = ParseJob.token_matching_data

    def counting_alloc_cache(self, token, size):
        calls["alloc"] += 1
        return alloc_cache(self, token, size)

    def counting_token_matching_data(self, token):
        calls["data"] += 1
        return token_matching_data(self, token)

    monkeypatch.setattr(ParseJob, "alloc_cache", counting_alloc_cache)
    monkeypatch.setattr(ParseJob, "token_matching_data", counting_token_matching_data)

    def results(g: Greynir) -> List[Any]:
        result: List[Any] = []
        for s in SENTENCES:
            r = g.parse_single(s)
            assert r is not None
            if r.tree is None:
                result.append(("error", r.err_index))
            else:
                result.append((r.combinations, r.score, r.tree.flat))
        return result

    with _matching_mode("native") as g:
        num_tokens = sum(len(list(g.tokenize(s))) for s in SENTENCES)
        first = results(g)
        # In the first pass, the core asks for the buffers of the tokens
        # that it has not seen before: of most tokens, but not all
        first_calls = dict(calls)
        assert num_tokens // 2 < first_calls["alloc"] < num_tokens
        assert num_tokens // 2 < first_calls["data"] < num_tokens
        # In the second pass, it has no need to ask for anything
        second = results(g)
        assert calls == first_calls
        assert second == first
        # Some sentences parse, and some don't
        assert sum(r[0] == "error" for r in first) in range(1, 3)
    # Without hand-over (callbacks only), the results are the same
    with _matching_mode("native") as g:
        monkeypatch.setattr(
            ParseJob, "known_buffers", lambda self: (ffi.NULL, ffi.NULL)
        )
        assert results(g) == first
        assert calls["alloc"] > first_calls["alloc"] + num_tokens // 2


def test_gate_class_flag():
    """Setting _USE_CPP_MATCHING = False must disable the fast path"""

    class PythonMatchingParser(Fast_Parser):
        _USE_CPP_MATCHING = False

    fp = PythonMatchingParser()
    try:
        assert not fp.uses_native_matching
    finally:
        fp.cleanup()

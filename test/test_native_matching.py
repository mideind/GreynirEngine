"""

    test_native_matching.py

    Tests for the native (C++) token/terminal matching fast path
    (build_matching_table()/encode_token_matching_data() in binparser.py
    and evalMatch() in eparser.cpp). Verifies that the fast path is
    enabled by default, produces results identical to Python matching,
    reports zero discrepancies in parity mode, and is automatically
    disabled for parser subclasses that override token wrapping.

"""

import os
from contextlib import contextmanager
from typing import Iterator, List, Optional

from tokenizer import TOK

from reynir import Greynir
from reynir.binparser import BIN_Token
from reynir.fastparser import Fast_Parser

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


def test_gate_subclass_wrap_token():
    """A parser subclass that overrides token wrapping (as e.g.
    GreynirCorrect does) must automatically fall back to Python matching"""

    class TokenWrappingParser(Fast_Parser):
        @staticmethod
        def wrap_token(t, ix):
            return BIN_Token(t, ix)

    fp = TokenWrappingParser()
    try:
        assert not fp.uses_native_matching
    finally:
        fp.cleanup()


def test_gate_class_flag():
    """Setting _USE_CPP_MATCHING = False must disable the fast path"""

    class PythonMatchingParser(Fast_Parser):
        _USE_CPP_MATCHING = False

    fp = PythonMatchingParser()
    try:
        assert not fp.uses_native_matching
    finally:
        fp.cleanup()

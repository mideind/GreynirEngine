# type: ignore
"""

    test_parse.py

    Tests for Greynir module

    Copyright © 2023 by Miðeind ehf.
    Original author: Vilhjálmur Þorsteinsson

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

"""

from typing import List, cast

from collections import defaultdict

import pytest

from tokenizer.definitions import AmountTuple, DateTimeTuple

from reynir import Greynir
from reynir.reynir import Terminal


@pytest.fixture(scope="module")
def r():
    """Provide a module-scoped Greynir instance as a test fixture"""
    r = Greynir()
    yield r
    # Do teardown here
    r.__class__.cleanup()


def test_parse(r: Greynir, verbose: bool = False) -> None:
    sentences = [
        # 0
        "Hér er verið að gera tilraunir með þáttun.",
        # 1
        "Margar málsgreinar koma hér fyrir.",
        # 2
        "Þetta takast ekki að þáttar.",  # Error sentence
        # 3
        "Fjórða málsgreinin er síðust.",
        # 4
        "Hitastig vatnsins var 30,5 gráður og ég var ánægð með það.",
        # 5
        "Hún skuldaði mér 1.000 dollara.",
        # 6
        "Ég hitti hana þann 17. júní árið 1944 á Þingvöllum.",
        # 7
        "Hann eignaðist hús við ströndina og henni tókst að mála það.",
        # 8
        "Barnið fór í augnrannsóknina eftir húsnæðiskaupin.",
        # 9
        "Barnið fór í loðfílarannsókn.",  # Test composite words
        # 10
        "Eðlisfræðingurinn Stephen Hawking lést í dag, á pí-deginum.",
        # 11
        "Löngu áður en Jón borðaði ísinn sem hafði bráðnað hratt "
        "í hádeginu fór ég á veitingastaðinn á horninu og keypti mér rauðvín "
        "með hamborgaranum sem ég borðaði í gær með mikilli ánægju.",
        # 12
        "Ég horfði á Pál borða kökuna.",
        # 13
        "Fyrir Pál eru þetta góð tíðindi.",
        # 14
        "Ég hef unnið og þrælað alla mína tíð.",
        # 15
        "Jón borðaði ísinn um svipað leyti og Gunna skrifaði bréfið.",
        # 16
        "Það að þau viðurkenna ekki að þjóðin er ósátt við gjörðir þeirra er alvarlegt.",
        # 17
        "Hann hefur nú viðurkennt að hafa ákveðið sjálfur að birta "
        "hvorki almenningi né Alþingi skýrsluna.",
        # 18
        "Ríkissjóður stendur í blóma ef 27 milljarða "
        "arðgreiðsla Íslandsbanka er talin með.",
        # 19
        "Auk alls þessa þá getum við líka einfaldlega vandað okkur meira.",
        # 20
        "Það er óskandi að gripið verði til margfalt öflugri aðgerða "
        "en verið hefur á liðnum árum og áratugum.",
        # 21
        "Eftir vanfjármögnun úrbóta sl. kjörtímabil, í margyfirlýstu góðæri "
        "þar sem fjárlagafrumvarp 2017 var samt undir núlli tekjumegin, "
        "er deginum ljósara að mikla viðbótarfjármögnun þarf svo koma megi "
        "mörgu í betra horf á næstu 1 - 2 árum.",
        # 22
        "Lögreglan fer ekki nánar ofan í það hvaða skemmdir það voru.",
        # 23
        "Ég leyfði þeim að taka allt sitt inn í veturinn.",
        # 24
        "Það sem þeir vilja berjast fyrir er ekki loforð, heldur áherslur.",
        # 25
        "Mér finnst í sjálfu sér slæmt að það skyldi hafa verið þannig.",
        # 26
        "Jón hefur aðgang að gögnum þeirra starfssviða sem eiga að vera aðskilin.",
        # 27
        "Fréttaveiturnar Reuters og Bloomberg fengu að vera viðstaddar fundinn.",
        # 28
        "Samtök ferðaþjónustunnar eru fylgjandi virðisaukandi þjónustu "
        "þar með talið bílastæðagjöldum.",
        # 29
        "Starfsmenn hans voru ekki á eitt sáttir.",
        # 30
        "Það var ekki bara á þann hátt að glútenið vantaði.",
        # 31
        "Slökkviliðið var á sama tíma í óðaönn við að slökkva eld "
        "sem kom upp í húsnæði við Bauganes í Skerjafirði.",
        # 32
        "Gömul mynd sem fannst nýlega í Þjóðskjalasafni Bandaríkjanna "
        "er sögð gefa í skyn að frægasti kvenkyns flugmaður sögunnar, "
        "Amelia Earhart, hafi ekki dáið í flugslysi í Kyrrahafinu.",
        # 33
        "Sams konar mál var svo höfðað í tvígang fyrir dómi, annars vegar "
        "með stefnu í apríl fyrir sex árum sem var felld niður og hins vegar "
        "í júlí ári seinna.",
        # 34
        "Lögreglan á Suðurlandi rannsakar nú hvort að maður um tvítugt "
        "hafi brotið kynferðislega gegn unglingsstúlku í liðinni viku.",
        # 35
        "Þetta hefur alltaf verið svona, að mér skilst.",
        # 36
        "Árásin átti sér stað um klukkan fimm aðfaranótt síðastliðins sunnudags "
        "þegar karlmaður var stunginn ítrekað í kviðinn með hnífi.",
    ]
    job = r.submit(" ".join(sentences))

    results = list(job.sentences())

    for i, sent in enumerate(results):
        if verbose:
            print("Sentence {0}: {1}".format(i, sent.tidy_text))
        assert sent.tidy_text == sentences[i], "'{0}' != '{1}'".format(
            sent.tidy_text, sentences[i]
        )
        assert not sent.is_foreign()
        if sent.parse():
            # Sentence parsed successfully
            assert i != 2
            if verbose:
                print("Successfully parsed")
        else:
            # An error occurred in the parse
            # The error token index is at sent.err_index
            assert i == 2
            assert sent.err_index == 5
            if verbose:
                print("Error in parse at token {0}".format(sent.err_index))

    assert job.num_sentences == len(sentences)
    assert job.num_parsed == len(sentences) - 1

    if verbose:
        print("Number of sentences : {0}".format(job.num_sentences))
        print("Thereof parsed      : {0}".format(job.num_parsed))
        print("Ambiguity           : {0:.2f}".format(job.ambiguity))
        print("Parsing time        : {0:.2f}".format(job.parse_time))
        print("Reduction time      : {0:.2f}".format(job.reduce_time))

    # Test that the parser finds the correct nouns
    assert results[0].tree.nouns == ["tilraun", "þáttun"]
    assert results[1].tree.nouns == ["málsgrein"]
    assert results[2].tree is None  # Error sentence
    assert results[3].tree.nouns == ["málsgrein"]
    assert results[4].tree.nouns == [
        "hitastig",
        "vatn",
        "gráða",
    ]
    assert results[5].tree.nouns == ["1.000 dollara"]
    # 'árið 1944' er tímaliður en ekki nafnliður
    assert results[6].tree.nouns == ["Þingvellir"]
    assert results[7].tree.nouns == ["hús", "strönd"]
    assert results[8].tree.nouns == ["barn", "augnrannsókn", "húsnæðiskaup"]
    assert results[9].tree.nouns == ["barn", "loðfíla-rannsókn"]
    assert results[10].tree.nouns == [
        "eðlisfræðingur",
        "Stephen Hawking",
        "dagur",
        "pí-dagur",
    ]
    assert results[11].tree.nouns == [
        "Jón",
        "ís",
        "hádegi",
        "veitingastaður",
        "horn",
        "rauðvín",
        "hamborgari",
        "ánægja",
    ]
    assert results[12].tree.nouns == ["Páll", "kaka"]

    assert results[22].tree.nouns == ["lögregla", "skemmd"]
    assert results[23].tree.nouns == ["vetur"]
    assert results[24].tree.nouns == ["loforð", "áhersla"]
    assert results[32].tree.nouns == [
        "mynd",
        "þjóðskjalasafn",
        "Bandaríki",
        "skyn",
        "flugmaður",
        "saga",
        "Amelia Earhart",
        "flugslys",
        "Kyrrahaf",
    ]

    # Test that the parser finds the correct verbs
    assert results[0].tree.verbs == ["vera", "vera", "gera"]
    assert results[1].tree.verbs == ["koma"]
    assert results[2].tree is None  # Error sentence
    assert results[3].tree.verbs == ["vera"]
    assert results[4].tree.verbs == ["vera", "vera"]
    assert results[5].tree.verbs == ["skulda"]
    assert results[6].tree.verbs == ["hitta"]
    assert results[7].tree.verbs == ["eigna", "taka", "mála"]
    assert results[8].tree.verbs == ["fara"]
    assert results[9].tree.verbs == ["fara"]
    assert results[10].tree.verbs == ["láta"]
    assert results[11].tree.verbs == [
        "borða",
        "hafa",
        "bráðna",
        "fara",
        "kaupa",
        "borða",
    ]
    assert results[12].tree.verbs == ["horfa", "borða"]
    assert (results[32].tree.verbs == ["finna", "segja", "gefa", "hafa", "deyja"]) or (
        results[32].tree.verbs == ["finna", "gefa", "hafa", "deyja"]
    )
    # Test that the parser finds the correct word lemmas
    assert results[0].tree.lemmas == [
        "hér",
        "vera",
        "vera",
        "að",
        "gera",
        "tilraun",
        "með",
        "þáttun",
        ".",
    ]
    assert results[1].tree.lemmas == [
        "margur",
        "málsgrein",
        "koma",
        "hér",
        "fyrir",
        ".",
    ]
    assert results[2].tree is None  # Error sentence
    assert results[3].tree.lemmas == ["fjórði", "málsgrein", "vera", "síðari", "."]
    assert results[4].tree.lemmas == [
        "hitastig",
        "vatn",
        "vera",
        "30,5",
        "gráða",
        "og",
        "ég",
        "vera",
        "ánægður",
        "með",
        "það",
        ".",
    ]
    assert results[5].tree.lemmas == ["hún", "skulda", "ég", "1.000 dollara", "."]
    assert results[6].tree.lemmas == [
        "ég",
        "hitta",
        "hún",
        "sá",
        "17. júní árið 1944",
        "á",
        "Þingvellir",
        ".",
    ]
    assert results[7].tree.lemmas == [
        "hann",
        "eigna",
        "hús",
        "við",
        "strönd",
        "og",
        "hún",
        "taka",
        "að",
        "mála",
        "það",
        ".",
    ]
    assert results[8].tree.lemmas == [
        "barn",
        "fara",
        "í",
        "augnrannsókn",
        "eftir",
        "húsnæðiskaup",
        ".",
    ]
    assert results[9].tree.lemmas == ["barn", "fara", "í", "loðfíla-rannsókn", "."]
    assert results[10].tree.lemmas == [
        "eðlisfræðingur",
        "Stephen Hawking",
        "láta",
        "í",
        "dagur",
        ",",
        "á",
        "pí-dagur",
        ".",
    ]
    assert results[11].tree.lemmas == [
        "löngu",
        "áður",
        "en",
        "Jón",
        "borða",
        "ís",
        "sem",
        "hafa",
        "bráðna",
        "hratt",
        "í",
        "hádegi",
        "fara",
        "ég",
        "á",
        "veitingastaður",
        "á",
        "horn",
        "og",
        "kaupa",
        "ég",
        "rauðvín",
        "með",
        "hamborgari",
        "sem",
        "ég",
        "borða",
        "í gær",
        "með",
        "mikill",
        "ánægja",
        ".",
    ]
    assert results[12].tree.lemmas == ["ég", "horfa", "á", "Páll", "borða", "kaka", "."]
    assert results[36].tree.lemmas == [
        "árás",
        "eiga",
        "sig",
        "staður",
        "um",
        "klukkan fimm",
        "aðfaranótt",
        "síðastliðinn",
        "sunnudagur",
        "þegar",
        "karlmaður",
        "vera",
        "stinga",
        "ítrekað",
        "í",
        "kviður",
        "með",
        "hnífur",
        ".",
    ]

    def num_pp(s):
        """Count the prepositional phrases in the parse tree for sentence s"""
        return len([t for t in s.tree.descendants if t.match("PP")])

    # Test that the correct number of prepositional phrases (PPs) is generated
    assert num_pp(results[8]) == 2
    assert num_pp(results[9]) == 1
    assert num_pp(results[10]) == 1
    assert num_pp(results[11]) == 4
    assert num_pp(results[12]) == 0


def test_consistency(r, verbose=False):
    """Check that multiple parses of the same sentences yield exactly
    the same preposition counts, and also identical scores. This is
    inter alia to guard agains nondeterminism that may arise from
    Python's random hash seeds."""

    sent15 = [
        "Barnið fór í augnrannsóknina eftir húsnæðiskaupin.",
        "Ég sendi póstinn frá Ísafirði með kettinum",
    ]
    sent45 = [
        "Barnið fór í augnrannsóknina fyrir húsnæðiskaupin.",
        "Ég sendi póstinn með kettinum til Ísafjarðar",
    ]
    for tc15, tc45 in zip(sent15, sent45):
        cnt = defaultdict(int)
        scores = defaultdict(int)
        ptime = 0.0

        ITERATIONS = 60
        if verbose:
            print(
                "Consistency test, {0} iterations:\n   {1}\n   {2}".format(
                    ITERATIONS, tc15, tc45
                )
            )

        for i in range(ITERATIONS):
            # The following two sentences have different scores
            if i % 5 == 4:
                # One fifth of the test cases
                j = r.submit(tc15)
            else:
                # Four fifths of the test cases
                j = r.submit(tc45)
            s = next(iter(j))
            s.parse()
            ptime += j.parse_time
            pp = [t.text for t in s.tree.descendants if t.match("PP")]
            cnt[len(pp)] += 1
            scores[s.score] += 1

        if verbose:
            print(
                "Parse time for {0} iterations was {1:.2f} seconds".format(
                    ITERATIONS, ptime
                )
            )

        # There should be 2 prepositions in all parse trees
        assert len(cnt) == 1
        assert 2 in cnt
        assert cnt[2] == ITERATIONS

        # The sum of all counts should be the number of iterations
        assert sum(scores.values()) == ITERATIONS
        if verbose:
            print(
                "There are {0} different scores in consistency check".format(
                    len(scores)
                )
            )
        # There should only be two different scores
        assert len(scores) == 2
        sc_set = set(scores.values())
        # The count for the scores should be 1/5 and 4/5 of the total, respectively
        assert ITERATIONS * 1 // 5 in sc_set
        assert ITERATIONS * 4 // 5 in sc_set


def test_long_parse(r, verbose=False):
    if verbose:
        print("Long parse test")
    txt = """[[Reynt er að efla áhuga ungs fólks á borgarstjórnarmálum með
        framboðsfundum og skuggakosningum en þótt kjörstaðirnir í þeim séu færðir
        inn í framhaldsskólana er þátttakan lítil. Dagur B. Eggertsson nýtur mun
        meira fylgis í embætti borgarstjóra en fylgi Samfylkingarinnar gefur til
        kynna samkvæmt könnun Fréttablaðsins.]][[Eins og fram kom í fréttum okkar
        í gær stefnir í met í fjölda framboða fyrir komandi borgarstjórnarkosningar
        í vor og gætu þau orðið að minnsta kosti fjórtán. Þá þarf minna fylgi nú en áður
        til að ná inn borgarfulltrúa, því borgarfulltrúum verður fjölgað úr fimmtán
        í tuttugu og þrjá.]][[Kosningabaráttan fyrir borgarstjórnarkosningarnar
        í vor er hafin í framhaldsskólum borgarinnar. Samhliða framboðskynningum fara
        fram skuggakosningar til borgarstjórnar í skólunum.]][[„Þetta er eiginlega
        æfing í því að taka þátt í lýðræðislegum kosningum. Við reynum að herma eftir því
        hvernig raunverulegar kosningar fara fram,“ segir Róbert Ferdinandsson
        kennari á félagsfræðibraut Fjölbrautaskólans við Ármúla.]]"""
    job = r.submit(txt)
    pg_count = 0
    sent_count = 0
    persons = []
    for pg in job.paragraphs():
        pg_count += 1
        if verbose:
            print("Paragraph {0}".format(pg_count))
        for sent in pg:
            sent_count += 1
            assert not sent.is_foreign()
            assert sent.parse(), "Could not parse sentence {0}".format(sent_count)
            persons.extend(sent.tree.persons)
    assert pg_count == 4
    assert sent_count == 8
    assert persons == ["Dagur B. Eggertsson", "Róbert Ferdinandsson"]

    if verbose:
        print("Number of sentences : {0}".format(job.num_sentences))
        print("Thereof parsed      : {0}".format(job.num_parsed))
        print("Ambiguity           : {0:.2f}".format(job.ambiguity))
        print("Parsing time        : {0:.2f}".format(job.parse_time))
        print("Reduction time      : {0:.2f}".format(job.reduce_time))


def test_properties(r):
    s = r.parse("Þetta er prófun.")["sentences"][0]
    _ = s.score
    _ = s.tokens
    _ = s.tree.view  # Should not raise exception
    try:
        _ = s.tree.tree
        assert False, "Should have raised exception"
    except AttributeError:
        pass


def test_foreign(r):
    s = r.parse_single(
        "Linie lotnicze WOW Air ogłosiły wznowienie lotów, "
        "ale tym razem firma będzie zajmowała się przewozem towarowym "
        "w ramach usługi cargo."
    )
    assert s.is_foreign()
    s = r.parse_single("Linie lotnicze")
    assert not s.is_foreign()
    s = r.parse_single("Linie lotnicze WOW Air ogłosiły")
    assert s.is_foreign()


def test_edge_cases(r):
    # Test that the parser does not crash on these edge cases
    r.parse_single("(x)")


def check_terminal(t, text, lemma, category, variants):
    assert t.text == text
    assert t.lemma == lemma
    assert t.category == category
    assert set(t.variants) == set(variants)


def check_terminals(t):
    assert len(t) == 7
    check_terminal(
        t[0], text="Jón", lemma="Jón", category="person", variants=["nf", "kk"]
    )
    check_terminal(
        t[1],
        text="greiddi",
        lemma="greiða",
        category="so",
        variants=["2", "þgf", "þf", "et", "p3", "fh", "gm", "þt"],
    )
    check_terminal(
        t[2],
        text="bænum",
        lemma="bær",
        category="no",
        variants=["et", "þgf", "kk", "gr"],
    )
    check_terminal(
        t[3],
        text="10 milljónir króna",
        lemma="10 milljónir króna",
        category="no",
        variants=["ft", "þf", "kvk"],
    )
    check_terminal(t[4], text="í", lemma="í", category="fs", variants=["þf"])
    check_terminal(
        t[5],
        text="skaðabætur",
        lemma="skaðabót",
        category="no",
        variants=["ft", "þf", "kvk"],
    )
    check_terminal(t[6], text=".", lemma=".", category="", variants=[])


def test_terminals(r):
    s = r.parse("Jón greiddi bænum 10 milljónir króna í skaðabætur.")["sentences"][0]
    check_terminals(s.terminals)


def test_amounts(r: Greynir) -> None:
    s = r.parse_single("Tjónið nam 10 milljörðum króna.")
    assert s is not None
    t: List[Terminal] = s.terminals or []
    assert len(t) == 4
    check_terminal(
        t[0],
        text="Tjónið",
        lemma="tjón",
        category="no",
        variants=["et", "nf", "hk", "gr"],
    )
    check_terminal(
        t[1],
        text="nam",
        lemma="nema",
        category="so",
        variants=["1", "þgf", "et", "p3", "gm", "þt", "fh"],
    )
    check_terminal(
        t[2],
        text="10 milljörðum króna",
        lemma="10 milljörðum króna",
        category="no",
        variants=["ft", "þgf", "kk"],
    )
    check_terminal(t[3], text=".", lemma=".", category="", variants=[])
    num, iso, _, _ = cast(AmountTuple, s.tokens[2].val)
    assert num == 10e9
    assert iso == "ISK"

    s = r.parse_single("Tjónið þann 22. maí nam einum milljarði króna.")
    assert s is not None
    t = s.terminals or []
    assert len(t) == 6
    check_terminal(
        t[0],
        text="Tjónið",
        lemma="tjón",
        category="no",
        variants=["et", "nf", "hk", "gr"],
    )
    check_terminal(
        t[1], text="þann", lemma="sá", category="fn", variants=["et", "kk", "þf"]
    )
    check_terminal(
        t[2], text="22. maí", lemma="22. maí", category="dagsafs", variants=[]
    )
    check_terminal(
        t[3],
        text="nam",
        lemma="nema",
        category="so",
        variants=["1", "þgf", "et", "p3", "gm", "þt", "fh"],
    )
    check_terminal(
        t[4],
        text="einum milljarði króna",
        lemma="einum milljarði króna",
        category="no",
        variants=["ft", "þgf", "kk"],
    )
    check_terminal(t[5], text=".", lemma=".", category="", variants=[])
    dt = cast(DateTimeTuple, s.tokens[2].val)
    assert dt == (0, 5, 22)
    num, iso, _, _ = cast(AmountTuple, s.tokens[4].val)
    assert num == 1e9
    assert iso == "ISK"

    s = r.parse_single("Tjónið þann 19. október 1983 nam 4,8 milljörðum dala.")
    assert s is not None
    t = s.terminals or []
    assert len(t) == 6
    check_terminal(
        t[0],
        text="Tjónið",
        lemma="tjón",
        category="no",
        variants=["et", "nf", "hk", "gr"],
    )
    check_terminal(
        t[1], text="þann", lemma="sá", category="fn", variants=["et", "kk", "þf"]
    )
    check_terminal(
        t[2],
        text="19. október 1983",
        lemma="19. október 1983",
        category="dagsföst",
        variants=[],
    )
    check_terminal(
        t[3],
        text="nam",
        lemma="nema",
        category="so",
        variants=["1", "þgf", "et", "p3", "gm", "þt", "fh"],
    )
    check_terminal(
        t[4],
        text="4,8 milljörðum dala",
        lemma="4,8 milljörðum dala",
        category="no",
        variants=["ft", "þgf", "kk"],
    )
    check_terminal(t[5], text=".", lemma=".", category="", variants=[])
    dt = cast(DateTimeTuple, s.tokens[2].val)
    assert dt == (1983, 10, 19)
    num, iso, _, _ = cast(AmountTuple, s.tokens[4].val)
    assert num == 4.8e9
    assert iso == "USD"

    s = r.parse_single("Tjónið nam sautján milljörðum breskra punda.")
    assert s is not None
    t = s.terminals or []
    assert len(t) == 4
    check_terminal(
        t[0],
        text="Tjónið",
        lemma="tjón",
        category="no",
        variants=["et", "nf", "hk", "gr"],
    )
    check_terminal(
        t[1],
        text="nam",
        lemma="nema",
        category="so",
        variants=["1", "þgf", "et", "p3", "gm", "þt", "fh"],
    )
    check_terminal(
        t[2],
        text="sautján milljörðum breskra punda",
        lemma="sautján milljörðum breskra punda",
        category="no",
        variants=["ft", "þgf", "kk"],
    )
    check_terminal(t[3], text=".", lemma=".", category="", variants=[])
    num, iso, _, _ = cast(AmountTuple, s.tokens[2].val)
    assert num == 17e9
    assert iso == "GBP"

    s = r.parse_single("Tjónið nam 17 breskum pundum.")
    assert s is not None
    t = s.terminals or []
    assert len(t) == 4
    check_terminal(
        t[0],
        text="Tjónið",
        lemma="tjón",
        category="no",
        variants=["et", "nf", "hk", "gr"],
    )
    check_terminal(
        t[1],
        text="nam",
        lemma="nema",
        category="so",
        variants=["1", "þgf", "et", "p3", "gm", "þt", "fh"],
    )
    check_terminal(
        t[2],
        text="17 breskum pundum",
        lemma="17 breskum pundum",
        category="no",
        variants=["ft", "þgf", "hk"],
    )
    check_terminal(t[3], text=".", lemma=".", category="", variants=[])
    num, iso, _, _ = cast(AmountTuple, s.tokens[2].val)
    assert num == 17
    assert iso == "GBP"

    s = r.parse_single("Tjónið nam tólf hundruð pundum.")
    assert s is not None
    t = s.terminals or []
    assert len(t) == 4
    check_terminal(
        t[0],
        text="Tjónið",
        lemma="tjón",
        category="no",
        variants=["et", "nf", "hk", "gr"],
    )
    check_terminal(
        t[1],
        text="nam",
        lemma="nema",
        category="so",
        variants=["1", "þgf", "et", "p3", "gm", "þt", "fh"],
    )
    check_terminal(
        t[2],
        text="tólf hundruð pundum",
        lemma="tólf hundruð pundum",
        category="no",
        variants=["ft", "þgf", "hk"],
    )
    check_terminal(t[3], text=".", lemma=".", category="", variants=[])
    num, iso, _, _ = cast(AmountTuple, s.tokens[2].val)
    assert num == 1200
    assert iso == "GBP"

    s = r.parse_single("Tjónið nam 17 pólskum zloty.")
    assert s is not None
    t = s.terminals or []
    assert len(t) == 4
    check_terminal(
        t[0],
        text="Tjónið",
        lemma="tjón",
        category="no",
        variants=["et", "nf", "hk", "gr"],
    )
    check_terminal(
        t[1],
        text="nam",
        lemma="nema",
        category="so",
        variants=["1", "þgf", "et", "p3", "gm", "þt", "fh"],
    )
    check_terminal(
        t[2],
        text="17 pólskum zloty",
        lemma="17 pólskum zloty",
        category="no",
        variants=["ft", "þgf", "hk"],
    )
    check_terminal(t[3], text=".", lemma=".", category="", variants=[])
    num, iso, _, _ = cast(AmountTuple, s.tokens[2].val)
    assert num == 17
    assert iso == "PLN"

    s = r.parse_single("Tjónið nam 101 indverskri rúpíu.")
    assert s is not None
    t = s.terminals or []
    assert len(t) == 4
    check_terminal(
        t[0],
        text="Tjónið",
        lemma="tjón",
        category="no",
        variants=["et", "nf", "hk", "gr"],
    )
    check_terminal(
        t[1],
        text="nam",
        lemma="nema",
        category="so",
        variants=["1", "þgf", "et", "p3", "gm", "þt", "fh"],
    )
    check_terminal(
        t[2],
        text="101 indverskri rúpíu",
        lemma="101 indverskri rúpíu",
        category="no",
        variants=["et", "þgf", "kvk"],
    )
    check_terminal(t[3], text=".", lemma=".", category="", variants=[])
    num, iso, _, _ = cast(AmountTuple, s.tokens[2].val)
    assert num == 101
    assert iso == "INR"

    s = r.parse_single("Tjónið nam 17 milljónum indónesískra rúpía.")
    assert s is not None
    t = s.terminals or []
    assert len(t) == 4
    check_terminal(
        t[0],
        text="Tjónið",
        lemma="tjón",
        category="no",
        variants=["et", "nf", "hk", "gr"],
    )
    check_terminal(
        t[1],
        text="nam",
        lemma="nema",
        category="so",
        variants=["1", "þgf", "et", "p3", "gm", "þt", "fh"],
    )
    check_terminal(
        t[2],
        text="17 milljónum indónesískra rúpía",
        lemma="17 milljónum indónesískra rúpía",
        category="no",
        variants=["ft", "þgf", "kvk"],
    )
    check_terminal(t[3], text=".", lemma=".", category="", variants=[])
    num, iso, _, _ = cast(AmountTuple, s.tokens[2].val)
    assert num == 17e6
    assert iso == "IDR"


def test_year_range(r):
    s = r.parse_single("Jón var Íslandsmeistari árin 1944-50.")
    t = s.terminals or []
    assert len(t) == 8
    check_terminal(
        t[0], text="Jón", lemma="Jón", category="person", variants=["nf", "kk"]
    ),
    check_terminal(
        t[1],
        text="var",
        lemma="vera",
        category="so",
        variants=["1", "nf", "et", "p3", "þt", "fh", "gm"],
    ),
    check_terminal(
        t[2],
        text="Íslandsmeistari",
        lemma="Íslandsmeistari",
        category="no",
        variants=["et", "nf", "kk"],
    ),
    check_terminal(
        t[3], text="árin", lemma="ár", category="no", variants=["hk", "gr", "ft", "þf"]
    ),
    check_terminal(t[4], text="1944", lemma="1944", category="ártal", variants=[]),
    check_terminal(t[5], text="–", lemma="–", category="", variants=[]),
    check_terminal(t[6], text="50", lemma="50", category="tala", variants=[]),
    check_terminal(t[7], text=".", lemma=".", category="", variants=[])


def test_terminal_types(r):
    # tölvupóstfang = email
    s = r.parse_single("Netfangið er valid@my-domain.reallylongtld.")
    t = s.terminals or []
    assert len(t) == 4
    check_terminal(
        t[2],
        text="valid@my-domain.reallylongtld",
        lemma="valid@my-domain.reallylongtld",
        category="tölvupóstfang",
        variants=["nf"],
    ),
    s = r.parse_single("Vefslóðin er http://www.vefur.is.")
    t = s.terminals or []
    assert len(t) == 4
    check_terminal(
        t[2],
        text="http://www.vefur.is",
        lemma="http://www.vefur.is",
        category="vefslóð",
        variants=["nf"],
    )
    s = r.parse_single("@notandi2 er betri en @notandi1.")
    t = s.terminals or []
    assert len(t) == 6
    check_terminal(
        t[0],
        text="@notandi2",
        lemma="@notandi2",
        category="notandanafn",
        variants=["nf"],
    )
    check_terminal(
        t[4],
        text="@notandi1",
        lemma="@notandi1",
        category="notandanafn",
        variants=["nf"],
    )
    s = r.parse_single("@UserTest.1 er betri en @UserTest.2, að mínu mati.")
    t = s.terminals or []
    assert len(t) == 10
    check_terminal(
        t[0],
        text="@UserTest.1",
        lemma="@UserTest.1",
        category="notandanafn",
        variants=["nf"],
    )
    check_terminal(
        t[4],
        text="@UserTest.2",
        lemma="@UserTest.2",
        category="notandanafn",
        variants=["nf"],
    )
    s = r.parse_single("Hér er H2SO4.")
    t = s.terminals or []
    assert len(t) == 4
    check_terminal(
        t[2],
        text="H2SO4",
        lemma="H2SO4",
        category="sameind",
        variants=["nf"],
    )
    s = r.parse_single("570607-6859 er kennitala fyrirtækisins.")
    t = s.terminals or []
    assert len(t) == 5
    check_terminal(
        t[0],
        text="570607-6859",
        lemma="570607-6859",
        category="kennitala",
        variants=["nf"],
    )
    s = r.parse_single("867-6998 er símanúmerið hans.")
    t = s.terminals or []
    assert len(t) == 5
    check_terminal(
        t[0],
        text="867-6998",
        lemma="867-6998",
        category="símanúmer",
        variants=["nf"],
    )


def test_single(r):
    s = r.parse_single("Jón greiddi bænum 10 milljónir króna í skaðabætur.")
    check_terminals(s.terminals)
    try:
        s = r.parse_single("")
        assert s is None
    except StopIteration:
        assert False, "Should not have raised StopIteration"
    s = r.parse_single("kötturinn lömdu hesturinn")
    assert s.combinations == 0
    assert s.tree is None


def test_complex(r, verbose=False):
    if verbose:
        print("Complex, sentence 1", end="")
    d = r.parse(
        "ákæran var þingfest en fréttastofu er kunnugt um að maðurinn "
        "játaði þar sem þinghaldið er lokað"
    )
    assert d["num_parsed"] == 1
    if verbose:
        print(
            ", parsing: {:.2f} seconds, reduction: {:.2f} seconds".format(
                d["parse_time"], d["reduce_time"]
            )
        )
        print("Complex, sentence 2", end="")
    d = r.parse(
        "Viðar Garðarsson, sem setti upp vefsíður fyrir Sigmund Davíð "
        "Gunnlaugsson í kjölfar birtingu Panamaskjalanna, segist ekki vita "
        "hvers vegna ákveðið var að segja að vefjunum væri haldið úti af "
        "stuðningsmönnum Sigmundar."
    )
    assert d["num_parsed"] == 1
    if verbose:
        print(
            ", parsing: {:.2f} seconds, reduction: {:.2f} seconds".format(
                d["parse_time"], d["reduce_time"]
            )
        )
        print("Complex, sentence 3", end="")
    d = r.parse(
        "Ákæran var þingfest í Héraðsdómi Reykjaness í dag "
        "en fréttastofu er ekki kunnugt um hvort maðurinn játaði eða neitaði "
        "sök þar sem þinghaldið í málinu er lokað."
    )
    assert d["num_parsed"] == 1
    if verbose:
        print(
            ", parsing: {:.2f} seconds, reduction: {:.2f} seconds".format(
                d["parse_time"], d["reduce_time"]
            )
        )
        print("Complex, sentence 4", end="")
    d = r.parse(
        "Út úr stílfærðri túlkun listamannsins á gamla , litla og mjóa "
        "prófessornum kom búlduleitur beljaki sem þess vegna hefði getað verið "
        "trökkdræver að norðan."
    )
    assert d["num_parsed"] == 1
    if verbose:
        print(
            ", parsing: {:.2f} seconds, reduction: {:.2f} seconds".format(
                d["parse_time"], d["reduce_time"]
            )
        )
        print("Complex, sentence 5", end="")
    d = r.parse(
        "Rétt hjá anddyrinu var ein af þessum höggnu andlitsmyndum "
        "af þjóðfrægum mönnum þar sem listamaðurinn hafði gefist upp við að ná "
        "svipnum og ákveðið að hafa þetta í staðinn stílfærða mynd sem túlkaði "
        "fremur innri mann fyrirmyndarinnar en þá ásjónu sem daglega blasti við "
        "samferðamönnum."
    )
    assert d["num_parsed"] == 1
    if verbose:
        print(
            ", parsing: {:.2f} seconds, reduction: {:.2f} seconds".format(
                d["parse_time"], d["reduce_time"]
            )
        )
        print("Complex, sentence 6", end="")
    d = r.parse(
        "Sú fullyrðing byggist á því að ef hlutverk skólastarfs er eingöngu til þess "
        "að undirbúa nemendur fyrir skilvirka og afkastamikla þátttöku í atvinnu- og "
        "viðskiptalífi, skerðist það rými sem einstaklingar fá í gegnum menntun til "
        "þess að rækta með sér þá flóknu hæfni sem þarf til að lifa í lýðræðissamfélagi; "
        "að móta eigin skoðanir, þjálfa gagnrýna hugsun og læsi, læra að lifa í "
        "margbreytilegu samfélagi, mynda tengsl við aðra, mótast sem einstaklingur "
        "í hnattrænu samfélagi, og takast á við ólík viðhorf, skoðanir og gildi — svo "
        "fátt eitt sé nefnt.",
        max_sent_tokens=None,
    )
    assert d["num_parsed"] == 1
    if verbose:
        print(
            ", parsing: {:.2f} seconds, reduction: {:.2f} seconds".format(
                d["parse_time"], d["reduce_time"]
            )
        )


def test_measurements(r):
    s = r.parse_single(
        "Ég vildi leggja rúm 220 tonn en hann vildi kaupa "
        "tæplega 3,8 km af efninu í yfir 32°F frosti."
    )
    assert (
        s.tree.flat == "S0 S-MAIN IP NP-SUBJ pfn_et_nf /NP-SUBJ "
        "VP VP-AUX so_et_p1 /VP-AUX VP so_1_þf_nh /VP NP-OBJ "
        "lo_þf_ft_hk tala_ft_þf_hk no_ft_þf_hk /NP-OBJ /VP "
        "/IP /S-MAIN C st /C S-MAIN IP NP-SUBJ pfn_kk_et_nf "
        "/NP-SUBJ VP VP-AUX so_et_p3 /VP-AUX VP so_1_þf_nh "
        "/VP NP-OBJ NP-MEASURE ao tala mælieining /NP-MEASURE "
        "PP P fs_þgf /P NP no_et_þgf_hk PP P fs_þgf "
        "/P NP NP-POSS ao mælieining "
        "/NP-POSS no_et_þgf_hk /NP /PP /NP /PP /NP-OBJ /VP "
        "/IP /S-MAIN p /S0"
    )


def test_abbreviations(r):
    s = r.parse_single("Ég borða köku BHM á laugard. í okt. nk. og mun þykja hún vond.")
    assert (
        s.tree.flat == "S0 S-MAIN IP NP-SUBJ pfn_et_nf /NP-SUBJ VP VP "
        "so_1_þf_et_p1 /VP NP-OBJ no_et_þf_kvk NP-POSS no_et_ef_hk "
        "/NP-POSS /NP-OBJ ADVP-DATE-REL P fs_þf /P no_kk_þf_et "
        "/ADVP-DATE-REL ADVP-DATE-REL P fs_þgf /P dagsafs lo_þgf_et_kk "
        "/ADVP-DATE-REL /VP C st /C VP VP-AUX so_et_p1 /VP-AUX VP "
        "so_1_nf_nh /VP NP-OBJ pfn_kvk_et_nf /NP-OBJ NP-PRD "
        "lo_sb_nf_et_kvk /NP-PRD /VP /IP /S-MAIN p /S0"
    )
    # The following also tests augmented variants for personal pronouns,
    # i.e. pfn_et_nf_p1 for 'ég' and pfn_et_kvk_nf_p3 for 'hún'
    # (the person is added; it's not included in BÍN)
    assert (
        s.tree.flat_with_all_variants == "S0 S-MAIN IP NP-SUBJ pfn_et_nf_p1 "
        "/NP-SUBJ VP VP so_1_þf_et_fh_gm_nt_p1 /VP NP-OBJ no_et_kvk_þf "
        "NP-POSS no_ef_et_hk /NP-POSS /NP-OBJ ADVP-DATE-REL P fs_þf "
        "/P no_et_kk_þf /ADVP-DATE-REL ADVP-DATE-REL P fs_þgf /P dagsafs "
        "lo_et_kk_þgf /ADVP-DATE-REL /VP C st /C VP VP-AUX so_et_fh_gm_nt_p1 "
        "/VP-AUX VP so_1_nf_gm_nh /VP NP-OBJ pfn_et_kvk_nf_p3 /NP-OBJ "
        "NP-PRD lo_et_kvk_nf_sb /NP-PRD /VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single(
        "T.d. var bréfið til KPMG dags. 10. júlí en hr. Friðgeir vildi senda það "
        "til ASÍ eða SÁÁ o.s.frv. áður en það birtist á mbl.is."
    )
    # TODO Doesn't work for some reason; 'birtist' takes a NP-PRD instead of NP-SUBJ.
    # assert (
    #     s.tree.flat_with_all_variants == "S0 S-MAIN IP ADVP ao /ADVP VP VP "
    #     "so_et_fh_gm_p3_þt /VP NP-SUBJ no_et_gr_hk_nf PP P fs_ef /P NP no_ef_et_hk /NP "
    #     "/PP /NP-SUBJ NP-PRD VP so_et_hk_lhþt_nf_sb /VP "
    #     "ADVP-DATE-REL raðnr no_et_kk_þf /ADVP-DATE-REL /NP-PRD /VP /IP /S-MAIN "
    #     "C st /C S-MAIN IP NP-SUBJ no_et_kk_nf person_kk_nf /NP-SUBJ VP "
    #     "VP-AUX so_et_fh_gm_p3_þt /VP-AUX VP so_1_þf_gm_nh /VP "
    #     "NP-OBJ pfn_et_hk_p3_þf /NP-OBJ PP P fs_ef /P "
    #     "NP no_ef_et_hk C st /C no_ef_et_hk ao /NP /PP /VP CP-ADV-TEMP "
    #     "C ao st /C IP NP-SUBJ pfn_et_hk_nf_p3 /NP-SUBJ VP VP so_0_et_fh_mm_nt_p3 /VP "
    #     "PP P fs_þgf /P NP lén_þgf /NP /PP /VP /IP /CP-ADV-TEMP /IP /S-MAIN p /S0"
    # ) or (
    #     s.tree.flat_with_all_variants == "S0 S-MAIN IP ADVP ao /ADVP VP VP "
    #     "so_et_fh_gm_p3_þt /VP NP-SUBJ no_et_gr_hk_nf PP P fs_ef /P NP no_ef_et_hk /NP "
    #     "/PP /NP-SUBJ NP-PRD VP so_et_hk_lhþt_nf_sb /VP "
    #     "ADVP-DATE-REL raðnr no_et_kk_þf /ADVP-DATE-REL /NP-PRD /VP /IP /S-MAIN "
    #     "C st /C S-MAIN IP NP-SUBJ no_et_kk_nf person_kk_nf /NP-SUBJ VP "
    #     "VP-AUX so_et_fh_gm_p3_þt /VP-AUX VP so_1_þf_gm_nh /VP "
    #     "NP-OBJ pfn_et_hk_p3_þf /NP-OBJ PP P fs_ef /P "
    #     "NP no_ef_et_hk C st /C no_ef_et_hk ao /NP /PP CP-ADV-TEMP "
    #     "C ao st /C IP NP-SUBJ pfn_et_hk_nf_p3 /NP-SUBJ VP VP so_0_et_fh_mm_nt_p3 /VP "
    #     "PP P fs_þgf /P NP lén_þgf /NP /PP /VP /IP /CP-ADV-TEMP /VP /IP /S-MAIN p /S0"
    # )


def test_attachment(r, verbose=False):
    """Test attachment of prepositions to nouns and verbs"""
    if verbose:
        print("Testing attachment of prepositions")
    # s = r.parse_single("Páll talaði við Pál um málið")
    # assert s.tree.flat == ""
    for _ in range(20):
        # Test consistency for 20 iterations
        s = r.parse_single("Ég setti dæmi um þetta í bókina mína.")
        assert (
            s.tree.flat == "S0 S-MAIN IP NP-SUBJ pfn_et_nf /NP-SUBJ "  # Ég
            "VP VP so_1_þf_et_p1 /VP NP-OBJ no_et_þf_hk "  # setti dæmi
            "PP P fs_þf /P NP fn_et_þf_hk /NP /PP "  # um þetta
            "/NP-OBJ PP P fs_þf /P NP no_et_þf_kvk fn_et_þf_kvk /NP /PP /VP "  # í bókina mína
            "/IP /S-MAIN p /S0"  # .
        )
        s = r.parse_single("Ég setti dæmi í bókina mína um þetta.")
        assert (
            s.tree.flat == "S0 S-MAIN IP NP-SUBJ pfn_et_nf /NP-SUBJ "  # Ég
            "VP VP so_1_þf_et_p1 /VP NP-OBJ no_et_þf_hk "  # setti dæmi
            "/NP-OBJ PP P fs_þf /P NP no_et_þf_kvk fn_et_þf_kvk "  # í bókina mína
            "PP P fs_þf /P NP fn_et_þf_hk /NP /PP /NP /PP /VP /IP /S-MAIN p /S0"  # um þetta .
        )


def test_nominative(r: Greynir) -> None:
    """Test conversion of noun phrases to nominative/indefinite/canonical forms"""

    s = r.parse_single("Frábærum bílskúrum þykir þetta leiðinlegt.")
    subj = s.tree.S_MAIN.IP.NP_SUBJ
    assert (
        "{0} {1}".format(subj[0].nominative, subj[1].nominative) == "Frábærir bílskúrar"
    )
    assert (
        "{0} {1}".format(subj[0].indefinite, subj[1].indefinite) == "Frábærir bílskúrar"
    )
    assert "{0} {1}".format(subj[0].canonical, subj[1].canonical) == "Frábær bílskúr"
    assert subj.nominative_np == "Frábærir bílskúrar"
    assert subj.indefinite_np == "Frábærir bílskúrar"
    assert subj.canonical_np == "Frábær bílskúr"

    s = r.parse_single("Frábærari bílskúrum þykir þetta leiðinlegt.")
    subj = s.tree.S_MAIN.IP.NP_SUBJ
    assert (
        "{0} {1}".format(subj[0].nominative, subj[1].nominative)
        == "Frábærari bílskúrar"
    )
    assert (
        "{0} {1}".format(subj[0].indefinite, subj[1].indefinite)
        == "Frábærari bílskúrar"
    )
    assert "{0} {1}".format(subj[0].canonical, subj[1].canonical) == "Frábærari bílskúr"
    assert subj.nominative_np == "Frábærari bílskúrar"
    assert subj.indefinite_np == "Frábærari bílskúrar"
    assert subj.canonical_np == "Frábærari bílskúr"

    s = r.parse_single("Frábærustum bílskúrum þykir þetta leiðinlegt.")
    subj = s.tree.S_MAIN.IP.NP_SUBJ
    assert (
        "{0} {1}".format(subj[0].nominative, subj[1].nominative)
        == "Frábærastir bílskúrar"
    )
    assert (
        "{0} {1}".format(subj[0].indefinite, subj[1].indefinite)
        == "Frábærastir bílskúrar"
    )
    assert (
        "{0} {1}".format(subj[0].canonical, subj[1].canonical) == "Frábærastur bílskúr"
    )
    assert subj.nominative_np == "Frábærastir bílskúrar"
    assert subj.indefinite_np == "Frábærastir bílskúrar"
    assert subj.canonical_np == "Frábærastur bílskúr"

    s = r.parse_single("Frábæru bílskúrunum þykir þetta leiðinlegt.")
    subj = s.tree.S_MAIN.IP.NP_SUBJ
    assert (
        "{0} {1}".format(subj[0].nominative, subj[1].nominative)
        == "Frábæru bílskúrarnir"
    )
    assert (
        "{0} {1}".format(subj[0].indefinite, subj[1].indefinite) == "Frábærir bílskúrar"
    )
    assert "{0} {1}".format(subj[0].canonical, subj[1].canonical) == "Frábær bílskúr"
    assert subj.nominative_np == "Frábæru bílskúrarnir"
    assert subj.indefinite_np == "Frábærir bílskúrar"
    assert subj.canonical_np == "Frábær bílskúr"

    s = r.parse_single("Frábærari bílskúrunum þykir þetta leiðinlegt.")
    subj = s.tree.S_MAIN.IP.NP_SUBJ
    assert (
        "{0} {1}".format(subj[0].nominative, subj[1].nominative)
        == "Frábærari bílskúrarnir"
    )
    assert (
        "{0} {1}".format(subj[0].indefinite, subj[1].indefinite)
        == "Frábærari bílskúrar"
    )
    assert "{0} {1}".format(subj[0].canonical, subj[1].canonical) == "Frábærari bílskúr"
    assert subj.nominative_np == "Frábærari bílskúrarnir"
    assert subj.indefinite_np == "Frábærari bílskúrar"
    assert subj.canonical_np == "Frábærari bílskúr"

    s = r.parse_single(
        "Ótrúlega frábærustu bílskúrunum þriggja góðglöðu alþingismannanna "
        "sem fóru út þykir þetta leiðinlegt."
    )
    subj = s.tree.S_MAIN.IP.NP_SUBJ
    assert (
        "{0} {1} {2}".format(subj[0].nominative, subj[1].nominative, subj[2].nominative)
        == "Ótrúlega frábærustu bílskúrarnir"
    )
    assert (
        "{0} {1} {2}".format(subj[0].indefinite, subj[1].indefinite, subj[2].indefinite)
        == "Ótrúlega frábærastir bílskúrar"
    )
    assert (
        "{0} {1} {2}".format(subj[0].canonical, subj[1].canonical, subj[2].canonical)
        == "Ótrúlega frábærastur bílskúr"
    )
    assert (
        subj.nominative_np
        == "Ótrúlega frábærustu bílskúrarnir þriggja góðglöðu alþingismannanna sem fóru út"
    )
    assert (
        subj.indefinite_np
        == "Ótrúlega frábærastir bílskúrar þriggja góðglöðu alþingismannanna sem fóru út"
    )
    assert subj.canonical_np == "Ótrúlega frábærastur bílskúr"
    subj = subj.NP_POSS
    assert subj.nominative_np == "þrír góðglöðu alþingismennirnir sem fóru út"
    assert subj.indefinite_np == "þrír góðglaðir alþingismenn sem fóru út"
    assert subj.canonical_np == "góðglaður alþingismaður"

    s = r.parse_single("Ég var í Hinu íslenska bókmenntafélagi.")
    subj = s.tree.S_MAIN.IP.VP.PP.NP
    assert subj.nominative_np == "Hið íslenska bókmenntafélag"
    assert subj.indefinite_np == "íslenskt bókmenntafélag"
    assert subj.canonical_np == "íslenskt bókmenntafélag"

    s = r.parse_single("Ég var með Páli Húnfjörð Jónssyni.")
    subj = s.tree.S_MAIN.IP.VP.PP.NP
    assert subj.nominative_np == "Páll Húnfjörð Jónsson"
    assert subj.indefinite_np == "Páll Húnfjörð Jónsson"
    assert subj.canonical_np == "Páll Húnfjörð Jónsson"

    s = r.parse_single("Ég var með Sigríði Sölku Kristínardóttur.")
    subj = s.tree.S_MAIN.IP.VP.PP.NP
    assert subj.nominative_np == "Sigríður Salka Kristínardóttir"
    assert subj.indefinite_np == "Sigríður Salka Kristínardóttir"
    assert subj.canonical_np == "Sigríður Salka Kristínardóttir"

    s = r.parse_single("Kristín málaði hús Hönnu Önfjörð Álfhildardóttur")
    assert (
        s.tree.first_match("NP-POSS").nominative_np == "Hanna Önfjörð Álfhildardóttir"
    )

    s = r.parse_single(
        "Stóri feiti Jólasveinninn beislaði "
        "fjögur sætustu hreindýrin og ók rauða VAGNINUM "
        "með fjölda gjafa til spenntu barnanna sem biðu "
        "milli vonar og ótta."
    )
    assert len(list(s.tree.all_matches("NP"))) == 6
    assert (
        len(list(s.tree.top_matches("NP"))) == 3
        or len(list(s.tree.top_matches(("NP")))) == 4
    )

    assert list(n.text for n in s.tree.all_matches("( no | lo)")) == [
        "Stóri",
        "feiti",
        "Jólasveinninn",
        "sætustu",
        "hreindýrin",
        "rauða",
        "VAGNINUM",
        "fjölda",
        "gjafa",
        "spenntu",
        "barnanna",
    ]
    assert list(n.nominative for n in s.tree.all_matches("( no | lo)")) == [
        "Stóri",
        "feiti",
        "Jólasveinninn",
        "sætustu",
        "hreindýrin",
        "rauði",
        "VAGNINN",
        "fjöldi",
        "gjafir",
        "spenntu",
        "börnin",
    ]
    assert list(n.canonical for n in s.tree.all_matches("( no | lo)")) == [
        "Stór",
        "feitur",
        "Jólasveinn",
        "sætast",
        "hreindýr",
        "rauður",
        "VAGN",
        "fjöldi",
        "gjöf",
        "spennt",
        "barn",
    ]
    assert list(
        n.canonical for t in s.tree.top_matches("NP") for n in t.all_matches("no")
    ) == ["Jólasveinn", "hreindýr", "VAGN", "fjöldi", "gjöf", "barn"]


def test_ifd_tag(r: Greynir) -> None:
    """Test IFD tagging"""
    s = r.parse_single(
        "Að minnsta kosti stal Guðbjörn J. Óskarsson 200 krónum þann 19. júní 2003 "
        "og þyngdist um 300 kg."
    )
    assert s.ifd_tags == [
        "aþ",
        "lkeþve",
        "nkeþ",
        "sfg3eþ",
        "nken-m",
        "nken-m",
        "nken-m",  # Guðbjörn J. Óskarsson
        "tfvfþ",
        "nvfþ",  # 200 krónum
        "fakeo",
        "ta",
        "nkeo",
        "ta",  # 19. júní 2003
        "c",
        "sfm3eþ",
        "ao",
        "ta",
        "x",  # 300 kg
        ".",
    ]
    s = r.parse_single(
        "Vestur-Þýskalandi bar blátt áfram að bjarga a.m.k. 284,47 börnum "
        "kl. 11:45 árið 374 f.Kr."
    )
    assert s.ifd_tags == [
        "nheþ-ö",
        "sfg3eþ",
        "lhensf",
        "aa",
        "cn",
        "sng",
        "aa",
        "tfkfn",  # 284,47
        "nhfþ",
        "nven",
        "ta",  # kl. 11:45
        "nheo",
        "ta",
        "aa",  # árið 374 f.Kr.
    ]


def test_tree_flat(r: Greynir, verbose=False):
    AMOUNTS = {
        "þf": [
            ("13", "þf", "tala"),
            ("1.234,5", "þf", "tala"),
            ("1,234.5", "þf", "tala"),
            ("13 þúsund", "þf", "tala töl"),
            ("13 þús.", "þf", "tala töl"),
            ("13 millj.", "þf", "tala töl"),
            ("13 mrð.", "þf", "tala töl"),
            ("3 þúsundir", "ef", "tala no_ft_kvk_þf"),
            ("1.234,5 milljónir", "ef", "tala no_ft_kvk_þf"),
            ("1.234,5 milljarða", "ef", "tala no_ft_kk_þf"),
            ("1,234.5 milljónir", "ef", "tala no_ft_kvk_þf"),
            ("1,234.5 milljarða", "ef", "tala no_ft_kk_þf"),
        ],
        "þgf": [
            ("13", "þgf", "tala"),
            ("1.234,5", "þgf", "tala"),
            ("1,234.5", "þgf", "tala"),
            ("13 þúsund", "þgf", "tala töl"),
            ("13 þús.", "þgf", "tala töl"),
            ("13 millj.", "þgf", "tala töl"),
            ("13 mrð.", "þgf", "tala töl"),
            ("3 þúsundum", "ef", "tala no_ft_hk_þgf"),
            ("1.234,5 milljónum", "ef", "tala no_ft_kvk_þgf"),
            ("1.234,5 milljörðum", "ef", "tala no_ft_kk_þgf"),
            ("1,234.5 milljónum", "ef", "tala no_ft_kvk_þgf"),
            ("1,234.5 milljörðum", "ef", "tala no_ft_kk_þgf"),
        ],
    }

    CURRENCIES = {
        "þf": (
            ("ISK", "no_ft_kvk_þf"),
            ("krónur", "no_ft_kvk_þf"),
            ("íslenskar krónur", "lo_ft_kvk_sb_þf no_ft_kvk_þf"),
            ("bresk pund", "lo_ft_hk_sb_þf no_ft_hk_þf"),
            ("danskar krónur", "lo_ft_kvk_sb_þf no_ft_kvk_þf"),
            ("bandaríkjadali", "no_ft_kk_þf"),
            ("bandaríska dali", "lo_ft_kk_sb_þf no_ft_kk_þf"),
            ("indónesískar rúpíur", "lo_ft_kvk_sb_þf no_ft_kvk_þf"),
            ("indverskar rúpíur", "lo_ft_kvk_sb_þf no_ft_kvk_þf"),
        ),
        "þgf": (
            ("ISK", "no_ft_kvk_þgf"),
            ("krónum", "no_ft_kvk_þgf"),
            ("íslenskum krónum", "lo_ft_kvk_sb_þgf no_ft_kvk_þgf"),
            ("breskum pundum", "lo_ft_hk_sb_þgf no_ft_hk_þgf"),
            ("dönskum krónum", "lo_ft_kvk_sb_þgf no_ft_kvk_þgf"),
            ("bandaríkjadölum", "no_ft_kk_þgf"),
            ("bandarískum dölum", "lo_ft_kk_sb_þgf no_ft_kk_þgf"),
            ("indónesískum rúpíum", "lo_ft_kvk_sb_þgf no_ft_kvk_þgf"),
            ("indverskum rúpíum", "lo_ft_kvk_sb_þgf no_ft_kvk_þgf"),
        ),
        "ef": (
            ("ISK", "no_ef_ft_kvk"),
            ("króna", "no_ef_ft_kvk"),
            ("íslenskra króna", "lo_ef_ft_kvk_sb no_ef_ft_kvk"),
            ("breskra punda", "lo_ef_ft_hk_sb no_ef_ft_hk"),
            ("danskra króna", "lo_ef_ft_kvk_sb no_ef_ft_kvk"),
            ("bandaríkjadala", "no_ef_ft_kk"),
            ("bandarískra dala", "lo_ef_ft_kk_sb no_ef_ft_kk"),
            ("indónesískra rúpía", "lo_ef_ft_kvk_sb no_ef_ft_kvk"),
            ("indverskra rúpía", "lo_ef_ft_kvk_sb no_ef_ft_kvk"),
        ),
    }

    no_mul_numbers = r._options.get("no_multiply_numbers") or False
    for verb_case, amounts in AMOUNTS.items():
        for amount, currency_case, t1 in amounts:
            if no_mul_numbers and " " in amount:
                # Different behaviour when the no_multiply_numbers
                # flag is set for '[number] [word]' combinations
                continue
            for currency, t2 in CURRENCIES[currency_case]:
                if verb_case == "þf":
                    sent = "Hann skuldaði mér " + amount + " " + currency + "."
                elif verb_case == "þgf":
                    sent = "Hann tapaði " + amount + " " + currency + "."
                else:
                    assert False  # Unknown verb case
                if verbose:
                    print(sent)
                s = r.parse_single(sent)
                np_obj = s.tree.S.IP.VP.NP_OBJ.flat_with_all_variants
                expected = "NP-OBJ " + t1 + " " + t2 + " /NP-OBJ"
                if np_obj != expected:
                    print(np_obj, expected)
                assert np_obj == expected


def test_noun_lemmas(r):
    """Test abbreviation lemmas ('Schengen' is an abbreviation), proper name
    lemmas ('Ísland'), and lemmas of literal terminals in the grammar
    ('munur:kk' in this case)"""
    sent = "Schengen rekur mun öflugri gagnagrunn en Ísland gæti gert."
    s = r.parse_single(sent)
    assert s.tree.nouns == ["Schengen", "munur", "gagnagrunnur", "Ísland"]
    s = r.parse_single("Maður kom út úr húsinu.")
    leaves = list(s.tree.leaves)
    assert len(leaves) == len(s.tokens)
    assert leaves[0].fl == "alm"  # Not örn
    s = r.parse_single("Húsið var til sölu.")
    leaves = list(s.tree.leaves)
    assert len(leaves) == len(s.tokens)
    assert leaves[0].fl == "alm"  # Not göt
    s = r.parse_single("Ég keypti Húsið.")
    leaves = list(s.tree.leaves)
    assert len(leaves) == len(s.tokens)
    assert leaves[2].fl == "göt"  # In this case it's not alm


def test_composite_words(r):
    s = r.parse_single("Hann var mennta- og menningarmálaráðherra.")
    assert (
        s.tree.flat_with_all_variants
        == "S0 S-MAIN IP NP-SUBJ pfn_et_kk_nf_p3 /NP-SUBJ VP VP so_1_nf_et_fh_gm_p3_þt /VP "
        "NP-PRD no_et_kk_nf st no_et_kk_nf /NP-PRD /VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single("Hann var dómsmála-, mennta- og menningarmálaráðherra.")
    assert (
        s.tree.flat_with_all_variants
        == "S0 S-MAIN IP NP-SUBJ pfn_et_kk_nf_p3 /NP-SUBJ VP VP so_1_nf_et_fh_gm_p3_þt /VP "
        "NP-PRD no_et_kk_nf no_et_kk_nf st no_et_kk_nf /NP-PRD /VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single(
        "Hann var dómsmála- ferðamála- mennta- og menningarmálaráðherra."
    )
    assert (
        s.tree.flat_with_all_variants
        == "S0 S-MAIN IP NP-SUBJ pfn_et_kk_nf_p3 /NP-SUBJ VP VP so_1_nf_et_fh_gm_p3_þt /VP "
        "NP-PRD no_et_kk_nf no_et_kk_nf no_et_kk_nf st no_et_kk_nf /NP-PRD /VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single("Hann var hálf-þýskur og fæddist í Vestur-Þýskalandi.")
    assert (
        s.tree.flat_with_all_variants
        == "S0 S-MAIN IP NP-SUBJ pfn_et_kk_nf_p3 /NP-SUBJ VP VP-AUX so_et_fh_gm_p3_þt /VP-AUX "
        "NP-PRD lo_et_kk_nf_sb /NP-PRD /VP C st /C VP VP so_0_et_fh_mm_p3_þt /VP "
        "PP P fs_þgf /P NP no_et_hk_þgf /NP /PP /VP /IP /S-MAIN p /S0"
    )
    # Note that 'hálf - þýskur' is not the same as 'hálf-þýskur'
    # and 'Vestur  -  Þýskaland' is not the same as 'Vestur-Þýskaland'
    s = r.parse_single("Ég borðaði sykursaltan fiskinn")
    assert s.lemmas == ["ég", "borða", "sykur-saltur", "fiskur"]
    s = r.parse_single("Ég borðaði sykurinnsaltan fiskinn")
    assert s.lemmas == ["ég", "borða", "sykur-inn-saltur", "fiskur"]
    s = r.parse_single("Ég borðaði sykrisaltan fiskinn")
    # 'sykrisaltan' is not a valid composite word, so this should get parsed
    # as an unknown noun - causing 'fiskinn' to be parsed as an adjective
    assert s.lemmas == ["ég", "borða", "sykrisaltan", "fiskinn"]
    s = r.parse_single("Hann hjólaði kattspenntur á kvenbretti niður brekkuna")
    assert s.lemmas == [
        "hann",
        "hjóla",
        "katt-spenntur",
        "á",  # "á",
        "kven-bretti",  # "kven-bretti", # 'ær' is said to be the direct object!
        "niður",
        "brekka",
    ]
    s = r.parse_single(
        "Málfræði-reglurnar sögðu að hann væri frá Vestur-Þýskalandi "
        "og Ytri-Hnausi í Þingvalla-sveit."
    )
    assert s.tree.nouns == [
        "Málfræði-regla",
        "Vestur-Þýskaland",
        "Ytri-Hnaus",
        "Þingvalla-sveit",
    ]
    s = r.parse_single("Þing-konur og -menn dvöldu í þingvalla-sveitinni.")
    assert s.tree.nouns == ["Þing-kona", "maður", "þingvalla-sveit"]


def test_foreign_names(r):
    s = r.parse_single("Aristóteles uppgötvaði þyngdarlögmálið.")
    assert (
        s.tree.flat_with_all_variants
        == "S0 S-MAIN IP NP-SUBJ person_kk_nf /NP-SUBJ VP VP so_1_þf_et_fh_gm_p3_þt /VP "
        "NP-OBJ no_et_gr_hk_þf /NP-OBJ /VP /IP /S-MAIN p /S0"
    )
    # Test to check whether 'Hafstein' works as a family name in nominative case
    s = r.parse_single(
        "Þetta voru Ólafur Ísleifsson, Júlíus Hafstein og Ingibjörg Sólrún Gísladóttir."
    )
    assert (
        s.tree.flat_with_all_variants
        == "S0 S-MAIN IP NP-SUBJ fn_et_hk_nf /NP-SUBJ VP VP so_1_nf_fh_ft_gm_p3_þt /VP NP-PRD "
        "person_kk_nf person_kk_nf p person_kk_nf person_kk_nf C st /C person_kvk_nf person_kvk_nf person_kvk_nf "
        "/NP-PRD /VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single(
        "Þetta voru Ólafur Ísleifsson, Bára Hafstein og Ingibjörg Sólrún Gísladóttir."
    )
    assert (
        s.tree.flat_with_all_variants
        == "S0 S-MAIN IP NP-SUBJ fn_et_hk_nf /NP-SUBJ VP VP so_1_nf_fh_ft_gm_p3_þt /VP NP-PRD "
        "person_kk_nf person_kk_nf p person_kvk_nf person_kvk_nf C st /C person_kvk_nf person_kvk_nf person_kvk_nf "
        "/NP-PRD /VP /IP /S-MAIN p /S0"
    )


def test_vocabulary(r):
    """Test words that should be in the vocabulary, coming from
    ord.auka.csv or ord.add.csv"""
    s = r.parse_single(
        """
        Í gær gekk ég út frá ströndum og fékk mér ís.
        """
    )
    assert s.tree is not None
    assert "strönd" in s.tree.nouns
    s = r.parse_single(
        """
        Rekjanleikinn var enginn þegar ég spurði um hann.
        """
    )
    assert s.tree is not None
    assert "rekjanleiki" in s.tree.nouns
    s = r.parse_single(
        """
        Jón hafði áhyggjur af seljanleika bréfanna.
        """
    )
    assert s.tree is not None
    assert "seljanleiki" in s.tree.nouns
    s = r.parse_single(
        """
        Tvískráning bréfanna er á döfinni.
        """
    )
    assert s.tree is not None
    assert "tvískráning" in s.tree.nouns
    s = r.parse_single(
        """
        Hann vanrækti börnin alla tíð.
        """
    )
    assert s.tree is not None
    assert "vanrækja" in s.tree.verbs
    s = r.parse_single(
        """
        Milli deildanna voru kínamúrar en starfsandi var góður.
        """
    )
    assert s.tree is not None
    assert "kínamúr" in s.tree.nouns
    assert "starfsandi" in s.tree.nouns

    j = r.submit(
        "Ég fór í Landmannalaugar. Það var gaman í Landmannalaugum.", parse=True
    )
    cnt = 0
    for sent in j:
        assert sent.tree is not None
        lemma_set = set([lemma.replace("-", "") for lemma in sent.lemmas])
        assert "Landmannalaugar" in lemma_set
        cnt += 1
    assert cnt == 2

    s = r.parse_single("Ég veipaði af miklum krafti og fór á marga vegu.")
    assert s.tree.flat_with_all_variants == (
        "S0 S-MAIN IP NP-SUBJ pfn_et_nf_p1 /NP-SUBJ VP VP so_0_et_fh_gm_p1_þt /VP "
        "PP P fs_þgf /P NP lo_et_kk_sb_þgf no_et_kk_þgf /NP /PP /VP C st /C VP "
        "VP so_0_et_fh_gm_p1_þt /VP PP P fs_þf /P NP lo_ft_kk_sb_þf no_ft_kk_þf "
        "/NP /PP /VP /IP /S-MAIN p /S0"
    )


def test_adjective_predicates(r):
    """Test adjectives with an associated predicate"""

    # Accusative case (þolfall)
    s = r.parse_single(
        """
        Hundurinn var viðstaddur sýninguna sem fjallaði um hann.
        """
    )
    assert "NP-PRD lo_sb_nf_sþf_et_kk NP-ADP no_et_þf_kvk" in s.tree.flat

    # Dative case (þágufall)
    s = r.parse_single(
        """
        Hundurinn var málkunnugur kettinum frá fyrri tíð.
        """
    )
    assert (
        "NP-PRD lo_sb_nf_sþgf_et_kk NP-ADP no_et_þgf_kk /NP-ADP /NP-PRD" in s.tree.flat
    )

    # Possessive case (eignarfall)
    s = r.parse_single(
        """
        Kötturinn þóttist vera frjáls ferða sinna.
        """
    )
    assert (
        "NP-PRD lo_sb_nf_sef_et_kk NP-ADP no_ft_ef_kvk fn_ft_ef_kvk /NP-ADP /NP-PRD"
        in s.tree.flat
    )
    s = r.parse_single(
        """
        Kötturinn hafði verið fullur sjálfstrausts.
        """
    )
    assert "NP-PRD lo_sb_nf_sef_et_kk NP-ADP no_et_ef_hk /NP-ADP /NP-PRD" in s.tree.flat
    s = r.parse_single(
        """
        Verkamaðurinn er verður launa sinna.
        """
    )
    assert (
        "NP-PRD lo_sb_nf_sef_et_kk NP-ADP no_ft_ef_hk fn_ft_ef_hk /NP-ADP /NP-PRD"
        in s.tree.flat
    )


def test_subj_op(r):
    """Test impersonal verbs"""
    # langa
    s = r.parse_single("hestinn langaði í brauð")
    assert s.tree is not None
    assert s.tree.nouns == ["hestur", "brauð"]
    assert s.tree.verbs == ["langa"]
    s = r.parse_single("hesturinn langaði í brauð")
    assert s.tree is None
    s = r.parse_single("hestinum langaði í brauð")
    assert s.tree is None
    s = r.parse_single("hestsins langaði í brauð")
    assert s.tree is None
    # dreyma e-ð
    s = r.parse_single("hestinn dreymdi köttinn")
    assert s.tree is not None
    assert s.tree.nouns == ["hestur", "köttur"]
    assert s.tree.verbs == ["dreyma"]
    s = r.parse_single("hesturinn dreymdi köttinn")
    assert s.tree is None
    s = r.parse_single("hestinum dreymdi köttinn")
    assert s.tree is None
    s = r.parse_single("hestsins dreymdi köttinn")
    assert s.tree is None
    s = r.parse_single("hestinn dreymdi kettinum")
    assert s.tree is None
    s = r.parse_single("hestinn dreymdi kattarins")
    assert s.tree is None
    # hraka
    s = r.parse_single("hestinum hrakaði hratt")
    assert s.tree is not None
    assert s.tree.nouns == ["hestur"]
    assert s.tree.verbs == ["hraka"]
    s = r.parse_single("hesturinn hrakaði hratt")
    assert s.tree is None
    s = r.parse_single("hestinn hrakaði hratt")
    assert s.tree is None
    s = r.parse_single("hestsins hrakaði hratt")
    assert s.tree is None
    # blöskra e-ð
    s = r.parse_single("hestinum blöskraði vitleysan í Páli")
    assert s.tree is not None
    assert s.tree.nouns == ["hestur", "vitleysa", "Páll"]
    assert s.tree.verbs == ["blöskra"]
    s = r.parse_single("hesturinn blöskraði vitleysan í Páli")
    assert s.tree is None
    s = r.parse_single("hestinn blöskraði vitleysan í Páli")
    assert s.tree is None
    s = r.parse_single("hestsins blöskraði vitleysan í Páli")
    assert s.tree is None
    s = r.parse_single("mér blöskraði vitleysuna í Páli")
    assert s.tree is None
    s = r.parse_single("mér blöskraði vitleysunni í Páli")
    assert s.tree is None
    s = r.parse_single("mér blöskraði vitleysunnar í Páli")
    assert s.tree is None


def test_names(r):
    s = r.parse_single("Sýningarnar voru í Gamla bíói á þriðjudagskvöldum.")
    assert s.tree is not None
    assert s.tree.persons == []
    assert s.tree.nouns == ["sýning", "bíó", "þriðjudagskvöld"]
    s = r.parse_single("Ruud van Nistelrooy og Thomas de Broglie komu í heimsókn.")
    assert "Thomas de Broglie" in s.tree.persons
    assert "Ruud van Nistelrooy" in s.tree.entities

    s = r.parse_single("Tómas Í. Guðmundsson og Guðfinna Á. Ákadóttir komu í heimsókn.")
    assert (
        "Tómas Í. Guðmundsson" in s.tree.persons
        and "Guðfinna Á. Ákadóttir" in s.tree.persons
    )

    s = r.parse_single("Tómas Í. og Guðfinna Á. komu í heimsókn.")
    assert "Tómas Í." in s.tree.persons and "Guðfinna Á." in s.tree.persons

    s = r.parse_single("Tómas Í Guðmundsson og Guðfinna Á Ákadóttir komu í heimsókn.")
    assert (
        "Tómas Í Guðmundsson" in s.tree.persons
        and "Guðfinna Á Ákadóttir" in s.tree.persons
    )

    s = r.parse_single("Tómas Í og Guðfinna Á komu í heimsókn.")
    assert "Tómas Í" in s.tree.persons and "Guðfinna Á" in s.tree.persons

    s = r.parse_single("Ég sá Jónínu Á í svifflugi.")
    assert "Jónína Á" in s.tree.persons
    s = r.parse_single("Ég sá Jónínu Á á Eyrarbakka.")
    assert "Jónína Á" in s.tree.persons
    s = r.parse_single("Við mættum Þorsteini Í í fallhlífarstökki.")
    assert "Þorsteinn Í" in s.tree.persons
    s = r.parse_single("Við mættum Þorsteini Í á Borðeyri.")
    assert "Þorsteinn Í" in s.tree.persons
    s = r.parse_single("Halldór Á Í Jónsson er stór maður")
    assert "Halldór Á Í Jónsson" in s.tree.persons
    s = r.parse_single("Halldór Á. Í. Jónsson er stór maður")
    assert "Halldór Á. Í. Jónsson" in s.tree.persons
    s = r.parse_single("Við hringdum í Hafstein Í.")
    assert "Hafsteinn Í." in s.tree.persons
    s = r.parse_single("Við hringdum í Hafstein Á.")
    assert "Hafsteinn Á." in s.tree.persons
    s = r.parse_single("Við hringdum í Hafstein B Guðmundsson")
    assert "Hafsteinn B Guðmundsson" in s.tree.persons
    s = r.parse_single("Við hringdum í Hafstein B. Guðmundsson")
    assert "Hafsteinn B. Guðmundsson" in s.tree.persons

    s = r.parse_single("Við hringdum í Guðna Th.")
    assert "Guðni Th." in s.tree.persons
    s = r.parse_single("Við hringdum í Baldvin Kr. Magnússon")
    assert "Baldvin Kr. Magnússon" in s.tree.persons
    s = r.parse_single("Við hringdum í Baldvin Kr.")
    assert "Baldvin Kr." in s.tree.persons

    s = r.parse(
        "Við vitum ekki hvaða hesta Jón á. Hann hefur verið bóndi í langan tíma."
    )
    assert len(s["sentences"]) == 2
    assert "Jón" in s["sentences"][0].tree.persons


def test_prepositions(r):
    s = r.parse_single("Ég fór niðrá bryggjuna.")
    assert s.tree is not None
    assert s.tree.match(
        "S0 >>> { IP > { VP > { PP > { P > { fs_þf } NP > { no_þf } } } } } "
    )
    s = r.parse_single("Ég var fjarri bílnum.")
    assert s.tree is not None
    assert s.tree.match(
        "S0 >>> { IP > { VP > { PP > { P > { fs_þgf } NP > { no_þgf } } } } } "
    )
    s = r.parse_single("Ég var víðsfjarri bílnum.")
    assert s.tree is not None
    assert s.tree.match(
        "S0 >>> { IP > { VP > { PP > { P > { fs_þgf } NP > { no_þgf } } } } } "
    )
    s = r.parse_single("Ég var allfjarri bílnum.")
    assert s.tree is not None
    assert s.tree.match(
        "S0 >>> { IP > { VP > { PP > { P > { fs_þgf } NP > { no_þgf } } } } } "
    )


def test_personally(r):
    s = r.parse_single("Mér persónulega þótti þetta ekki flott.")
    assert s.tree is not None
    assert (
        s.tree.flat_with_all_variants
        == "S0 S-MAIN IP NP-SUBJ pfn_et_p1_þgf ao /NP-SUBJ VP VP so_subj_op_þgf_et_fh_gm_þt /VP "
        "NP fn_et_hk_nf /NP NP-PRD eo lo_et_hk_nf_sb /NP-PRD /VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single("Þessi samningur varðar þig persónulega.")
    assert s.tree is not None
    assert (
        s.tree.flat_with_all_variants
        == "S0 S-MAIN IP NP-SUBJ fn_et_kk_nf no_et_kk_nf /NP-SUBJ VP VP "
        "so_1_þf_et_fh_gm_nt_p3 /VP NP-OBJ pfn_et_p2_þf ao /NP-OBJ /VP /IP /S-MAIN p /S0"
    ) or (
        s.tree.flat_with_all_variants
        == "S0 S-MAIN IP NP-SUBJ fn_et_kk_nf no_et_kk_nf /NP-SUBJ VP VP "
        "so_1_þf_subj_op_þf_et_fh_gm_nt /VP NP-OBJ pfn_et_p2_þf ao /NP-OBJ /VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single("Þetta kom illa við þær persónulega.")
    assert s.tree is not None
    assert (
        s.tree.flat_with_all_variants
        == "S0 S-MAIN IP NP-SUBJ fn_et_hk_nf /NP-SUBJ VP VP so_0_et_fh_gm_p3_þt /VP "
        "ADVP ao /ADVP PP P fs_þf /P NP pfn_ft_kvk_p3_þf ao /NP /PP /VP /IP /S-MAIN p /S0"
    )


def test_adjectives(r):
    sents = [
        "Páll er skemmtilegur.",
        "Páll varð skemmtilegur.",
        "Páll má vera skemmtilegur.",
        "Páll mætti verða skemmtilegur.",
        "Páll skyldi vera skemmtilegur.",
        "Páll skal verða skemmtilegur.",
        "Páll hefur verið skemmtilegur.",
        "Páll hefur orðið skemmtilegur.",
        "Páll hefði viljað vera skemmtilegur.",
        "Páll hefði viljað verða skemmtilegur.",
        "Páll hefði getað verið skemmtilegur.",
        "Páll hefði getað orðið skemmtilegur.",
        # Of mikið af því góða?
        # "Páll hefði getað átt að vera skemmtilegur.",
        # "Páll hafði getað átt að verða skemmtilegur.",
        "Páll mætti hafa verið skemmtilegur.",
        "Páll má hafa orðið skemmtilegur.",
        "Páll skal hafa verið skemmtilegur.",
        "Páll skyldi hafa orðið skemmtilegur.",
        "Páll gæti hafa verið skemmtilegur.",
        "Páll gæti hafa orðið skemmtilegur.",
        "Páll ætti að vera skemmtilegur.",
        "Páll ætti að hafa verið skemmtilegur.",
        "Páll átti að verða skemmtilegur.",
        "Páll á að hafa orðið skemmtilegur.",
        "Páll gæti hafa átt að vera skemmtilegur.",
        "Páll getur hafa átt að verða skemmtilegur.",
    ]
    for sent in sents:
        s = r.parse_single(sent)
        assert s.tree is not None
        assert s.tree.nouns == ["Páll"]
        assert s.tree.S_MAIN.IP.VP.NP_PRD.lemmas == ["skemmtilegur"]


def test_all_mine(r):
    s = r.parse_single("Ég setti allt mitt í hlutabréfin.")
    assert s.tree is not None
    assert s.tree.nouns == ["hlutabréf"]
    assert s.tree.S.IP.VP.NP_OBJ.lemmas == ["allur", "minn"]
    s = r.parse_single("Ég tapaði öllu mínu í spilakössum.")
    assert s.tree is not None
    assert s.tree.nouns == ["spilakassi"]
    assert s.tree.S.IP.VP.NP_OBJ.lemmas == ["allur", "minn"]
    s = r.parse_single("Þú settir allt þitt í hlutabréfin.")
    assert s.tree is not None
    assert s.tree.nouns == ["hlutabréf"]
    assert s.tree.S.IP.VP.NP_OBJ.lemmas == ["allur", "þinn"]
    s = r.parse_single("Þú tapaðir öllu þínu í spilakössum.")
    assert s.tree is not None
    assert s.tree.nouns == ["spilakassi"]
    assert s.tree.S.IP.VP.NP_OBJ.lemmas == ["allur", "þinn"]
    s = r.parse_single("Hann setti allt sitt í hlutabréfin.")
    assert s.tree is not None
    assert s.tree.nouns == ["hlutabréf"]
    assert s.tree.S.IP.VP.NP_OBJ.lemmas == ["allur", "sinn"]
    s = r.parse_single("Hún tapaði öllu sínu í spilakössum.")
    assert s.tree is not None
    assert s.tree.nouns == ["spilakassi"]
    assert s.tree.S.IP.VP.NP_OBJ.lemmas == ["allur", "sinn"]


def test_company(r):
    s = r.parse_single("Hands ASA er dótturfyrirtæki Celestial Inc.")
    assert s.tree is not None
    assert (
        s.tree.flat_with_all_variants
        == "S0 S-MAIN IP NP-SUBJ fyrirtæki fyrirtæki /NP-SUBJ "
        "VP VP so_1_nf_et_fh_gm_nt_p3 /VP NP-PRD no_et_hk_nf NP-POSS "
        "fyrirtæki fyrirtæki /NP-POSS /NP-PRD /VP /IP /S-MAIN /S0"
    )

    # NP-COMPANY is no longer in the SimpleTree format
    # assert [t.lemma for t in s.tree.all_matches("NP-COMPANY")] == [
    #    "Hands ASA",
    #    "Celestial Inc.",
    # ]
    s = r.parse_single("Hann réðst inn á skrifstofu Samherja hf. og rændi gögnum.")
    assert s.tree is not None
    assert (
        s.tree.flat_with_all_variants
        == "S0 S-MAIN IP NP-SUBJ pfn_et_kk_nf_p3 /NP-SUBJ VP VP so_0_et_fh_mm_p3_þt "
        "/VP PP ADVP-DIR ao /ADVP-DIR P fs_þf /P NP no_et_kvk_þf NP-POSS "
        "fyrirtæki fyrirtæki /NP-POSS /NP /PP /VP C st /C VP VP "
        "so_1_þgf_et_fh_gm_p3_þt /VP NP-OBJ no_ft_hk_þgf /NP-OBJ /VP /IP /S-MAIN p /S0"
    )

    # !!! Note that lemmas of words found in BÍN are in lower case
    # assert [t.lemma for t in s.tree.all_matches("NP-COMPANY")] == ["Samherja hf."]


def test_kludgy_ordinals():
    from reynir import Greynir

    r2 = Greynir()
    s = r2.parse_single(
        "Hann keypti 3ja herbergja íbúð á 1stu hæðinni "
        "en hún átti 2ja strokka mótorhjól af 4ðu kynslóð."
    )
    assert s.tree is not None
    # þriggja herbergja
    assert "NP-POSS to_ft_ef_hk no_ft_ef_hk /NP-POSS" in s.tree.flat
    # á fyrstu hæðinni
    assert "PP P fs_þgf /P NP lo_þgf_et_kvk no_et_þgf_kvk /NP /PP" in s.tree.flat
    # tveggja strokka
    assert "NP-POSS to_ft_ef_kk no_ft_ef_kk /NP-POSS" in s.tree.flat
    # af fjórðu kynslóð
    assert "PP P fs_þgf /P NP lo_þgf_et_kvk no_et_þgf_kvk /NP /PP" in s.tree.flat


def test_adjective_dative(r):
    s = r.parse_single(
        "Páli er í grundvallaratriðum óheimilt að gegna öðrum störfum "
        "meðan hann er þingmaður."
    )
    assert (
        s.tree.flat == "S0 S-MAIN IP IP NP-SUBJ person_þgf_kk /NP-SUBJ VP "
        "so_et_p3 /VP PP P fs_þgf /P NP no_ft_þgf_hk /NP /PP NP-PRD lo_nf_et_hk_sb "
        "/NP-PRD /IP IP-INF TO nhm /TO VP VP so_1_þgf_nh /VP "
        "NP-OBJ fn_ft_þgf_hk no_ft_þgf_hk /NP-OBJ /VP /IP-INF CP-ADV-TEMP "
        "C st /C IP NP-SUBJ pfn_kk_et_nf /NP-SUBJ VP VP so_1_nf_et_p3 /VP "
        "NP-PRD no_et_nf_kk /NP-PRD /VP /IP /CP-ADV-TEMP /IP /S-MAIN p /S0"
    )


def test_ambig_phrases(r):
    def has_verbs(s, v):
        return set(s.tree.verbs) == set(v)

    s = r.parse_single("Hann var sá sem ég treysti best.")
    assert has_verbs(s, ("vera", "treysta"))
    s = r.parse_single("Hún hefur verið sú sem ég treysti best.")
    assert has_verbs(s, ("hafa", "vera", "treysta"))
    s = r.parse_single("Hún væri sú sem ég treysti best.")
    assert has_verbs(s, ("vera", "treysta"))
    s = r.parse_single("Ég fór að kaupa inn en hún var að selja eignir.")
    assert has_verbs(s, ("vera", "fara", "kaupa", "selja"))
    s = r.parse_single("Ég setti gleraugun ofan á kommóðuna.")
    assert has_verbs(s, ("setja",))
    s = r.parse_single("Hugmynd Jóns varð ofan á í umræðunni.")
    assert has_verbs(s, ("verða",))
    s = r.parse_single("Efsta húsið er það síðasta sem var lokið við.")
    assert (has_verbs(s, ("vera", "ljúka"))) or (has_verbs(s, ("vera", "lúka")))
    s = r.parse_single("Hún var fljót að fara út.")
    assert has_verbs(s, ("vera", "fara"))
    s = r.parse_single("Það var forsenda þess að hún var fljót að maturinn var góður.")
    assert has_verbs(s, ("vera",))
    s = r.parse_single("Peningarnir verða nýttir til uppbyggingar.")
    assert has_verbs(s, ("verða", "nýta"))
    s = r.parse_single("Ég vildi ekki segja neitt sem ræðan stangaðist á við.")
    assert has_verbs(s, ("vilja", "segja", "stanga"))
    s = r.parse_single("Reglurnar stönguðust á við raunveruleikann.")
    assert has_verbs(s, ("stanga",))
    s = r.parse_single("Hann braut gegn venju með því að hnerra.")
    assert has_verbs(s, ("brjóta", "hnerra"))
    s = r.parse_single("Hann braut gegn venju með því að ræðan var óhefðbundin.")
    assert has_verbs(s, ("brjóta", "vera"))


def test_relative_clause(r):
    s = r.parse_single("Þetta eru lausnirnar sem kallað hefur verið eftir.")
    assert (
        s.tree.flat_with_all_variants
        == "S0 S-MAIN IP NP-SUBJ fn_et_hk_nf /NP-SUBJ VP VP "
        "so_1_nf_fh_ft_gm_nt_p3 /VP NP-PRD no_ft_gr_kvk_nf CP-REL C stt /C "
        "IP NP-PRD lo_et_hk_nf_sb /NP-PRD VP-AUX VP so_et_fh_gm_nt_p3 /VP "
        "VP so_gm_sagnb /VP /VP-AUX ADVP ao /ADVP /IP /CP-REL /NP-PRD /VP /IP "
        "/S-MAIN p /S0"
    ) or (
        s.tree.flat_with_all_variants
        == "S0 S-MAIN IP NP-SUBJ fn_et_hk_nf /NP-SUBJ VP VP "
        "so_1_nf_fh_ft_gm_nt_p3 /VP NP-PRD no_ft_gr_kvk_nf CP-REL C stt /C "
        "IP NP-PRD lo_et_hk_nf_sb /NP-PRD VP-AUX VP so_et_fh_gm_nt_p3 /VP "
        "VP so_gm_sagnb /VP /VP-AUX /IP /CP-REL /NP-PRD ADVP ao /ADVP /VP /IP "
        "/S-MAIN p /S0"
    )


def test_neutral_pronoun(r):
    s = r.parse_single("Hán var ánægt með hest háns.")
    assert (
        s.tree.flat_with_all_variants
        == "S0 S-MAIN IP NP-SUBJ pfn_et_hk_nf_p3 /NP-SUBJ "
        "VP VP-AUX so_et_fh_gm_p3_þt /VP-AUX NP-PRD lo_et_hk_nf_sb /NP-PRD "
        "PP P fs_þf /P NP no_et_kk_þf NP-POSS pfn_ef_et_hk_p3 /NP-POSS /NP /PP "
        "/VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single("Hán langaði að tala við hán um málið.")
    assert (
        s.tree.flat_with_all_variants
        == "S0 S-MAIN IP NP-SUBJ pfn_et_hk_p3_þf /NP-SUBJ VP "
        "VP so_1_þf_subj_op_þf_et_fh_gm_þt /VP IP-INF-OBJ TO nhm /TO VP VP so_0_gm_nh "
        "/VP PP P fs_þf /P NP pfn_et_hk_p3_þf /NP /PP PP P fs_þf /P NP no_et_gr_hk_þf "
        "/NP /PP /VP /IP-INF-OBJ /VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single("Hán Alda var ánægt.")
    assert (
        s.tree.flat_with_all_variants == "S0 S-MAIN IP NP-SUBJ pfn_et_hk_nf_p3 "
        "person_kvk_nf /NP-SUBJ VP VP-AUX so_et_fh_gm_p3_þt /VP-AUX NP-PRD lo_et_hk_nf_sb "
        "/NP-PRD /VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single("Hán Halldór var ánægt.")
    assert (
        s.tree.flat_with_all_variants == "S0 S-MAIN IP NP-SUBJ pfn_et_hk_nf_p3 "
        "person_kk_nf /NP-SUBJ VP VP-AUX so_et_fh_gm_p3_þt /VP-AUX NP-PRD lo_et_hk_nf_sb "
        "/NP-PRD /VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single("Hán Auður leitaði álits háns Ilmar.")
    # 'Auður' er bæði í kk og kvk í BÍN
    assert (
        s.tree.flat_with_all_variants == "S0 S-MAIN IP NP-SUBJ pfn_et_hk_nf_p3 "
        "person_kvk_nf /NP-SUBJ VP VP so_1_ef_et_fh_gm_p3_þt /VP NP-OBJ "
        "no_ef_et_hk NP-POSS pfn_ef_et_hk_p3 person_ef_kvk /NP-POSS /NP-OBJ "
        "/VP /IP /S-MAIN p /S0"
    ) or (
        s.tree.flat_with_all_variants == "S0 S-MAIN IP NP-SUBJ pfn_et_hk_nf_p3 "
        "person_kk_nf /NP-SUBJ VP VP so_1_ef_et_fh_gm_p3_þt /VP NP-OBJ "
        "no_ef_et_hk NP-POSS pfn_ef_et_hk_p3 person_ef_kvk /NP-POSS /NP-OBJ "
        "/VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single("Háni féll illa að talað var af vanvirðingu um hán.")
    assert (
        s.tree.flat_with_all_variants == "S0 S-MAIN IP NP-SUBJ pfn_et_hk_p3_þgf "
        "/NP-SUBJ VP VP so_1_nf_subj_op_þgf_et_fh_gm_þt /VP NP-OBJ eo CP-THT "
        "C st /C IP VP VP so_gm_sagnb /VP VP so_et_fh_gm_p3_þt /VP PP P fs_þgf "
        "/P NP no_et_kvk_þgf /NP /PP PP P fs_þf /P NP pfn_et_hk_p3_þf /NP /PP "
        "/VP /IP /CP-THT /NP-OBJ /VP /IP /S-MAIN p /S0"
    ) or (
        s.tree.flat_with_all_variants == "S0 S-MAIN IP NP-SUBJ pfn_et_hk_p3_þgf "
        "/NP-SUBJ VP VP so_1_nf_subj_op_þgf_et_fh_gm_þt /VP CP-THT-OBJ ADVP eo "
        "/ADVP C st /C IP VP VP so_et_hk_lhþt_nf_sb /VP VP-AUX so_et_fh_gm_p3_þt /VP-AUX "
        "PP P fs_þgf /P NP no_et_kvk_þgf /NP /PP PP P fs_þf /P NP "
        "pfn_et_hk_p3_þf /NP /PP /VP /IP /CP-THT-OBJ /VP /IP /S-MAIN p /S0"
    )


def test_þess_getið(r):
    s = r.parse_single("Ég lét þess ekki getið að Jón væri frábær.")
    assert s is not None
    assert s.tree is not None
    assert "láta" in s.tree.verbs
    assert "geta" in s.tree.verbs
    s = r.parse_single("Ég mun galvaskur láta þess getið að Jón sé frábær.")
    assert s is not None
    assert s.tree is not None
    assert "láta" in s.tree.verbs
    assert "geta" in s.tree.verbs
    s = r.parse_single("Ég hef ætíð látið þess getið að Jón sé frábær.")
    assert s is not None
    assert s.tree is not None
    assert "láta" in s.tree.verbs
    assert "geta" in s.tree.verbs
    s = r.parse_single("Ég sagðist hafa látið þess getið að Jón sé frábær.")
    assert s is not None
    assert s.tree is not None
    assert "segja" in s.tree.verbs
    assert "hafa" in s.tree.verbs
    assert "láta" in s.tree.verbs
    assert "geta" in s.tree.verbs


def test_þau(r):
    s = r.parse_single("Ég sá þau Margréti áður en þau hlupust á brott.")
    assert s and s.tree
    assert s.tree.S.IP.VP.NP_OBJ.tidy_text == "þau Margréti"
    s = r.parse_single("Þær Þórhildur urðu aldrei sáttar eftir þetta.")
    assert s and s.tree
    assert s.tree.S.IP.NP_SUBJ.tidy_text == "Þær Þórhildur"
    s = r.parse_single("Ég fór til þeirra Sigurjóns.")
    assert s and s.tree
    assert s.tree.S.IP.VP.PP.NP.tidy_text == "þeirra Sigurjóns"
    s = r.parse_single("Mér leiddust stælarnir í þeim Gunnlaugi.")
    # The argument frames have been tighened, when the subject frames are
    # merged with the object frames this should work for 'leiðast'.
    # assert s and s.tree
    # assert s.tree.S.IP.NP_SUBJ.PP.NP.tidy_text == "þeim Gunnlaugi"


def test_deterministic_reduction(r):
    """Repeated parses of the same sentence must yield the same tree,
    even when the parse forest contains subtrees with exactly equal
    scores. The ambiguous sentences below used to come out differently
    between runs when the C++ parser's Earley state hash included
    memory addresses, making the family order in the forest - and
    thereby the reducer's tie-breaking - nondeterministic."""
    sentences = [
        "Ása sá sól.",
        "Konan sem kom í heimsókn í gær ætlar að kaupa nýja íbúð í miðbænum.",
        "Hr. Jón Jónsson býr á Laugavegi 26 og á 3,4 milljónir króna í banka.",
        "Það rignir sjaldan í Reykjavík í júlí en þó gerist það stundum.",
        "Tuttugu og þrír hestar, fimm kýr og tólf kindur voru á bænum.",
    ]
    for sent in sentences:
        flats = set()
        for _ in range(5):
            s = r.parse_single(sent)
            assert s is not None and s.tree is not None
            flats.add(s.tree.flat)
        assert len(flats) == 1, f"Nondeterministic parse of '{sent}': {flats}"


def test_aukafall(r):
    s = r.parse_single("Mér blöskrar framkoma Páls.")
    assert s and s.tree
    s = r.parse_single("Mig brestur þolinmæði.")
    assert s and s.tree
    s = r.parse_single("Mig grípur mikill geigur.")
    assert s and s.tree
    s = r.parse_single("Mig þvarr allur máttur.")
    assert s and s.tree
    s = r.parse_single("Mig þraut örendið.")
    assert s and s.tree


def test_impersonal_passive_prep(r):
    """The 'vera* bent á' ambiguous phrase must retain the preposition
    meaning of 'á', so that 'er bent á' + Nl parses"""
    s = r.parse_single("Í skýrslunni er bent á kostina.")
    assert s and s.tree
    assert (
        s.tree.flat_with_all_variants
        == "S0 S-MAIN IP PP P fs_þgf /P NP no_et_gr_kvk_þgf /NP /PP "
        "VP VP-AUX so_et_fh_gm_nt_p3 /VP-AUX VP so_gm_sagnb /VP "
        "PP P fs_þf /P NP no_ft_gr_kk_þf /NP /PP /VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single("Í skýrslunni er bent á kosti og galla upptöku evru.")
    assert s and s.tree
    # 'bent á' followed by a subordinate clause must still work
    s = r.parse_single("Í skýrslunni er bent á að vandinn sé mikill.")
    assert s and s.tree
    s = r.parse_single(
        "Í nýrri ársskýrslu sjóðsins um Ísland er bent á kosti og galla "
        "upptöku evru og varað við því að verðtrygging í íslensku "
        "efnahagslífi geti viðhaldið verðbólgu."
    )
    assert s and s.tree


def test_uninflected_genitive_names(r):
    """Non-inflecting (foreign) person names, i.e. names having identical
    forms in nf/þf/þgf, should also be accepted in genitive contexts"""
    s = r.parse_single("Samtök Paul Watson mótmæltu hvalveiðum.")
    assert s and s.tree
    assert (
        s.tree.flat_with_all_variants
        == "S0 S-MAIN IP NP-SUBJ no_ft_hk_nf NP-POSS person_ef_kk person_ef_kk "
        "/NP-POSS /NP-SUBJ VP VP so_1_þgf_fh_ft_gm_p3_þt /VP "
        "NP-OBJ no_ft_kvk_þgf /NP-OBJ /VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single("Ég las bók John Lennon.")
    assert s and s.tree
    s = r.parse_single(
        "Samtök Paul Watson leiða líkur að því að þau hafi með aðgerðum "
        "sínum frá því að hvalveiðitímabilið hófst bjargað lífi "
        "allt að þrjátíu langreyða."
    )
    assert s and s.tree
    # Inflecting Icelandic names must not gain a genitive interpretation
    s = r.parse_single("Samtök Guðmundur Jónsson eru góð.")
    assert s.tree is None
    # Token-level check of person name cases
    from reynir.bintokenizer import tokenize

    toks = [t for t in tokenize("Samtök Paul Watson mótmæltu hvalveiðum.")]
    pw = next(t for t in toks if t.txt == "Paul Watson")
    assert set(pn.case for pn in pw.person_names) == {"nf", "þf", "þgf", "ef"}
    toks = [t for t in tokenize("Þarna gengur Jón.")]
    jon = next(t for t in toks if t.txt == "Jón")
    assert "ef" not in set(pn.case for pn in jon.person_names)


def test_sem_role_relative_clause(r):
    """A 'sem' + Nl_nf role complement ('starfar sem sérfræðingur')
    must be allowed inside a subject-gap relative clause"""
    s = r.parse_single("Konan, sem starfar sem sérfræðingur hjá bankanum, er glöð.")
    assert s and s.tree
    assert (
        s.tree.flat_with_all_variants
        == "S0 S-MAIN IP NP-SUBJ no_et_gr_kvk_nf p CP-REL C stt /C "
        "IP VP so_0_et_fh_gm_nt_p3 /VP CP-ADV-CMP C st /C NP no_et_kk_nf "
        "PP P fs_þgf /P NP no_et_gr_kk_þgf /NP /PP /NP /CP-ADV-CMP /IP "
        "/CP-REL p /NP-SUBJ VP VP-AUX so_et_fh_gm_nt_p3 /VP-AUX "
        "NP-PRD lo_et_kvk_nf_sb /NP-PRD /VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single(
        "Doktor Stefán Ólafsson, sem starfar sem sérfræðingur hjá Eflingu, "
        "gefur ekki mikið fyrir myljandi hagnað bankanna."
    )
    assert s and s.tree


def test_oblique_subject_infinitive(r):
    """Oblique subject + perfect infinitive ('hafa' + supine) in the
    complement of segja/telja: 'segir Spáni hafa mistekist'"""
    s = r.parse_single("Hún segir Spáni hafa mistekist að vernda landamærin.")
    assert s and s.tree
    assert (
        s.tree.flat_with_all_variants
        == "S0 S-MAIN IP NP-SUBJ pfn_et_kvk_nf_p3 /NP-SUBJ VP VP "
        "so_1_þf_et_fh_gm_nt_p3 /VP IP NP no_et_kk_þgf /NP VP so_0_gm_nh /VP "
        "VP so_mm_sagnb /VP IP-INF TO nhm /TO VP VP so_1_þf_gm_nh /VP "
        "NP-OBJ no_ft_gr_hk_þf /NP-OBJ /VP /IP-INF /IP /VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single("Hún segir mig hafa dreymt vel.")
    assert s and s.tree
    s = r.parse_single("Hún telur Spáni hafa mistekist.")
    assert s and s.tree
    s = r.parse_single(
        "Hún segir Spáni hafa mistekist að vernda ytri landamæri "
        "Schengen-svæðisins gegn innrás."
    )
    assert s and s.tree


def test_postposed_vegna(r):
    """A genitive Nl preceding 'vegna' ('sýningarinnar vegna')
    should parse as a prepositional phrase"""
    s = r.parse_single("Sýningarinnar vegna ákvað hann þetta.")
    assert s and s.tree
    assert (
        s.tree.flat_with_all_variants
        == "S0 S-MAIN IP PP NP no_ef_et_gr_kvk /NP P fs_ef /P /PP "
        "VP VP so_1_þf_et_fh_gm_p3_þt /VP NP-SUBJ pfn_et_kk_nf_p3 /NP-SUBJ "
        "NP-OBJ fn_et_hk_þf /NP-OBJ /VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single("Hann gerði þetta mín vegna.")
    assert s and s.tree
    s = r.parse_single("Hann gerði þetta veðursins vegna.")
    assert s and s.tree
    # Normal (preposed) order must be unaffected
    s = r.parse_single("Hann gerði þetta vegna veðursins.")
    assert s and s.tree
    s = r.parse_single("Trén standa beggja vegna vegarins.")
    assert s and s.tree
    s = r.parse_single(
        "Umboðsmaður Boy George sagði að sýningarinnar vegna hefði hann "
        "ákveðið að söngvarinn yrði ekki með í henni."
    )
    assert s and s.tree


def test_pronoun_postposed_adjective(r):
    """A personal pronoun followed by an agreeing adjective phrase
    should form a noun phrase: '(með) hann fremstan (í fararbroddi)'"""
    s = r.parse_single("Með hann fremstan í fararbroddi vann liðið leikinn.")
    assert s and s.tree
    assert (
        s.tree.flat_with_all_variants
        == "S0 S-MAIN IP PP P fs_þf /P NP pfn_et_kk_p3_þf lo_esb_et_kk_þf "
        "PP P fs_þgf /P NP no_et_kk_þgf /NP /PP /NP /PP "
        "VP VP so_1_þf_et_fh_gm_p3_þt /VP NP-SUBJ no_et_gr_hk_nf /NP-SUBJ "
        "NP-OBJ no_et_gr_kk_þf /NP-OBJ /VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single("Ég hitti hana glaða.")
    assert s and s.tree
    s = r.parse_single(
        "Með hann fremstan í fararbroddi tókst liði Levante "
        "að bjarga sér frá falli."
    )
    assert s and s.tree


def test_designation_numeral(r) -> None:
    """An uninflected neuter nominative numeral used as a designation
    after a noun: '(lögreglu)stöð tvö', 'stofa fimm'"""
    s = r.parse_single("Hann býr í umdæmi lögreglustöðvar tvö.")
    assert s and s.tree
    assert (
        s.tree.flat_with_all_variants
        == "S0 S-MAIN IP NP-SUBJ pfn_et_kk_nf_p3 /NP-SUBJ VP VP so_0_et_fh_gm_nt_p3 /VP "
        "PP P fs_þgf /P NP no_et_hk_þgf NP-POSS no_ef_et_kvk to_ft_hk_nf "
        "/NP-POSS /NP /PP /VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single("Hann býr í stofu fimm.")
    assert s and s.tree
    s = r.parse_single(
        "Það átti sér stað í umdæmi lögreglustöðvar tvö, "
        "sem sér um Hafnarfjörð og Garðabæ."
    )
    assert s and s.tree
    # An agreeing numeral must still be preferred where possible
    s = r.parse_single("Ég sá mennina þrjá.")
    assert s and s.tree
    assert "to_ft_kk_þf" in s.tree.flat_with_all_variants


def test_skommu_eftir_ad(r) -> None:
    """'skömmu eftir' is merged into a single preposition token in
    Phrases.conf; it must also work as a temporal conjunction head:
    '(svona) skömmu eftir að X gerðist'"""
    s = r.parse_single("Við hittumst skömmu eftir að atburðirnir áttu sér stað.")
    assert s and s.tree
    assert (
        s.tree.flat_with_all_variants
        == "S0 S-MAIN IP NP-SUBJ pfn_ft_nf_p1 /NP-SUBJ VP VP "
        "so_0_fh_ft_mm_nt_p1 /VP CP-ADV-TEMP C P ao fs /P st /C "
        "IP NP-SUBJ no_ft_gr_kk_nf /NP-SUBJ VP VP so_2_þgf_þf_fh_ft_gm_p3_þt /VP "
        "NP-IOBJ abfn_þgf /NP-IOBJ NP-OBJ no_et_kk_þf /NP-OBJ /VP /IP "
        "/CP-ADV-TEMP /VP /IP /S-MAIN p /S0"
    )
    # With a preceding degree adverb
    s = r.parse_single("Við hittumst svona skömmu eftir að atburðirnir áttu sér stað.")
    assert s and s.tree
    s = r.parse_single("Við hittumst örskömmu eftir að atburðirnir áttu sér stað.")
    assert s and s.tree
    # The plain prepositional use must still work
    s = r.parse_single("Við hittumst skömmu eftir fundinn.")
    assert s and s.tree
    # The original full sentence
    s = r.parse_single(
        "„Það var mikilvægt að koma saman svona skömmu eftir að þessir "
        "atburðir áttu sér stað, og fara yfir staðreyndir málsins og hvað "
        "við getum lært af þessu,“ segir Þorbjörg Sigríður Gunnlaugsdóttir "
        "dómsmálaráðherra, um fjarfund ráðherra Schengen ríkjanna sem "
        "haldinn var í morgun."
    )
    assert s and s.tree


def _rel_clause_pp(r, sentence: str) -> str:
    """Parse and return the contents of the first CP-REL in flat form"""
    s = r.parse_single(sentence)
    assert s and s.tree
    flat = s.tree.flat
    assert "CP-REL" in flat
    return flat[flat.index("CP-REL") : flat.index("/CP-REL")]


def test_rel_clause_pp_attachment(r) -> None:
    """A PP that matches the relative clause verb ('sjá um X') must stay
    inside the relative clause instead of escaping to the main clause.
    This used to fail when a shared preposition subtree was scored in
    one verb context and the memoized score reused in another."""
    for sentence in (
        "Það átti sér stað í umdæmi lögreglustöðvar tvö, "
        "sem sér um Hafnarfjörð og Garðabæ.",
        "Slysið varð í umdæmi stöðvarinnar, sem sér um Hafnarfjörð og Garðabæ.",
        "Hún las bókina um konuna, sem sér um Hafnarfjörð.",
    ):
        assert "fs_þf" in _rel_clause_pp(r, sentence), sentence
    # Exact tree for the sentence from greynir.is that exposed the bug
    s = r.parse_single(
        "Það átti sér stað í umdæmi lögreglustöðvar tvö, "
        "sem sér um Hafnarfjörð og Garðabæ."
    )
    assert s and s.tree
    assert (
        s.tree.flat_with_all_variants
        == "S0 S-MAIN IP NP-SUBJ pfn_et_hk_nf_p3 /NP-SUBJ VP VP "
        "so_2_þgf_þf_et_fh_gm_p3_þt /VP NP-IOBJ abfn_þgf /NP-IOBJ "
        "NP-OBJ no_et_kk_þf PP P fs_þgf /P NP no_et_hk_þgf "
        "NP-POSS no_ef_et_kvk to_ft_hk_nf p "
        "CP-REL C stt /C IP VP VP so_0_et_fh_gm_nt_p3 /VP "
        "PP P fs_þf /P NP no_et_kk_þf C st /C no_et_kk_þf /NP /PP "
        "/VP /IP /CP-REL /NP-POSS /NP /PP /NP-OBJ /VP /IP /S-MAIN p /S0"
    )
    # The relative clause attaches to the nearest noun (lögreglustöðvar)
    # A preposition that matches the main verb (fresta e-u vegna e-s)
    # must still attach to the verb phrase, not the object noun phrase
    s = r.parse_single("Dómarinn frestaði mótinu vegna veðurs.")
    assert s and s.tree
    assert (
        s.tree.flat
        == "S0 S-MAIN IP NP-SUBJ no_et_nf_kk /NP-SUBJ VP VP so_1_þgf_et_p3 /VP "
        "NP-OBJ no_et_þgf_hk /NP-OBJ PP P fs_ef /P NP no_et_ef_kk /NP /PP "
        "/VP /IP /S-MAIN p /S0"
    )


def test_reflexive_verb_frames(r) -> None:
    """Verb frames in Verbs.conf whose object is a reflexive pronoun
    ('átta |sig /á þgf', 'tryggja sér |þf') used to be dropped entirely,
    leaving verbs such as 'átta' unknown to the parser. They are now
    registered under the pronoun's case, so that 1st and 2nd person
    objects ('áttaði mig') as well as non-reflexive objects in the same
    frame ('tryggði gestunum sigur') parse."""
    for sentence, verb in (
        ("Ég áttaði mig á þessu.", "átta"),
        ("Hann áttaði sig á villu síns vegar.", "átta"),
        ("Við áttuðum okkur ekki á því hvað þetta var erfitt.", "átta"),
        ("Liðið tryggði gestunum sigur.", "tryggja"),
        ("Hún ímyndaði sér þetta.", "ímynda"),
        ("Hún furðaði sig á þessu.", "furða"),
        ("Hann notfærði sér aðstöðuna.", "notfæra"),
        ("Hann faðmaði hana.", "faðma"),
        ("Þau minnka losun.", "minnka"),
        ("Þau trúlofuðu sig árið 2011 og gengu í hjónaband árið 2013.", "trúlofa"),
    ):
        s = r.parse_single(sentence)
        assert s is not None and s.tree is not None, sentence
        assert verb in s.tree.verbs, sentence
    # A verb reading that is only licensed by a reflexive frame
    # ('eiga sér |þf') must not displace a preposition reading
    s = r.parse_single("Eðlisfræðingurinn lést í dag, á pí-deginum.")
    assert s is not None and s.tree is not None
    assert s.tree.verbs == ["láta"]


def test_verb_particle_before_object(r) -> None:
    """A verb particle may precede the object ('bjó til hús',
    'kastaði upp boltanum'); the particle is accepted if Verbs.conf lists
    it for the verb (*til, *upp), and the object is parsed as a direct
    object rather than as the object of a preposition."""
    for sentence, pattern in (
        ("Hann bjó til hús.", "VP so_1_þf_et_p3 /VP ao NP-OBJ no_et_þf_hk /NP-OBJ"),
        ("Hann tók upp bókina.", "VP so_1_þf_et_p3 /VP ao NP-OBJ no_et_þf_kvk /NP-OBJ"),
        ("Hann kastaði upp boltanum.", "VP so_1_þgf_et_p3 /VP ao NP-OBJ no_et_þgf_kk /NP-OBJ"),
        ("Hann skilaði inn skýrslunni.", "VP so_1_þgf_et_p3 /VP ao NP-OBJ no_et_þgf_kvk /NP-OBJ"),
        ("Hann sagði upp störfum.", "VP so_1_þgf_et_p3 /VP ao NP-OBJ no_ft_þgf_hk /NP-OBJ"),
        ("Hún hefur búið til mat.", "VP so_1_þf_sagnb /VP ao NP-OBJ no_et_þf_kk /NP-OBJ"),
        ("Hún ætlar að búa til mat.", "VP so_1_þf_nh /VP ao NP-OBJ no_et_þf_kk /NP-OBJ"),
        ("Hann ætlar að skila inn skýrslunni.", "VP so_1_þgf_nh /VP ao NP-OBJ no_et_þgf_kvk /NP-OBJ"),
        ("Búðu til mat!", "VP so_1_þf_bh /VP ao NP-OBJ no_et_þf_kk /NP-OBJ"),
    ):
        s = r.parse_single(sentence)
        assert s is not None and s.tree is not None, sentence
        assert pattern in s.tree.flat, (sentence, s.tree.flat)
    # Prepositional phrases are still preferred where the verb
    # does not take the particle
    for sentence in (
        "Hann bjó í húsinu.",
        "Hann kastaði upp á þakið.",
        "Hann ætlar að kasta upp á þakið.",
    ):
        s = r.parse_single(sentence)
        assert s is not None and s.tree is not None, sentence
        assert " PP " in s.tree.flat and "NP-OBJ" not in s.tree.flat, (sentence, s.tree.flat)


def test_deterministic_tie_break() -> None:
    """Equally scored families of children are resolved by the position
    of the production in the grammar (first alternative wins) and then
    by the spans of the child nodes, never by the order in which the
    parser happened to complete the derivations."""
    from reynir.reducer import _ReductionScope

    class FakeReducer:
        """Stand-in for ParseForestReducer with no verb context"""

        def get_current_verb(self):
            return None

        def set_current_verb(self, verb):
            pass

        def push_current_verb(self, verb):
            pass

        def pop_current_verb(self):
            pass

    class FakeNode:
        is_completed = False
        nonterminal = None
        start = 0
        end = 3

        def __init__(self, start=0, end=3):
            self.start = start
            self.end = end

    class FakeProd:
        priority = 0

        def __init__(self, index):
            self.index = index

    def choose(families):
        """families: list of (prod, children); all scored equally.
        Returns the index of the winning family."""
        reducer = FakeReducer()
        scope = _ReductionScope(reducer, FakeNode())  # type: ignore
        for ix, (prod, children) in enumerate(families):
            scope.start_family(ix, prod, children)  # type: ignore
            for _ in children:
                scope.add_child(ix, {"sc": 1})  # type: ignore
        _, chosen = scope.process(FakeNode())  # type: ignore
        return chosen

    a, b = FakeNode(0, 1), FakeNode(1, 3)
    # The production appearing first in the grammar wins,
    # regardless of family order
    assert choose([(FakeProd(10), [a, b]), (FakeProd(5), [a, b])]) == 1
    assert choose([(FakeProd(5), [a, b]), (FakeProd(10), [a, b])]) == 0
    # Same production: the derivation whose first child spans more wins
    p = FakeProd(7)
    left_heavy = [FakeNode(0, 2), FakeNode(2, 3)]
    right_heavy = [FakeNode(0, 1), FakeNode(1, 3)]
    assert choose([(p, right_heavy), (p, left_heavy)]) == 1
    assert choose([(p, left_heavy), (p, right_heavy)]) == 0
    # A better score still beats a better key
    reducer = FakeReducer()
    scope = _ReductionScope(reducer, FakeNode())  # type: ignore
    scope.start_family(0, FakeProd(5), [a, b])  # type: ignore
    scope.add_child(0, {"sc": 1})  # type: ignore
    scope.start_family(1, FakeProd(10), [a, b])  # type: ignore
    scope.add_child(1, {"sc": 2})  # type: ignore
    assert scope.process(FakeNode())[1] == 1  # type: ignore


def test_locative_i_prefers_dative(r) -> None:
    """When the noun form is the same in accusative and dative, 'í' is
    read as locative (dative) unless a verb frame says otherwise"""
    for sentence in (
        "Áfram óvissa meðan ástandið er svona í Úkraínu.",
        "Regína er sviðsstjóri velferðarsviðs í Reykjavík.",
        "Samkomulagið er í höfn.",
        "Slysið varð í umdæmi lögreglunnar.",
    ):
        s = r.parse_single(sentence)
        assert s and s.tree, sentence
        assert "P fs_þgf /P" in s.tree.flat, sentence
        assert "P fs_þf /P" not in s.tree.flat, sentence
    # Directional readings governed by the verb frame stay accusative
    for sentence in (
        "Chelsea kom í heimsókn.",
        "Hann fór í bæinn.",
        "Hún setti bókina í hillu.",
    ):
        s = r.parse_single(sentence)
        assert s and s.tree, sentence
        assert "P fs_þf /P" in s.tree.flat, sentence
        assert "P fs_þgf /P" not in s.tree.flat, sentence


def test_verb_with_clitic_subject(r) -> None:
    """Interrogative verb forms with a cliticized second person subject
    ('ertu', 'viltu', 'geturðu') parse as verbs with an included subject"""
    for sentence, lemma in (
        ("Ertu búinn?", "vera"),
        ("Viltu koma út að leika?", "vilja"),
        ("Geturðu hjálpað mér?", "geta"),
        ("Veistu hvað klukkan er?", "vita"),
        ("Hefurðu heyrt eitthvað frá íbúunum?", "hafa"),
        ("Ertu duglegur að hreyfa þig?", "vera"),
        ("Hvernig komstu í kynni við vinnuna?", "koma"),
        ("Ferðu á ballið?", "fara"),
        ("Áttu einhverja sögu af vandræðalegu stefnumóti?", "eiga"),
        ("Þá viltu það ekki.", "vilja"),
    ):
        s = r.parse_single(sentence)
        assert s and s.tree, sentence
        flat = s.tree.flat
        assert "NP-SUBJ" not in flat, sentence
        assert "_sp" in flat, sentence
        assert lemma in s.tree.verbs, sentence
    # The clitic form is not an imperative of 'erta'
    s = r.parse_single("Ertu búinn?")
    assert s and s.tree
    assert s.tree.flat == (
        "S0 S-QUE IP VP VP-AUX so_et_sp /VP-AUX VP so_lhþt_sb_nf_et_kk /VP "
        "/VP /IP p /S-QUE /S0"
    )
    # A regular second person form does not get an implied subject
    s = r.parse_single("Ert búinn?")
    assert s and s.tree is None
    # An explicit subject still parses normally
    s = r.parse_single("Ert þú búinn?")
    assert s and s.tree
    assert "NP-SUBJ pfn_et_nf /NP-SUBJ" in s.tree.flat


def test_article_with_nominalized_adjective(r) -> None:
    """The free article 'hinn/hin/hið' followed by an adjective forms
    a noun phrase on its own ('hið sama', 'hið opinbera', 'hið versta'),
    or an adverbial phrase with certain superlatives ('hið fyrsta')"""
    for sentence, phrase in (
        ("Hið sama á við um starfsfólk deildarinnar.", "NP-SUBJ gr_et_nf_hk lo_nf_et_hk /NP-SUBJ"),
        ("Hið rétta er að það kviknaði í bátnum.", "NP-SUBJ gr_et_nf_hk lo_nf_et_hk /NP-SUBJ"),
        # 'sama gildir' is disambiguated in Phrases.conf; the adjective
        # reading must survive so that the article can attach to it
        ("Hið sama gildir um fleiri tegundir.", "NP-SUBJ gr_et_nf_hk lo_nf_et_hk /NP-SUBJ"),
        ("Hið opinbera greiðir kostnaðinn.", "NP-SUBJ gr_et_nf_hk lo_nf_et_hk /NP-SUBJ"),
        ("Björgunarsveitir óttast hið versta.", "NP-OBJ gr_et_þf_hk lo_þf_et_hk /NP-OBJ"),
        ("Eftir útskýringar kom hið sanna í ljós.", "NP-SUBJ gr_et_nf_hk lo_nf_et_hk /NP-SUBJ"),
        ("Hann sá hið góða og hið illa.", "gr_et_þf_hk lo_þf_et_hk C st /C gr_et_þf_hk lo_þf_et_hk"),
        ("Verkefnið þarf að leysa hið fyrsta.", "ADVP gr_et_þf_hk lo_vb_et_þf_hk /ADVP"),
        ("Íbúum var gert að yfirgefa heimili sín hið snarasta.", "ADVP gr_et_þf_hk lo_vb_et_þf_hk /ADVP"),
        # The article still attaches to a following noun
        ("Hið nýja hús er stórt.", "NP-SUBJ gr_et_nf_hk lo_nf_et_hk no_et_nf_hk /NP-SUBJ"),
        ("Hann fékk hið fyrsta verkefni.", "NP-OBJ gr_et_þf_hk lo_þf_et_hk no_et_þf_hk /NP-OBJ"),
    ):
        s = r.parse_single(sentence)
        assert s and s.tree, sentence
        assert phrase in s.tree.flat, (sentence, s.tree.flat)


def test_quoted_question_attribution(r) -> None:
    """A quoted question or exclamation followed directly by an
    attribution ('spyr hann', 'sagði hún', 'bætir hún við') without
    an intervening comma"""
    for sentence, attr in (
        ("„Komst hann ekki í hópinn?“ sagði hann.", "segja"),
        ("„Við erum að falla á tíma!“ skrifar Limbourg.", "skrifa"),
        ("„Áttu mynd?“ spyr sá þriðji.", "spyrja"),
        ("„Er þetta verk dagskrárstjórans?“ spyr hann.", "spyrja"),
        ("„Er það ekki bara flott fyrirsögn?“ svarar Ottó hlæjandi.", "svara"),
        ("„Hvað er það sem Miðflokkurinn er að gera?“ bætir hún við.", "bæta"),
        ("„Er þetta gott?“ sagði Sindri og bætti við: „Þetta er mjög gott.“", "segja"),
        ("„Er þátturinn ekki að verða búinn?“ spurði Þorgerður og hló.", "hlæja"),
    ):
        s = r.parse_single(sentence)
        assert s and s.tree, sentence
        flat = s.tree.flat
        assert flat.startswith("S0 S-QUOTE IP CP-QUOTE "), (sentence, flat)
        assert attr in s.tree.verbs, sentence
    # A proper noun as the attributed source is third person singular
    s = r.parse_single("„Við erum að falla á tíma!“ skrifar Limbourg.")
    assert s and s.tree
    assert "VP so_0_gm_fh_et_p3 /VP sérnafn" in s.tree.flat
    s = r.parse_single("„Þetta er gott,“ segir Limbourg.")
    assert s and s.tree
    assert "VP so_0_gm_fh_et_p3 /VP sérnafn" in s.tree.flat


if __name__ == "__main__":
    # When invoked as a main module, do a verbose test
    from reynir import Greynir

    g = Greynir()
    test_parse(g, verbose=True)
    test_properties(g)
    test_long_parse(g, verbose=True)
    try:
        test_consistency(g, verbose=True)
    except Exception as e:
        print(e)
    test_terminals(g)
    test_single(g)
    test_year_range(g)
    test_amounts(g)
    test_complex(g, verbose=True)
    test_attachment(g, verbose=True)
    test_measurements(g)
    test_abbreviations(g)
    try:
        test_nominative(g)
    except Exception as e:
        print(e)
    test_ifd_tag(g)
    test_tree_flat(g, verbose=True)
    test_noun_lemmas(g)
    test_composite_words(g)
    test_foreign_names(g)
    test_vocabulary(g)
    test_adjective_predicates(g)
    test_subj_op(g)
    test_names(g)
    test_prepositions(g)
    test_personally(g)
    test_company(g)
    test_adjectives(g)
    test_all_mine(g)
    try:
        test_kludgy_ordinals()
    except Exception as e:
        print(e)
    test_adjective_dative(g)
    test_ambig_phrases(g)
    test_relative_clause(g)
    try:
        test_neutral_pronoun(g)
    except Exception as e:
        print(e)
    test_foreign(g)
    test_aukafall(g)
    test_impersonal_passive_prep(g)
    test_uninflected_genitive_names(g)
    test_sem_role_relative_clause(g)
    test_oblique_subject_infinitive(g)
    test_postposed_vegna(g)
    test_pronoun_postposed_adjective(g)
    test_designation_numeral(g)
    test_skommu_eftir_ad(g)
    test_rel_clause_pp_attachment(g)
    test_reflexive_verb_frames(g)
    test_verb_particle_before_object(g)
    test_deterministic_tie_break()
    test_locative_i_prefers_dative(g)
    test_verb_with_clitic_subject(g)
    test_article_with_nominalized_adjective(g)
    test_quoted_question_attribution(g)
    g.__class__.cleanup()

"""

    test_parse.py

    Tests for Reynir module

    Copyright(C) 2018 by Miðeind ehf.
    Original author: Vilhjálmur Þorsteinsson

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""

from collections import defaultdict

r = None


def test_init():
    """ Test that importing and initializing the reynir module works """
    from reynir import Reynir

    global r
    r = Reynir()


def test_parse(verbose=False):

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
    ]
    job = r.submit(" ".join(sentences))

    results = list(job.sentences())

    for i, sent in enumerate(results):
        if verbose:
            print("Sentence {0}: {1}".format(i, sent.tidy_text))
        assert sent.tidy_text == sentences[i], "'{0}' != '{1}'".format(
            sent.tidy_text, sentences[i]
        )
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
    assert results[5].tree.nouns == [
        "1.000 dollara"
    ]
    # 'árið 1944' er tímaliður en ekki nafnliður
    assert results[6].tree.nouns == [
        "Þingvellir"
    ]
    assert results[7].tree.nouns == ["hús", "strönd"]
    assert results[8].tree.nouns == ["barn", "augnrannsókn", "húsnæðiskaup"]
    assert results[9].tree.nouns == ["barn", "loðfíla-rannsókn"]
    assert results[10].tree.nouns == ["eðlisfræðingur", "dagur", "pí", "dagur"]
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
        "Stephen",
        "Hawking",
        "láta",
        "í",
        "dagur",
        ",",
        "á",
        "pí",
        "—",
        "dagur",
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

    def num_pp(s):
        """ Count the prepositional phrases in the parse tree for sentence s """
        return len([t for t in s.tree.descendants if t.match("PP")])

    # Test that the correct number of prepositional phrases (PPs) is generated
    assert num_pp(results[8]) == 2
    assert num_pp(results[9]) == 1
    assert num_pp(results[10]) == 1
    assert num_pp(results[11]) == 4


def test_consistency(verbose=False):
    """ Check that multiple parses of the same sentences yield exactly
        the same preposition counts, and also identical scores. This is
        inter alia to guard agains nondeterminism that may arise from
        Python's random hash seeds. """

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


def test_long_parse(verbose=False):
    if verbose:
        print("Long parse test")
    txt = """
        [[ Reynt er að efla áhuga ungs fólks á borgarstjórnarmálum með framboðsfundum og skuggakosningum en þótt
        kjörstaðirnir í þeim séu færðir inn í framhaldsskólana er þátttakan lítil. Dagur B. Eggertsson nýtur mun
        meira fylgis í embætti borgarstjóra en fylgi Samfylkingarinnar gefur til kynna samkvæmt könnun Fréttablaðsins. ]]
        [[ Eins og fram kom í fréttum okkar í gær stefnir í met í fjölda framboða fyrir komandi borgarstjórnarkosningar
        í vor og gætu þau orðið að minnsta kosti fjórtán. Þá þarf minna fylgi nú en áður til að ná inn borgarfulltrúa,
        því borgarfulltrúum verður fjölgað úr fimmtán í tuttugu og þrjá. ]]
        [[ Kosningabaráttan fyrir borgarstjórnarkosningarnar í vor er hafin í framhaldsskólum borgarinnar. Samhliða
        framboðskynningum fara fram skuggakosningar til borgarstjórnar í skólunum. ]]
        [[ „Þetta er eiginlega æfing í því að taka þátt í lýðræðislegum kosningum. Við reynum að herma eftir því
        hvernig raunverulegar kosningar fara fram,“ segir Róbert Ferdinandsson kennari á félagsfræðibraut
        Fjölbrautaskólans við Ármúla. ]]
    """
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


def test_properties():
    s = r.parse("Þetta er prófun.")["sentences"][0]
    _ = s.score
    _ = s.tokens
    _ = s.tree.view  # Should not raise exception
    try:
        _ = s.tree.tree
        assert False, "Should have raised exception"
    except AttributeError:
        pass


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


def test_terminals():
    s = r.parse("Jón greiddi bænum 10 milljónir króna í skaðabætur.")["sentences"][0]
    check_terminals(s.terminals)


def test_amounts():
    s = r.parse_single("Tjónið nam 10 milljörðum króna.")
    t = s.terminals
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
    assert s.tokens[2].val[0] == 10e9
    assert s.tokens[2].val[1] == "ISK"

    s = r.parse_single("Tjónið þann 22. maí nam einum milljarði króna.")
    t = s.terminals
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
    assert s.tokens[2].val == (0, 5, 22)
    assert s.tokens[4].val[0] == 1e9
    assert s.tokens[4].val[1] == "ISK"

    s = r.parse_single("Tjónið þann 19. október 1983 nam 4,8 milljörðum dala.")
    t = s.terminals
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
    assert s.tokens[2].val == (1983, 10, 19)
    assert s.tokens[4].val[0] == 4.8e9
    assert s.tokens[4].val[1] == "USD"

    s = r.parse_single("Tjónið nam sautján milljörðum breskra punda.")
    t = s.terminals
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
    assert s.tokens[2].val[0] == 17e9
    assert s.tokens[2].val[1] == "GBP"

    s = r.parse_single("Tjónið nam 17 breskum pundum.")
    t = s.terminals
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
    assert s.tokens[2].val[0] == 17
    assert s.tokens[2].val[1] == "GBP"

    s = r.parse_single("Tjónið nam 17 pólskum zloty.")
    t = s.terminals
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
    assert s.tokens[2].val[0] == 17
    assert s.tokens[2].val[1] == "PLN"

    s = r.parse_single("Tjónið nam 101 indverskri rúpíu.")
    t = s.terminals
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
    assert s.tokens[2].val[0] == 101
    assert s.tokens[2].val[1] == "INR"

    s = r.parse_single("Tjónið nam 17 milljónum indónesískra rúpía.")
    t = s.terminals
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
    assert s.tokens[2].val[0] == 17e6
    assert s.tokens[2].val[1] == "IDR"


def test_year_range():
    s = r.parse_single("Jón var formaður árin 1944-50.")
    t = s.terminals
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
        text="formaður",
        lemma="formaður",
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


def test_single():
    s = r.parse_single("Jón greiddi bænum 10 milljónir króna í skaðabætur.")
    check_terminals(s.terminals)
    try:
        _ = r.parse_single("")
        assert False, "Should have raised StopIteration"
    except StopIteration:
        pass
    s = r.parse_single("kötturinn lömdu hesturinn")
    assert s.combinations == 0
    assert s.tree is None


def test_complex(verbose=False):
    if verbose:
        print("Complex, sentence 1", end="")
    d = r.parse(
        "ákæran var þingfest en fréttastofu er kunnugt um að maðurinn "
        "játaði þar sem þinghaldið er lokað"
    )
    if verbose:
        print(", time: {:.2f} seconds".format(d["parse_time"]))
        print("Complex, sentence 2", end="")
    d = r.parse(
        "Viðar Garðarsson, sem setti upp vefsíður fyrir Sigmund Davíð "
        "Gunnlaugsson í kjölfar birtingu Panamaskjalanna, segist ekki vita "
        "hvers vegna ákveðið var að segja að vefjunum væri haldið úti af "
        "stuðningsmönnum Sigmundar."
    )
    if verbose:
        print(", time: {:.2f} seconds".format(d["parse_time"]))
        print("Complex, sentence 3", end="")
    d = r.parse(
        "Ákæran var þingfest í Héraðsdómi Reykjaness í dag "
        "en fréttastofu er ekki kunnugt um hvort maðurinn játaði eða neitaði "
        "sök þar sem þinghaldið í málinu er lokað."
    )
    if verbose:
        print(", time: {:.2f} seconds".format(d["parse_time"]))
        print("Complex, sentence 4", end="")
    d = r.parse(
        "Út úr stílfærðri túlkun listamannsins á gamla , litla og mjóa "
        "prófessornum kom búlduleitur beljaki sem þess vegna hefði getað verið "
        "trökkdræver að norðan."
    )
    if verbose:
        print(", time: {:.2f} seconds".format(d["parse_time"]))
        print("Complex, sentence 5", end="")
    d = r.parse(
        "Rétt hjá anddyrinu var ein af þessum höggnu andlitsmyndum "
        "af þjóðfrægum mönnum þar sem listamaðurinn hafði gefist upp við að ná "
        "svipnum og ákveðið að hafa þetta í staðinn stílfærða mynd sem túlkaði "
        "fremur innri mann fyrirmyndarinnar en þá ásjónu sem daglega blasti við "
        "samferðamönnum."
    )
    if verbose:
        print(", time: {:.2f} seconds".format(d["parse_time"]))
        print("Complex, sentence 6", end="")
    d = r.parse(
        "Sú fullyrðing byggist á því að ef hlutverk skólastarfs er eingöngu til þess "
        "að undirbúa nemendur fyrir skilvirka og afkastamikla þátttöku í atvinnu- og "
        "viðskiptalífi, skerðist það rými sem einstaklingar fá í gegnum menntun til "
        "þess að rækta með sér þá flóknu hæfni sem þarf til að lifa í lýðræðissamfélagi; "
        "að móta eigin skoðanir, þjálfa gagnrýna hugsun og læsi, læra að lifa í "
        "margbreytilegu samfélagi, mynda tengsl við aðra, mótast sem einstaklingur "
        "í hnattrænu samfélagi, og takast á við ólík viðhorf, skoðanir og gildi — svo "
        "fátt eitt sé nefnt."
    )
    if verbose:
        print(", time: {:.2f} seconds".format(d["parse_time"]))


def test_measurements():
    s = r.parse_single(
        "Ég vildi leggja rúm 220 tonn en hann vildi kaupa "
        "tæplega 3,8 km af efninu í yfir 32°F frosti."
    )
    assert (
        s.tree.flat == "P S-MAIN IP NP-SUBJ pfn_et_nf /NP-SUBJ VP so_et_p1 so_1_þf_nh "
        "NP-OBJ lo_þf_ft_hk tala_ft_þf_hk no_ft_þf_hk /NP-OBJ /VP /IP /S-MAIN st "
        "S-MAIN IP NP-SUBJ pfn_kk_et_nf /NP-SUBJ VP-SEQ VP so_et_p3 so_1_þf_nh "
        "NP-OBJ NP-MEASURE ao tala mælieining /NP-MEASURE /NP-OBJ /VP "
        "PP fs_þgf NP no_et_þgf_hk PP fs_þgf NP NP-POSS NP-MEASURE ao tala "
        "mælieining /NP-MEASURE /NP-POSS no_et_þgf_hk /NP /PP /NP "
        "/PP /VP-SEQ /IP /S-MAIN p /P"
    )


def test_abbreviations():
    s = r.parse_single(
        "Ég borða köku BHM á laugard. í okt. nk. og mun þykja hún vond."
    )
    assert (
        s.tree.flat == "P S-MAIN IP NP-SUBJ pfn_et_nf /NP-SUBJ VP-SEQ VP "
        "so_1_þf_et_p1 NP-OBJ no_et_þf_kvk NP-POSS no_et_ef_hk PP fs_þgf "
        "NP no_et_þgf_kk /NP /PP /NP-POSS /NP-OBJ /VP ADVP ADVP-DATE-REL "
        "fs_þgf dagsafs lo_þgf_et_kk /ADVP-DATE-REL /ADVP st VP so_et_p1 "
        "so_1_nf_nh NP-OBJ pfn_kvk_et_nf /NP-OBJ /VP ADJP lo_sb_nf_et_kvk "
        "/ADJP /VP-SEQ /IP /S-MAIN p /P"
    )
    # The following also tests augmented variants for personal pronouns,
    # i.e. pfn_et_nf_p1 for 'ég' and pfn_et_kvk_nf_p3 for 'hún'
    # (the person is added; it's not included in BÍN)
    assert (
        s.tree.flat_with_all_variants == "P S-MAIN IP NP-SUBJ pfn_et_nf_p1 /NP-SUBJ "
        "VP-SEQ VP so_1_þf_et_fh_gm_nt_p1 NP-OBJ no_et_kvk_þf NP-POSS no_ef_et_hk "
        "PP fs_þgf NP no_et_kk_þgf /NP /PP /NP-POSS /NP-OBJ /VP "
        "ADVP ADVP-DATE-REL fs_þgf dagsafs lo_et_kk_þgf /ADVP-DATE-REL /ADVP st "
        "VP so_et_fh_gm_nt_p1 so_1_nf_gm_nh NP-OBJ pfn_et_kvk_nf_p3 /NP-OBJ /VP "
        "ADJP lo_et_kvk_nf_sb /ADJP /VP-SEQ /IP /S-MAIN p /P"
    )


def test_attachment(verbose=False):
    """ Test attachment of prepositions to nouns and verbs """
    if verbose:
        print("Testing attachment of prepositions")
    for _ in range(20):
        # Test consistency for 20 iterations
        s = r.parse_single("Ég setti dæmi um þetta í bókina mína.")
        assert (
            s.tree.flat == "P S-MAIN IP NP-SUBJ pfn_et_nf /NP-SUBJ "  # Ég
            "VP-SEQ VP so_1_þf_et_p1 NP-OBJ no_et_þf_hk "  # setti dæmi
            "PP fs_þf NP fn_et_þf_hk /NP /PP "  # um þetta
            "/NP-OBJ /VP PP fs_þf NP no_et_þf_kvk fn_et_þf_kvk /NP /PP /VP-SEQ "  # í bókina mína
            "/IP /S-MAIN p /P"
        )  # .
        s = r.parse_single("Ég setti dæmi í bókina mína um þetta.")
        assert (
            s.tree.flat == "P S-MAIN IP NP-SUBJ pfn_et_nf /NP-SUBJ "  # Ég
            "VP-SEQ VP so_1_þf_et_p1 NP-OBJ no_et_þf_hk "  # setti dæmi
            "/NP-OBJ /VP PP fs_þf NP no_et_þf_kvk fn_et_þf_kvk "  # í bókina mína
            "PP fs_þf NP fn_et_þf_hk /NP /PP /NP /PP /VP-SEQ /IP /S-MAIN p /P"
        )  # um þetta .


def test_nominative():
    """ Test conversion of noun phrases to nominative/indefinite/canonical forms """

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

    s = r.parse_single("Kristín málaði hús Hönnu Önfjörð Álfhildardóttur")
    assert (
        s.tree.first_match("NP-POSS").nominative_np == "Hanna Önfjörð Álfhildardóttir"
    )

    s = r.parse_single(
        "Stóri feiti jólasveinninn beislaði "
        "fjögur sætustu hreindýrin og ók rauða vagninum "
        "með fjölda gjafa til spenntu barnanna sem biðu "
        "milli vonar og ótta."
    )
    assert len(list(s.tree.all_matches("NP"))) == 6
    assert len(list(s.tree.top_matches("NP"))) == 3

    assert list(n.text for n in s.tree.all_matches("( no | lo)")) == [
        "Stóri",
        "feiti",
        "jólasveinninn",
        "sætustu",
        "hreindýrin",
        "rauða",
        "vagninum",
        "fjölda",
        "gjafa",
        "spenntu",
        "barnanna",
    ]
    assert list(n.nominative for n in s.tree.all_matches("( no | lo)")) == [
        "Stóri",
        "feiti",
        "jólasveinninn",
        "sætustu",
        "hreindýrin",
        "rauði",
        "vagninn",
        "fjöldi",
        "gjafir",
        "spenntu",
        "börnin",
    ]
    assert list(n.canonical for n in s.tree.all_matches("( no | lo)")) == [
        "Stór",
        "feitur",
        "jólasveinn",
        "sætast",
        "hreindýr",
        "rauður",
        "vagn",
        "fjöldi",
        "gjöf",
        "spennt",
        "barn",
    ]
    assert list(
        n.canonical for t in s.tree.top_matches("NP") for n in t.all_matches("no")
    ) == ["jólasveinn", "hreindýr", "vagn", "fjöldi", "gjöf", "barn"]


def test_ifd_tag():
    """ Test IFD tagging """
    s = r.parse_single(
        "Að minnsta kosti stal Guðbjörn J. Óskarsson 200 krónum þann 19. júní 2003 og þyngdist um 300 kg."
    )
    assert s.ifd_tags == [
        "aþ",
        "lkeþve",
        "nkeþ",
        "sfg3eþ",
        "nken-m", "nken-m", "nken-m",  # Guðbjörn J. Óskarsson
        "tfvfþ",  "nvfþ",  # 200 krónum
        "fakeo",
        "ta", "nkeo", "ta",  # 19. júní 2003
        "c",
        "sfm3eþ",
        "aa",
        "ta", "x",  # 300 kg
        ".",
    ]
    s = r.parse_single(
        "Vestur-Þýskalandi bar blátt áfram að bjarga a.m.k. 284,47 börnum kl. 11:45 árið 374 f.Kr."
    )
    assert s.ifd_tags == [
        'nheþ-ö',
        'sfg3eþ',
        'lhensf',
        'aa',
        'cn',
        'sng',
        'aa',
        'tfkfn',  # 284,47
        'nhfþ',
        'nven', 'ta',  # kl. 11:45
        'nheo', 'ta', 'aa',  # árið 374 f.Kr
        '.'
    ]


def test_tree_flat():

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
        ]
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
        )
    }

    for verb_case, amounts in AMOUNTS.items():
        for amount, currency_case, t1 in amounts:
            for currency, t2 in CURRENCIES[currency_case]:
                if verb_case == "þf":
                    sent = "Hann skuldaði mér " + amount + " " + currency + "."
                elif verb_case == "þgf":
                    sent = "Hann tapaði " + amount + " " + currency + "."
                else:
                    assert False  # Unknown verb case
                s = r.parse_single(sent)
                np_obj = s.tree.S.IP.VP.NP_OBJ.flat_with_all_variants
                assert np_obj == "NP-OBJ " + t1 + " " + t2 + " /NP-OBJ"


def test_noun_lemmas():
    """ Test abbreviation lemmas ('Schengen' is an abbreviation), proper name
        lemmas ('Ísland'), and lemmas of literal terminals in the grammar
        ('munur:kk' in this case) """
    sent = "Schengen rekur mun öflugri gagnagrunn en Ísland gæti gert."
    s = r.parse_single(sent)
    assert s.tree.nouns == ["Schengen", "munur", "gagnagrunnur", "Ísland"]


def test_composite_words():
    s = r.parse_single("Hann var mennta- og menningarmálaráðherra.")
    assert (
        s.tree.flat_with_all_variants ==
        "P S-MAIN IP NP-SUBJ pfn_et_kk_nf_p3 /NP-SUBJ VP so_1_nf_et_fh_gm_p3_þt "
        "NP-PRD no_et_kk_nf st no_et_kk_nf /NP-PRD /VP /IP /S-MAIN p /P"
    )
    s = r.parse_single("Ég borðaði sykursaltan fiskinn")
    assert s.lemmas == ['ég', 'borða', 'sykur-saltur', 'fiskur']
    s = r.parse_single("Ég borðaði sykurinnsaltan fiskinn")
    assert s.lemmas == ['ég', 'borða', 'sykur-inn-saltur', 'fiskur']
    s = r.parse_single("Ég borðaði sykrisaltan fiskinn")
    # 'sykrisaltan' is not a valid composite word, so this should get parsed
    # as an unknown noun - causing 'fiskinn' to be parsed as an adjective
    assert s.lemmas == ['ég', 'borða', 'sykrisaltan', 'fiskinn']
    s = r.parse_single("Hann fékk reynslulausn úr fangelsi")
    assert s.lemmas == ['hann', 'fá', 'reynslu-lausn', 'úr', 'fangelsi']


def test_compressed_bin():
    import reynir.bincompress as bc
    binc = bc.BIN_Compressed()
    assert "gleraugu" in binc
    assert "Ísland" in binc
    assert "Vestur-Þýskaland" in binc
    assert "glerxaugu" not in binc
    assert "x" not in binc
    assert "X" not in binc
    assert (
        binc.lookup("aðförin") ==
        [('aðför', 123454, 'kvk', 'alm', 'aðförin', 'NFETgr')]
    )
    assert (
        binc.lookup("einkabílnum") ==
        [('einkabíll', 75579, 'kk', 'alm', 'einkabílnum', 'ÞGFETgr')]
    )
    nominal_forms = [m[4] for m in binc.nominative("einkabílnum") if m[5] == "NFET"]
    assert nominal_forms == ['einkabíll']
    # Test non-latin-1 code point (should not throw an exception)
    assert "Domino’s" not in binc
    # Test errata (BinErrata.conf)
    assert (
        binc.lookup("Hafnarfjörður") ==
        [('Hafnarfjörður', 303729, 'kk', 'örn', 'Hafnarfjörður', 'NFET')]
    )


def test_foreign_names():
    s = r.parse_single("Aristóteles uppgötvaði þyngdarlögmálið.")
    assert (
        s.tree.flat_with_all_variants ==
        "P S-MAIN IP NP-SUBJ person_kk_nf /NP-SUBJ VP so_1_þf_et_fh_gm_p3_þt "
        "NP-OBJ no_et_gr_hk_þf /NP-OBJ /VP /IP /S-MAIN p /P"
    )
    # Test to check whether 'Hafstein' works as a family name in nominative case
    s = r.parse_single("Þetta voru Ólafur Ísleifsson, Júlíus Hafstein og Ingibjörg Sólrún Gísladóttir.")
    assert (
        s.tree.flat_with_all_variants ==
        "P S-MAIN IP NP-SUBJ fn_et_hk_nf /NP-SUBJ VP so_1_nf_fh_ft_gm_p3_þt NP-PRD "
        "person_kk_nf person_kk_nf p person_kk_nf person_kk_nf st person_kvk_nf person_kvk_nf person_kvk_nf "
        "/NP-PRD /VP /IP /S-MAIN p /P"
    )
    s = r.parse_single("Þetta voru Ólafur Ísleifsson, Bára Hafstein og Ingibjörg Sólrún Gísladóttir.")
    assert (
        s.tree.flat_with_all_variants ==
        "P S-MAIN IP NP-SUBJ fn_et_hk_nf /NP-SUBJ VP so_1_nf_fh_ft_gm_p3_þt NP-PRD "
        "person_kk_nf person_kk_nf p person_kvk_nf person_kvk_nf st person_kvk_nf person_kvk_nf person_kvk_nf "
        "/NP-PRD /VP /IP /S-MAIN p /P"
    )


def test_vocabulary():
    """ Test words that should be in the vocabulary, coming from
        ord.auka.csv or ord.add.csv """
    s = r.parse_single("""
        Í gær gekk ég út frá ströndum og fékk mér ís.
        """)
    assert s.tree is not None
    assert "strönd" in s.tree.nouns
    s = r.parse_single("""
        Rekjanleikinn var enginn þegar ég spurði um hann.
        """)
    assert s.tree is not None
    assert "rekjanleiki" in s.tree.nouns
    s = r.parse_single("""
        Jón hafði áhyggjur af seljanleika bréfanna.
        """)
    assert s.tree is not None
    assert "seljanleiki" in s.tree.nouns
    s = r.parse_single("""
        Tvískráning bréfanna er á döfinni.
        """)
    assert s.tree is not None
    assert "tvískráning" in s.tree.nouns
    s = r.parse_single("""
        Hann vanrækti börnin alla tíð.
        """)
    assert s.tree is not None
    assert "vanrækja" in s.tree.verbs
    s = r.parse_single("""
        Milli deildanna voru kínamúrar en starfsandi var góður.
        """)
    assert s.tree is not None
    assert "kínamúr" in s.tree.nouns
    assert "starfsandi" in s.tree.nouns


def test_adjective_predicates():
    """ Test adjectives with an associated predicate """

    # Accusative case (þolfall)
    s = r.parse_single("""
        Hundurinn var viðstaddur sýninguna sem fjallaði um hann.
        """)
    assert "ADJP lo_sb_nf_sþf_et_kk NP no_et_þf_kvk" in s.tree.flat

    # Dative case (þágufall)
    s = r.parse_single("""
        Hundurinn var málkunnugur kettinum frá fyrri tíð.
        """)
    assert "ADJP lo_sb_nf_sþgf_et_kk NP no_et_þgf_kk /NP /ADJP" in s.tree.flat

    # Possessive case (eignarfall)
    s = r.parse_single("""
        Kötturinn þóttist vera frjáls ferða sinna.
        """)
    assert "NP-PRD ADJP lo_sb_nf_sef_et_kk NP no_ft_ef_kvk fn_ft_ef_kvk /NP /ADJP" in s.tree.flat
    s = r.parse_single("""
        Kötturinn hafði verið fullur sjálfstrausts.
        """)
    assert "ADJP lo_sb_nf_sef_et_kk NP no_et_ef_hk /NP /ADJP" in s.tree.flat
    s = r.parse_single("""
        Verkamaðurinn er verður launa sinna.
        """)
    assert "ADJP lo_sb_nf_sef_et_kk NP no_ft_ef_hk fn_ft_ef_hk /NP /ADJP" in s.tree.flat


def test_subj_op():
    """ Test impersonal verbs """
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


def test_finish():
    r.__class__.cleanup()


if __name__ == "__main__":
    # When invoked as a main module, do a verbose test
    test_init()
    test_compressed_bin()
    test_parse(verbose=True)
    test_properties()
    test_long_parse(verbose=True)
    test_consistency(verbose=True)
    test_terminals()
    test_single()
    test_year_range()
    test_amounts()
    test_complex(verbose=True)
    test_attachment(verbose=True)
    test_measurements()
    test_abbreviations()
    test_nominative()
    test_ifd_tag()
    test_tree_flat()
    test_noun_lemmas()
    test_composite_words()
    test_foreign_names()
    test_vocabulary()
    test_adjective_predicates()
    test_subj_op()
    test_finish()

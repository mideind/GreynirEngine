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


def test_parse(verbose = False):

    sentences = [
        # 0
        "Hér er verið að gera tilraunir með þáttun.",
        # 1
        "Margar málsgreinar koma hér fyrir.",
        # 2
        "Þetta takast ekki að þáttar.", # Error sentence
        # 3
        "Fjórða málsgreinin er síðust.",
        # 4
        "Vatnið var 30,5 gráða heitt og ég var ánægður með það.",
        # 5
        "Hún skuldaði mér 1.000 dollara.",
        # 6
        "Ég hitti hana þann 17. júní árið 1944 á Þingvöllum.",
        # 7
        "Hann eignaðist hús við ströndina og henni tókst að mála það.",
        # 8
        "Barnið fór í augnrannsóknina eftir húsnæðiskaupin.",
        # 9
        "Barnið fór í loðfílarannsókn.", # Test composite words
        # 10
        "Eðlisfræðingurinn Stephen Hawking lést í dag, á pí-deginum.",
        # 11
        "Löngu áður en Jón borðaði ísinn sem hafði bráðnað hratt "
        "í hádeginu fór ég á veitingastaðinn á horninu og keypti mér rauðvín "
        "með hamborgaranum sem ég borðaði í gær með mikilli ánægju."
    ]
    job = r.submit(" ".join(sentences))

    results = list(job.sentences())

    for i, sent in enumerate(results):
        if verbose:
            print("Sentence {0}: {1}".format(i, sent.tidy_text))
        assert sent.tidy_text == sentences[i], "'{0}' != '{1}'".format(sent.tidy_text, sentences[i])
        if sent.parse():
            # Sentence parsed successfully
            assert i != 2
            if verbose:
                print("Successfully parsed")
                # print(sent.tree)
                # print(ParseForestDumper.dump_forest(sent.tree))
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
    assert results[0].tree.nouns == [ "tilraun", "þáttun" ]
    assert results[1].tree.nouns == [ "málsgrein" ]
    assert results[2].tree == None # Error sentence
    assert results[3].tree.nouns == [ "málsgrein" ]
    assert results[4].tree.nouns == [ "Vatnið", "gráða" ] # 'Vatnið' is a proper place name (örnefni)
    assert results[5].tree.nouns == [ ]
    assert results[6].tree.nouns == [ "ár", "Þingvellir" ]
    assert results[7].tree.nouns == [ "hús", "strönd" ]
    assert results[8].tree.nouns == [ "barn", "augnrannsókn", "húsnæðiskaup" ]
    assert results[9].tree.nouns == [ "barn", "loðfíla-rannsókn" ]
    assert results[10].tree.nouns == [ "eðlisfræðingur", "pí", "dagur" ]
    assert results[11].tree.nouns == [ 'Jón', 'ís', 'veitingastaður', 'horn', 'rauðvín',
        'hamborgari', 'ánægja' ]

    # Test that the parser finds the correct verbs
    assert results[0].tree.verbs == [ "vera", "vera", "gera" ]
    assert results[1].tree.verbs == [ "koma" ]
    assert results[2].tree == None # Error sentence
    assert results[3].tree.verbs == [ "vera" ]
    assert results[4].tree.verbs == [ "vera", "vera" ]
    assert results[5].tree.verbs == [ "skulda" ]
    assert results[6].tree.verbs == [ "hitta" ]
    assert results[7].tree.verbs == [ "eigna", "taka", "mála" ]
    assert results[8].tree.verbs == [ "fara" ]
    assert results[9].tree.verbs == [ "fara" ]
    assert results[10].tree.verbs == [ "láta" ]
    assert results[11].tree.verbs == [ 'borða', 'hafa', 'bráðna', 'fara', 'kaupa', 'borða' ]

    # Test that the parser finds the correct word lemmas
    assert results[0].tree.lemmas == [ "hér", "vera", "vera", "að", "gera",
        "tilraun", "með", "þáttun", "." ]
    assert results[1].tree.lemmas == [ "margur", "málsgrein", "koma", "hér", "fyrir", "." ]
    assert results[2].tree == None # Error sentence
    assert results[3].tree.lemmas == [ "fjórði", "málsgrein", "vera", "síðari", "." ]
    assert results[4].tree.lemmas == [ "Vatnið", "vera", "30,5", "gráða", "heitur",
        "og", "ég", "vera", "ánægður", "með", "það", "." ]
    assert results[5].tree.lemmas == [ "hún", "skulda", "ég", "1.000 dollara", "." ]
    assert results[6].tree.lemmas == [ "ég", "hitta", "hún", "sá", "17. júní",
        "ár", "1944", "á", "Þingvellir", "." ]
    assert results[7].tree.lemmas == [ "hann", "eigna", "hús", "við", "strönd",
        "og", "hún", "taka", "að", "mála", "það", "." ]
    assert results[8].tree.lemmas == [ "barn", "fara", "í", "augnrannsókn", "eftir",
        "húsnæðiskaup", "." ]
    assert results[9].tree.lemmas == [ "barn", "fara", "í", "loðfíla-rannsókn", "." ]
    assert results[10].tree.lemmas == [ "eðlisfræðingur", "Stephen", "Hawking",
        "láta", "í dag", ",", "á", "pí", "—", "dagur", "." ]
    assert results[11].tree.lemmas == [ 'langur', 'áður', 'en', 'Jón', 'borða', 'ís',
        'sem', 'hafa', 'bráðna', 'hratt', 'í hádeginu', 'fara', 'ég', 'á',
        'veitingastaður', 'á', 'horn', 'og', 'kaupa', 'ég', 'rauðvín', 'með',
        'hamborgari', 'sem', 'ég', 'borða', 'í gær', 'með', 'mikill', 'ánægja', '.' ]

    def num_pp(s):
        """ Count the prepositional phrases in the parse tree for sentence s """
        return len([t for t in s.tree.descendants if t.match("PP")])

    # Test that the correct number of prepositional phrases (PPs) is generated
    assert num_pp(results[8]) == 2
    assert num_pp(results[9]) == 1
    assert num_pp(results[10]) == 1
    assert num_pp(results[11]) == 4


def test_consistency(verbose = False):
    """ Check that multiple parses of the same sentences yield exactly
        the same preposition counts, and also identical scores. This is
        inter alia to guard agains nondeterminism that may arise from
        Python's random hash seeds. """

    sent15 = [
        "Barnið fór í augnrannsóknina eftir húsnæðiskaupin.",
        "Ég sendi póstinn frá Ísafirði með kettinum"
    ]
    sent45 = [
        "Barnið fór í augnrannsóknina fyrir húsnæðiskaupin.",
        "Ég sendi póstinn með kettinum til Ísafjarðar"
    ]
    for tc15, tc45 in zip(sent15, sent45):

        cnt = defaultdict(int)
        scores = defaultdict(int)
        ptime = 0.0

        ITERATIONS = 100
        if verbose:
            print("Consistency test, {0} iterations:\n   {1}\n   {2}".format(ITERATIONS, tc15, tc45))

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
            pp = [ t.text for t in s.tree.descendants if t.match("PP") ]
            cnt[len(pp)] += 1
            scores[s.score] += 1

        if verbose:
            print("Parse time for {0} iterations was {1:.2f} seconds".format(ITERATIONS, ptime))

        # There should be 2 prepositions in all parse trees
        assert len(cnt) == 1
        assert 2 in cnt
        assert cnt[2] == ITERATIONS

        # The sum of all counts should be the number of iterations
        assert sum(scores.values()) == 100
        if verbose:
            print("There are {0} different scores in consistency check".format(len(scores)))
        # There should only be two different scores
        assert len(scores) == 2
        sc_set = set(scores.values())
        # The count for the scores should be 1/5 and 4/5 of the total, respectively
        assert ITERATIONS * 1 // 5 in sc_set
        assert ITERATIONS * 4 // 5 in sc_set


def test_long_parse(verbose = False):
    if verbose:
        print("Long parse test")
    txt = """
        [[ Reynt er að efla áhuga ungs fólks á borgarstjórnarmálum með framboðsfundum og skuggakosningum en þótt kjörstaðirnir í þeim séu færðir inn í framhaldsskólana er þátttakan lítil. Dagur B. Eggertsson nýtur mun meira fylgis í embætti borgarstjóra en fylgi Samfylkingarinnar gefur til kynna samkvæmt könnun Fréttablaðsins. ]]
        [[ Eins og fram kom í fréttum okkar í gær stefnir í met í fjölda framboða fyrir komandi borgarstjórnarkosningar í vor og gætu þau orðið að minnsta kosti fjórtán. Þá þarf minna fylgi nú en áður til að ná inn borgarfulltrúa, því borgarfulltrúum verður fjölgað úr fimmtán í tuttugu og þrjá. ]]
        [[ Kosningabaráttan fyrir borgarstjórnarkosningarnar í vor er hafin í framhaldsskólum borgarinnar. Samhliða framboðskynningum fara fram skuggakosningar til borgarstjórnar í skólunum. ]]
        [[ „Þetta er eiginlega æfing í því að taka þátt í lýðræðislegum kosningum. Við reynum að herma eftir því hvernig raunverulegar kosningar fara fram,“ segir Róbert Ferdinandsson kennari á félagsfræðibraut Fjölbrautaskólans við Ármúla. ]]
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
            assert sent.parse()
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
    _ = s.tree.view # Should not raise exception
    try:
        _ = s.tree.tree
        assert False, "Should have raised exception"
    except AttributeError:
        pass


def test_terminals():
    from reynir import Terminal
    s = r.parse("Jón greiddi bænum 10 milljónir króna í skaðabætur.")["sentences"][0]
    t = s.terminals
    assert t == [
        Terminal(text='Jón', lemma='Jón', category='person', variants=['nf', 'kk']),
        Terminal(text='greiddi', lemma='greiða', category='so', variants=['2', 'þgf', 'þf', 'et', 'p3']),
        Terminal(text='bænum', lemma='bær', category='no', variants=['et', 'þgf', 'kk']),
        Terminal(text='10', lemma='10', category='tala', variants=['ft', 'þf', 'kvk']),
        Terminal(text='milljónir', lemma='milljón', category='no', variants=['ft', 'þf', 'kvk']),
        Terminal(text='króna', lemma='króna', category='no', variants=['ft', 'ef', 'kvk']),
        Terminal(text='í', lemma='í', category='fs', variants=['þf']),
        Terminal(text='skaðabætur', lemma='skaðabót', category='no', variants=['ft', 'þf', 'kvk']),
        Terminal(text='.', lemma='.', category='', variants=[])
    ]


def test_single():
    from reynir import Terminal
    s = r.parse_single("Jón greiddi bænum 10 milljónir króna í skaðabætur.")
    t = s.terminals
    assert t == [
        Terminal(text='Jón', lemma='Jón', category='person', variants=['nf', 'kk']),
        Terminal(text='greiddi', lemma='greiða', category='so', variants=['2', 'þgf', 'þf', 'et', 'p3']),
        Terminal(text='bænum', lemma='bær', category='no', variants=['et', 'þgf', 'kk']),
        Terminal(text='10', lemma='10', category='tala', variants=['ft', 'þf', 'kvk']),
        Terminal(text='milljónir', lemma='milljón', category='no', variants=['ft', 'þf', 'kvk']),
        Terminal(text='króna', lemma='króna', category='no', variants=['ft', 'ef', 'kvk']),
        Terminal(text='í', lemma='í', category='fs', variants=['þf']),
        Terminal(text='skaðabætur', lemma='skaðabót', category='no', variants=['ft', 'þf', 'kvk']),
        Terminal(text='.', lemma='.', category='', variants=[])
    ]
    try:
        _ = r.parse_single("")
        assert False, "Should have raised StopIteration"
    except StopIteration:
        pass
    s = r.parse_single("kötturinn lömdu hesturinn")
    assert s.combinations == 0
    assert s.tree is None


def test_complex(verbose = False):
    if verbose:
        print("Complex, sentence 1")
    _ = r.parse_single("ákæran var þingfest en fréttastofu er kunnugt um að maðurinn "
        "játaði þar sem þinghaldið er lokað")
    if verbose:
        print("Complex, sentence 2")
    _ = r.parse_single("Viðar Garðarsson, sem setti upp vefsíður fyrir Sigmund Davíð "
       "Gunnlaugsson í kjölfar birtingu Panamaskjalanna, segist ekki vita "
       "hvers vegna ákveðið var að segja að vefjunum væri haldið úti af "
       "stuðningsmönnum Sigmundar.")
    if verbose:
        print("Complex, sentence 3")
    _ = r.parse_single("Ákæran var þingfest í Héraðsdómi Reykjaness í dag "
       "en fréttastofu er ekki kunnugt um hvort maðurinn játaði eða neitaði "
       "sök þar sem þinghaldið í málinu er lokað.")
    if verbose:
        print("Complex, sentence 4")
    _ = r.parse_single("út úr stílfærðri túlkun listamannsins á gamla , litla og mjóa "
        "prófessornum kom búlduleitur beljaki sem þess vegna hefði getað verið "
        "trökkdræver að norðan .")

def test_finish():
    r.__class__.cleanup()


if __name__ == "__main__":
    # When invoked as a main module, do a verbose test
    test_init()
    test_parse(verbose = True)
    test_properties()
    test_long_parse(verbose = True)
    test_consistency(verbose = True)
    test_terminals()
    test_single()
    test_complex(verbose = True)
    test_finish()


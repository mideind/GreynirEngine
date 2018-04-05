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

from reynir import Reynir, ParseForestDumper

def test_parse(verbose = False):

    sentences = [
        # 0
        "Hér er verið að gera tilraunir með þáttun.",
        # 1
        "Margar málsgreinar koma hér fyrir.",
        # 2
        "Þetta takast ekki að þáttar.", # Villa
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
        "Eðlisfræðingurinn Stephen Hawking lést í dag, á pí-deginum."
    ]
    r = Reynir()
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

    # Test that the parser finds the correct word stems
    assert results[0].tree.stems == [ "hér", "vera", "vera", "að", "gera",
        "tilraun", "með", "þáttun", "." ]
    assert results[1].tree.stems == [ "margur", "málsgrein", "koma", "hér", "fyrir", "." ]
    assert results[2].tree == None # Error sentence
    assert results[3].tree.stems == [ "fjórði", "málsgrein", "vera", "síðari", "." ]
    assert results[4].tree.stems == [ "Vatnið", "vera", "30,5", "gráða", "heitur",
        "og", "ég", "vera", "ánægður", "með", "það", "." ]
    assert results[5].tree.stems == [ "hún", "skulda", "ég", "1.000 dollara", "." ]
    assert results[6].tree.stems == [ "ég", "hitta", "hún", "sá", "17. júní",
        "ár", "1944", "á", "Þingvellir", "." ]
    assert results[7].tree.stems == [ "hann", "eigna", "hús", "við", "strönd",
        "og", "hún", "taka", "að", "mála", "það", "." ]
    assert results[8].tree.stems == [ "barn", "fara", "í", "augnrannsókn", "eftir",
        "húsnæðiskaup", "." ]
    assert results[9].tree.stems == [ "barn", "fara", "í", "loðfíla-rannsókn", "." ]
    assert results[10].tree.stems == [ "eðlisfræðingur", "Stephen", "Hawking",
        "láta", "í dag", ",", "á", "pí", "—", "dagur", "." ]

    # Test that the correct number of prepositional phrases (PPs) is generated
    pp8 = [ t.text for t in results[8].tree.descendants if t.match("PP") ]
    assert len(pp8) == 2
    pp9 = [ t.text for t in results[9].tree.descendants if t.match("PP") ]
    assert len(pp9) == 1
    pp10 = [ t.text for t in results[10].tree.descendants if t.match("PP") ]
    assert len(pp10) == 1

    Reynir.cleanup()

if __name__ == "__main__":
    test_parse(verbose = True)

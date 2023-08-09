# type: ignore
"""

    test_reynir.py

    Tests for Greynir module

    Copyright © 2023 Miðeind ehf.
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

from reynir import Greynir
from reynir.binparser import augment_terminal
from reynir.bindb import GreynirBin
from reynir.bintokenizer import MIDDLE_NAME_ABBREVS, NOT_NAME_ABBREVS, TOK
from tokenizer import detokenize


def test_augment_terminal():
    a = augment_terminal("so_subj_op_þf", "langaði", "OP-GM-FH-ÞT-3P-ET")
    assert a == "so_subj_op_þf_et_fh_gm_þt"
    a = augment_terminal("so_subj_sagnb_þf", "langað", "GM-SAGNB")
    assert a == "so_subj_sagnb_þf_gm"
    a = augment_terminal("so_subj_lhþt_et_kvk", "valin", "LHÞT-SB-KVK-NFET")
    assert a == "so_subj_lhþt_et_kvk_nf_sb"
    a = augment_terminal("so_subj_nh", "skorta", "GM-NH")
    assert a == "so_subj_nh_gm"
    a = augment_terminal("so_subj_nh_þgf", "blöskra", "GM-NH")
    assert a == "so_subj_nh_þgf_gm"
    a = augment_terminal("so_1_þf_subj_op_þgf", "þraut", "OP-GM-FH-ÞT-1P-ET")
    assert a == "so_1_þf_subj_op_þgf_et_fh_gm_þt"
    a = augment_terminal("so_2_þgf_þf_p1_et", "skrifa", "GM-FH-NT-1P-ET")
    assert a == "so_2_þgf_þf_et_fh_gm_nt_p1"
    a = augment_terminal("so_0_lhþt_et_kk", "kembdur", "LHÞT-SB-KK-NFET")
    assert a == "so_0_et_kk_lhþt_nf_sb"


def test_lemmas():
    g = Greynir()
    s = g.parse_single(
        "Hallbjörn borðaði ísinn kl. 14 meðan Icelandair át 3 teppi "
        "frá Íran og Xochitl var tilbeðin."
    )
    assert s.lemmas is not None
    assert s.categories is not None
    assert list(zip(s.lemmas, s.categories)) == [
        ("Hallbjörn", "kk"),
        ("borða", "so"),
        ("ís", "kk"),
        ("kl. 14", ""),
        ("meðan", "st"),
        ("Icelandair", "entity"),
        ("éta", "so"),
        ("3", ""),
        ("teppi", "hk"),
        ("frá", "fs"),
        ("Íran", "hk"),
        ("og", "st"),
        ("Xochitl", "entity"),
        ("vera", "so"),
        ("tilbiðja", "so"),
        (".", ""),
    ]
    assert s.lemmas_and_cats == [
        ("Hallbjörn", "person_kk"),
        ("borða", "so"),
        ("ís", "kk"),
        ("kl. 14", ""),
        ("meðan", "st"),
        ("Icelandair", "entity"),
        ("éta", "so"),
        ("3", ""),
        ("teppi", "hk"),
        ("frá", "fs"),
        ("Íran", "hk"),
        ("og", "st"),
        ("Xochitl", "entity"),
        ("vera", "so"),
        ("tilbiðja", "so"),
        (".", ""),
    ]
    s = g.parse_single("Sigurður langaði í köttur")
    assert s.tree is None
    assert s.lemmas is None
    assert s.categories is None
    assert s.lemmas_and_cats is None


# Tests for more complex tokenization in bintokenizer


def test_names():
    g = Greynir(parse_foreign_sentences=True)
    s = g.parse_single("Hér er Jón.")
    assert s.lemmas == ["hér", "vera", "Jón", "."]

    s = g.parse_single("Hér er Díana.")
    assert s.lemmas == ["hér", "vera", "Díana", "."]

    s = g.parse_single("Hér er Jón Daði.")
    assert s.lemmas == ["hér", "vera", "Jón Daði", "."]

    s = g.parse_single("Hér er Díana Valdís.")
    assert s.lemmas == ["hér", "vera", "Díana Valdís", "."]

    s = g.parse_single("Hér er Jón Daði Vignisson.")
    assert s.lemmas == ["hér", "vera", "Jón Daði Vignisson", "."]

    s = g.parse_single("Hér er Díana Valdís Bjartmarsdóttir.")
    assert s.lemmas == ["hér", "vera", "Díana Valdís Bjartmarsdóttir", "."]

    s = g.parse_single("Hér er Björn.")
    assert s.lemmas == ["hér", "vera", "Björn", "."]

    s = g.parse_single("Hér er Blær.")
    assert s.lemmas == ["hér", "vera", "Blær", "."]

    s = g.parse_single("Hér er Björn Arnarson.")
    assert s.lemmas == ["hér", "vera", "Björn Arnarson", "."]

    s = g.parse_single("Hér er Sóley Bjartmarsdóttir.")
    assert s.lemmas == ["hér", "vera", "Sóley Bjartmarsdóttir", "."]

    s = g.parse_single("Hér er Jón Zoëga.")
    assert s.lemmas == ["hér", "vera", "Jón Zoëga", "."]

    s = g.parse_single("Hér er Gyða Waage.")
    assert s.lemmas == ["hér", "vera", "Gyða Waage", "."]

    s = g.parse_single("Hér er Sigríður Á. Andersen.")
    assert s.lemmas == ["hér", "vera", "Sigríður Á. Andersen", "."]

    s = g.parse_single("Hér er Gvendur P. Aspelund.")
    assert s.lemmas == ["hér", "vera", "Gvendur P. Aspelund", "."]

    s = g.parse_single("Hér er Jakob Díönu- og Styrmisson.")
    assert s.lemmas == ["hér", "vera", "Jakob Díönu- og Styrmisson", "."]

    s = g.parse_single("Hér er Gvendur Ragnheiðarson.")
    assert s.lemmas == ["hér", "vera", "Gvendur Ragnheiðarson", "."]

    s = g.parse_single("Hér er Sóley Petrudóttir.")
    assert s.lemmas == ["hér", "vera", "Sóley Petrudóttir", "."]

    s = g.parse_single("Hér er Sóley Péturs- og Petrudóttir.")
    assert s.lemmas == ["hér", "vera", "Sóley Péturs- og Petrudóttir", "."]

    s = g.parse_single("Hér er Svanur Hildar- og Pálsson Scheving.")
    assert s.lemmas == ["hér", "vera", "Svanur Hildar- og Pálsson Scheving", "."]

    s = g.parse_single("Hér eru Áki og Andri Brjánssynir.")
    # assert s.lemmas == ['hér', 'vera', 'Áki og Andri Brjánssynir', '.']    # Out of scope

    s = g.parse_single("Hér eru Ína og Una Brjánsdætur.")
    # assert s.lemmas == ['hér', 'vera', 'Ína og Una Brjánsdætur', '.']    # Out of scope

    s = g.parse_single("Hér eru Áki og Láki Brjánssynir.")
    # assert s.lemmas == ['hér', 'vera', 'Áki og Láki Brjánssynir', '.']    # Out of scope

    s = g.parse_single("Hér eru Ína og Mína Brjánsdætur.")
    # assert s.lemmas == ['hér', 'vera', 'Ína og Mína Brjánsdætur', '.']    # Out of scope

    s = g.parse_single("Hér eru Áki og Ína Brjánsbörn.")
    # assert s.lemmas == ['hér', 'vera', 'Áki og Ína Brjánsbörn', '.']    # Out of scope

    s = g.parse_single("Hér er Jack Nicholson.")
    assert s.lemmas == ["hér", "vera", "Jack Nicholson", "."]

    s = g.parse_single("Hér er Diane Lane.")
    assert s.lemmas == ["hér", "vera", "Diane Lane", "."]

    s = g.parse_single("Hér er Finsbury Park.")
    assert s.lemmas == ["hér", "vera", "Finsbury Park", "."]

    s = g.parse_single("Hér er Sky Sports.")
    assert s.lemmas == ["hér", "vera", "Sky Sports", "."]  # Out of scope

    # s = g.parse_single("Hér er J. K. Rowling.")
    # assert s.lemmas == ['hér', 'vera', 'J. K. Rowling', '.']    # Out of scope

    s = g.parse_single("Hér er Parsley Ecothelial Welmington III.")
    assert s.lemmas == ["hér", "vera", "Parsley Ecothelial Welmington III", "."]

    s = g.parse_single("Hér er Dietrich van Helsing.")
    assert s.lemmas == ["hér", "vera", "Dietrich van Helsing", "."]

    s = g.parse_single("Hér er Helmine van de Fnupft.")
    assert s.lemmas == ["hér", "vera", "Helmine van de Fnupft", "."]

    s = g.parse_single("Hér er Carla de la Cruz.")
    assert s.lemmas == ["hér", "vera", "Carla de la Cruz", "."]

    s = g.parse_single("Hér er Barack Obama.")
    assert s.lemmas == ["hér", "vera", "Barack Obama", "."]

    s = g.parse_single("Hér er Finnur de la Cruz.")
    assert s.lemmas == ["hér", "vera", "Finnur de la Cruz", "."]

    # s = g.parse_single("Hér er Derek Árnason.")
    # assert s.lemmas == ['hér', 'vera', 'Derek Árnason', '.']

    s = g.parse_single("Hér er Díana Woodward.")
    assert s.lemmas == ["hér", "vera", "Díana Woodward", "."]

    # s = g.parse_single("Hér er Knut Axel Holding AS.")
    # assert s.lemmas == ['hér', 'vera', 'Knut Axel Holding AS', '.']    # Out of scope

    # s = g.parse_single("Hér er Matthildur Ármannsdóttir ehf.")
    # assert s.lemmas == ['hér', 'vera', 'Matthildur Ármannsdóttir ehf.', '.']   # Out of scope

    s = g.parse_single("Hér er Super Mattel AS.")
    assert s.lemmas == ["hér", "vera", "Super Mattel AS", "."]

    # s = g.parse_single("Hér er WOW Cyclothon.")
    # assert s.lemmas == ['hér', 'vera', 'WOW Cyclothon', '.']   # Out of scope

    s = g.parse_single("Hér er SHAPP Games.")
    assert s.lemmas == ["hér", "vera", "SHAPP Games", "."]

    # s = g.parse_single("Hér er Fiat a10.")
    # assert s.lemmas == ['hér', 'vera', 'Fiat a10', '.']        # Out of scope

    s = g.parse_single("Hér er Ikea.")
    assert s.lemmas == ["hér", "vera", "Ikea", "."]

    # s = g.parse_single("Hér er Styrmir Halldórsson H225.")
    # assert s.lemmas == ['hér', 'vera', 'Styrmir Halldórsson H225', '.']    # Out of scope

    s = g.parse_single("Hér er The Trials and Tribulations of the Cat.")
    assert s.lemmas == ["hér", "vera", "The Trials and Tribulations of the Cat", "."]

    s = g.parse_single("Hér er Making Pastels: In Search of Quietness.")
    assert s.lemmas == [
        "hér",
        "vera",
        "Making Pastels",
        ":",
        "In Search of Quietness",
        ".",
    ]

    # False positives to avoid
    s = g.parse_single("Hér er von Helgu.")
    assert s.lemmas == ["hér", "vera", "von", "Helga", "."]

    s = g.parse_single("Hér er Helgi Björns.")
    assert s.lemmas == ["hér", "vera", "Helgi Björns", "."]

    s = g.parse_single("Hér er Jón de la.")
    assert s.lemmas == ["hér", "vera", "Jón", "de", "la", "."]


def test_compounds_with_numbers():
    """Compounds containing numbers, either
    with a hyphen or not"""
    pass
    # g = Greynir()

    # Tokens with letters and numbers are split up so this fails
    # s = g.parse_single("Hér er X3-jeppi.")
    # assert s.lemmas == ['hér', 'vera', 'X3-jeppi', '.']

    # Tokens with letters and numbers are split up so this fails
    # s = g.parse_single("Hér er Bombardier Q-400.")
    # assert s.lemmas == ['hér', 'vera', 'Bombardier Q-400', '.']

    # Tokens with letters and numbers are split up so this fails
    # s = g.parse_single("Hér er U20-landsliðið.")
    # assert s.lemmas == ['hér', 'vera', 'U20-landslið', '.']

    # Tokens with letters and numbers are split up so this fails
    # s = g.parse_single("Hér er ómega-3 fitusýra.")
    # assert s.lemmas == ['hér', 'vera', 'ómega-3', 'fitusýra', '.']

    # The entity combination doesn't recognize the hyphenated word
    # s = g.parse_single("Hér er Coca Cola-bikarinn.")
    # assert s.lemmas == ['hér', 'vera', 'Coca Cola-bikar', '.']


def test_sentence_split():
    g = Greynir()
    tlist = list(g.tokenize("Ég hitti próf. Jón Mýrdal áðan."))
    assert len([t for t in tlist if t.kind == TOK.S_BEGIN]) == 1
    assert len([t for t in tlist if t.kind == TOK.S_END]) == 1
    tlist = list(g.tokenize("Ég tók samræmt próf. Það var létt."))
    assert len([t for t in tlist if t.kind == TOK.S_BEGIN]) == 2
    assert len([t for t in tlist if t.kind == TOK.S_END]) == 2
    tlist = list(g.tokenize("Þetta er próf. Hann taldi það víst."))
    assert len([t for t in tlist if t.kind == TOK.S_BEGIN]) == 2
    assert len([t for t in tlist if t.kind == TOK.S_END]) == 2
    tlist = list(g.tokenize("Próf. Páll var ósammála próf. Höllu um ritgerðina."))
    assert len([t for t in tlist if t.kind == TOK.S_BEGIN]) == 1
    assert len([t for t in tlist if t.kind == TOK.S_END]) == 1
    tlist = list(g.tokenize("Ég hitti dr. Jón Mýrdal áðan."))
    assert len([t for t in tlist if t.kind == TOK.S_BEGIN]) == 1
    assert len([t for t in tlist if t.kind == TOK.S_END]) == 1
    tlist = list(g.tokenize("Ég hitti t.d. hr. Jón Mýrdal þann 23. maí."))
    assert len([t for t in tlist if t.kind == TOK.S_BEGIN]) == 1
    assert len([t for t in tlist if t.kind == TOK.S_END]) == 1


def test_auto_uppercase():
    g = Greynir(auto_uppercase=True)

    for abbr in MIDDLE_NAME_ABBREVS:
        if abbr not in NOT_NAME_ABBREVS:
            # No period, no extra tokens
            s = g.parse_single(f"hér er jón {abbr}")
            assert detokenize(s.tokens) == f"hér er Jón {abbr.capitalize()}"
            assert f"Jón {abbr.capitalize()}" in s.tree.persons

            # No period, extra tokens
            s = g.parse_single(f"við jón {abbr} erum góðir vinir")
            assert (
                detokenize(s.tokens) == f"við Jón {abbr.capitalize()} erum góðir vinir"
            )
            assert f"Jón {abbr.capitalize()}" in s.tree.persons

        # No period, surname
        s = g.parse_single(f"hér er jón {abbr} guðnason")
        assert detokenize(s.tokens) == f"hér er Jón {abbr.capitalize()} Guðnason"
        assert f"Jón {abbr.capitalize()} Guðnason" in s.tree.persons

        # With period, no extra tokens
        s = g.parse_single(f"hér er jón {abbr}.")
        assert detokenize(s.tokens) == f"hér er Jón {abbr.capitalize()}."
        assert f"Jón {abbr.capitalize()}." in s.tree.persons

        # With period, extra tokens
        s = g.parse_single(f"við jón {abbr}. erum góðir vinir")
        assert detokenize(s.tokens) == f"við Jón {abbr.capitalize()}. erum góðir vinir"
        assert f"Jón {abbr.capitalize()}." in s.tree.persons

        # With period, surname
        s = g.parse_single(f"hér er jón {abbr}. guðnason")
        assert detokenize(s.tokens) == f"hér er Jón {abbr.capitalize()}. Guðnason"
        assert f"Jón {abbr.capitalize()}. Guðnason" in s.tree.persons

    s = g.parse_single("hver er guðni th jóhannesson")
    assert detokenize(s.tokens) == "hver er Guðni Th Jóhannesson"
    assert "Guðni Th Jóhannesson" in s.tree.persons

    s = g.parse_single("hver er guðni th. jóhannesson")
    assert detokenize(s.tokens) == "hver er Guðni Th. Jóhannesson"
    assert "Guðni Th. Jóhannesson" in s.tree.persons

    s = g.parse_single("hver er gunnar thoroddsen")
    assert detokenize(s.tokens) == "hver er Gunnar Thoroddsen"
    assert "Gunnar Thoroddsen" in s.tree.persons

    s = g.parse_single("hver er eliza reid")
    assert detokenize(s.tokens) == "hver er Eliza Reid"
    assert "Eliza Reid" in s.tree.persons

    s = g.parse_single("hver er hæð jóns")
    assert detokenize(s.tokens) == "hver er hæð Jóns"
    assert "Jón" in s.tree.persons

    s = g.parse_single("hver er hæð sólar í dag í reykjavík")
    assert "Í" not in detokenize(s.tokens)
    assert "Sólar Í Dag Í Reykjavík" not in s.tree.persons

    s = g.parse_single("mikil sól var í dag í reykjavík")
    assert "Í" not in detokenize(s.tokens)
    assert "Mikill" not in s.tree.persons

    s = g.parse_single("sólin gægðist fram úr skýjunum")
    assert "Sól" not in s.tree.persons

    s = g.parse_single(
        "hver er guðmundur í. hámundarson, sonur hámundar á. guðmundssonar"
    )
    assert (
        detokenize(s.tokens)
        == "hver er Guðmundur Í. Hámundarson, sonur Hámundar Á. Guðmundssonar"
    )
    assert (
        "Guðmundur Í. Hámundarson" in s.tree.persons
        and "Hámundur Á. Guðmundsson" in s.tree.persons
    )

    s = g.parse_single(
        "hver er guðmundur í hámundarson, sonur hámundar á guðmundssonar"
    )
    assert (
        detokenize(s.tokens)
        == "hver er Guðmundur Í Hámundarson, sonur Hámundar Á Guðmundssonar"
    )
    assert (
        "Guðmundur Í Hámundarson" in s.tree.persons
        and "Hámundur Á Guðmundsson" in s.tree.persons
    )

    s = g.parse_single(
        "ég hitti loft á bíldudal, blæ á seyðisfirði og skúla í keflavík"
    )
    assert (
        detokenize(s.tokens)
        == "ég hitti Loft á Bíldudal, Blæ á Seyðisfirði og Skúla í Keflavík"
    )
    assert (
        "Loftur" in s.tree.persons
        and "Blær" in s.tree.persons
        and "Skúli" in s.tree.persons
    )

    s = g.parse_single("hver er lofthæna s melkorkudóttir")
    assert detokenize(s.tokens) == "hver er Lofthæna S Melkorkudóttir"
    assert "Lofthæna S Melkorkudóttir" in s.tree.persons

    s = g.parse_single("katrín jakobs hitti justin p. j. trudeau um daginn")
    assert detokenize(s.tokens) == "Katrín Jakobs hitti Justin P. J. Trudeau um daginn"
    assert (
        "Katrín Jakobs" in s.tree.persons and "Justin P. J. Trudeau" in s.tree.persons
    )

    s = g.parse_single("katrín jakobsdóttir hitti justin p j trudeau um daginn")
    assert (
        detokenize(s.tokens) == "Katrín Jakobsdóttir hitti Justin P J Trudeau um daginn"
    )
    assert (
        "Katrín Jakobsdóttir" in s.tree.persons
        and "Justin P J Trudeau" in s.tree.persons
    )

    s = g.parse_single("rætt var við dag b eggertsson, borgarstjóra reykjavíkur")
    assert (
        detokenize(s.tokens)
        == "rætt var við Dag B Eggertsson, borgarstjóra Reykjavíkur"
    )
    assert "Dagur B Eggertsson" in s.tree.persons

    s = g.parse_single("rætt var við dag b. eggertsson, borgarstjóra reykjavíkur")
    assert (
        detokenize(s.tokens)
        == "rætt var við Dag B. Eggertsson, borgarstjóra Reykjavíkur"
    )
    assert "Dagur B. Eggertsson" in s.tree.persons

    s = g.parse_single(
        "úrsúla von der leyen (fædd 8. október 1958) er þýskur stjórnmálamaður "
        "og núverandi forseti framkvæmdastjórnar evrópusambandsins"
    )
    assert (
        detokenize(s.tokens)
        == "Úrsúla von der Leyen (fædd 8. október 1958) er þýskur stjórnmálamaður "
        "og núverandi forseti framkvæmdastjórnar Evrópusambandsins"
    )
    assert "Úrsúla von der Leyen" in s.tree.persons

    s = g.parse_single("það er fallegur dagur í dag")
    assert "Í" not in detokenize(s.tokens)

    s = g.parse_single("hann dagur í. dagsson er forkunnarfagur")
    assert detokenize(s.tokens) == "hann Dagur Í. Dagsson er forkunnarfagur"
    assert "Dagur Í. Dagsson" in s.tree.persons

    s = g.parse_single("hann dagur í dagsson er forkunnarfagur")
    assert detokenize(s.tokens) == "hann Dagur Í Dagsson er forkunnarfagur"
    assert "Dagur Í Dagsson" in s.tree.persons

    s = g.parse_single("guðmundur er bóndi á stöpum og mjólkar kýr")
    assert detokenize(s.tokens) == "Guðmundur er bóndi á Stöpum og mjólkar kýr"
    assert "Guðmundur" in s.tree.persons and "Guðmundur Er Bóndi" not in s.tree.persons

    s = g.parse_single("hvað er gummi í mörgum íþróttafélögum")
    assert detokenize(s.tokens) == "hvað er Gummi í mörgum íþróttafélögum"
    assert "Gummi" in s.tree.persons

    s = g.parse_single("gunnar á hlíðarenda var vinur njáls á bergþórshvoli")
    assert detokenize(s.tokens) == "Gunnar á Hlíðarenda var vinur Njáls á Bergþórshvoli"
    assert "Gunnar" in s.tree.persons and "Njáll" in s.tree.persons

    s = g.parse_single("ég hitti ástbjörn í hverri viku og gunnu á miðvikudögum")
    assert (
        detokenize(s.tokens)
        == "ég hitti Ástbjörn í hverri viku og Gunnu á miðvikudögum"
    )
    assert "Ástbjörn" in s.tree.persons and "Gunna" in s.tree.persons

    s = g.parse_single("ég hringdi í baldvin kr. magnússon")
    assert detokenize(s.tokens) == "ég hringdi í Baldvin Kr. Magnússon"
    assert "Baldvin Kr. Magnússon" in s.tree.persons

    s = g.parse_single("hafðu samband við jón s. 5885522")
    assert detokenize(s.tokens) == "hafðu samband við Jón s. 5885522"
    assert "Jón" in s.tree.persons

    s = g.parse_single("hafðu samband við jón s. jónsson")
    assert detokenize(s.tokens) == "hafðu samband við Jón S. Jónsson"
    assert "Jón S. Jónsson" in s.tree.persons

    s = g.parse_single("ég veit ekki hvar hann baldur er.")
    assert detokenize(s.tokens) == "ég veit ekki hvar hann Baldur er."
    assert "Baldur" in s.tree.persons


def test_compounds():
    db = GreynirBin()
    _, m = db.lookup_g("fjármála- og efnahagsráðherra")
    assert m
    assert m[0].stofn == "fjármála- og efnahags-ráðherra"
    assert m[0].ordmynd == "fjármála- og efnahags-ráðherra"

    _, m = db.lookup_g("tösku- og hanskabúðina")
    assert m
    assert m[0].stofn == "tösku- og hanskabúð"
    assert m[0].ordmynd == "tösku- og hanskabúðina"

    _, m = db.lookup_g("Félags- og barnamálaráðherra")
    assert m
    assert m[0].stofn == "Félags- og barnamála-ráðherra"
    assert m[0].ordmynd == "Félags- og barnamála-ráðherra"

    _, m = db.lookup_g("Félags- og Barnamálaráðherra")  # sic
    assert m
    assert m[0].stofn == "Félags- og barnamála-ráðherra"
    assert m[0].ordmynd == "Félags- og barnamála-ráðherra"


if __name__ == "__main__":

    test_augment_terminal()

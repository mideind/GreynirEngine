"""

    test_reynir.py

    Tests for Greynir module

    Copyright (C) 2020 Miðeind ehf.
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

import functools

from reynir import Greynir
from reynir.binparser import augment_terminal
from reynir.bincompress import BIN_Compressed
from reynir.bindb import BIN_Db
from reynir.bintokenizer import TOK


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


def test_bin():
    """ Test querying for different cases of words """

    b = BIN_Compressed()

    def f(word, case, stem, cat, beyging_filter=None):
        meanings = b.lookup_case(
            word, case, cat=cat, stem=stem, beyging_filter=beyging_filter
        )
        return {(m[4], m[5]) for m in meanings}

    def declension(word, stem, cat, beyging_filter=None):
        result = []

        def bf(b):
            if beyging_filter is not None and not beyging_filter(b):
                return False
            return "2" not in b and "3" not in b

        for case in ("NF", "ÞF", "ÞGF", "EF"):
            wf_list = list(f(word, case, stem, cat, bf))
            result.append(wf_list[0][0] if wf_list else "N/A")
        return tuple(result)

    lo_filter = lambda b: "EVB" in b and "FT" in b

    assert f("fjarðarins", "NF", "fjörður", "kk") == {("fjörðurinn", "NFETgr")}
    assert f("breiðustu", "NF", "breiður", "lo", lo_filter) == {
        ("breiðustu", "EVB-KVK-NFFT"),
        ("breiðustu", "EVB-HK-NFFT"),
        ("breiðustu", "EVB-KK-NFFT"),
    }
    assert b.lookup_case("fjarðarins", "NF", cat="kk", stem="fjörður") == {
        ("fjörður", 5697, "kk", "alm", "fjörðurinn", "NFETgr")
    }
    assert b.lookup_case("breiðastra", "NF", cat="lo", stem="breiður") == {
        ("breiður", 388135, "lo", "alm", "breiðastir", "ESB-KK-NFFT"),
        ("breiður", 388135, "lo", "alm", "breiðastar", "ESB-KVK-NFFT"),
        ("breiður", 388135, "lo", "alm", "breiðust", "ESB-HK-NFFT"),
    }
    assert f("fjarðarins", "ÞF", "fjörður", "kk") == {("fjörðinn", "ÞFETgr")}
    assert f("breiðustu", "ÞF", "breiður", "lo", lo_filter) == {
        ("breiðustu", "EVB-KVK-ÞFFT"),
        ("breiðustu", "EVB-HK-ÞFFT"),
        ("breiðustu", "EVB-KK-ÞFFT"),
    }
    assert f("fjarðarins", "ÞGF", "fjörður", "kk") == {("firðinum", "ÞGFETgr")}
    assert f("breiðustu", "ÞGF", "breiður", "lo", lo_filter) == {
        ("breiðustu", "EVB-KVK-ÞGFFT"),
        ("breiðustu", "EVB-HK-ÞGFFT"),
        ("breiðustu", "EVB-KK-ÞGFFT"),
    }
    assert f("fjarðarins", "EF", "fjörður", "kk") == {("fjarðarins", "EFETgr")}
    assert f("breiðustu", "EF", "breiður", "lo", lo_filter) == {
        ("breiðustu", "EVB-KVK-EFFT"),
        ("breiðustu", "EVB-HK-EFFT"),
        ("breiðustu", "EVB-KK-EFFT"),
    }
    assert declension("brjóstsykur", "brjóstsykur", "kk") == (
        "brjóstsykur",
        "brjóstsykur",
        "brjóstsykri",
        "brjóstsykurs",
    )
    assert declension("smáskífa", "smáskífa", "kvk", lambda b: "ET" in b) == (
        "smáskífa",
        "smáskífu",
        "smáskífu",
        "smáskífu",
    )
    assert declension("smáskífa", "smáskífa", "kvk", lambda b: "FT" in b) == (
        "smáskífur",
        "smáskífur",
        "smáskífum",
        "smáskífa",
    )
    assert declension("ungabarn", "ungabarn", "hk") == (
        "ungabarn",
        "ungabarn",
        "ungabarni",
        "ungabarns",
    )
    assert declension("geymir", "geymir", "kk") == (
        "geymir",
        "geymi",
        "geymi",
        "geymis",
    )
    assert declension("sulta", "sulta", "kvk", lambda b: "ET" in b) == (
        "sulta", "sultu", "sultu", "sultu"
    )
    assert declension("vígi", "vígi", "hk", lambda b: "ET" in b) == (
        "vígi", "vígi", "vígi", "vígis"
    )
    assert declension("buxur", "buxur", "kvk") == (
        "buxur", "buxur", "buxum", "buxna"
    )
    assert declension("ríki", "ríki", "hk", lambda b: "ET" in b) == (
        "ríki", "ríki", "ríki", "ríkis"
    )
    assert declension("ríki", "ríki", "hk", lambda b: "FT" in b) == (
        "ríki", "ríki", "ríkjum", "ríkja"
    )
    assert declension("ríki", "ríkir", "kk") == (
        "ríkir", "ríki", "ríki", "ríkis"
    )
    assert declension("brjóstsykurinn", "brjóstsykur", "kk") == (
        "brjóstsykurinn",
        "brjóstsykurinn",
        "brjóstsykrinum",
        "brjóstsykursins",
    )
    assert declension("smáskífan", "smáskífa", "kvk") == (
        "smáskífan",
        "smáskífuna",
        "smáskífunni",
        "smáskífunnar",
    )
    assert declension("ungabarnið", "ungabarn", "hk") == (
        "ungabarnið",
        "ungabarnið",
        "ungabarninu",
        "ungabarnsins",
    )
    assert declension("geymirinn", "geymir", "kk") == (
        "geymirinn",
        "geyminn",
        "geyminum",
        "geymisins",
    )
    assert declension("sultan", "sulta", "kvk") == (
        "sultan",
        "sultuna",
        "sultunni",
        "sultunnar",
    )
    assert declension("vígið", "vígi", "hk") == (
        "vígið", "vígið", "víginu", "vígisins"
    )
    assert declension("ríkið", "ríki", "hk") == (
        "ríkið", "ríkið", "ríkinu", "ríkisins"
    )
    assert declension("geymarnir", "geymir", "kk") == (
        "geymarnir",
        "geymana",
        "geymunum",
        "geymanna",
    )
    assert declension("sulturnar", "sulta", "kvk") == (
        "sulturnar",
        "sulturnar",
        "sultunum",
        "sultnanna",
    )
    assert declension("vígin", "vígi", "hk") == (
        "vígin",
        "vígin",
        "vígjunum",
        "vígjanna",
    )
    assert declension("buxurnar", "buxur", "kvk") == (
        "buxurnar",
        "buxurnar",
        "buxunum",
        "buxnanna",
    )
    assert declension("ríkin", "ríki", "hk") == (
        "ríkin",
        "ríkin",
        "ríkjunum",
        "ríkjanna",
    )
    assert declension("Vestur-Þýskalands", "Vestur-Þýskaland", "hk") == (
        "Vestur-Þýskaland",
        "Vestur-Þýskaland",
        "Vestur-Þýskalandi",
        "Vestur-Þýskalands",
    )


def test_bindb():
    db = BIN_Db()
    # Test the lemma lookup functionality
    w, m = db.lookup_lemma("eignast")
    assert w == "eignast"
    assert len(m) > 0
    assert m[0].stofn == "eigna"
    w, m = db.lookup_lemma("ábyrgjast")
    assert w == "ábyrgjast"
    assert len(m) > 0
    assert m[0].stofn == "ábyrgjast"
    w, m = db.lookup_lemma("ábyrgja")
    assert w == "ábyrgja"
    assert len(m) > 0
    assert m[0].stofn == "á-byrgja"
    w, m = db.lookup_lemma("ábyrgir")
    assert w == "ábyrgir"
    assert len(m) == 0
    w, m = db.lookup_lemma("stór")
    assert w == "stór"
    assert len(m) > 0
    assert m[0].stofn == "stór"
    w, m = db.lookup_lemma("stórar")
    assert w == "stórar"
    assert len(m) == 0
    w, m = db.lookup_lemma("sig")
    assert w == "sig"
    assert len(m) > 0
    assert any(mm.ordfl == "abfn" for mm in m)
    w, m = db.lookup_lemma("sér")
    assert w == "sér"
    assert len(m) > 0
    assert not any(mm.ordfl == "abfn" for mm in m)
    w, m = db.lookup_lemma("hann")
    assert w == "hann"
    assert len(m) > 0
    assert any(mm.ordfl == "pfn" for mm in m)
    w, m = db.lookup_lemma("hán")
    assert w == "hán"
    assert len(m) > 0
    assert any(mm.ordfl == "pfn" for mm in m)
    w, m = db.lookup_lemma("háns")
    assert w == "háns"
    assert len(m) == 0
    w, m = db.lookup_lemma("hinn")
    assert w == "hinn"
    assert len(m) > 0
    assert any(mm.ordfl == "gr" for mm in m)
    w, m = db.lookup_lemma("einn")
    assert w == "einn"
    assert len(m) > 0
    assert any(mm.ordfl == "to" for mm in m)
    w, m = db.lookup_lemma("núll")
    assert w == "núll"
    assert len(m) > 0
    assert any(mm.ordfl == "to" for mm in m)


def test_lemmas():
    g = Greynir()
    s = g.parse_single(
        "Hallbjörn borðaði ísinn kl. 14 meðan Icelandair át 3 teppi "
        "frá Íran og Xochitl var tilbeðin."
    )
    assert (
        list(zip(s.lemmas, s.categories)) == [
            ('Hallbjörn', 'kk'), ('borða', 'so'), ('ís', 'kk'), ('kl. 14', ''),
            ('meðan', 'st'), ('Icelandair', 'entity'), ('éta', 'so'), ('3', ''),
            ('teppi', 'hk'), ('frá', 'fs'), ('Íran', 'hk'), ('og', 'st'),
            ('Xochitl', 'entity'), ('vera', 'so'), ('tilbiðja', 'so'), ('.', '')
        ]
    )
    assert (
        s.lemmas_and_cats == [
            ('Hallbjörn', 'person_kk'), ('borða', 'so'), ('ís', 'kk'), ('kl. 14', ''),
            ('meðan', 'st'), ('Icelandair', 'entity'), ('éta', 'so'), ('3', ''),
            ('teppi', 'hk'), ('frá', 'fs'), ('Íran', 'hk'), ('og', 'st'),
            ('Xochitl', 'entity'), ('vera', 'so'), ('tilbiðja', 'so'), ('.', '')
        ]
    )
    s = g.parse_single("Sigurður langaði í köttur")
    assert s.tree is None
    assert s.lemmas is None
    assert s.categories is None
    assert s.lemmas_and_cats is None

def test_tokens():
    g = Greynir()
    s = g.parse_single("Hér er Jón.")
    assert s.lemmas == ['hér', 'vera', 'Jón', '.']

    s = g.parse_single("Hér er Díana.")
    assert s.lemmas == ['hér', 'vera', 'Díana', '.']

    s = g.parse_single("Hér er Jón Daði.")
    assert s.lemmas == ['hér', 'vera', 'Jón Daði', '.']

    s = g.parse_single("Hér er Díana Valdís.")
    assert s.lemmas == ['hér', 'vera', 'Díana Valdís', '.']

    s = g.parse_single("Hér er Jón Daði Vignisson.")
    assert s.lemmas == ['hér', 'vera', 'Jón Daði Vignisson', '.']

    s = g.parse_single("Hér er Díana Valdís Bjartmarsdóttir.")
    assert s.lemmas == ['hér', 'vera', 'Díana Valdís Bjartmarsdóttir', '.']

    s = g.parse_single("Hér er Björn.")
    assert s.lemmas == ['hér', 'vera', 'Björn', '.']

    s = g.parse_single("Hér er Blær.")
    assert s.lemmas == ['hér', 'vera', 'Blær', '.']

    s = g.parse_single("Hér er Björn Arnarson.")
    assert s.lemmas == ['hér', 'vera', 'Björn Arnarson', '.']

    s = g.parse_single("Hér er Sóley Bjartmarsdóttir.")
    assert s.lemmas == ['hér', 'vera', 'Sóley Bjartmarsdóttir', '.']

    s = g.parse_single("Hér er Jón Zoëga.")
    assert s.lemmas == ['hér', 'vera', 'Jón Zoëga', '.']

    s = g.parse_single("Hér er Gyða Waage.")
    assert s.lemmas == ['hér', 'vera', 'Gyða Waage', '.']

    s = g.parse_single("Hér er Sigríður Á. Andersen.")
    assert s.lemmas == ['hér', 'vera', 'Sigríður Á. Andersen', '.']

    s = g.parse_single("Hér er Gvendur P. Aspelund.")
    assert s.lemmas == ['hér', 'vera', 'Gvendur P. Aspelund', '.']

    s = g.parse_single("Hér er Jakob Díönu- og Styrmisson.")
    assert s.lemmas == ['hér', 'vera', 'Jakob Díönu- og Styrmisson', '.']

    s = g.parse_single("Hér er Gvendur Ragnheiðarson.")
    assert s.lemmas == ['hér', 'vera', 'Gvendur Ragnheiðarson', '.']

    s = g.parse_single("Hér er Sóley Petrudóttir.")
    assert s.lemmas == ['hér', 'vera', 'Sóley Petrudóttir', '.']

    s = g.parse_single("Hér er Sóley Péturs- og Petrudóttir.")
    assert s.lemmas == ['hér', 'vera', 'Sóley Péturs- og Petrudóttir', '.']

    s = g.parse_single("Hér er Svanur Hildar- og Pálsson Scheving.")
    assert s.lemmas == ['hér', 'vera', 'Svanur Hildar- og Pálsson Scheving', '.']

    # The following examples are not covered at the moment, included in case they will be
    #s = g.parse_single("Hér eru Áki og Andri Brjánssynir.")
    #assert s.lemmas == ['hér', 'vera', 'Áki og Andri Brjánssynir', '.']

    #s = g.parse_single("Hér eru Ína og Una Brjánsdætur.")
    #assert s.lemmas == ['hér', 'vera', 'Ína og Una Brjánsdætur', '.']

    #s = g.parse_single("Hér eru Áki og Láki Brjánssynir.")
    #assert s.lemmas == ['hér', 'vera', 'Áki og Láki Brjánssynir', '.']

    #s = g.parse_single("Hér eru Ína og Mína Brjánsdætur.")
    #assert s.lemmas == ['hér', 'vera', 'Ína og Mína Brjánsdætur', '.']

    #s = g.parse_single("Hér eru Áki og Ína Brjánsbörn.")
    #assert s.lemmas == ['hér', 'vera', 'Áki og Ína Brjánsbörn', '.']

    s = g.parse_single("Hér er Jack Nicholson.")
    assert s.lemmas == ['hér', 'vera', 'Jack Nicholson', '.']

    s = g.parse_single("Hér er Diane Lane.")
    assert s.lemmas == ['hér', 'vera', 'Diane Lane', '.']

    s = g.parse_single("Hér er Finsbury Park.")
    #assert s.lemmas == ['hér', 'vera', 'Finsbury Park', '.']

    s = g.parse_single("Hér er Sky Sports.")
    #assert s.lemmas == ['hér', 'vera', 'Sky Sports', '.']

    s = g.parse_single("Hér er J. K. Rowling.")
    #assert s.lemmas == ['hér', 'vera', 'J. K. Rowling', '.']

    s = g.parse_single("Hér er Parsley Ecothelial Welmington III.")
    assert s.lemmas == ['hér', 'vera', 'Parsley Ecothelial Welmington III', '.']

    s = g.parse_single("Hér er Dietrich van Helsing.")
    assert s.lemmas == ['hér', 'vera', 'Dietrich van Helsing', '.']

    s = g.parse_single("Hér er Helmine van de Fnupft.")
    assert s.lemmas == ['hér', 'vera', 'Helmine van de Fnupft', '.']

    s = g.parse_single("Hér er Carla de la Cruz.")
    assert s.lemmas == ['hér', 'vera', 'Carla de la Cruz', '.']

    s = g.parse_single("Hér er Barack Obama.")
    assert s.lemmas == ['hér', 'vera', 'Barack Obama', '.']

    s = g.parse_single("Hér er Finnur de la Cruz.")
    assert s.lemmas == ['hér', 'vera', 'Finnur de la Cruz', '.']

    s = g.parse_single("Hér er Derek Árnason.")
    #assert s.lemmas == ['hér', 'vera', 'Derek Árnason', '.']

    s = g.parse_single("Hér er Díana Woodward.")
    assert s.lemmas == ['hér', 'vera', 'Díana Woodward', '.']

    s = g.parse_single("Hér er Knut Axel Holding AS.")
    #assert s.lemmas == ['hér', 'vera', 'Knut Axel Holding AS', '.']

    s = g.parse_single("Hér er Matthildur Ármannsdóttir ehf..")
    #assert s.lemmas == ['hér', 'vera', 'Matthildur Ármannsdóttir ehf.', '.']

    s = g.parse_single("Hér er Super Mattel AS.")
    assert s.lemmas == ['hér', 'vera', 'Super Mattel AS', '.']

    s = g.parse_single("Hér er WOW Cyclothon.")
    #assert s.lemmas == ['hér', 'vera', 'WOW Cyclothon', '.']

    s = g.parse_single("Hér er SHAPP Games.")
    assert s.lemmas == ['hér', 'vera', 'SHAPP Games', '.']

    s = g.parse_single("Hér er Fiat a10.")
    #assert s.lemmas == ['hér', 'vera', 'Fiat a10', '.']

    s = g.parse_single("Hér er Ikea.")
    assert s.lemmas == ['hér', 'vera', 'Ikea', '.']

    s = g.parse_single("Hér er Styrmir Halldórsson H225.")
    #assert s.lemmas == ['hér', 'vera', 'Styrmir Halldórsson H225', '.']

    s = g.parse_single("Hér er The Trials and Tribulations of the Cat.")
    assert s.lemmas == ['hér', 'vera', 'The Trials and Tribulations of the Cat', '.']

    s = g.parse_single("Hér er Making Pastels: In Search of Quietness.")
    #assert s.lemmas == ['hér', 'vera', 'Making Pastels: In Search of Quietness', '.']

    s = g.parse_single("Hér er von Helgu.")
    assert s.lemmas == ['hér', 'vera', 'von', 'Helga', '.']

    s = g.parse_single("Hér er Helgi Björns.")
    assert s.lemmas == ['hér', 'vera', 'Helgi Björns', '.']

    s = g.parse_single("Hér er Jón de la.")
    assert s.lemmas == ['hér', 'vera', 'Jón', 'de', 'la', '.']


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
    tlist = list(g.tokenize("Ég hitti hr. Jón Mýrdal áðan."))
    assert len([t for t in tlist if t.kind == TOK.S_BEGIN]) == 1
    assert len([t for t in tlist if t.kind == TOK.S_END]) == 1

if __name__ == "__main__":

    test_augment_terminal()
    test_bin()

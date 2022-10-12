# type: ignore
"""

    test_cases.py

    Tests for Greynir module

    Copyright (C) 2022 Miðeind ehf.
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

import pytest

from reynir import Greynir


@pytest.fixture(scope="module")
def r():
    """Provide a module-scoped Greynir instance as a test fixture"""
    r = Greynir()
    yield r
    # Do teardown here
    r.__class__.cleanup()


def test_cases(r: Greynir) -> None:
    s = r.parse_single("Ég átti svakalega stóran hest með fallegasta makkann.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "svakalega stór hestur með fallegasta makkann"
    assert np_obj.accusative_np == "svakalega stóran hest með fallegasta makkann"
    assert np_obj.dative_np == "svakalega stórum hesti með fallegasta makkann"
    assert np_obj.genitive_np == "svakalega stórs hests með fallegasta makkann"

    s = r.parse_single("Ég átti svakalega stóra hestinn með fallegasta makkann.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "svakalega stóri hesturinn með fallegasta makkann"
    assert np_obj.accusative_np == "svakalega stóra hestinn með fallegasta makkann"
    assert np_obj.dative_np == "svakalega stóra hestinum með fallegasta makkann"
    assert np_obj.genitive_np == "svakalega stóra hestsins með fallegasta makkann"

    s = r.parse_single("Ég átti hinn svakalega stóra hest með fallegasta makkann.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "hinn svakalega stóri hestur með fallegasta makkann"
    assert np_obj.accusative_np == "hinn svakalega stóra hest með fallegasta makkann"
    assert np_obj.dative_np == "hinum svakalega stóra hesti með fallegasta makkann"
    assert np_obj.genitive_np == "hins svakalega stóra hests með fallegasta makkann"

    s = r.parse_single("Ég átti svakalega stóra hesta með fallegasta makkann.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "svakalega stórir hestar með fallegasta makkann"
    assert np_obj.accusative_np == "svakalega stóra hesta með fallegasta makkann"
    assert np_obj.dative_np == "svakalega stórum hestum með fallegasta makkann"
    assert np_obj.genitive_np == "svakalega stórra hesta með fallegasta makkann"

    s = r.parse_single("Ég átti svakalega stóru hestana með fallegasta makkann.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "svakalega stóru hestarnir með fallegasta makkann"
    assert np_obj.accusative_np == "svakalega stóru hestana með fallegasta makkann"
    assert np_obj.dative_np == "svakalega stóru hestunum með fallegasta makkann"
    assert np_obj.genitive_np == "svakalega stóru hestanna með fallegasta makkann"

    s = r.parse_single("Ég átti hina svakalega stóru hesta með fallegasta makkann.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "hinir svakalega stóru hestar með fallegasta makkann"
    assert np_obj.accusative_np == "hina svakalega stóru hesta með fallegasta makkann"
    assert np_obj.dative_np == "hinum svakalega stóru hestum með fallegasta makkann"
    assert np_obj.genitive_np == "hinna svakalega stóru hesta með fallegasta makkann"

    s = r.parse_single("Ég átti svakalega stóran hest með fallegasta makkann.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "svakalega stór hestur með fallegasta makkann"
    assert np_obj.accusative_np == "svakalega stóran hest með fallegasta makkann"
    assert np_obj.dative_np == "svakalega stórum hesti með fallegasta makkann"
    assert np_obj.genitive_np == "svakalega stórs hests með fallegasta makkann"

    s = r.parse_single("Ég átti allra stærsta hestinn með fallegasta makkann.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "allra stærsti hesturinn með fallegasta makkann"
    assert np_obj.accusative_np == "allra stærsta hestinn með fallegasta makkann"
    assert np_obj.dative_np == "allra stærsta hestinum með fallegasta makkann"
    assert np_obj.genitive_np == "allra stærsta hestsins með fallegasta makkann"

    s = r.parse_single("Ég átti hinn allra stærsta hest með fallegasta makkann.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "hinn allra stærsti hestur með fallegasta makkann"
    assert np_obj.accusative_np == "hinn allra stærsta hest með fallegasta makkann"
    assert np_obj.dative_np == "hinum allra stærsta hesti með fallegasta makkann"
    assert np_obj.genitive_np == "hins allra stærsta hests með fallegasta makkann"

    s = r.parse_single("Ég átti allra stærsta hesta með fallegasta makkann.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "allra stærstir hestar með fallegasta makkann"
    assert np_obj.accusative_np == "allra stærsta hesta með fallegasta makkann"
    assert np_obj.dative_np == "allra stærstum hestum með fallegasta makkann"
    assert np_obj.genitive_np == "allra stærstra hesta með fallegasta makkann"

    s = r.parse_single("Ég átti allra stærstu hestana með fallegasta makkann.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "allra stærstu hestarnir með fallegasta makkann"
    assert np_obj.accusative_np == "allra stærstu hestana með fallegasta makkann"
    assert np_obj.dative_np == "allra stærstu hestunum með fallegasta makkann"
    assert np_obj.genitive_np == "allra stærstu hestanna með fallegasta makkann"

    s = r.parse_single("Ég átti hina allra stærstu hesta með fallegasta makkann.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "hinir allra stærstu hestar með fallegasta makkann"
    assert np_obj.accusative_np == "hina allra stærstu hesta með fallegasta makkann"
    assert np_obj.dative_np == "hinum allra stærstu hestum með fallegasta makkann"
    assert np_obj.genitive_np == "hinna allra stærstu hesta með fallegasta makkann"

    s = r.parse_single("Ég átti allra stærsta hestinn sem kunni fimm gangtegundir.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "allra stærsti hesturinn sem kunni fimm gangtegundir"
    assert np_obj.accusative_np == "allra stærsta hestinn sem kunni fimm gangtegundir"
    assert np_obj.dative_np == "allra stærsta hestinum sem kunni fimm gangtegundir"
    assert np_obj.genitive_np == "allra stærsta hestsins sem kunni fimm gangtegundir"

    s = r.parse_single("Ég átti hinn allra stærsta hest sem kunni fimm gangtegundir.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert (
        np_obj.nominative_np == "hinn allra stærsti hestur sem kunni fimm gangtegundir"
    )
    assert np_obj.accusative_np == "hinn allra stærsta hest sem kunni fimm gangtegundir"
    assert np_obj.dative_np == "hinum allra stærsta hesti sem kunni fimm gangtegundir"
    assert np_obj.genitive_np == "hins allra stærsta hests sem kunni fimm gangtegundir"

    s = r.parse_single("Ég átti allra stærsta hesta sem kunnu fimm gangtegundir.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "allra stærstir hestar sem kunnu fimm gangtegundir"
    assert np_obj.accusative_np == "allra stærsta hesta sem kunnu fimm gangtegundir"
    assert np_obj.dative_np == "allra stærstum hestum sem kunnu fimm gangtegundir"
    assert np_obj.genitive_np == "allra stærstra hesta sem kunnu fimm gangtegundir"

    s = r.parse_single("Ég átti allra stærstu hestana sem kunnu fimm gangtegundir.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "allra stærstu hestarnir sem kunnu fimm gangtegundir"
    assert np_obj.accusative_np == "allra stærstu hestana sem kunnu fimm gangtegundir"
    assert np_obj.dative_np == "allra stærstu hestunum sem kunnu fimm gangtegundir"
    assert np_obj.genitive_np == "allra stærstu hestanna sem kunnu fimm gangtegundir"

    s = r.parse_single("Ég átti hina allra stærstu hesta sem kunnu fimm gangtegundir.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert (
        np_obj.nominative_np == "hinir allra stærstu hestar sem kunnu fimm gangtegundir"
    )
    assert (
        np_obj.accusative_np == "hina allra stærstu hesta sem kunnu fimm gangtegundir"
    )
    assert np_obj.dative_np == "hinum allra stærstu hestum sem kunnu fimm gangtegundir"
    assert np_obj.genitive_np == "hinna allra stærstu hesta sem kunnu fimm gangtegundir"

    s = r.parse_single(
        "Pál, hinn vinsæla landsliðsmann sem spilaði þrjátíu leiki "
        "með landsliðinu á sínum tíma, langar að leggja skóna á hilluna."
    )
    assert (
        s.tree.S_MAIN.IP.NP_SUBJ.nominative_np
        == "Páll , hinn vinsæli landsliðsmaður sem spilaði þrjátíu leiki með landsliðinu á sínum tíma"
    )
    assert (
        s.tree.S_MAIN.IP.NP_SUBJ.accusative_np
        == "Pál , hinn vinsæla landsliðsmann sem spilaði þrjátíu leiki með landsliðinu á sínum tíma"
    )
    assert (
        s.tree.S_MAIN.IP.NP_SUBJ.dative_np
        == "Páli , hinum vinsæla landsliðsmanni sem spilaði þrjátíu leiki með landsliðinu á sínum tíma"
    )
    assert (
        s.tree.S_MAIN.IP.NP_SUBJ.genitive_np
        == "Páls , hins vinsæla landsliðsmanns sem spilaði þrjátíu leiki með landsliðinu á sínum tíma"
    )

    s = r.parse_single(
        "Pósturinn Páll, hinn sívinsæli gleðigjafi, er á dagskrá í sumar."
    )
    assert (
        s.tree.S_MAIN.IP.NP_SUBJ.nominative_np
        == "Pósturinn Páll , hinn sívinsæli gleðigjafi"
    )
    assert (
        s.tree.S_MAIN.IP.NP_SUBJ.accusative_np
        == "Póstinn Pál , hinn sívinsæla gleðigjafa"
    )
    assert (
        s.tree.S_MAIN.IP.NP_SUBJ.dative_np
        == "Póstinum Páli , hinum sívinsæla gleðigjafa"
    )
    assert (
        s.tree.S_MAIN.IP.NP_SUBJ.genitive_np
        == "Póstsins Páls , hins sívinsæla gleðigjafa"
    )

    s = r.parse_single(
        "Pósturinn Páll og kötturinn Njáll, tveir sívinsælir gleðigjafar, eru á dagskrá í sumar."
    )
    assert (
        s.tree.S_MAIN.IP.NP_SUBJ.nominative_np
        == "Pósturinn Páll og kötturinn Njáll , tveir sívinsælir gleðigjafar"
    )
    assert (
        s.tree.S_MAIN.IP.NP_SUBJ.accusative_np
        == "Póstinn Pál og köttinn Njál , tvo sívinsæla gleðigjafa"
    )
    assert (
        s.tree.S_MAIN.IP.NP_SUBJ.dative_np
        == "Póstinum Páli og kettinum Njáli , tveimur sívinsælum gleðigjöfum"
    )
    assert (
        s.tree.S_MAIN.IP.NP_SUBJ.genitive_np
        == "Póstsins Páls og kattarins Njáls , tveggja sívinsælla gleðigjafa"
    )

    s = r.parse_single("Rauð viðvörun hefur verið gefin út.")
    assert s.tree.S_MAIN.IP.NP_SUBJ.nominative_np == "Rauð viðvörun"
    assert s.tree.S_MAIN.IP.NP_SUBJ.accusative_np == "Rauða viðvörun"
    assert s.tree.S_MAIN.IP.NP_SUBJ.dative_np == "Rauðri viðvörun"
    assert s.tree.S_MAIN.IP.NP_SUBJ.genitive_np == "Rauðrar viðvörunar"

    s = r.parse_single("Rauða viðvörunin hefur verið gefin út.")
    assert s.tree.S_MAIN.IP.NP_SUBJ.nominative_np == "Rauða viðvörunin"
    assert s.tree.S_MAIN.IP.NP_SUBJ.accusative_np == "Rauðu viðvörunina"
    assert s.tree.S_MAIN.IP.NP_SUBJ.dative_np == "Rauðu viðvöruninni"
    assert s.tree.S_MAIN.IP.NP_SUBJ.genitive_np == "Rauðu viðvörunarinnar"


def test_noun_phrases(r):
    """Test functions for easy manipulation of noun phrases"""

    # Doesn't work for some reason
    np = r.parse_noun_phrase("þrír lúxus-miðar á Star Wars í dag")
    assert np.tree is not None
    assert np.nominative == "þrír lúxus-miðar á Star Wars í dag"
    assert np.accusative == "þrjá lúxus-miða á Star Wars í dag"
    assert np.dative == "þremur lúxus-miðum á Star Wars í dag"
    assert np.genitive == "þriggja lúxus-miða á Star Wars í dag"
    assert np.indefinite == "þrír lúxus-miðar á Star Wars í dag"
    assert np.canonical == "lúxus-miði"

    from reynir import NounPhrase

    np = NounPhrase(
        "þrír glæsilegir lúxus-bíómiðar á Star Wars "
        "og að auki tveir stútfullir pokar af ilmandi poppi"
    )
    assert np.parsed
    assert len(np) == len(str(np))
    assert (
        "Hér er kvittunin þín fyrir {np:þgf}. "
        "Þar með ertu búin(n) að kaupa {np:þf}.".format(np=np)
        == "Hér er kvittunin þín fyrir þremur glæsilegum lúxus-bíómiðum "
        "á Star Wars og að auki tveimur stútfullum pokum af ilmandi poppi. "
        "Þar með ertu búin(n) að kaupa þrjá glæsilega lúxus-bíómiða "
        "á Star Wars og að auki tvo stútfulla poka af ilmandi poppi."
    )
    np = NounPhrase("skjótti hesturinn")
    assert np.parsed
    assert np.case == "nf"
    assert np.person == "p3"
    assert np.number == "et"
    assert np.gender == "kk"
    assert str(np) == "skjótti hesturinn"
    assert "Hér er {np:nf}".format(np=np) == "Hér er skjótti hesturinn"
    assert "Um {np:þf}".format(np=np) == "Um skjótta hestinn"
    assert "Frá {np:þgf}".format(np=np) == "Frá skjótta hestinum"
    assert "Til {np:ef}".format(np=np) == "Til skjótta hestsins"
    assert "Hér er {np:ángr}".format(np=np) == "Hér er skjóttur hestur"
    np = NounPhrase("þrír skjóttir hestar")
    assert np.parsed
    assert np.number == "ft"
    assert np.case == "nf"
    assert np.person == "p3"
    assert np.gender == "kk"
    assert str(np) == "þrír skjóttir hestar"
    assert len(np) == len(str(np))
    assert "Umræðuefnið er {np:stofn}".format(np=np) == "Umræðuefnið er skjóttur hestur"
    try:
        "Óleyfilegt {np:.2f}".format(np=np)
    except ValueError:
        pass
    else:
        assert False, "Should have raised ValueError"
    try:
        "Óleyfilegt {np:abc}".format(np=np)
    except ValueError:
        pass
    else:
        assert False, "Should have raised ValueError"
    np = NounPhrase("Doddi át kökuna")
    assert not np.parsed
    assert np.gender is None
    assert np.number is None
    assert np.case is None
    assert np.person is None
    np = NounPhrase("")
    assert not np.parsed
    assert np.gender is None
    assert np.number is None
    assert np.case is None
    assert np.person is None
    np = NounPhrase("buxur")
    assert np.parsed
    assert np.number == "ft"
    assert np.genitive == "buxna"
    np = NounPhrase("buxur", force_number="et")
    assert not np.parsed
    np = NounPhrase("gleraugun hans afa", force_number="ft")
    assert np.parsed
    assert np.number == "ft"
    assert np.genitive == "gleraugnanna hans afa"
    np = NounPhrase("gleraugun hans afa", force_number="et")
    assert not np.parsed
    np = NounPhrase("eyjar", force_number="ft")
    assert np.parsed
    assert np.number == "ft"
    assert np.nominative == "eyjar"
    np = NounPhrase("eyjar", force_number="et")
    assert np.parsed
    assert np.number == "et"
    assert np.nominative == "ey"
    np = NounPhrase("eyjar", force_number="plural")
    assert np.parsed
    assert np.number == "ft"
    assert np.nominative == "eyjar"
    np = NounPhrase("eyjar", force_number="singular")
    assert np.parsed
    assert np.number == "et"
    assert np.nominative == "ey"
    np = NounPhrase("Spánn")
    assert np.parsed
    assert np.nominative == "Spánn"
    assert np.genitive == "Spánar"


def test_addresses():
    from reynir import NounPhrase

    np = NounPhrase("Laugavegi 20b")
    assert np.nominative == "Laugavegur 20b"
    assert np.accusative == "Laugaveg 20b"
    assert np.dative == "Laugavegi 20b"
    assert np.genitive == "Laugavegar 20b"
    np = NounPhrase("Baugatanga 6C")
    assert np.nominative == "Baugatangi 6C"
    assert np.accusative == "Baugatanga 6C"
    assert np.dative == "Baugatanga 6C"
    assert np.genitive == "Baugatanga 6C"
    np = NounPhrase("Æðarvarp 17")
    assert np.nominative == "Æðarvarp 17"
    assert np.accusative == "Æðarvarp 17"
    assert np.dative == "Æðarvarpi 17"
    assert np.genitive == "Æðarvarps 17"
    np = NounPhrase("Vættaborgir 17")
    assert np.nominative == "Vættaborgir 17"
    assert np.accusative == "Vættaborgir 17"
    assert np.dative == "Vættaborgum 17"
    assert np.genitive == "Vættaborga 17"
    np = NounPhrase("Vættaborga 17")
    assert np.nominative == "Vættaborgir 17"
    assert np.accusative == "Vættaborgir 17"
    assert np.dative == "Vættaborgum 17"
    assert np.genitive == "Vættaborga 17"
    np = NounPhrase("Sólarsölum 3B")
    assert np.nominative == "Sólarsalir 3B"
    assert np.accusative == "Sólarsali 3B"
    assert np.dative == "Sólarsölum 3B"
    assert np.genitive == "Sólarsala 3B"
    np = NounPhrase("Gamla vitanum í Garðskaga á Reykjanesi")
    assert np.nominative == "Gamli vitinn í Garðskaga á Reykjanesi"
    assert np.accusative == "Gamla vitann í Garðskaga á Reykjanesi"
    assert np.dative == "Gamla vitanum í Garðskaga á Reykjanesi"
    assert np.genitive == "Gamla vitans í Garðskaga á Reykjanesi"
    np = NounPhrase("Gamla vitans í Garðskaga á Reykjanesi")
    assert np.nominative == "Gamli vitinn í Garðskaga á Reykjanesi"
    assert np.accusative == "Gamla vitann í Garðskaga á Reykjanesi"
    assert np.dative == "Gamla vitanum í Garðskaga á Reykjanesi"
    assert np.genitive == "Gamla vitans í Garðskaga á Reykjanesi"


if __name__ == "__main__":
    # When invoked as a main module, do a verbose test
    from reynir import Greynir

    greynir = Greynir()
    test_cases(greynir)
    test_noun_phrases(greynir)
    test_addresses()
    greynir.__class__.cleanup()

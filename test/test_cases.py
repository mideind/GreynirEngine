"""

    test_cases.py

    Tests for Reynir module

    Copyright(C) 2019 by Miðeind ehf.
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

r = None


def test_init():
    """ Test that importing and initializing the reynir module works """
    from reynir import Reynir
    global r
    r = Reynir()


def test_finish():
    r.__class__.cleanup()


def test_cases():
    s = r.parse_single("Ég átti svakalega stóran hest með fallegasta makkann.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "svakalega stór hestur með fallegasta makkann"
    assert np_obj.accusative_np == 'svakalega stóran hest með fallegasta makkann'
    assert np_obj.dative_np == 'svakalega stórum hesti með fallegasta makkann'
    assert np_obj.possessive_np == 'svakalega stórs hests með fallegasta makkann'

    s = r.parse_single("Ég átti svakalega stóra hestinn með fallegasta makkann.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "svakalega stóri hesturinn með fallegasta makkann"
    assert np_obj.accusative_np == 'svakalega stóra hestinn með fallegasta makkann'
    assert np_obj.dative_np == 'svakalega stóra hestinum með fallegasta makkann'
    assert np_obj.possessive_np == 'svakalega stóra hestsins með fallegasta makkann'

    s = r.parse_single("Ég átti hinn svakalega stóra hest með fallegasta makkann.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "hinn svakalega stóri hestur með fallegasta makkann"
    assert np_obj.accusative_np == 'hinn svakalega stóra hest með fallegasta makkann'
    assert np_obj.dative_np == 'hinum svakalega stóra hesti með fallegasta makkann'
    assert np_obj.possessive_np == 'hins svakalega stóra hests með fallegasta makkann'

    s = r.parse_single("Ég átti svakalega stóra hesta með fallegasta makkann.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "svakalega stórir hestar með fallegasta makkann"
    assert np_obj.accusative_np == 'svakalega stóra hesta með fallegasta makkann'
    assert np_obj.dative_np == 'svakalega stórum hestum með fallegasta makkann'
    assert np_obj.possessive_np == 'svakalega stórra hesta með fallegasta makkann'

    s = r.parse_single("Ég átti svakalega stóru hestana með fallegasta makkann.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "svakalega stóru hestarnir með fallegasta makkann"
    assert np_obj.accusative_np == 'svakalega stóru hestana með fallegasta makkann'
    assert np_obj.dative_np == 'svakalega stóru hestunum með fallegasta makkann'
    assert np_obj.possessive_np == 'svakalega stóru hestanna með fallegasta makkann'

    s = r.parse_single("Ég átti hina svakalega stóru hesta með fallegasta makkann.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "hinir svakalega stóru hestar með fallegasta makkann"
    assert np_obj.accusative_np == 'hina svakalega stóru hesta með fallegasta makkann'
    assert np_obj.dative_np == 'hinum svakalega stóru hestum með fallegasta makkann'
    assert np_obj.possessive_np == 'hinna svakalega stóru hesta með fallegasta makkann'

    s = r.parse_single("Ég átti svakalega stóran hest með fallegasta makkann.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "svakalega stór hestur með fallegasta makkann"
    assert np_obj.accusative_np == 'svakalega stóran hest með fallegasta makkann'
    assert np_obj.dative_np == 'svakalega stórum hesti með fallegasta makkann'
    assert np_obj.possessive_np == 'svakalega stórs hests með fallegasta makkann'

    s = r.parse_single("Ég átti allra stærsta hestinn með fallegasta makkann.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "allra stærsti hesturinn með fallegasta makkann"
    assert np_obj.accusative_np == 'allra stærsta hestinn með fallegasta makkann'
    assert np_obj.dative_np == 'allra stærsta hestinum með fallegasta makkann'
    assert np_obj.possessive_np == 'allra stærsta hestsins með fallegasta makkann'

    s = r.parse_single("Ég átti hinn allra stærsta hest með fallegasta makkann.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "hinn allra stærsti hestur með fallegasta makkann"
    assert np_obj.accusative_np == 'hinn allra stærsta hest með fallegasta makkann'
    assert np_obj.dative_np == 'hinum allra stærsta hesti með fallegasta makkann'
    assert np_obj.possessive_np == 'hins allra stærsta hests með fallegasta makkann'

    s = r.parse_single("Ég átti allra stærsta hesta með fallegasta makkann.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "allra stærstir hestar með fallegasta makkann"
    assert np_obj.accusative_np == 'allra stærsta hesta með fallegasta makkann'
    assert np_obj.dative_np == 'allra stærstum hestum með fallegasta makkann'
    assert np_obj.possessive_np == 'allra stærstra hesta með fallegasta makkann'

    s = r.parse_single("Ég átti allra stærstu hestana með fallegasta makkann.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "allra stærstu hestarnir með fallegasta makkann"
    assert np_obj.accusative_np == 'allra stærstu hestana með fallegasta makkann'
    assert np_obj.dative_np == 'allra stærstu hestunum með fallegasta makkann'
    assert np_obj.possessive_np == 'allra stærstu hestanna með fallegasta makkann'

    s = r.parse_single("Ég átti hina allra stærstu hesta með fallegasta makkann.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "hinir allra stærstu hestar með fallegasta makkann"
    assert np_obj.accusative_np == 'hina allra stærstu hesta með fallegasta makkann'
    assert np_obj.dative_np == 'hinum allra stærstu hestum með fallegasta makkann'
    assert np_obj.possessive_np == 'hinna allra stærstu hesta með fallegasta makkann'

    s = r.parse_single("Ég átti allra stærsta hestinn sem kunni fimm gangtegundir.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "allra stærsti hesturinn sem kunni fimm gangtegundir"
    assert np_obj.accusative_np == 'allra stærsta hestinn sem kunni fimm gangtegundir'
    assert np_obj.dative_np == 'allra stærsta hestinum sem kunni fimm gangtegundir'
    assert np_obj.possessive_np == 'allra stærsta hestsins sem kunni fimm gangtegundir'

    s = r.parse_single("Ég átti hinn allra stærsta hest sem kunni fimm gangtegundir.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "hinn allra stærsti hestur sem kunni fimm gangtegundir"
    assert np_obj.accusative_np == 'hinn allra stærsta hest sem kunni fimm gangtegundir'
    assert np_obj.dative_np == 'hinum allra stærsta hesti sem kunni fimm gangtegundir'
    assert np_obj.possessive_np == 'hins allra stærsta hests sem kunni fimm gangtegundir'

    s = r.parse_single("Ég átti allra stærsta hesta sem kunnu fimm gangtegundir.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "allra stærstir hestar sem kunnu fimm gangtegundir"
    assert np_obj.accusative_np == 'allra stærsta hesta sem kunnu fimm gangtegundir'
    assert np_obj.dative_np == 'allra stærstum hestum sem kunnu fimm gangtegundir'
    assert np_obj.possessive_np == 'allra stærstra hesta sem kunnu fimm gangtegundir'

    s = r.parse_single("Ég átti allra stærstu hestana sem kunnu fimm gangtegundir.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "allra stærstu hestarnir sem kunnu fimm gangtegundir"
    assert np_obj.accusative_np == 'allra stærstu hestana sem kunnu fimm gangtegundir'
    assert np_obj.dative_np == 'allra stærstu hestunum sem kunnu fimm gangtegundir'
    assert np_obj.possessive_np == 'allra stærstu hestanna sem kunnu fimm gangtegundir'

    s = r.parse_single("Ég átti hina allra stærstu hesta sem kunnu fimm gangtegundir.")
    np_obj = s.tree.S_MAIN.IP.VP.NP_OBJ
    assert np_obj.nominative_np == "hinir allra stærstu hestar sem kunnu fimm gangtegundir"
    assert np_obj.accusative_np == 'hina allra stærstu hesta sem kunnu fimm gangtegundir'
    assert np_obj.dative_np == 'hinum allra stærstu hestum sem kunnu fimm gangtegundir'
    assert np_obj.possessive_np == 'hinna allra stærstu hesta sem kunnu fimm gangtegundir'

    s = r.parse_single("Pál, hinn vinsæla landsliðsmann sem spilaði þrjátíu leiki "
        "með landsliðinu á sínum tíma, langar að leggja skóna á hilluna.")
    assert (s.tree.S_MAIN.IP.NP_SUBJ.nominative_np ==
        'Páll , hinn vinsæli landsliðsmaður sem spilaði þrjátíu leiki með landsliðinu á sínum tíma'
    )
    assert (s.tree.S_MAIN.IP.NP_SUBJ.accusative_np ==
        'Pál , hinn vinsæla landsliðsmann sem spilaði þrjátíu leiki með landsliðinu á sínum tíma'
    )
    assert (s.tree.S_MAIN.IP.NP_SUBJ.dative_np ==
        'Páli , hinum vinsæla landsliðsmanni sem spilaði þrjátíu leiki með landsliðinu á sínum tíma'
    )
    assert(s.tree.S_MAIN.IP.NP_SUBJ.possessive_np ==
        'Páls , hins vinsæla landsliðsmanns sem spilaði þrjátíu leiki með landsliðinu á sínum tíma'
    )

    s = r.parse_single("Pósturinn Páll, hinn sívinsæli gleðigjafi, er á dagskrá í sumar.")
    assert (s.tree.S_MAIN.IP.NP_SUBJ.nominative_np ==
        "Pósturinn Páll , hinn sívinsæli gleðigjafi"
    )
    assert (s.tree.S_MAIN.IP.NP_SUBJ.accusative_np ==
        "Póstinn Pál , hinn sívinsæla gleðigjafa"
    )
    assert (s.tree.S_MAIN.IP.NP_SUBJ.dative_np ==
        "Póstinum Páli , hinum sívinsæla gleðigjafa"
    )
    assert (s.tree.S_MAIN.IP.NP_SUBJ.possessive_np ==
        "Póstsins Páls , hins sívinsæla gleðigjafa"
    )


if __name__ == "__main__":
    # When invoked as a main module, do a verbose test
    test_init()
    test_cases()
    test_finish()

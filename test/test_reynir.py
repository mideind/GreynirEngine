"""

    test_reynir.py

    Tests for Greynir module

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

import functools

from reynir.binparser import augment_terminal
from reynir.bincompress import BIN_Compressed


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


if __name__ == "__main__":

    test_augment_terminal()
    test_bin()

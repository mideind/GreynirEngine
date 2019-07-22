# -*- encoding: utf-8 -*-
"""

    test_reynir.py

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

import functools

from reynir import Reynir
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

    def f(word, case, stem, cat, func=None):
        meanings = b.lookup_case(word, case)
        return set([
            (m[4], m[5]) for m in meanings
            if m[0] == stem and m[2] == cat and (func is None or func(m[5]))
        ])

    def declension(stem, cat, func=None):
        result = []
        for case in ("NF", "ÞF", "ÞGF", "EF"):
            wf_list = list(f(stem, case, stem, cat, func))
            result.append(wf_list[0][0] if wf_list else "N/A")
        return tuple(result)

    bf = lambda b: ("FVB" in b and "ET" in b)
    assert(
        f("fjarðarins", "NF", "fjörður", "kk") ==
        {('firðir', 'NFFT'), ('firðirnir', 'NFFTgr'), ('fjörður', 'NFET'), ('fjörðurinn', 'NFETgr')}
    )
    assert(
        f("breiðustu", "NF", "breiður", "lo", bf) ==
        {('breiða', 'FVB-KVK-NFET'), ('breiða', 'FVB-HK-NFET'), ('breiði', 'FVB-KK-NFET')}
    )
    assert(
        b.lookup_case("fjarðarins", "NF", "kk", {"ET", "gr"}) ==
        {('fjörður', 5697, 'kk', 'alm', 'fjörðurinn', 'NFETgr')}
    )
    assert(
        b.lookup_case("breiðustu", "NF", "lo", {"FT", "KK", "ESB"}) ==
        {('breiður', 388135, 'lo', 'alm', 'breiðastir', 'ESB-KK-NFFT')}
    )
    assert(
        f("fjarðarins", "ÞF", "fjörður", "kk") ==
        {('firði', 'ÞFFT'), ('firðina', 'ÞFFTgr'), ('fjörð', 'ÞFET'), ('fjörðinn', 'ÞFETgr')}
    )
    assert(
        f("breiðustu", "ÞF", "breiður", "lo", bf) ==
        {('breiða', 'FVB-KK-ÞFET'), ('breiða', 'FVB-HK-ÞFET'), ('breiðu', 'FVB-KVK-ÞFET')}
    )
    assert(
        f("fjarðarins", "ÞGF", "fjörður", "kk") ==
        {('firði', 'ÞGFET'), ('firðinum', 'ÞGFETgr'), ('fjörðum', 'ÞGFFT'), ('fjörðunum', 'ÞGFFTgr')}
    )
    assert(
        f("breiðustu", "ÞGF", "breiður", "lo", bf) ==
        {('breiða', 'FVB-KK-ÞGFET'), ('breiða', 'FVB-HK-ÞGFET'), ('breiðu', 'FVB-KVK-ÞGFET')}
    )
    assert(
        f("fjarðarins", "EF", "fjörður", "kk") ==
        {('fjarða', 'EFFT'), ('fjarðanna', 'EFFTgr'), ('fjarðar', 'EFET'), ('fjarðarins', 'EFETgr')}
    )
    assert(
        f("breiðustu", "EF", "breiður", "lo", bf) ==
        {('breiða', 'FVB-KK-EFET'), ('breiða', 'FVB-HK-EFET'), ('breiðu', 'FVB-KVK-EFET')}
    )
    bf_et = lambda b: ("ET" in b and "gr" not in b)
    assert(
        declension("brjóstsykur", "kk", bf_et) ==
        ("brjóstsykur", "brjóstsykur", "brjóstsykri", "brjóstsykurs")
    )
    assert(
        declension("smáskífa", "kvk", bf_et) ==
        ("smáskífa", "smáskífu", "smáskífu", "smáskífu")
    )
    assert(
        declension("ungabarn", "hk", bf_et) ==
        ("ungabarn", "ungabarn", "ungabarni", "ungabarns")
    )
    assert(
        declension("geymir", "kk", bf_et) ==
        ("geymir", "geymi", "geymi", "geymis")
    )
    assert(
        declension("sulta", "kvk", bf_et) ==
        ("sulta", "sultu", "sultu", "sultu")
    )
    assert(
        declension("vígi", "hk", bf_et) ==
        ("vígi", "vígi", "vígi", "vígis")
    )
    assert(
        declension("buxur", "kvk", bf_et) ==
        ("N/A", "N/A", "N/A", "N/A")
    )
    assert(
        declension("ríki", "hk", bf_et) ==
        ("ríki", "ríki", "ríki", "ríkis")
    )

    bf_et_gr = lambda b: ("ET" in b and "gr" in b)
    assert(
        declension("brjóstsykur", "kk", bf_et_gr) ==
        ("brjóstsykurinn", "brjóstsykurinn", "brjóstsykrinum", "brjóstsykursins")
    )
    assert(
        declension("smáskífa", "kvk", bf_et_gr) ==
        ("smáskífan", "smáskífuna", "smáskífunni", "smáskífunnar")
    )
    assert(
        declension("ungabarn", "hk", bf_et_gr) ==
        ("ungabarnið", "ungabarnið", "ungabarninu", "ungabarnsins")
    )
    assert(
        declension("geymir", "kk", bf_et_gr) ==
        ("geymirinn", "geyminn", "geyminum", "geymisins")
    )
    assert(
        declension("sulta", "kvk", bf_et_gr) ==
        ("sultan", "sultuna", "sultunni", "sultunnar")
    )
    assert(
        declension("vígi", "hk", bf_et_gr) ==
        ("vígið", "vígið", "víginu", "vígisins")
    )
    assert(
        declension("buxur", "kvk", bf_et_gr) ==
        ("N/A", "N/A", "N/A", "N/A")
    )
    assert(
        declension("ríki", "hk", bf_et_gr) ==
        ("ríkið", "ríkið", "ríkinu", "ríkisins")
    )

    bf_ft_gr = lambda b: ("FT" in b and "gr" in b)
    assert(
        declension("geymir", "kk", bf_ft_gr) ==
        ("geymarnir", "geymana", "geymunum", "geymanna")
    )
    assert(
        declension("sulta", "kvk", bf_ft_gr) ==
        ("sulturnar", "sulturnar", "sultunum", "sultanna")
    )
    assert(
        declension("vígi", "hk", bf_ft_gr) ==
        ("vígin", "vígin", "vígjunum", "vígjanna")
    )
    assert(
        declension("buxur", "kvk", bf_ft_gr) ==
        ("buxurnar", "buxurnar", "buxunum", "buxnanna")
    )
    assert(
        declension("ríki", "hk", bf_ft_gr) ==
        ("ríkin", "ríkin", "ríkjunum", "ríkjanna")
    )

    # A bit more fancy way of specifying constraints on the
    # returned word forms

    lookup_noun_sg_masc_indefinite = functools.partial(
        b.lookup_case, cat="kk", must_set={"ET"}, must_not_set={"gr"}
    )
    lookup_adj_sg_fem_strong = functools.partial(
        b.lookup_case, cat="lo", must_set={"ET", "KVK", "FSB"}
    )
    lookup_adj_pl_fem_weak = functools.partial(
        b.lookup_case, cat="lo", must_set={"FT", "KVK", "FVB"}
    )
    def decl(word, func):
        result = []
        for case in ("NF", "ÞF", "ÞGF", "EF"):
            mlist = list(func(word, case))
            assert len(mlist) <= 1
            if mlist:
                result.append(mlist[0][4])
            else:
                result.append("N/A")
        return tuple(result)
    assert(
        decl("sími", lookup_noun_sg_masc_indefinite) ==
        ("sími", "síma", "síma", "síma")
    )
    assert(
        decl("lítill", lookup_adj_sg_fem_strong) ==
        ("lítil", "litla", "lítilli", "lítillar")
    )
    assert(
        decl("lítill", lookup_adj_pl_fem_weak) ==
        ("litlu", "litlu", "litlu", "litlu")
    )


if __name__ == "__main__":

    test_augment_terminal()
    test_bin()

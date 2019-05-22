# -*- encoding: utf-8 -*-
"""

    test_reynir.py

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

from reynir import Reynir
from reynir.binparser import augment_terminal


r = Reynir()


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


if __name__ == "__main__":

    test_augment_terminal()

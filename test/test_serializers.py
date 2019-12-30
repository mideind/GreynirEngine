"""

    test_serializers.py

    Tests for Greynir module

    Copyright(C) 2019 by Miðeind ehf.

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

import json

import pytest


@pytest.fixture(scope="module")
def r():
    """ Provide a module-scoped Greynir instance as a test fixture """
    from reynir import Greynir
    r = Greynir()
    yield r
    # Do teardown here
    r.__class__.cleanup()


def test_serializers(r):
    orig = r.parse_single("""
        Ég fór niðrá bryggjuna með Reyni í gær. Það var 17. Júní árið 2020.
        Við sáum tvo seli og örugglega fleiri en 100 mavá.
        Klukkan var orðin tólf þegar við fórum heim.
        Morguninn eftir vaknaði ég kl. 07:30.
        Ég var fyrstur á fætur en Reynir númer 2.
    """)
    assert orig.tree is not None

    json_str = orig.dumps(indent=2)

    new = r.load_single(**json.loads(json_str))
    assert new.tree is not None
    assert new.tree.match("S0 >> { IP > { VP > { PP > { P > { fs } } } } } ")

    assert orig.tokens == new.tokens
    assert orig.terminals == new.terminals

    assert orig.tree.flat_with_all_variants == orig.tree.flat_with_all_variants
    assert json.loads(orig.dumps(indent=2)) == json.loads(new.dumps(indent=2))


if __name__ == "__main__":
    # When invoked as a main module, do a verbose test
    from reynir import Greynir
    r = Greynir()
    test_serializers(r)
    r.__class__.cleanup()

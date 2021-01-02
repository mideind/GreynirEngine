"""

    test_serializers.py

    Tests for JSON serialization of sentences

    Copyright (C) 2021 by Miðeind ehf.

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
    sents = [
        "Ég fór niðrá bryggjuna með Reyni Vilhjálmssyni í gær.",
        "Það var 17. júní árið 2020.",
        "Við sáum tvo seli og örugglega fleiri en 100 máva.",
        "Klukkan var orðin tólf þegar við fórum heim.",
        "Bíllinn kostaði €30.000 en ég greiddi 25500 USD fyrir hann.",
        "Morguninn eftir vaknaði ég kl. 07:30.",
        "Ég var fyrstur á fætur en Þuríður Hálfdánardóttir var númer 2.",
    ]
    for sent in sents:
        orig = r.parse_single(sent)
        assert orig.tree is not None

        json_str = r.dumps_single(orig, indent=2)
        new = r.loads_single(json_str)

        assert new.tree is not None

        assert orig.tokens == new.tokens
        assert orig.terminals == new.terminals

        assert orig.tree.flat_with_all_variants == orig.tree.flat_with_all_variants
        cls = r.__class__
        assert json.loads(orig.dumps(cls, indent=2)) == json.loads(new.dumps(cls, indent=2))


if __name__ == "__main__":
    # When invoked as a main module, do a verbose test
    from reynir import Greynir
    r = Greynir()
    test_serializers(r)
    r.__class__.cleanup()

"""

    test_binary_grammar.py

    Tests for robust loading of the binary grammar file,
    i.e. newGrammar()/readBinary() in eparser.cpp. A corrupt or
    truncated binary grammar file should cause newGrammar() to
    return NULL (surfacing as a GrammarError in Python), never
    to crash.

"""

import struct

import pytest

from reynir._eparser import lib as eparser, ffi  # type: ignore
from reynir.fastparser import Fast_Parser

BIN_FILE: str = Fast_Parser._GRAMMAR_BINARY_FILE

# The binary grammar header layout (see Grammar._write_binary()
# in grammar.py): 16 byte signature, then two unsigned ints
# (number of terminals, number of nonterminals), then a signed int
# (root nonterminal index)
SIGNATURE = b"Greynir00.00.01\n"
ROOT_OFFSET = len(SIGNATURE) + 8


@pytest.fixture(scope="module", autouse=True)
def ensure_binary_grammar():
    """Make sure the binary grammar file exists before running
    the tests in this module"""
    fp = Fast_Parser()
    fp.cleanup()
    yield


def load_grammar(path: str) -> bool:
    """Attempt to load a binary grammar file; return True if successful"""
    g = eparser.newGrammar(str(path).encode("utf-8"))
    if g == ffi.NULL:
        return False
    eparser.deleteGrammar(g)
    return True


def test_valid_grammar_loads() -> None:
    assert load_grammar(BIN_FILE)


def test_nonexistent_file_fails() -> None:
    assert not load_grammar(BIN_FILE + ".does-not-exist")


def test_truncated_grammar_fails(tmp_path) -> None:
    with open(BIN_FILE, "rb") as f:
        data = f.read()
    p = tmp_path / "truncated.bin"
    for cut in (0, 7, 16, 24, 28, len(data) // 2, len(data) - 4):
        p.write_bytes(data[:cut])
        assert not load_grammar(str(p)), (
            "Grammar truncated at {0} bytes should fail to load".format(cut)
        )


def test_bad_signature_fails(tmp_path) -> None:
    with open(BIN_FILE, "rb") as f:
        data = bytearray(f.read())
    data[0:7] = b"Invalid"
    p = tmp_path / "badsig.bin"
    p.write_bytes(data)
    assert not load_grammar(str(p))


def test_bad_root_fails(tmp_path) -> None:
    with open(BIN_FILE, "rb") as f:
        data = bytearray(f.read())
    p = tmp_path / "badroot.bin"
    # A nonnegative root index is invalid
    data[ROOT_OFFSET : ROOT_OFFSET + 4] = struct.pack("<i", 1)
    p.write_bytes(data)
    assert not load_grammar(str(p))
    # A root index out of the nonterminal range is invalid
    data[ROOT_OFFSET : ROOT_OFFSET + 4] = struct.pack("<i", -(2**24))
    p.write_bytes(data)
    assert not load_grammar(str(p))


def test_garbage_body_fails(tmp_path) -> None:
    with open(BIN_FILE, "rb") as f:
        header = f.read(ROOT_OFFSET + 4)
    p = tmp_path / "garbage.bin"
    p.write_bytes(header + b"\xff" * 256)
    assert not load_grammar(str(p))


def _minimal_grammar(production_item: int) -> bytes:
    """Construct a minimal binary grammar with one terminal, one
    nonterminal and a single one-item production"""
    buf = SIGNATURE
    buf += struct.pack("<II", 1, 1)  # One terminal, one nonterminal
    buf += struct.pack("<i", -1)  # Root nonterminal index
    buf += struct.pack("<I", 1)  # One production
    buf += struct.pack("<III", 0, 0, 1)  # Production id 0, priority 0, length 1
    buf += struct.pack("<i", production_item)
    return buf


def test_minimal_valid_grammar_loads(tmp_path) -> None:
    p = tmp_path / "minimal.bin"
    p.write_bytes(_minimal_grammar(1))  # Terminal index 1: valid
    assert load_grammar(str(p))


def test_out_of_range_production_items_fail(tmp_path) -> None:
    p = tmp_path / "baditem.bin"
    # Terminal index 2 is out of range (there is only one terminal)
    p.write_bytes(_minimal_grammar(2))
    assert not load_grammar(str(p))
    # A zero item is invalid within a production
    p.write_bytes(_minimal_grammar(0))
    assert not load_grammar(str(p))
    # Nonterminal index -2 is out of range (there is only one nonterminal)
    p.write_bytes(_minimal_grammar(-2))
    assert not load_grammar(str(p))

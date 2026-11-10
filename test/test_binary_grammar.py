"""

    test_binary_grammar.py

    Tests for robust loading of the binary grammar file,
    i.e. newGrammar()/readBinary() in eparser.cpp. A corrupt or
    truncated binary grammar file should cause newGrammar() to
    return NULL (surfacing as a GrammarError in Python), never
    to crash.

    Also tests that the binary grammar file is reproducible, i.e.
    that compiling the same grammar always yields the same binary.

"""

import os
import struct
import subprocess
import sys

import pytest

from reynir._eparser import lib as eparser, ffi  # type: ignore
from reynir.fastparser import Fast_Parser
from reynir.grammar import Grammar

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


# A small grammar where the right hand sides have 'free variants',
# i.e. variants that do not occur in the nonterminal being defined
FREE_VARIANT_GRAMMAR = """
/tala = et ft
/fall = nf þf
/kyn = kk kvk hk
/pers = p1 p2 p3

S0 → Liður/fall so/pers/tala/kyn

Liður/fall →
    lo/tala/fall/kyn no/tala/fall/kyn
    | fn/kyn/tala/fall
"""


def test_free_variant_production_order(tmp_path) -> None:
    """A rule with free variants is expanded into one production for each
    combination of their values. The order of those productions is part
    of the grammar: the lowest numbered production wins exact score ties
    in the reducer. It must thus be well defined, with the free variant
    that is mentioned first in the rule varying fastest, and not depend
    on the iteration order of a set."""
    fname = tmp_path / "free.grammar"
    fname.write_text(FREE_VARIANT_GRAMMAR, encoding="utf-8")
    g = Grammar()
    g.read(str(fname))

    def productions(nt_name: str) -> list:
        """Return the productions of a nonterminal, in index order"""
        plist = sorted((p.index, p) for _, p in g.nt_dict[g.nonterminals[nt_name]])
        return [" ".join(str(item) for item in p) for _, p in plist]

    tala, fall, kyn, pers = ("et", "ft"), ("nf", "þf"), ("kk", "kvk", "hk"), "123"
    # Free variants in order of first appearance: fall, pers, tala, kyn
    assert productions("S0") == [
        f"Liður_{f} so_p{p}_{t}_{k}"
        for k in kyn
        for t in tala
        for p in pers
        for f in fall
    ]
    # First alternative: tala, kyn; second alternative: kyn, tala
    # (the variant /fall is not free here, as it belongs to the nonterminal)
    assert productions("Liður_þf") == [
        f"lo_{t}_þf_{k} no_{t}_þf_{k}" for k in kyn for t in tala
    ] + [f"fn_{k}_{t}_þf" for t in tala for k in kyn]


# Program that compiles Greynir.grammar to the binary file given as
# an argument, without touching the binary grammar of the installation
COMPILE_GRAMMAR = """
import sys
from reynir.binparser import BIN_Parser

fname = BIN_Parser._GRAMMAR_FILE
g = BIN_Parser._grammar_class()
with open(fname, "r", encoding="utf-8") as f:
    g.read_from_generator(fname, f, binary_fname=sys.argv[1], force_new_binary=True)
"""


def test_binary_grammar_is_reproducible(tmp_path) -> None:
    """Compiling Greynir.grammar in two Python processes with different
    string hash seeds must give identical binary grammar files. Otherwise,
    the outcome of exact score ties in the reducer - and thereby the parse
    trees of some sentences - would vary between installations."""
    paths = [tmp_path / "seed{0}.bin".format(seed) for seed in (1, 2)]
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", COMPILE_GRAMMAR, str(path)],
            env=dict(os.environ, PYTHONHASHSEED=str(seed)),
        )
        for seed, path in zip((1, 2), paths)
    ]
    for proc in procs:
        assert proc.wait(timeout=300) == 0
    binaries = [path.read_bytes() for path in paths]
    assert binaries[0].startswith(SIGNATURE)
    assert binaries[0] == binaries[1]

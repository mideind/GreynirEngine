"""

    Greynir: Natural language processing for Icelandic

    Parser benchmark

    Copyright © 2026 Miðeind ehf.

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

    This program measures the parsing speed of GreynirEngine on a corpus
    of sentences, and how the time divides between the C++ Earley-Scott
    parser core (the earleyParse() function in eparser.cpp) and the rest
    of the pipeline (tokenization, token/terminal matching callbacks,
    conversion of the parse forest to Python objects, and reduction).

    Usage:

        uv run python benchmarks/bench_parse.py [corpus.txt] [options]

    The corpus is a text file with one sentence per line; by default, the
    file corpus.txt in the same directory as this program.

    The corpus is parsed several times ('passes') by the same parser.
    The first pass is 'cold': the token/terminal matching cache of the
    parser is empty. In later passes the cache is 'warm', which is close
    to the steady state of a long-running process. For each kind of pass,
    the fastest one is reported, as that is the measurement least
    affected by other activity on the machine.

    With the --digest option, the program instead writes a digest of the
    parse forest of each sentence, as returned from the C++ core. The
    digests are sensitive to everything in a forest, including the order
    of the families of children of each node (which decides the outcome
    of exact score ties in the reducer). To verify that a change to the
    core does not alter its output in any way, run the program with
    --digest before and after the change and compare the two outputs:

        uv run python benchmarks/bench_parse.py --digest > before.txt
        (change eparser.cpp; then: uv sync --reinstall-package reynir)
        uv run python benchmarks/bench_parse.py --digest > after.txt
        diff before.txt after.txt

    A change to the core may legitimately alter the order of the families
    (it follows from the order in which the core processes its states),
    as long as the forests are otherwise the same. Add the --unordered
    option to get digests that do not depend on that order.

"""

from typing import Any, Dict, List, Optional

import argparse
import hashlib
import json
import os
import time

from reynir import Greynir, __version__
from reynir import fastparser

DEFAULT_CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus.txt")

ffi: Any = fastparser.ffi
NULL: Any = ffi.NULL


def forest_digest(root: Any) -> str:
    """Return a digest of a parse forest returned from the C++ core.
    Nodes are identified by the order in which they are first visited,
    so the digest does not depend on memory addresses. The traversal is
    iterative, since forests can be deep."""
    h = hashlib.sha1()
    ids: Dict[Any, int] = {NULL: 0}
    stack: List[Any] = [root]
    num_nodes = 0
    while stack:
        node = stack.pop()
        if node in ids:
            continue
        ids[node] = len(ids)
        num_nodes += 1
        lb = node.label
        prod = -1 if lb.pProd == NULL else lb.pProd.nId
        h.update(
            "N{0}:{1},{2},{3},{4},{5}".format(
                ids[node], lb.iNt, lb.nDot, prod, lb.nI, lb.nJ
            ).encode("ascii")
        )
        children: List[Any] = []
        fe = node.pHead
        while fe != NULL:
            # Children that have not been visited yet are described by their
            # position in the list of pending nodes of this node, which is
            # resolved when their own records are written to the digest
            h.update("F{0}".format(fe.pProd.nId).encode("ascii"))
            for child in (fe.p1, fe.p2):
                if child in ids:
                    h.update("c{0}".format(ids[child]).encode("ascii"))
                else:
                    h.update(b"p")
                    children.append(child)
            fe = fe.pNext
        # Visit the children in order: the first one is popped first
        stack.extend(reversed(children))
    return "{0} nodes, {1}".format(num_nodes, h.hexdigest())


def forest_digest_unordered(root: Any) -> str:
    """Return a digest of a parse forest that does not depend on the order
    of the families of children within each node, nor on the order in
    which the nodes are visited: two forests have the same digest if they
    consist of the same nodes, each with the same set of families.
    A node is identified by its label, which is unique within a forest."""

    def label(node: Any) -> Any:
        if node == NULL:
            return None
        lb = node.label
        prod = -1 if lb.pProd == NULL else lb.pProd.nId
        return (lb.iNt, lb.nDot, prod, lb.nI, lb.nJ)

    records: List[Any] = []
    seen: Dict[Any, bool] = {NULL: True}
    stack: List[Any] = [root]
    num_families = 0
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen[node] = True
        families: List[Any] = []
        fe = node.pHead
        while fe != NULL:
            families.append(repr((fe.pProd.nId, label(fe.p1), label(fe.p2))))
            stack.append(fe.p1)
            stack.append(fe.p2)
            fe = fe.pNext
        families.sort()
        num_families += len(families)
        records.append(repr((label(node), families)))
    records.sort()
    h = hashlib.sha1("\n".join(records).encode("ascii"))
    return "{0} nodes, {1} families, {2}".format(
        len(records), num_families, h.hexdigest()
    )


class CoreProbe:

    """A stand-in for the CFFI library object of the C++ core, which
    measures the time spent in earleyParse() and optionally calculates
    digests of the returned parse forests. All other attributes are
    delegated to the real library object."""

    def __init__(
        self, lib: Any, digest: bool = False, unordered: bool = False
    ) -> None:
        self._lib = lib
        self._digest = digest
        self._digest_func = forest_digest_unordered if unordered else forest_digest
        self.seconds = 0.0
        self.tokens = 0
        self.parses = 0
        self.digests: List[str] = []

    def reset(self) -> None:
        self.seconds = 0.0
        self.tokens = 0
        self.parses = 0
        self.digests = []

    def __getattr__(self, name: str) -> Any:
        return getattr(self._lib, name)

    def earleyParse(
        self, parser: Any, num_tokens: int, root: int, handle: int, err: Any
    ) -> Any:
        t0 = time.perf_counter()
        node = self._lib.earleyParse(parser, num_tokens, root, handle, err)
        self.seconds += time.perf_counter() - t0
        self.tokens += num_tokens
        self.parses += 1
        if self._digest:
            if node == NULL:
                self.digests.append("no parse, error at {0}".format(err[0]))
            else:
                self.digests.append(self._digest_func(node))
        return node


def read_corpus(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def run_pass(g: Greynir, probe: CoreProbe, sentences: List[str]) -> Dict[str, Any]:
    """Parse the corpus once and return the measurements"""
    probe.reset()
    num_parsed = 0
    t0 = time.perf_counter()
    for sentence in sentences:
        s = g.parse_single(sentence)
        if s is not None and s.tree is not None:
            num_parsed += 1
    total = time.perf_counter() - t0
    return dict(
        sentences=len(sentences),
        parsed=num_parsed,
        tokens=probe.tokens,
        total_seconds=total,
        core_seconds=probe.seconds,
        digests=probe.digests,
    )


def best_pass(passes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return min(passes, key=lambda p: p["total_seconds"]) if passes else None


def describe(label: str, p: Dict[str, Any]) -> str:
    total: float = p["total_seconds"]
    core: float = p["core_seconds"]
    tokens: int = p["tokens"]
    return (
        "{0:5s} total {1:7.3f} s  {2:7.0f} tokens/s  |  "
        "core {3:7.3f} s  {4:7.0f} tokens/s  {5:5.1f}% of total".format(
            label,
            total,
            tokens / total,
            core,
            tokens / core if core else 0.0,
            100.0 * core / total,
        )
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Benchmark the GreynirEngine parser")
    ap.add_argument("corpus", nargs="?", default=DEFAULT_CORPUS)
    ap.add_argument(
        "-n",
        "--passes",
        type=int,
        default=5,
        help="number of warm passes over the corpus (default 5)",
    )
    ap.add_argument(
        "--digest",
        action="store_true",
        help="write a digest of the parse forest of each sentence, and no timings",
    )
    ap.add_argument(
        "--unordered",
        action="store_true",
        help="with --digest: write digests that do not depend on the order "
        "of the families of children of each node",
    )
    ap.add_argument("--json", action="store_true", help="write the results as JSON")
    args = ap.parse_args()

    sentences = read_corpus(args.corpus)

    # Route the calls from fastparser.py into the C++ core through our probe
    probe = CoreProbe(fastparser.eparser, digest=args.digest, unordered=args.unordered)
    fastparser.eparser = probe  # type: ignore

    g = Greynir()
    # Parse a sentence to load the grammar and the vocabulary database,
    # so that this one-time cost is not included in the measurements.
    # (Note that this warms the matching cache for the tokens involved.)
    g.parse_single("Hér er prófun.")

    if args.digest:
        p = run_pass(g, probe, sentences)
        for ix, digest in enumerate(p["digests"]):
            print("{0}: {1}".format(ix + 1, digest))
        return

    cold = run_pass(g, probe, sentences)
    warm = best_pass([run_pass(g, probe, sentences) for _ in range(args.passes)])

    if args.json:
        result: Dict[str, Any] = dict(version=__version__, cold=cold, warm=warm)
        for p in (cold, warm):
            if p is not None:
                del p["digests"]
        print(json.dumps(result, indent=2))
        return

    print(
        "GreynirEngine {0}: {1} sentences, {2} parsed, {3} tokens".format(
            __version__, cold["sentences"], cold["parsed"], cold["tokens"]
        )
    )
    print(describe("cold", cold))
    if warm is not None:
        print(describe("warm", warm))


if __name__ == "__main__":
    main()

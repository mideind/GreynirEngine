"""Parses from many threads at once must give the same results as from one.

On free-threaded Python (3.14t) the threads really run in parallel, so this
exercises the caches that all parses share, from empty and while they are
being replaced, under contention. With the GIL, the threads only interleave,
which needs fewer of them to show up.
"""

import random
import sys
import sysconfig
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest

from reynir import Greynir, bindb
from reynir.fastparser import Fast_Parser, ParseJob

FREE_THREADED = bool(sysconfig.get_config_var("Py_GIL_DISABLED"))
# With the GIL the threads take turns, so more of them add run time but little coverage
THREADS = 8 if FREE_THREADED else 4
# Each thread parses a random sample of this share of the sentences. The samples
# overlap, so the threads still meet the same tokens at the same time.
SAMPLE = 0.5

SENTENCES = [
    "Hundurinn beit manninn í gær.",
    "Ég fór í bíó með vinum mínum á laugardaginn.",
    "Ríkisstjórnin hefur ákveðið að hækka skatta á næsta ári.",
    "Jón Jónsson keypti 3 kg af kartöflum fyrir 1.500 krónur.",
    "Hún sagði að hann hefði komið heim seint um kvöldið.",
    "Forsætisráðherra Íslands hitti forseta Frakklands í París 12. mars 2024.",
    "Börnin léku sér úti í garðinum þangað til það fór að rigna.",
    "Ég hef aldrei séð jafn fallegt sólarlag.",
    "Verðbólgan mældist 4,5% í síðasta mánuði samkvæmt Hagstofunni.",
    "Bókin sem ég las var mjög skemmtileg.",
    "Hvað kostar miði til Akureyrar?",
    "Lögreglan handtók tvo menn vegna gruns um innbrot.",
    "Kötturinn stökk upp á borðið og velti glasinu.",
    "Við ætlum að halda upp á afmælið hans á morgun.",
    "Skipið sigldi frá Reykjavík til Vestmannaeyja í morgun.",
    "Fyrirtækið skilaði hagnaði upp á 2 milljarða króna.",
    "Það er ekki hægt að treysta honum.",
    "Hann gaf henni blóm og hún þakkaði honum fyrir.",
    "Stúlkan hljóp hratt niður brekkuna.",
    "Kennarinn útskýrði verkefnið fyrir nemendunum.",
    "Þingmenn deildu um frumvarpið langt fram á nótt.",
    "Ég veit ekki hvort hann kemur.",
    "Skólinn var lokaður vegna veðurs.",
    "Snjórinn bráðnaði hratt í hlýindunum.",
]

ParseResult = tuple[str | None, int | None, int | None]


def _parse(g: Greynir, text: str) -> ParseResult:
    s = g.parse_single(text)
    assert s is not None
    tree = s.tree
    return (tree.flat if tree is not None else None, s.score, s.combinations)


def test_parallel_parses_match_serial(monkeypatch: pytest.MonkeyPatch) -> None:
    g = Greynir()
    expected = {text: _parse(g, text) for text in SENTENCES}

    # Caches so small that the threads keep starting them afresh, and
    # fill the same empty caches at the same time
    monkeypatch.setattr(Fast_Parser, "_MAX_MATCHING_CACHE_SIZE", 16)
    monkeypatch.setattr(bindb, "_LOOKUP_CACHE_SIZE", 16)
    barrier = threading.Barrier(THREADS)

    def work(seed: int) -> list[str]:
        texts = random.Random(seed).sample(SENTENCES, int(len(SENTENCES) * SAMPLE))
        barrier.wait()
        return [text for text in texts if _parse(g, text) != expected[text]]

    with ThreadPoolExecutor(THREADS) as pool:
        mismatches = [m for ms in pool.map(work, range(THREADS)) for m in ms]
    assert mismatches == []


def test_open_jobs_keep_their_handles(monkeypatch: pytest.MonkeyPatch) -> None:
    # A long parse keeps its handle while the jobs of other threads cycle
    # through the rest
    monkeypatch.setattr(ParseJob, "_MAX_JOBS", 4)
    grammar: Any = None  # Not used by these jobs

    def make() -> ParseJob:
        return ParseJob.make(grammar, [], {}, {})

    with make() as held:
        for _ in range(10):
            with make() as other:
                assert other.handle != held.handle
        assert ParseJob._jobs[held.handle] is held
        others = [make() for _ in range(3)]
        # All handles are in use
        with pytest.raises(RuntimeError):
            make()
        for job in others:
            ParseJob.delete(job.handle)


@pytest.mark.skipif(not FREE_THREADED, reason="needs free-threaded Python")
def test_gil_stays_disabled() -> None:
    # An extension that does not declare free-threading support turns the GIL back on at import
    Greynir().parse_single("Hundurinn beit manninn.")
    # Free-threaded builds are 3.13 or later
    assert sys.version_info >= (3, 13)
    assert not sys._is_gil_enabled()

"""

    Greynir: Natural language processing for Icelandic

    Utility class for incremental parsing of token streams

    Copyright © 2023 Miðeind ehf.
    Original author: Vilhjálmur Þorsteinsson

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

    This module implements a simple utility class for parsing token
    streams into paragraphs and sentences. The parse is incremental so
    that the client can take action on each paragraph and sentence as
    it is processed. Also, time.sleep(0) is called between sentences
    to make multi-threaded parses proceed more smoothly and evenly.

"""

import time
from typing import Iterable, Iterator, List, Optional, Tuple

from tokenizer import paragraphs, Tok

from .bintokenizer import tokens_are_foreign
from .fastparser import Fast_Parser, Node, ParseError
from .reducer import Reducer
from .settings import Settings


# Number of tree combinations that must be exceeded for a verbose
# parse dump to include the sentence text (as opposed to just basic stats)
_VERBOSE_AMBIGUITY_THRESHOLD = 1000

# The ratio of words in a sentence that must be found in BÍN
# for it to be analyzed as an Icelandic sentence
ICELANDIC_RATIO = 0.5


# The same type is defined in the Tokenizer module
SentenceTuple = Tuple[int, List[Tok]]


class IncrementalParser:

    """Utility class to parse a token list as a sequence of paragraphs
    containing sentences. Typical usage:

    toklist = tokenize(text)
    fp = Fast_Parser()
    ip = IncrementalParser(fp, toklist)
    for p in ip.paragraphs():
        for sent in p.sentences():
            if sent.parse():
                # sentence parsed successfully
                # do something with sent.tree
            else:
                # an error occurred in the parse
                # the error token index is at sent.err_index
    num_sentences = ip.num_sentences
    num_parsed = ip.num_parsed
    ambiguity = ip.ambiguity
    parse_time = ip.parse_time

    """

    class _IncrementalSentence:

        """An internal sentence representation class"""

        def __init__(self, ip: "IncrementalParser", s: List[Tok]) -> None:
            self._ip = ip
            self._s = s
            self._len = len(s)
            assert self._len > 0  # Input should be already sanitized
            self._err_index: Optional[int] = None
            self._tree: Optional[Node] = None
            self._score = 0
            self._error: Optional[ParseError] = None

        def __len__(self):
            return self._len

        def parse(self) -> bool:
            """Parse the sentence"""
            num = 0
            score = 0
            forest: Optional[Node] = None
            try:
                if tokens_are_foreign(self._s, min_icelandic_ratio=ICELANDIC_RATIO):
                    raise ParseError(
                        "Sentence is probably not in Icelandic", token_index=0
                    )
                forest = self._ip._parser.go(self._s)
                num = Fast_Parser.num_combinations(forest)
                if num > 1:
                    forest, score = self._ip._reducer.go_with_score(forest)
            except ParseError as e:
                # The ParseError may originate in the reducer.go_with_score()
                # function, and in that case, forest is not None; be sure to reset it
                forest = None
                score = 0
                num = 0
                self._err_index = e.token_index
                self._error = e
            self._tree = forest
            self._score = score
            self._ip._add_sentence(self, num)
            return num > 0

        @property
        def tokens(self) -> List[Tok]:
            return self._s

        @property
        def tree(self) -> Optional[Node]:
            return self._tree

        @property
        def score(self) -> int:
            return self._score

        @property
        def error(self) -> Optional[ParseError]:
            return self._error

        @property
        def err_index(self) -> int:
            return self._len - 1 if self._err_index is None else self._err_index

        @property
        def text(self) -> str:
            return " ".join(t.txt for t in self._s if t.txt)

        def __str__(self) -> str:
            return self.text

    class _IncrementalParagraph:

        """An internal paragraph representation class"""

        def __init__(self, ip: "IncrementalParser", p: List[SentenceTuple]) -> None:
            self._ip = ip
            self._p = p

        def sentences(self) -> Iterator["IncrementalParser._IncrementalSentence"]:
            """Yield the sentences within the paragraph, nicely wrapped"""
            Sent = IncrementalParser._IncrementalSentence
            for _, sent in self._p:
                # Call time.sleep(0) to yield the current thread, i.e.
                # enable the threading subsystem and/or eventlet under Gunicorn
                # to switch threads at this point - since the parsing of an
                # entire article can take a long time
                time.sleep(0)
                yield Sent(self._ip, sent)

    def __init__(
        self, parser: Fast_Parser, toklist: Iterable[Tok], verbose: bool = False
    ) -> None:
        self._parser = parser
        self._reducer = Reducer(parser.grammar)
        self._num_sent = 0
        self._num_parsed_sent = 0
        self._num_tokens = 0
        self._num_combinations = 0
        self._total_score = 0
        self._total_ambig = 0.0
        self._total_tokens = 0
        self._start_time = self._last_time = time.time()
        self._verbose = verbose
        self._toklist = list(toklist)

    def _add_sentence(
        self, s: "IncrementalParser._IncrementalSentence", num: int
    ) -> None:
        """Add a processed sentence to the statistics"""
        slen = len(s)
        self._num_sent += 1
        self._num_tokens += slen
        if num > 0:
            # The sentence was parsed successfully
            self._num_parsed_sent += 1
            self._num_combinations += num
            ambig_factor = num ** (1 / slen)
            self._total_ambig += ambig_factor * slen
            self._total_tokens += slen
            self._total_score += s.score
        # Debugging output, if requested and enabled
        if self._verbose and Settings.DEBUG:
            current_time = time.time()
            print(
                "Parsed sentence of length {0} with {1} combinations{3} "
                "in {4:.1f} seconds{2}".format(
                    slen,
                    num,
                    ("\n" + s.text) if num >= _VERBOSE_AMBIGUITY_THRESHOLD else "",
                    " and score " + str(s.score) if num >= 1 else "",
                    current_time - self._last_time,
                )
            )
            self._last_time = current_time

    def paragraphs(self) -> Iterator["IncrementalParser._IncrementalParagraph"]:
        """Yield the paragraphs from the token stream"""
        Para = IncrementalParser._IncrementalParagraph
        for p in paragraphs(self._toklist):
            yield Para(self, p)

    @property
    def num_tokens(self) -> int:
        return self._num_tokens

    @property
    def num_sentences(self) -> int:
        return self._num_sent

    @property
    def num_parsed(self) -> int:
        return self._num_parsed_sent

    @property
    def num_combinations(self) -> int:
        return self._num_combinations

    @property
    def total_score(self) -> int:
        return self._total_score

    @property
    def ambiguity(self) -> float:
        return (
            (self._total_ambig / self._total_tokens) if self._total_tokens > 0 else 1.0
        )

    @property
    def parse_time(self) -> float:
        return time.time() - self._start_time

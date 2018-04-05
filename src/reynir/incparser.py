"""

    Reynir: Natural language processing for Icelandic

    Utility class for incremental parsing of token streams

    Copyright (c) 2017 Vilhjalmur Thorsteinsson

       This program is free software: you can redistribute it and/or modify
       it under the terms of the GNU General Public License as published by
       the Free Software Foundation, either version 3 of the License, or
       (at your option) any later version.
       This program is distributed in the hope that it will be useful,
       but WITHOUT ANY WARRANTY; without even the implied warranty of
       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
       GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see http://www.gnu.org/licenses/.


    This module implements a simple utility class for parsing token
    streams into paragraphs and sentences. The parse is incremental so
    that the client can take action on each paragraph and sentence as
    it is processed.

"""

import time
from collections import defaultdict

from tokenizer import TOK, paragraphs

if not __package__:
    from fastparser import Fast_Parser, ParseError
    from reducer import Reducer
    from settings import Settings
else:
    from .fastparser import Fast_Parser, ParseError
    from .reducer import Reducer
    from .settings import Settings

# Number of tree combinations that must be exceeded for a verbose
# parse dump to include the sentence text (as opposed to just basic stats)
_VERBOSE_AMBIGUITY_THRESHOLD = 1000


class IncrementalParser:

    """ Utility class to parse a token list as a sequence of paragraphs
        containing sentences. Typical usage:

        toklist = tokenize(text)
        bp = BIN_Parser()
        ip = IncrementalParser(bp, toklist)
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

        def __init__(self, ip, s):
            self._ip = ip
            self._s = s
            self._len = len(s)
            assert self._len > 0 # Input should be already sanitized
            self._err_index = None
            self._tree = None

        def __len__(self):
            return self._len

        def parse(self):
            """ Parse the sentence """
            num = 0
            score = 0
            try:
                forest = self._ip._parser.go(self._s)
                if forest is not None:
                    num = Fast_Parser.num_combinations(forest)
                    if num > 1:
                        forest, score = self._ip._reducer.go_with_score(forest)
            except ParseError as e:
                forest = None
                self._err_index = e.token_index
            self._tree = forest
            self._ip._add_sentence(self, num, score)
            return num > 0

        @property
        def tokens(self):
            return self._s

        @property
        def tree(self):
            return self._tree

        @property
        def err_index(self):
            return self._len - 1 if self._err_index is None else self._err_index

        @property
        def text(self):
            return " ".join(t.txt for t in self._s)

        def __str__(self):
            return self.text


    class _IncrementalParagraph:

        def __init__(self, ip, p):
            self._ip = ip
            self._p = p

        def sentences(self):
            """ Yield the sentences within the paragraph, nicely wrapped """
            for _, sent in self._p:
                yield IncrementalParser._IncrementalSentence(self._ip, sent)


    def __init__(self, parser, toklist, verbose = False):
        self._parser = parser
        self._reducer = Reducer(parser.grammar)
        self._num_sent = 0
        self._num_parsed_sent = 0
        self._num_tokens = 0
        self._num_combinations = 0
        self._total_score = 0
        self._total_ambig = 0.0
        self._total_tokens = 0
        self._start_time = time.time()
        self._verbose = verbose
        self._toklist = toklist
        
        # Count distinct tokens
        #self._toklist = list(toklist)
        #print("Article has {0} tokens".format(len(self._toklist)))
        #tokencount = defaultdict(int)
        #for t in self._toklist:
        #    tokencount[(t.kind, t.txt)] += 1
        #print("Article has {0} distinct tokens".format(len(tokencount)))
        #for t in sorted(tokencount.items(), key = lambda x : x[1], reverse = True)[0:20]:
        #    print("Token '{0}' ({1}) occurs {2} times".format(t[0][1], TOK.descr[t[0][0]], t[1]))

    def _add_sentence(self, s, num, score):
        """ Add a processed sentence to the statistics """
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
            self._total_score += score
        # Debugging output, if requested and enabled
        if self._verbose and Settings.DEBUG:
            print("Parsed sentence of length {0} with {1} combinations{2}"
                .format(slen, num,
                    ("\n" + s.text) if num >= _VERBOSE_AMBIGUITY_THRESHOLD else ""))

    def paragraphs(self):
        """ Yield the paragraphs from the token stream """
        for p in paragraphs(self._toklist):
            yield IncrementalParser._IncrementalParagraph(self, p)

    @property
    def num_tokens(self):
        return self._num_tokens

    @property
    def num_sentences(self):
        return self._num_sent

    @property
    def num_parsed(self):
        return self._num_parsed_sent

    @property
    def num_combinations(self):
        return self._num_combinations

    @property
    def total_score(self):
        return self._total_score

    @property
    def ambiguity(self):
        return (self._total_ambig / self._total_tokens) if self._total_tokens > 0 else 1.0

    @property
    def parse_time(self):
        return time.time() - self._start_time


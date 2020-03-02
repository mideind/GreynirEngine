"""

    Greynir: Natural language processing for Icelandic

    High-level wrapper for the Greynir tokenizer, parser and reducer

    Copyright (c) 2020 Miðeind ehf.
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
    along with this program.  If not, see http://www.gnu.org/licenses/.


    This module implements a high-level interface to the Greynir
    tokenizer, parser and reducer for parsing Icelandic text into
    trees.

"""

import time
import operator
from threading import Lock
from collections import namedtuple

from tokenizer import correct_spaces, paragraphs, mark_paragraphs

from .bintokenizer import tokenize as bin_tokenize
from .fastparser import Fast_Parser, ParseError
from .reducer import Reducer
from .cache import cached_property
from .matcher import SimpleTree


# The Sentence.terminals attribute returns a list of Terminal objects

Terminal = namedtuple(
    "Terminal",
    ("text", "lemma", "category", "variants", "index")
)


class _Sentence:

    """ A container for a sentence that has been extracted from the
        tokenizer. The sentence can be explicitly parsed by calling
        sentence.parse(). After parsing, a number of query functions
        are available on the parse tree. """

    def __init__(self, job, s):
        self._job = job
        # s is a token list
        self._s = s
        self._len = len(s)
        assert self._len > 0  # Input should be already sanitized
        self._err_index = None
        self._tree = self._simplified_tree = None
        self._num = None  # Number of possible combinations
        self._score = None  # Score of best parse tree
        self._terminals = None  # Cached terminals
        if self._job.parse_immediately:
            # We want an immediate parse of the sentence
            self.parse()

    def __len__(self):
        """ Return the number of tokens in the sentence """
        return self._len

    def parse(self):
        """ Parse the sentence """
        if self._num is not None:
            # Already parsed
            return self._num > 0
        job = self._job
        num = 0
        score = 0
        tree = None
        try:
            # Invoke the parser on the sentence tokens
            tree, num, score = job.parse(self._s)
        except ParseError as e:
            self._err_index = self._len - 1 if e.token_index is None else e.token_index
        self._tree = tree
        if tree is None:
            self._simplified_tree = None
        else:
            # Create a simplified tree as well
            self._simplified_tree = SimpleTree.from_deep_tree(tree, self._s)
        self._num = num
        self._score = score
        return num > 0

    @property
    def err_index(self):
        """ Return the index of the error token, if an error occurred;
            otherwise None """
        return self._err_index

    @property
    def tokens(self):
        """ Return the tokens in the sentence """
        return self._s

    @property
    def combinations(self):
        """ Return the number of different parse tree combinations for the sentence,
            or 0 if no parse tree was found, or None if the sentence hasn't been parsed """
        return self._num

    @property
    def score(self):
        """ The score of the best parse tree for the sentence """
        return self._score

    @property
    def tree(self):
        """ Return the simplified parse tree, or None if the sentence hasn't been parsed """
        return self._simplified_tree

    @property
    def deep_tree(self):
        """ Return the original deep tree, as constructed by the parser, corresponding
            directly to grammar nonterminals and terminals """
        return self._tree

    @property
    def flat_tree(self):
        """ Return a flat text representation of the simplified parse tree """
        return None if self.tree is None else self.tree.flat

    @cached_property
    def text(self):
        """ Return a raw text representation of the sentence,
            with spaces between all tokens """
        return " ".join(t.txt for t in self._s if t.txt)

    @property
    def tidy_text(self):
        """ Return a [more] correctly spaced text representation of the sentence """
        if self.tree is None:
            # Not parsed (yet)
            txt = self.text
        else:
            # Use the terminal text representation - it's got fancy em/en-dashes and stuff
            txt = " ".join(t.text for t in self.terminals)
        return correct_spaces(txt)

    @property
    def terminals(self):
        """ Return a list of tuples, one for each terminal in the sentence.
            The tuples contain the original text of the token that matched
            the terminal, the associated word lemma, the category, and a set
            of variants (case, number, gender, etc.) """
        if self.tree is None:
            # Must parse the sentence first, without errors
            return None
        if self._terminals is not None:
            # Already calculated and cached
            return self._terminals
        # Generate the terminal list from the parse tree
        self._terminals = [
            Terminal(d.text, d.lemma, d.tcat, d.all_variants, d.index)
            for d in self.terminal_nodes
        ]
        return self._terminals

    @cached_property
    def terminal_nodes(self):
        """ Return a list of the terminal nodes within the parse tree
            for this sentence """
        if self.tree is None:
            return None
        return [d for d in self.tree.descendants if d.is_terminal]

    @property
    def lemmas(self):
        """ Convenience property to return the lemmas only """
        t = self.terminals
        return None if t is None else [terminal[1] for terminal in t]

    @property
    def ifd_tags(self):
        """ Return a list of Icelandic Frequency Dictionary (IFD) tags for
            the terminals/tokens in this sentence. """
        if self.tree is None:
            return None
        # Flatten the ifd_tags lists for the individual nodes
        # (nonterminal nodes return an empty list in the ifd_tags property)
        return [ifd_tag for d in self.tree.descendants for ifd_tag in d.ifd_tags]

    def __str__(self):
        return self.text


class _NounPhrase(_Sentence):

    """ A specialization for parsed noun phrases,
        providing easy access to inflectional forms """

    _nom = operator.attrgetter('nominative_np')
    _acc = operator.attrgetter('accusative_np')
    _dat = operator.attrgetter('dative_np')
    _gen = operator.attrgetter('genitive_np')
    _ind = operator.attrgetter('indefinite_np')
    _can = operator.attrgetter('canonical_np')

    def _get(self, getter):
        if self.tree is None:
            return None
        return correct_spaces(getter(self.tree))

    @cached_property
    def nominative(self):
        """ Return nominative form (nefnifall) """
        return self._get(self._nom)

    @cached_property
    def indefinite(self):
        """ Return indefinite form (nefnifall án greinis) """
        return self._get(self._ind)

    @cached_property
    def canonical(self):
        """ Return canonical form (nefnifall eintölu án greinis) """
        return self._get(self._can)

    @cached_property
    def accusative(self):
        """ Return accusative form (þolfall) """
        return self._get(self._acc)

    @cached_property
    def dative(self):
        """ Return dative form (þágufall) """
        return self._get(self._dat)

    @cached_property
    def genitive(self):
        """ Return genitive form (eignarfall) """
        return self._get(self._gen)


class _Paragraph:

    """ Encapsulates a paragraph that contains sentences """

    def __init__(self, job, p):
        self._job = job
        self._p = p

    def sentences(self):
        """ Yield the sentences within the paragraph, nicely wrapped """
        # self._p is a generator that yields (ix, toklist) tuples,
        # where ix is a starting index of the sentence within the
        # token stream, and toklist is the list of tokens in the sentence,
        # not including S_BEGIN and S_END tokens.
        for _, sent in self._p:
            yield self._job._create_sentence(sent)

    def __iter__(self):
        """ Allow easy iteration of sentences within this paragraph """
        return iter(self.sentences())


class _Job:

    """ A parsing job object, allowing incremental parsing of text
        by paragraph and/or sentence.
    """

    def __init__(
        self, greynir, tokens, *,
        parse=False, root=None, progress_func=None
    ):
        self._r = greynir
        self._parser = self._r.parser
        self._reducer = self._r.reducer
        self._tokens = tokens
        self._parse_time = 0.0
        self._reduce_time = 0.0
        self._parse = parse
        # Pre-counted number of sentences (used for progress monitoring)
        self._cnt_sent = 0
        # Accumulated number of sentences generated so far
        self._num_sent = 0
        self._num_parsed = 0
        self._num_tokens = 0
        self._num_combinations = 0
        self._total_ambig = 0.0
        self._total_tokens = 0
        # The grammar root nonterminal to be used
        # for parsing within this job
        self._root = root
        # A progress function to call during processing
        self._progress_func = progress_func

    def _add_sentence(self, s, num, parse_time, reduce_time):
        """ Add a processed sentence to the statistics """
        slen = len(s)
        self._num_sent += 1
        self._num_tokens += slen
        if num > 0:
            # The sentence was parsed successfully
            self._num_parsed += 1
            self._num_combinations += num
            ambig_factor = num ** (1 / slen)
            self._total_ambig += ambig_factor * slen
            self._total_tokens += slen
        # Accumulate the total time spent on parsing and reduction
        self._parse_time += parse_time
        # Accumulate the time thereof spent on reduction
        self._reduce_time += reduce_time
        # Call the progress function, if any
        if self._progress_func is not None:
            assert self._cnt_sent > 0
            assert self._num_sent <= self._cnt_sent
            self._progress_func(self._num_sent / self._cnt_sent)

    def _create_sentence(self, s):
        """ Create a fresh _Sentence object """
        return self._r.create_sentence(self, s)

    @property
    def parse_immediately(self):
        """ Return True if sentences in the job should be parsed immediately """
        return self._parse

    def paragraphs(self):
        """ Yield the paragraphs from the token stream """
        if self._progress_func is not None:
            # We have a progress function, so we must pre-count
            # the sentences to be processed. This means that all input
            # data must be converted to lists, exhausting generators.
            # Note that the paragraph splitting phase applies the
            # token-level corrections, so they are not really
            # counted in the progress.
            plist = [
                [(ix, list(sent)) for ix, sent in p]
                for p in paragraphs(self._tokens)
            ]
            self._cnt_sent = sum(len(p) for p in plist)
        else:
            # No progress function: use generators throughout
            plist = paragraphs(self._tokens)
        for p in plist:
            yield _Paragraph(self, p)

    def sentences(self):
        """ Yield the sentences from the token stream """
        for p in self.paragraphs():
            yield from p.sentences()

    def parse(self, tokens):
        """ Parse the token sequence, returning a parse tree,
            the number of trees in the parse forest, and the
            score of the best tree """
        num = 0
        score = 0
        t0 = t1 = time.time()
        try:
            forest = self.parser.go(tokens, root=self._root)  # May raise ParseError
            t1 = time.time()
            if forest is not None:
                num = Fast_Parser.num_combinations(forest)
                if num > 1:
                    # Reduce the parse forest to a single
                    # "best" (highest-scoring) parse tree
                    forest, score = self.reducer.go_with_score(forest)
            return forest, num, score
        finally:
            # Accumulate statistics in the job object
            now = time.time()
            self._add_sentence(tokens, num, parse_time=now - t0, reduce_time=now - t1)

    def __iter__(self):
        """ Allow easy iteration of sentences within this job """
        return iter(self.sentences())

    @property
    def parser(self):
        """ The job's associated parser object """
        return self._parser

    @property
    def reducer(self):
        """ The job's associated reducer object """
        return self._reducer

    @property
    def num_tokens(self):
        """ Total number of tokens in sentences submitted to this job """
        return self._num_tokens

    @property
    def num_sentences(self):
        """ Total number of sentences submitted to this job """
        return self._num_sent

    @property
    def num_parsed(self):
        """ Total number of sentences successfully parsed within this job """
        return self._num_parsed

    @property
    def num_combinations(self):
        """ Sum of the total number of parse tree combinations for sentences within this job """
        return self._num_combinations

    @property
    def ambiguity(self):
        """ The weighted average total ambiguity of parsed sentences within this job """
        return (
            (self._total_ambig / self._total_tokens) if self._total_tokens > 0 else 1.0
        )

    @property
    def parse_time(self):
        """ Total time spent on parsing (including reduction) during this job,
            in seconds """
        return self._parse_time

    @property
    def reduce_time(self):
        """ Total time spent on tree reduction during this job, in seconds """
        return self._reduce_time


class _Job_NP(_Job):

    """ Specialized _Job class that creates _NounPhrase objects
        instead of _Sentence objects """

    def __init__(self, greynir, tokens):
        # Parse the tokens with 'Nl' (noun phrase) as the root nonterminal
        # instead of the usual default 'S0' (sentence) root
        super().__init__(greynir, tokens, parse=True, root="Nl")

    def _create_sentence(self, s):
        """ Create a fresh _NounPhrase object """
        return _NounPhrase(self, s)


class Greynir:

    """ Utility class to tokenize and parse text, organized
        as a sequence of sentences or alternatively as paragraphs
        of sentences. Typical usage:

        g = Greynir()
        job = g.submit(my_text)
        # Iterate through sentences and parse each one:
        for sent in job:
            if sent.parse():
                # sentence parsed successfully
                # do something with sent.tree
                print(sent.tree)
            else:
                # an error occurred in the parse
                # the error token index is at sent.err_index
                pass
        # Alternatively, split into paragraphs first:
        job = g.submit(my_text)
        for p in job.paragraphs(): # Yields paragraphs
            for sent in p.sentences(): # Yields sentences
                if sent.parse():
                    # sentence parsed successfully
                    # do something with sent.tree
                    print(sent.tree)
                else:
                    # an error occurred in the parse
                    # the error token index is at sent.err_index
                    pass
        # After parsing all sentences in a job, the following
        # statistics are available:
        num_sentences = job.num_sentences   # Total number of sentences
        num_parsed = job.num_parsed         # Thereof successfully parsed
        ambiguity = job.ambiguity           # Average ambiguity factor
        parse_time = job.parse_time         # Elapsed time since job was created

    """

    _parser = None
    _reducer = None
    _lock = Lock()

    def __init__(self, **options):
        """ Tokenization options can be passed as keyword arguments to the
            Greynir constructor """
        self._options = options

    def tokenize(self, text):
        """ Call the tokenizer (overridable in derived classes) """
        return bin_tokenize(text, **self._options)

    def create_sentence(self, job, s):
        """ Override this in derived classes to modify how sentences
            are created or postprocessed """
        return _Sentence(job, s)

    @property
    def parser(self):
        """ Return the parser instance to be used """
        with self._lock:
            if Greynir._parser is None:
                # Initialize a singleton instance of the parser and the reducer.
                # Both classes are re-entrant and thread safe.
                Greynir._parser = Fast_Parser()
                Greynir._reducer = Reducer(Greynir._parser.grammar)
            return Greynir._parser

    @property
    def reducer(self):
        """ Return the reducer instance to be used """
        # Should always retrieve the parser attribute first
        assert Greynir._reducer is not None
        return Greynir._reducer

    def submit(
        self, text, parse=False, *,
        split_paragraphs=False,
        progress_func=None
    ):
        """ Submit a text to the tokenizer and parser, yielding a job object.
            The paragraphs and sentences of the text can then be iterated
            through via the job object. If parse is set to True, the
            sentences are automatically parsed before being returned.
            Otherwise, they need to be explicitly parsed by calling
            sent.parse(). This is a more incremental, asynchronous
            approach than Greynir.parse().
            
            If progress_func is given, it will be called during processing
            with a single float parameter between 0.0..1.0 indicating the
            ratio of progress so far with the parsing job. """

        if split_paragraphs:
            # Original text consists of paragraphs separated by newlines:
            # insert paragraph separators before tokenization
            text = mark_paragraphs(text)
        tokens = self.tokenize(text)
        return _Job(self, tokens, parse=parse, progress_func=progress_func)

    def parse(self, text, *, progress_func=None):
        """ Convenience function to parse text synchronously and return
            a summary of all contained sentences. The progress_func parameter
            works as described for Greynir.submit(). """
        tokens = self.tokenize(text)
        job = _Job(self, tokens, parse=True, progress_func=progress_func)
        # Iterating through the sentences in the job causes
        # them to be parsed and their statistics collected
        sentences = [sent for sent in job]
        return dict(
            sentences=sentences,
            num_sentences=job.num_sentences,
            num_parsed=job.num_parsed,
            num_tokens=job.num_tokens,
            ambiguity=job.ambiguity,
            parse_time=job.parse_time,
            reduce_time=job.reduce_time,
        )

    def parse_single(self, sentence):
        """ Convenience function to parse a single sentence only """
        tokens = self.tokenize(sentence)
        job = _Job(self, tokens, parse=True)
        # Raises StopIteration if no sentence was parsed
        return next(iter(job))

    def parse_noun_phrase(self, noun_phrase):
        """ Convenience function to parse a noun phrase """
        tokens = self.tokenize(noun_phrase)
        # Use a _Job_NP to generate _NounPhrase objects instead of _Sentence objects
        job = _Job_NP(self, tokens)
        # Raises StopIteration if no sentence was parsed
        return next(iter(job))

    @classmethod
    def cleanup(cls):
        """ Discard memory resources held by the Greynir class object """
        cls._reducer = None
        if cls._parser is not None:
            Fast_Parser.discard_grammar()
            cls._parser.cleanup()
            cls._parser = None


# Allow old class name for compatibility
Reynir = Greynir

"""

    Greynir: Natural language processing for Icelandic

    Copyright (C) 2021 Miðeind ehf.

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

    This module contains a function to (simplistically) lemmatize text without 
    parsing.

"""

from typing import Iterable, Union, Callable, Tuple, List, Optional

from .bintokenizer import tokenize, TOK, Tok, TokenIterator


def simple_lemmatize(
    sent: str, multiple: bool = False, sort: Callable = None
) -> Iterable[Union[Tuple, List, None]]:
    """Simplistically lemmatize words in a given string, returning an iterable
    of (lemma, category) tuples. The default behaviour is to return the
    first lemma provided by bintokenizer. If multiple lemmas are requested
    via arg flag, a list of potential (lemma, cat) tuples is returned.
    Optionally, a sort function can be provided to determine the ordering of
    potential lemmas."""

    # Look up and yield lemmas for each token in text
    # Should this yield "lemmas" for non-word tokens such as
    # numbers, dates, URLs, etc.?
    for t in tokenize(sent):
        y: Optional[Union[Tuple, List]] = None
        if t.kind == TOK.WORD:
            if t.val:
                # Known word
                y = [(v.stofn, v.ordfl) for v in t.val]
            else:
                # Unknown word: assume it's an entity
                y = [(t.txt, "entity")]
        elif t.kind == TOK.PERSON:
            assert t.val
            # Person name w. gender
            y = [(t.val[0][0], "person_" + t.val[0][1])]
        elif t.kind == TOK.ENTITY or t.kind == TOK.COMPANY:
            # Entity or company name
            y = [(t.txt, "entity")]
        # We're returning a lemma for this token
        if y is not None:
            y = list(set(y))  # Remove duplicates
            if sort:
                y = sorted(y, key=sort)
            if not multiple:
                y = y[0]  # Naively return first lemma
            yield y

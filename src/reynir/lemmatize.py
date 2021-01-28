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

from typing import Iterable, Union, Callable, Tuple

from .bintokenizer import tokenize, TOK, Tok


def simple_lemmatize(
    sent: str, multiple: bool = False, sort: Callable = None
) -> Iterable:
    # Tokenize
    return _lemmatize(tokenize(sent))


def _lemmatize(
    sent: Iterable[Tok], multiple: bool = False, sort: Callable = None
) -> Iterable[Tuple]:
    """ Simplistically lemmatize a list of tokens, returning an iterable of
    (lemma, category) tuples. The default behaviour is to return the
    first lemma provided by bintokenizer. If multiple lemmas are requested, 
    returns full list of potential lemmas. A sort function can be provided
    to determine the ordering of multiple lemmas. """
    for t in sent:
        #print(t)
        if t.kind == TOK.WORD:
            if t.val:
                # Known word
                yield (t.val[0].stofn, t.val[0].ordfl)
            else:
                # Unknown word: assume it's an entity
                yield (t.txt, "entity")
        elif t.kind == TOK.PERSON:
            assert t.val
            # Name, gender
            yield (t.val[0][0], "person_" + t.val[0][1])
        elif t.kind == TOK.ENTITY or t.kind == TOK.COMPANY:
            # Entity or company name
            yield (t.txt, "entity")


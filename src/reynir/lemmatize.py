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

    This module contains a function to (simplistically) lemmatize text
    without parsing it.

"""

from typing import Optional, Union, Callable, Tuple, List, Iterator, TypeVar, Protocol

from abc import abstractmethod
from collections import OrderedDict

from .bintokenizer import tokenize, TOK


class Comparable(Protocol):

    """ Protocol for annotating comparable types """

    @abstractmethod
    def __lt__(self: "CT", other: "CT") -> bool:
        ...


CT = TypeVar("CT", bound=Comparable)

LemmaTuple = Tuple[str, str]  # Lemma, category (ordfl)


def simple_lemmatize(
    txt: str,
    *,
    all_lemmas: bool = False,
    sortkey: Callable[[LemmaTuple], Comparable] = None,
) -> Union[Iterator[LemmaTuple], Iterator[List[LemmaTuple]]]:
    """ Simplistically lemmatize a list of tokens, returning a generator of
        (lemma, category) tuples. The default behaviour is to return the
        first lemma provided by bintokenizer. If all_lemmas are requested,
        returns full list of potential lemmas. A sort function can be provided
        to determine the ordering of that list. """
    for t in tokenize(txt):
        y: Optional[List[LemmaTuple]] = None
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
        if y:
            # We're returning a lemma for this token
            # Remove duplicates while preserving order
            y = list(OrderedDict.fromkeys(y))
            if sortkey is not None:
                y.sort(key=sortkey)
            if all_lemmas:
                yield y
            else:
                yield y[0]  # Naively return first lemma

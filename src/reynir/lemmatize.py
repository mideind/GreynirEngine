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

from typing import Optional, Union, Callable, Tuple, List, Iterator, TypeVar, cast

from abc import abstractmethod, ABCMeta
from collections import OrderedDict

from .bindb import BIN_Tuple
from .bintokenizer import tokenize, TOK


# In Python >= 3.8, the base class could be typing.Protocol
class Comparable(metaclass=ABCMeta):

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
    sortkey: Optional[Callable[[LemmaTuple], Comparable]] = None,
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
                if "-" in t.txt:
                    # The original word already contains a hyphen: leave'em in
                    y = [(v.stofn, v.ordfl) for v in cast(List[BIN_Tuple], t.val)]
                else:
                    # The original word doesn't contain a hyphen: any hyphens
                    # in the lemmas must come from the compounding algorithm
                    y = [(v.stofn.replace("-", ""), v.ordfl) for v in cast(List[BIN_Tuple], t.val)]
            else:
                # Unknown word: assume it's an entity
                y = [(t.txt, "entity")]
        elif t.kind == TOK.PERSON:
            assert t.person_names
            # Person name w. gender
            person_name = t.person_names[0]
            y = [(person_name.name, "person_" + (person_name.gender or "hk"))]
        elif t.kind == TOK.ENTITY or t.kind == TOK.COMPANY:
            # Entity or company name
            y = [(t.txt, "entity")]
        if y is not None:
            # OK, we're returning one or more lemmas for this token
            # Remove duplicates while preserving order
            y = list(OrderedDict.fromkeys(y))
            if sortkey is not None:
                y.sort(key=sortkey)
            if all_lemmas:
                yield y
            else:
                yield y[0]  # Naively return first lemma

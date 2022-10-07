"""

    Greynir: Natural language processing for Icelandic

    Copyright (C) 2021 Miðeind ehf.
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

    This module exposes the Greynir API, i.e. the identifiers that are
    directly accessible via the reynir module object after importing it.

"""

# Expose the Greynir API

from .reynir import (
    Greynir,
    Reynir,
    Terminal,
    LemmaTuple,
    ProgressFunc,
    ParseResult,
    Sentence,
    Paragraph,
    ICELANDIC_RATIO,
)

# Import the following _underscored classes to be able to use them
# in type signatures in derived classes
from .reynir import (
    _Job,
    _Sentence,
    _Paragraph,
)
from .nounphrase import NounPhrase
from .fastparser import ParseForestPrinter, ParseForestDumper, ParseForestFlattener
from .fastparser import ParseError, ParseForestNavigator
from .settings import Settings
from .bintokenizer import tokenize, TokenList
from .version import __version__

# Expose the tokenizer API

from tokenizer import (
    TOK,
    Tok,
    paragraphs,
    correct_spaces,
    mark_paragraphs,
    TP_LEFT,
    TP_CENTER,
    TP_RIGHT,
    TP_NONE,
    TP_WORD,
    KLUDGY_ORDINALS_PASS_THROUGH,
    KLUDGY_ORDINALS_MODIFY,
    KLUDGY_ORDINALS_TRANSLATE,
)
from tokenizer.abbrev import Abbreviations

__author__ = "Miðeind ehf."
__copyright__ = "(C) 2021 Miðeind ehf."

__all__ = (
    "TP_LEFT",
    "TP_RIGHT",
    "TP_CENTER",
    "TP_NONE",
    "TP_WORD",
    "KLUDGY_ORDINALS_MODIFY",
    "KLUDGY_ORDINALS_PASS_THROUGH",
    "KLUDGY_ORDINALS_TRANSLATE",
    "Greynir",
    "Reynir",
    "Terminal",
    "LemmaTuple",
    "ProgressFunc",
    "ParseResult",
    "Sentence",
    "Paragraph",
    "ICELANDIC_RATIO",
    "TOK",
    "Tok",
    "paragraphs",
    "correct_spaces",
    "mark_paragraphs",
    "_Job",
    "_Sentence",
    "_Paragraph",
    "NounPhrase",
    "ParseForestPrinter",
    "ParseForestDumper",
    "ParseForestFlattener",
    "ParseError",
    "ParseForestNavigator",
    "Settings",
    "tokenize",
    "TokenList",
    "__version__",
    "__author__",
    "__copyright__",
)

Abbreviations.initialize()
Settings.read("config/GreynirPackage.conf")

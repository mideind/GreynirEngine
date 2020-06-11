"""

    Greynir: Natural language processing for Icelandic

    Copyright (C) 2020 Miðeind ehf.
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
    along with this program.  If not, see <https://www.gnu.org/licenses/>.

    This module exposes the Greynir API, i.e. the identifiers that are
    directly accessible via the reynir module object after importing it.

"""

# Expose the Greynir API

from .reynir import Greynir, Reynir, Terminal
# Import the following _underscored classes to be able to use them
# in type signatures in derived classes
from .reynir import _Job, _Sentence, _Paragraph, ProgressFunc, ParseResult
from .nounphrase import NounPhrase
from .fastparser import ParseForestPrinter, ParseForestDumper, ParseForestFlattener
from .fastparser import ParseError, ParseForestNavigator
from .settings import Settings
from .bintokenizer import tokenize
from .version import __version__

# Expose the tokenizer API

from tokenizer import TOK, Tok, correct_spaces, mark_paragraphs, Abbreviations
from tokenizer import (
    TP_LEFT, TP_CENTER, TP_RIGHT, TP_NONE, TP_WORD,
    KLUDGY_ORDINALS_PASS_THROUGH,
    KLUDGY_ORDINALS_MODIFY,
    KLUDGY_ORDINALS_TRANSLATE
)

__author__ = "Miðeind ehf."
__copyright__ = "(C) 2020 Miðeind ehf."

Abbreviations.initialize()
Settings.read("config/ReynirPackage.conf")


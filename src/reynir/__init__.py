"""

    Reynir: Natural language processing for Icelandic

    Copyright(C) 2018 Miðeind ehf.
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

"""

# Expose the reynir API

from .reynir import Reynir, Terminal
from .fastparser import ParseForestPrinter, ParseForestDumper, ParseForestFlattener
from .fastparser import ParseError, ParseForestNavigator
from .settings import Settings

# Expose the tokenizer API

from tokenizer import TOK, Tok, tokenize, correct_spaces
from tokenizer import TP_LEFT, TP_CENTER, TP_RIGHT, TP_NONE, TP_WORD
from tokenizer import Abbreviations

__author__ = u"Vilhjálmur Þorsteinsson"

Abbreviations.initialize()
Settings.read("config/ReynirPackage.conf")


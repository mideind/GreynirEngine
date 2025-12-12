[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9](https://img.shields.io/badge/python-3.9-blue.svg)](https://www.python.org/downloads/release/python-3817/)
![Release](https://shields.io/github/v/release/mideind/GreynirEngine?display_name=tag)
![PyPI](https://img.shields.io/pypi/v/reynir)
[![Build](https://github.com/mideind/GreynirEngine/actions/workflows/python-package.yml/badge.svg)]()

<img src="https://raw.githubusercontent.com/mideind/GreynirEngine/master/doc/_static/greynir-logo-large.png" alt="Greynir" width="200" height="200" align="right" style="margin-left:20px; margin-bottom: 20px;">

# GreynirEngine

**A fast, efficient natural language processing engine for Icelandic**

## Overview

Greynir is a Python 3 (>=3.9) package,
published by [Miðeind ehf.](https://mideind.is), for
**working with Icelandic natural language text**.
Greynir can parse text into **sentence trees**, find **lemmas**,
inflect **noun phrases**, assign **part-of-speech tags** and much more.

Greynir's sentence trees can *inter alia* be used to extract
information from text, for instance about people, titles, entities, facts,
actions and opinions.

Full documentation for Greynir is [available here](https://greynir.is/doc/).

Greynir is the engine of [Greynir.is](https://greynir.is),
a natural-language front end for a database of over 10 million
sentences parsed from Icelandic news articles, and
[Embla](https://embla.is), a voice-driven virtual assistant app
for smart devices such as iOS and Android phones.

Greynir includes a hand-written
[context-free grammar](https://github.com/mideind/GreynirEngine/blob/master/src/reynir/Greynir.grammar)
for the Icelandic language, consisting of over 7,000 lines of grammatical
productions in [extended Backus-Naur format](https://en.wikipedia.org/wiki/Extended_Backus%E2%80%93Naur_form).
Its fast C++ parser core is able to cope with long and ambiguous sentences,
using an [Earley-type parser](https://en.wikipedia.org/wiki/Earley_parser)
as [enhanced by Scott and Johnstone](https://www.sciencedirect.com/science/article/pii/S0167642309000951).

Greynir employs the [Tokenizer](https://pypi.org/project/tokenizer/) package,
by the same authors, to tokenize text, and
uses [BinPackage](https://pypi.org/project/islenska/) as its database of
Icelandic vocabulary and morphology.

## Examples

### Use Greynir to easily inflect noun phrases

````python
from reynir import NounPhrase as Nl

# Create a NounPhrase ('nafnliður') object
karfa = Nl("þrír lúxus-miðar á Star Wars og tveir brimsaltir pokar af poppi")

# Print the NounPhrase in the correct case for each context
# (þf=þolfall/accusative, þgf=þágufall/dative). Note that
# the NounPhrase class implements __format__(), allowing you
# to use the case as a format specification, for instance in f-strings.

print(f"Þú keyptir {karfa:þf}.")
print(f"Hér er kvittunin þín fyrir {karfa:þgf}.")
````

The program outputs the following text, correctly inflected:

````text
Þú keyptir þrjá lúxus-miða á Star Wars og tvo brimsalta poka af poppi.
Hér er kvittunin þín fyrir þremur lúxus-miðum á Star Wars og tveimur brimsöltum pokum af poppi.
````

### Use Greynir to parse a sentence

````python
>>> from reynir import Greynir
>>> g = Greynir()
>>> sent = g.parse_single("Ása sá sól.")
>>> print(sent.tree.view)
P                               # Root
+-S-MAIN                        # Main sentence
    +-IP                          # Inflected phrase
    +-NP-SUBJ                   # Noun phrase, subject
        +-no_et_nf_kvk: 'Ása'     # Noun, singular, nominative, feminine
    +-VP                        # Verb phrase containing arguments
        +-VP                      # Verb phrase containing verb
        +-so_1_þf_et_p3: 'sá'   # Verb, 1 accusative arg, singular, 3rd p
        +-NP-OBJ                  # Noun phrase, object
        +-no_et_þf_kvk: 'sól'   # Noun, singular, accusative, feminine
+-'.'                           # Punctuation
>>> sent.tree.nouns
['Ása', 'sól']
>>> sent.tree.verbs
['sjá']
>>> sent.tree.flat
'P S-MAIN IP NP-SUBJ no_et_nf_kvk /NP-SUBJ VP so_1_þf_et_p3
    NP-OBJ no_et_þf_kvk /NP-OBJ /VP /IP /S-MAIN p /P'
>>> # The subject noun phrase (S.IP.NP also works)
>>> sent.tree.S.IP.NP_SUBJ.lemmas
['Ása']
>>> # The verb phrase
>>> sent.tree.S.IP.VP.lemmas
['sjá', 'sól']
>>> # The object within the verb phrase (S.IP.VP.NP also works)
>>> sent.tree.S.IP.VP.NP_OBJ.lemmas
['sól']
````

## Prerequisites

This package runs on CPython 3.9 or newer, and on PyPy 3.9 or newer.

To find out which version of Python you have, enter:

````sh
python --version
````

If a binary wheel package isn't available on [PyPI](https://pypi.org>)
for your system, you may need to have the `python3-dev` package
(or its Windows equivalent) installed on your
system to set up Greynir successfully. This is
because a source distribution install requires a C++ compiler and linker:

````sh
# Debian or Ubuntu
sudo apt-get install python3-dev
````

Depending on your system, you may also need to install `libffi-dev`:

````sh
# Debian or Ubuntu
sudo apt-get install libffi-dev
````

## Installation

To install this package, assuming Python 3 is your default Python:

````sh
pip install reynir
````

If you have **git** installed and want to be able to edit
the source, do like so:

````sh
git clone https://github.com/mideind/GreynirEngine
cd GreynirEngine
# [ Activate your virtualenv here if you have one ]
pip install -e .
````

The package source code is in `GreynirEngine/src/reynir`.

## Tests

To run the built-in tests, install [pytest](https://docs.pytest.org/en/latest),
`cd` to your `GreynirEngine` subdirectory (and optionally activate your
virtualenv), then run:

````sh
python -m pytest
````

## Evaluation

A parsing test pipeline for different parsing schemas, including the Greynir schema,
has been developed. It is available [here](https://github.com/mideind/ParsingTestPipe).

## Documentation

Please consult [Greynir's documentation](https://greynir.is/doc/) for detailed
[installation instructions](https://greynir.is/doc/installation.html),
a [quickstart guide](https://greynir.is/doc/quickstart.html),
and [reference information](https://greynir.is/doc/reference.html),
as well as important information about
[copyright and licensing](https://greynir.is/doc/copyright.html).

## Troubleshooting

If parsing seems to hang, it is possible that a lock file that GreynirEngine
uses has been left locked. This can happen if a Python process that uses
GreynirEngine is killed abruptly. The solution is to delete the lock file
and try again:

On Linux and macOS:

````sh
rm /tmp/greynir-grammar  # May require sudo privileges
````

On Windows:

````cmd
del %TEMP%\greynir-grammar
````

## Copyright and licensing

Greynir is Copyright © 2016-2025 by [Miðeind ehf.](https://mideind.is).
The original author of this software is *Vilhjálmur Þorsteinsson*.

<a href="https://mideind.is"><img src="https://raw.githubusercontent.com/mideind/GreynirEngine/master/doc/_static/mideind-horizontal-small.png" alt="Miðeind ehf."
    width="214" height="66" align="right" style="margin-left:20px; margin-bottom: 20px;"></a>

This software is licensed under the **MIT License**:

*Permission is hereby granted, free of charge, to any person*
*obtaining a copy of this software and associated documentation*
*files (the "Software"), to deal in the Software without restriction,*
*including without limitation the rights to use, copy, modify, merge,*
*publish, distribute, sublicense, and/or sell copies of the Software,*
*and to permit persons to whom the Software is furnished to do so,*
*subject to the following conditions:*

**The above copyright notice and this permission notice shall be**
**included in all copies or substantial portions of the Software.**

*THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,*
*EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF*
*MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.*
*IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY*
*CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,*
*TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE*
*SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.*

If you would like to use this software in ways that are incompatible
with the standard MIT license, [contact Miðeind ehf.](mailto:mideind@mideind.is)
to negotiate custom arrangements.

----

GreynirEngine indirectly embeds the [Database of Icelandic Morphology](https://bin.arnastofnun.is),
([Beygingarlýsing íslensks nútímamáls](https://bin.arnastofnun.is)), abbreviated BÍN.
GreynirEngine does not claim any endorsement by the BÍN authors or copyright holders.

The BÍN source data are publicly available under the
[CC BY-SA 4.0 license](https://creativecommons.org/licenses/by-sa/4.0/), as further
detailed [here in English](https://bin.arnastofnun.is/DMII/LTdata/conditions/)
and [here in Icelandic](https://bin.arnastofnun.is/gogn/mimisbrunnur/).

In accordance with the BÍN license terms, credit is hereby given as follows:

*Beygingarlýsing íslensks nútímamáls. Stofnun Árna Magnússonar í íslenskum fræðum.*
*Höfundur og ritstjóri Kristín Bjarnadóttir.*

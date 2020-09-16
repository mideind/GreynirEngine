
.. image:: https://github.com/mideind/ReynirPackage/blob/master/doc/_static/GreynirLogo220.png?raw=true

==========================================================
A fast, efficient natural language processor for Icelandic
==========================================================

.. image:: https://travis-ci.com/mideind/ReynirPackage.svg?branch=master
    :target: https://travis-ci.com/mideind/ReynirPackage

********
Overview
********

Greynir is a Python 3 (>= 3.6) package for
**working with Icelandic natural language text**.
Greynir can parse text into **sentence trees**, find **lemmas**,
inflect **noun phrases**, assign **part-of-speech tags** and much more.

Greynir's sentence trees can *inter alia* be used to extract
information from text, for instance about people, titles, entities, facts,
actions and opinions.

Full documentation for Greynir is `available here <https://greynir.is/doc/>`__.

Greynir is the engine of `Greynir.is <https://greynir.is>`_, a natural-language
front end for a database of over 10 million sentences parsed from Icelandic
news articles, and `Embla <https://embla.is>`_, a voice-driven virtual assistant app
for smart devices such as iOS and Android phones.

Greynir uses the `Tokenizer <https://pypi.org/project/tokenizer/>`_ package,
by the same authors, to tokenize text.

********
Examples
********

Use Greynir to easily inflect noun phrases:
-------------------------------------------

.. code-block:: python

    from reynir import NounPhrase as Nl

    # Create a NounPhrase ('nafnliður') object
    nl = Nl("þrír lúxus-miðar á Star Wars og tveir brimsaltir pokar af poppi")

    # Print the NounPhrase in the correct case for each context
    # (þf=þolfall/accusative, þgf=þágufall/dative)

    print("Þú keyptir {nl:þf}.".format(nl=nl))
    print("Hér er kvittunin þín fyrir {nl:þgf}.".format(nl=nl))

The program outputs the following text, correctly inflected::

    Þú keyptir þrjá lúxus-miða á Star Wars og tvo brimsalta poka af poppi.
    Hér er kvittunin þín fyrir þremur lúxus-miðum á Star Wars og tveimur brimsöltum pokum af poppi.

Use Greynir to parse a sentence:
--------------------------------

.. code-block:: python

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

*************
Prerequisites
*************

This package runs on CPython 3.6 or newer, and on PyPy 3.6 or newer.

To find out which version of Python you have, enter::

    $ python --version

If a binary wheel package isn't available on `PyPi <https://pypi.org>`__
for your system, you may need to have the ``python3-dev`` package
(or its Windows equivalent) installed on your
system to set up Greynir successfully. This is
because a source distribution install requires a C++ compiler and linker::

    $ # Debian or Ubuntu:
    $ sudo apt-get install python3-dev

Depending on your system, you may also need to install ``libffi-dev``::

    $ # Debian or Ubuntu
    $ sudo apt-get install libffi-dev

************
Installation
************

To install this package, assuming Python 3 is your default Python::

    $ pip install reynir

If you have **git** and **git-lfs** installed and want to be able to edit
the source, do like so::

    $ git clone https://github.com/mideind/ReynirPackage
    $ cd ReynirPackage
    $ # [ Activate your virtualenv here if you have one ]
    $ git lfs install
    $ git pull
    $ pip install -e .

The package source code is now in ``ReynirPackage/src/reynir``.

Note that **git-lfs** is required to clone and pull the full compressed binary
files for the *Beygingarlýsing íslensks nútímamáls* (BÍN) database. If it is
missing, you will get assertion errors when you try to run Greynir.

*****
Tests
*****

To run the built-in tests, install `pytest <https://docs.pytest.org/en/latest/>`__,
``cd`` to your ``ReynirPackage`` subdirectory (and optionally activate your
virtualenv), then run::

    $ python -m pytest

*************
Documentation
*************

Please consult `Greynir's documentation <https://greynir.is/doc/>`__ for detailed
`installation instructions <https://greynir.is/doc/installation.html>`_,
a `quickstart guide <https://greynir.is/doc/quickstart.html>`_,
and `reference information <https://greynir.is/doc/reference.html>`_,
as well as important information
about `copyright and licensing <https://greynir.is/doc/copyright.html>`__.

***********************
Copyright and licensing
***********************

Greynir is *copyright © 2020 by Miðeind ehf.*
The original author of this software is *Vilhjálmur Þorsteinsson*.

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

.. image:: https://github.com/mideind/ReynirPackage/blob/master/doc/_static/MideindLogoVert100.png?raw=true
   :align: right
   :alt: Miðeind ehf.

If you would like to use this software in ways that are incompatible
with the standard MIT license, `contact Miðeind ehf. <mailto:mideind@mideind.is>`__
to negotiate custom arrangements.

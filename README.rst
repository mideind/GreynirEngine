===============================================================
Reynir: A fast, efficient natural language parser for Icelandic
===============================================================

.. image:: https://github.com/mideind/ReynirPackage/blob/master/doc/_static/ReynirLogo216.png

.. image:: https://travis-ci.com/mideind/ReynirPackage.svg?branch=master
    :target: https://travis-ci.com/mideind/ReynirPackage

********
Overview
********

**Reynir** is a Python 3.x package for
**parsing Icelandic text into sentence trees** (i.e. full constituency parse trees).
The trees can then be used to extract information from the text, for instance
about people, titles, entities, facts, actions and opinions.

Along the way, Reynir tokenizes the text, finds **lemmas** and assigns
**part-of-speech (POS) tags** to every word.

Full documentation for Reynir is `available here <https://greynir.is/doc/>`_.

Reynir is the engine of `Greynir.is <https://greynir.is>`_, a natural-language
front end for a database of 8 million sentences parsed from Icelandic
news articles.

Reynir uses the `Tokenizer <https://pypi.org/project/tokenizer/>`_ package,
by the same authors, to tokenize text.

*******
Example
*******

>>> from reynir import Reynir
>>> r = Reynir()
>>> sent = r.parse_single("Ása sá sól.")
>>> print(sent.tree.view)
P                               # Root
+-S-MAIN                        # Main sentence
  +-IP                          # Inflected phrase
    +-NP-SUBJ                   # Noun phrase, subject
      +-no_et_nf_kvk: 'Ása'     # Noun, singular, nominative, feminine
    +-VP                        # Verb phrase containing arguments
      +-VP                      # Verb phrase containing verb
        +-so_1_þf_et_p3: 'sá'   # Verb, 1 accusative arg, singular, 3rd p
      +-NP-OBJ                # Noun phrase, object
        +-no_et_þf_kvk: 'sól' # Noun, singular, accusative, feminine
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

This package runs on CPython 3.4 or newer, and on PyPy 3.5 or newer.

If a binary wheel package isn't available on `PyPi <https://pypi.org>`_
for your system, you may need to have the ``python3-dev`` and/or potentially
``python3.6-dev`` packages (or their Windows equivalents) installed on your
system to set up Reynir successfully. This is because a source distribution
install requires a C++ compiler and linker::

    # Debian or Ubuntu:
    sudo apt-get install python3-dev
    sudo apt-get install python3.6-dev

************
Installation
************

To install this package::

    $ pip3 install reynir   # or pip install reynir if Python3 is your default

If you want to be able to edit the source, do like so (assuming you have **git** installed)::

    $ git clone https://github.com/mideind/ReynirPackage
    $ cd ReynirPackage
    $ # [ Activate your virtualenv here if you have one ]
    $ python setup.py develop

The package source code is now in ``ReynirPackage/src/reynir``.

*****
Tests
*****

To run the built-in tests, install `pytest <https://docs.pytest.org/en/latest/>`_,
``cd`` to your ``ReynirPackage`` subdirectory (and optionally activate your
virtualenv), then run::

    $ python -m pytest

*************
Documentation
*************

Please consult `Reynir's documentation <https://greynir.is/doc/>`_ for detailed
`installation instructions <https://greynir.is/doc/installation.html>`_,
a `quickstart guide <https://greynir.is/doc/quickstart.html>`_,
and `reference information <https://greynir.is/doc/reference.html>`_,
as well as important information
about `copyright and licensing <https://greynir.is/doc/copyright.html>`_.


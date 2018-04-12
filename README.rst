===============================================================
Reynir: A fast, efficient natural language parser for Icelandic
===============================================================

********
Overview
********

**Reynir** parses sentences of Icelandic text into **parse trees**.
A parse tree recursively describes the grammatical structure
of the sentence, including its noun phrases, verb phrases,
prepositional phrases, etc.

The individual tokens (words and punctuation) of the sentence
correspond to leaves in the parse tree.

By examining and processing the parse tree, information and meaning
can be extracted from the sentence.

*******
Example
*******

>>> from reynir import Reynir
>>> r = Reynir()
>>> job = r.submit("Ása sá sól.")
>>> sent = next(job.sentences())
>>> sent.parse()
True
>>> sent.tree.nouns
['Ása', 'sól']
>>> sent.tree.verbs
['sjá']
>>> sent.tree.flat
'P S-MAIN IP NP-SUBJ no_et_nf_kvk /NP-SUBJ VP so_1_þf_et_p3 NP-OBJ no_et_þf_kvk /NP-OBJ /VP /IP /S-MAIN p /P'
>>> sent.tree.S.IP.NP_SUBJ.lemmas # The subject noun phrase (S.IP.NP also works)
['Ása']
>>> sent.tree.S.IP.VP.lemmas # The verb phrase
['sjá', 'sól']
>>> sent.tree.S.IP.VP.NP_OBJ.lemmas # The object within the verb phrase (S.IP.VP.NP also works)
['sól']

*************
Prerequisites
*************

This package runs on CPython 3.4 or newer, and on PyPy 3.5
or newer. PyPy is recommended for best performance.

You need to have ``python3-dev`` and/or potentially ``python3.6-dev`` installed on your system::

	# Debian or Ubuntu:
	sudo apt-get install python3-dev
	sudo apt-get install python3.6-dev

************
Installation
************

To install this package::

	pip3 install reynir

*************
Documentation
*************

Please consult `Reynir's documentation <https://greynir.is/doc/>`_ for more detailed
`installation instructions <https://greynir.is/doc/installation.html>`_,
a `quickstart guide <https://greynir.is/doc/quickstart.html>`_,
and `reference information <https://greynir.is/doc/reference.html>`_,
as well as important information
about `copyright and licensing <https://greynir.is/doc/copyright.html>`_.


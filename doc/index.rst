.. Reynir documentation master file, created by
   sphinx-quickstart on Sun Apr  8 01:20:08 2018.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.


Welcome to Reynir
=================

*Til að gagnast sem flestum er skjölun Reynis á ensku. - In order to serve
the widest possible audience, Reynir's documentation is in English.*

Reynir is a Python 3.x package for **parsing Icelandic text into sentence trees**.
The trees can then be used to extract information from the text, for instance
about contained nouns and noun phrases, person names, verbs, word stems, etc.

.. figure:: _static/GreynirTreeExampleSmall.png
   :align: center
   :alt: An example of a parse tree

   Reynir is the engine of `Greynir.is <https://greynir.is>`_

To get acquainted with Reynir, we recommend that you start with the :ref:`overview`,
proceed with the :ref:`installation` instructions, and then look at the :ref:`quickstart`.
For further reference, consult the :ref:`reference` section.

This documentation also contains :ref:`important information about copyright and licensing <copyright>`.

Batteries included
------------------

To start using Reynir with Python, you (usually) need :ref:`ony one command <installation>`::

   $ pip install reynir

**No database to set up, no further data to download.**
The entire `Database of Modern Icelandic Inflection <http://bin.arnastofnun.is/DMII/>`_
(`Beygingarlýsing íslensks nútímamáls <http://bin.arnastofnun.is>`_),
with over 6 million entries, is embedded within Reynir in compressed form.
By looking up word forms in this database, and applying over 16,000
grammar rules (productions), Reynir is able to infer what the most likely
word stems are, how they are inflected in the parsed text, and where they
fit in the overall sentence structure.

Reynir is thoroughly documented, and its source code is of course
`available on GitHub <https://github.com/vthorsteinsson/ReynirPackage>`_.

Enabling your application
-------------------------

Reynir can serve as an enabling component of applications such as:

   * Natural language query systems
   * Bots and conversational systems
   * Information extraction tools
   * Intelligent search tools
   * Grammatical pattern analysis
   * Text similarity
   * Author identification
   * Sentiment analysis
   * Content summarization
   * Content category labeling
   * Generation of training corpora for machine learning

About Reynir
------------

Reynir is a project and product of Miðeind ehf. of Reykjavík, Iceland. It is a free open source software
project (:ref:`GNU GPLv3 <copyright>`), started in mid-2015 by its original author, Vilhjálmur Þorsteinsson.
Its aim is to produce an **industrial-strength Natural Language Processing toolset for Icelandic**,
with the hope of supporting the language on the digital front in times of rapid advances in language
technology; changes that may leave low-resource languages at a disadvantage unless explicit action is
taken to strengthen their position.


.. toctree::
   :maxdepth: 1
   :hidden:

   overview
   installation
   quickstart
   reference
   patterns
   nonterminals
   copyright


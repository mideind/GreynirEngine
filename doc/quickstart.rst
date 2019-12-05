.. _quickstart:

Quickstart
==========

After :ref:`installing Greynir <installation>`, fire up your
Python 3 interpreter::

    $ python3

...and try something like the following::

    from reynir import Greynir

    my_text = "Litla gula hænan fann fræ. Það var hveitifræ."

    # Initialize Greynir and submit the text as a parse job
    g = Greynir()
    job = g.submit(my_text)

    # Iterate through sentences and parse each one
    for sent in job:
        sent.parse()
        print("Sentence: {0}".format(sent.tidy_text))
        print("Lemmas:   {0}".format(sent.lemmas))
        print("Parse tree:\n{0}\n".format(sent.tree.view))

The output of the program is as follows::

    Sentence: Litla gula hænan fann fræ.
    Lemmas:   ['lítill', 'gulur', 'hæna', 'finna', 'fræ', '.']
    Parse tree:
    S0
    +-S-MAIN
      +-IP
        +-NP-SUBJ
          +-lo_nf_et_kvk: 'Litla'
          +-lo_nf_et_kvk: 'gula'
          +-no_et_nf_kvk: 'hænan'
        +-VP
          +-VP
            +-so_1_þf_et_p3: 'fann'
          +-NP-OBJ
            +-no_et_þf_hk: 'fræ'
    +-'.'
    Sentence: Það var hveitifræ.
    Lemmas:   ['það', 'vera', 'hveitifræ', '.']
    Parse tree:
    S0
    +-S-MAIN
      +-IP
        +-NP-SUBJ
          +-pfn_hk_et_nf: 'Það'
        +-VP
          +-VP
            +-so_1_nf_et_p3: 'var'
          +-NP-PRD
            +-no_et_nf_hk: 'hveitifræ'
    +-'.'

The code first creates an instance of the :py:class:`Greynir` class
and assigns it to the ``g`` object. The :py:class:`Greynir` class is
Greynir's main service interface.

Next, the program submits a piece of text containing two sentences to
Greynir, which returns a job object. Each job object encapsulates a
stream of sentences that will be, or have been, processed through
Greynir's tokenizer and parser.

A job object is a Python generator, and the ``for`` loop iterates through
the job's sentence stream, returning each sentence in turn in the ``sent``
object.

The ``for`` loop body parses the sentence by calling ``sent.parse()``.
This function returns ``True`` if the sentence was successfully parsed, i.e.
at least one valid parse tree was found for it, or ``False`` otherwise.

The sentence object has a number of properties, including ``sent.tidy_text``
which returns a normalized form of the tokenized sentence.

If the sentence was successfully parsed, the ``sent.tree`` property
(of type :py:class:`SimpleTree`)
contains its best parse tree. This tree can be further queried via
properties such as ``sent.lemmas``, which returns a list of the
word lemmas in the sentence, and ``sent.tree.view``, which
returns a string with an "ASCII art" representation of the parse tree.

The parse tree contains grammar **nonterminals** in uppercase, such
as ``S0`` (root), ``S-MAIN`` (main sentence), ``IP`` (inflected
phrase - *beygingarliður*), ``NP-SUBJ`` (noun phrase - subject,
*frumlag*), ``VP`` (verb phrase - *sagnliður*), etc.

Nonterminals are listed and explained in the :ref:`nonterminals` section.

The tree also shows grammar **terminals** (leaves, corresponding to
tokens) in lowercase, as well as their :ref:`grammatical variants <variants>`
(features). Examples are ``pfn_hk_et_nf`` (personal pronoun,
neutral gender, singular, nominative case), and ``so_1_nf_et_p3``
(verb, one argument in nominative case, singular, 3rd person).

Terminals and variants are listed and explained in the :ref:`terminals`
section.

The sentence and tree properties and functions are further
detailed and described in the :ref:`reference` section.


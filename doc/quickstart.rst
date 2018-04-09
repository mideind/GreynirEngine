.. _quickstart:

Quickstart
==========

After :ref:`installing Reynir <installation>`, fire up your Python 3 interpreter::

    $ python3

...and try something like the following::

    from reynir import Reynir

    my_text = "Litla gula hænan átti fræ. Það var hveitifræ."

    # Initialize Reynir and submit the text as a parse job
    r = Reynir()
    job = r.submit(my_text)

    # Iterate through sentences and parse each one
    for sent in job:
        sent.parse()
        print("Sentence:   {0}".format(sent.tidy_text))
        print("Stems:      {0}".format(sent.stems))
        print("Parse tree: {0}".format(sent.tree.flat))

The output of the program is as follows (line breaks inserted)::

    Sentence:   Litla gula hænan átti fræ.
    Stems:      ['lítill', 'gulur', 'hæna', 'eiga', 'fræ', '.']
    Parse tree: P S-MAIN IP NP-SUBJ lo_nf_et_kvk lo_nf_et_kvk no_et_nf_kvk
        /NP-SUBJ VP so_1_þf_et_p3 NP-OBJ no_et_þf_hk /NP-OBJ /VP /IP
        /S-MAIN p /P
    Sentence:   Það var hveitifræ.
    Stems:      ['það', 'vera', 'hveitifræ', '.']
    Parse tree: P S-MAIN IP NP-SUBJ pfn_hk_et_nf /NP-SUBJ VP so_1_nf_et_p3
        NP-PRD no_et_nf_hk /NP-PRD /VP /IP /S-MAIN p /P

The code first creates an instance of the ``Reynir`` class and assigns
it to the ``r`` object. The ``Reynir`` class is Reynir's main service interface.
We recommend that you only create a single ``Reynir`` instance in your program,
since each initialization maps the entire Icelandic lexicon into
memory (about 60 megabytes).

Next, the program submits a piece of text containing two sentences to Reynir, which
returns a job object. Each job object encapsulates a stream of sentences that
will be, or have been, processed through Reynir's tokenizer and parser.

A job object is a Python generator, and the ``for`` loop iterates through
the job's sentence stream, returning each sentence in turn in the ``sent``
object.

The ``for`` loop body parses the sentence by calling ``sent.parse()``.
This function returns ``True`` if the sentence was successfully parsed, i.e.
at least one valid parse tree was found for it, or ``False`` otherwise.

The sentence object has a number of properties, including ``sent.tidy_text``
which returns a normalized form of the tokenized sentence.

If the sentence was successfully parsed, the ``sent.tree`` property
contains its best parse tree. This tree can be further queried via
properties such as ``sent.stems`` which returns a list of the
stems of the word in the sentence, and ``sent.tree.flat`` which
returns a string with a compact form of the parse tree.

The parse tree contains grammar **nonterminals** in uppercase, such
as ``P`` (paragraph), ``S-MAIN`` (main sentence), ``IP`` (inflected
phrase - *beygingarliður*), ``NP-SUBJ`` (noun phrase - subject,
*frumlag*), ``VP`` (verb phrase - *sagnliður*), etc. An open
nonterminal scope is closed by a forward slash ``/`` followed
by the nonterminal name. A verb phrase is thus enclosed by
``VP [...] /VP``.

The tree also shows grammar **terminals** (leaves, corresponding to
tokens) in lowercase. Examples are ``pfn_hk_et_nf`` (personal pronoun,
neutral gender, singular, nominative case), and ``so_1_nf_et_p3``
(verb, one argument in nominative case, singular, 3rd person).

The sentence and tree properties and functions are further
detailed and described in the :ref:`reference` section.

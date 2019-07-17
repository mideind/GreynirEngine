.. _reference:

Reference
=========

The following sections describe the available classes, methods
and properties of Reynir.

Separate sections describe grammar :ref:`nonterminals` and :ref:`terminals`.

The following classes are documented herein:

* The :py:class:`Reynir` class
* The :py:class:`_Job` class
* The :py:class:`_Paragraph` class
* The :py:class:`_Sentence` class
* The :py:class:`SimpleTree` class

Initializing Reynir
-------------------

After installing the ``reynir`` package (see :ref:`installation`),
use the following code to import it and initialize an instance of
the :py:class:`Reynir` class::

    from reynir import Reynir
    r = Reynir()

Now you can use the ``r`` instance to parse text, by calling
the :py:meth:`Reynir.submit()`, :py:meth:`Reynir.parse()` and/or
:py:meth:`Reynir.parse_single()` methods on it.

.. topic:: The Reynir instance

    It is recommended to initialize **only one instance** of the Reynir class for
    the duration of your program/process, since each instance needs to read
    its own configuration data. This includes the compressed
    *Database of Modern Icelandic Inflection (BÍN)* which occupies about 60 megabytes
    of memory. However, if you run Reynir in multiple processes, BÍN will
    -- under most operating systems -- only be mapped once into the
    computer's physical address space.

The Reynir class
----------------

.. py:class:: Reynir

    .. py:method:: __init__(self, **options)

        Initializes the :py:class:`Reynir` instance.

        Tokenizer options can be passed via keyword arguments, as in
        ``r = Reynir(convert_numbers=True)``. See the
        documentation for the `Tokenizer <https://github.com/mideind/Tokenizer>`_
        package for further information.

    .. py:method:: submit(self, text : string, parse : bool = False,
            *, split_paragraphs = False) -> _Job

        Submits a text string to Reynir for parsing and returns
        a :py:class:`_Job` object.

        :param str text: The text to parse. Can be a single sentence
            or multiple sentences.
        :param bool parse: Controls whether the text is parsed immediately or
            upon demand. Defaults to ``False``.
        :param bool split_paragraphs: Indicates that the text should be
            split into paragraps, with paragraph breaks at newline
            characters (``\n``). Defaults to ``False``.
        :return: A fresh :py:class:`_Job` object.

        The given text string is tokenized and split into paragraphs and sentences.
        If the ``parse`` parameter is ``True``, the sentences are parsed
        immediately, before returning from the method.
        Otherwise, parsing is incremental (on demand) and is invoked by
        calling :py:meth:`_Sentence.parse()` explicitly on each sentence.

        Returns a :py:class:`_Job` object which supports iteration through
        the paragraphs (via :py:meth:`_Job.paragraphs()`) and sentences
        (via :py:meth:`_Job.sentences()` or :py:meth:`_Job.__iter__()`) of
        the parse job.

    .. py:method:: parse(self, text : string) -> dict

        Parses a text string and returns a dictionary with the parse job results.

        :param str text: The text to parse. Can be a single sentence
            or multiple sentences.
        :return: A dictionary containing the parse results as well as statistics
            from the parse job.

        The given text string is tokenized and split into sentences. An internal parse
        job is created and the sentences are parsed. The resulting :py:class:`_Sentence`
        objects are returned in a list in the ``sentences`` field in the dictionary.
        The text is treated as one contiguous paragraph.

        The result dictionary contains the following items:

        * ``sentences``: A list of :py:class:`_Sentence` objects corresponding
            to the sentences found in the text. If a sentence could
            not be parsed, the corresponding object's
            ``tree`` property will be ``None``.

        * ``num_sentences``: The number of sentences found in the text.

        * ``num_parsed``: The number of sentences that were successfully parsed.

        * ``ambiguity``: A ``float`` weighted average of the ambiguity of the parsed
            sentences. Ambiguity is defined as the *n*-th root of the number
            of possible parse trees for the sentence, where *n* is the number
            of tokens in the sentence.

        * ``parse_time``: A ``float`` with the wall clock time, in seconds,
            spent on tokenizing and parsing the sentences.


        Example *(try it!)*::

            from reynir import Reynir
            r = Reynir()
            my_text = "Litla gula hænan fann fræ. Það var hveitifræ."
            d = r.parse(my_text)
            print("{0} sentences were parsed".format(d["num_parsed"]))
            for sent in d["sentences"]:
                print("The parse tree for '{0}' is:\n{1}"
                    .format(
                        sent.tidy_text,
                        "[Null]" if sent.tree is None else sent.tree.flat
                    )
                )


    .. py:method:: parse_single(self, sentence : string) -> _Sentence

        Parses a single sentence from a string and returns a corresponding
        :py:class:`_Sentence` object.

        :param str sentence: The single sentence to parse.
        :return: A :py:class:`_Sentence` object. Raises ``StopIteration`` if
            no sentence could be extracted from the string.

        The given sentence string is tokenized. An internal parse
        job is created and the first sentence found in the string is parsed.
        Paragraph markers are ignored.
        A single :py:class:`_Sentence` object is returned. If the sentence
        could not be parsed, :py:attr:`_Sentence.tree` is ``None`` and
        :py:attr:`_Sentence.combinations` is zero.

        Example::

            from reynir import Reynir
            r = Reynir()
            my_text = "Litla gula hænan fann fræ"
            sent = r.parse_single(my_text)
            if sent.tree is None:
                print("The sentence could not be parsed.")
            else:
                print("The parse tree for '{0}' is:\n{1}"
                    .format(sent.tidy_text, sent.tree.view))


        Output::

            The parse tree for 'Litla gula hænan fann fræ' is:
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


    .. py:classmethod:: cleanup(cls)

        Deallocates memory resources allocated by :py:meth:`__init__`.

        If your code has finished using Reynir and you want to free up the
        memory allocated for its resources, including the 60 megabytes for the
        *Database of Modern Icelandic Inflection (BÍN)*,
        call :py:meth:`Reynir.cleanup()`.

        After calling :py:meth:`Reynir.cleanup()` the functionality of Reynir is
        no longer available via existing instances of :py:class:`Reynir`.
        However, you can initialize new instances (via ``r = Reynir()``),
        causing the configuration to be re-read and memory to be allocated again.

The _Job class
----------------

Instances of this class are returned from :py:meth:`Reynir.submit()`.
You should not need to instantiate it yourself, hence the leading underscore
in the class name.

.. py:class:: _Job

    .. py:method:: paragraphs(self)

        Returns a generator of :py:class:`_Paragraph` objects, corresponding
        to paragraphs in the parsed text. Paragraphs are assumed to be delimited by
        ``[[`` and ``]]`` markers in the text, surrounded by whitespace.
        These markers are optional and not required. If they are not present,
        the text is assumed to be one contiguous paragraph.

        Example::

            from reynir import Reynir
            r = Reynir()
            my_text = ("[[ Þetta er fyrsta efnisgreinin. Hún er stutt. ]] "
                "[[ Hér er önnur efnisgreinin. Hún er líka stutt. ]]")
            j = r.submit(my_text)
            for pg in j.paragraphs():
                for sent in pg:
                    print(sent.tidy_text)
                print()


        Output::

            Þetta er fyrsta efnisgreinin.
            Hún er stutt.

            Hér er önnur efnisgreinin.
            Hún er líka stutt.


    .. py:method:: sentences(self)

        Returns a generator of :py:class:`_Sentence` objects. Each object
        corresponds to a sentence in the parsed text. If the sentence has
        already been successfully parsed, its :py:attr:`_Sentence.tree`
        property will contain its (best) parse tree. Otherwise, the property is
        ``None``.

    .. py:method:: __iter__(self)

        A shorthand for calling :py:meth:`_Job.sentences()`, supporting the
        Python iterator protocol. You can iterate through the sentences of
        a parse job via a ``for`` loop::

            for sent in job:
                sent.parse()
                # Do something with sent


    .. py:attribute:: num_sentences

        Returns an ``int`` with the accumulated number of sentences that have been
        submitted for parsing via this job.

    .. py:attribute:: num_parsed

        Returns an ``int`` with the accumulated number of sentences that have been
        sucessfully parsed via this job.

    .. py:attribute:: num_tokens

        Returns an ``int`` with the accumulated number of tokens in sentences that have
        been submitted for parsing via this job.

    .. py:attribute:: num_combinations

        Returns an ``int`` with the accumulated number of parse tree combinations for
        the sentences that have been successfully parsed via this job.

    .. py:attribute:: ambiguity

        Returns a ``float`` with the weighted average ambiguity factor of
        the sentences that
        have been successfully parsed via this job. The ambiguity factor
        of a sentence is defined as the *n*-th root of the total number
        of parse tree combination for the sentence, where *n* is the number
        of tokens in the sentence. The average across sentences is weighted
        by token count.

    .. py:attribute:: parse_time

        Returns a ``float`` with the accumulated wall clock time, in seconds,
        that has been spent parsing sentences via this job.

The _Paragraph class
--------------------

Instances of this class are returned from :py:meth:`_Job.paragraphs()`.
You should not need to instantiate it yourself,
hence the leading underscore in the class name.

.. py:class:: _Paragraph

    .. py:method:: sentences(self)

        Returns a generator of :py:class:`_Sentence` objects. Each object
        corresponds to a sentence within the paragraph in the parsed text.
        If the sentence has
        already been successfully parsed, its :py:attr:`_Sentence.tree`
        property will contain its (best) parse tree. Otherwise, the property is
        ``None``.

    .. py:method:: __iter__(self)

        A shorthand for calling :py:meth:`_Paragraph.sentences()`, supporting the
        Python iterator protocol. You can iterate through the sentences of
        a paragraph via a ``for`` loop::

            for pg in job.paragraphs():
                for sent in pg:
                    sent.parse()
                    # Do something with sent


The _Sentence class
-------------------

Instances of this class are returned from :py:meth:`_Job.sentences()` and
:py:meth:`_Job.__iter__()`. You should not need to instantiate it yourself,
hence the leading underscore in the class name.

.. py:class:: _Sentence

    .. py:method:: __len__(self) -> int

        Returns an ``int`` with the number of tokens in the sentence.

    .. py:attribute:: text

        Returns a ``str`` with the raw text representation of the sentence, with spaces
        between all tokens. For a more correctly formatted version of the text,
        use the :py:attr:`_Sentence.tidy_text` property instead.

        Example::

            from reynir import Reynir
            r = Reynir()
            s = r.parse_single("Jón - faðir Ásgeirs - átti 2/3 hluta "
                "af landinu árin 1944-1950.")
            print(s.text)


        Output (note the intervening spaces, also before the period at the end)::

            Jón - faðir Ásgeirs - átti 2/3 hluta af landinu árin 1944 - 1950 .


    .. py:method:: __str__(self) -> str

        Returns a ``str`` with the raw text representation of the sentence, with spaces
        between all tokens. For a more correctly formatted version of the text,
        use the :py:attr:`_Sentence.tidy_text` property instead.

    .. py:attribute:: tidy_text

        Returns a ``str`` with a text representation of the sentence, with
        correct spacing between tokens, and em- and en-dashes substituted for
        regular hyphens as appropriate.

        Example::

            from reynir import Reynir
            r = Reynir()
            s = r.parse_single("Jón - faðir Ásgeirs - átti 2/3 hluta "
                "af landinu árin 1944-1950.")
            print(s.tidy_text)


        Output (note the dashes and the period at the end)::

            Jón — faðir Ásgeirs — átti 2/3 hluta af landinu árin 1944–1950.


    .. py:attribute:: tokens

        Returns a ``list`` of tokens in the sentence. Each token is represented
        by a ``Tok`` ``namedtuple`` instance from the ``Tokenizer`` package.

        Example::

            from reynir import Reynir, TOK
            r = Reynir()
            s = r.parse_single("5. janúar sá Ása 5 sólir.")
            for t in s.tokens:
                print(TOK.descr[t.kind], t.txt)


        outputs::

            DATE 5. janúar
            WORD sá
            PERSON Ása
            NUMBER 5
            WORD sólir
            PUNCTUATION .


    .. py:method:: parse(self) -> bool

        Parses the sentence (unless it has already been parsed) and returns
        ``True`` if at least one parse tree was found, or ``False`` otherwise.
        For successfully parsed sentences, :py:attr:`_Sentence.tree` contains
        the best parse tree. Otherwise, :py:attr:`_Sentence.tree` is ``None``.
        If the parse is not successful, the 0-based index of the token where
        the parser gave up is stored in :py:attr:`_Sentence.err_index`.

    .. py:attribute:: err_index

        Returns an ``int`` with the 0-based index of the token where the
        parser could not find any grammar production to continue the parse,
        or ``None`` if the sentence has not been parsed yet or if no error
        occurred during the parse.

    .. py:attribute:: combinations

        Returns an ``int`` with the number of possible parse trees for the
        sentence, or ``0`` if no parse trees were found, or ``None`` if the
        sentence hasn't been parsed yet.

    .. py:attribute:: score

        Returns an ``int`` representing the score that the best parse tree
        got from the scoring heuristics of Reynir. The score is ``0`` if
        the sentence has not been successfully parsed.

    .. py:attribute:: tree

        Returns a :py:class:`SimpleTree` object representing the best
        (highest-scoring) parse tree for the sentence,
        in a *simplified form* that is easy to work with.

        If the sentence has not yet been parsed, or no parse tree was found
        for it, this property is ``None``.

    .. py:attribute:: deep_tree

        Returns the best (highest-scoring) parse tree for the sentence,
        in a *detailed form* corresponding directly to Reynir's context-free grammar
        for Icelandic.

        If the sentence has not yet been parsed, or no parse tree was found
        for it, this property is ``None``.

        Example::

            from reynir import Reynir
            r = Reynir()
            s = r.parse_single("Ása sá sól.")
            print(repr(s.deep_tree))


        Output:

        .. code-block:: none

            S0
              Málsgrein
                MgrInnihald
                  Yfirsetning
                    HreinYfirsetning
                      Setning
                        Setning_et_p3_kvk
                          BeygingarliðurÁnUmröðunar_et_p3_kvk
                            NlFrumlag_nf_et_p3_kvk
                              Nl_et_p3_nf_kvk
                                NlEind_et_p3_nf_kvk
                                  NlStak_et_p3_nf_kvk
                                    NlStak_p3_et_nf_kvk
                                      NlKjarni_et_nf_kvk
                                        Fyrirbæri_nf_kvk
                                          'Ása' -> no_et_nf_kvk
                            BeygingarliðurMegin_et_p3_kvk
                              SagnRuna_et_p3_kvk
                                SagnRunaKnöpp_et_p3_kvk
                                  Sagnliður_et_p3_kvk
                                    Sögn_1_et_p3_kvk
                                      'sá' -> so_1_þf_et_p3
                                      NlBeintAndlag_þf
                                        Nl_þf
                                          NlEind_et_p3_þf_kvk
                                            NlStak_et_p3_þf_kvk
                                              NlStak_p3_et_þf_kvk
                                                NlKjarni_et_þf_kvk
                                                  Fyrirbæri_þf_kvk
                                                    'sól' -> no_et_þf_kvk
                  Lokatákn?
                    Lokatákn
                      '.' -> "."


    .. py:attribute:: flat_tree

        Returns the best (highest-scoring) parse tree for the sentence,
        simplified and flattened to a text string. Nonterminal scopes are
        delimited like so: ``NAME ... /NAME`` where ``NAME`` is the name of
        the nonterminal, for example ``NP`` for noun phrases and ``VP`` for
        verb phrases. Terminals have lower-case identifiers with their
        various grammar variants separated by underscores, e.g.
        ``no_þf_kk_et`` for a noun, accusative case, masculine gender, singular.

        If the sentence has not yet been parsed, or no parse tree was found
        for it, this property is ``None``.

    .. py:attribute:: terminals

        Returns a ``list`` of the terminals in the best parse tree for the
        sentence, in the order in which they occur in the sentence (token order).
        Each terminal corresponds to a token in the sentence. The entry for each
        terminal is a ``namedtuple`` called ``Terminal``, having five fields:

        0. **text**: The token text.

        1. **lemma**: The lemma of the word, if the token is a word, otherwise
            it is the text of the token. Lemmas of composite words include hyphens
            ``-`` at the component boundaries. Examples: ``borgar-stjórnarmál``,
            ``skugga-kosning``.

        2. **category**: The word :ref:`category <categories>`
            (``no`` for noun, ``so`` for verb, etc.)

        3. **variants**: A list of the :ref:`grammatical variants <variants>` for
            the word or token, or an empty list if not applicable. The variants include
            the case (``nf``, ``þf``, ``þgf``, ``ef``), gender (``kvk``, ``kk``, ``hk``),
            person, verb form, adjective degree, etc. This list identical to the one returned
            from :py:attr:`SimpleTree.all_variants` for the terminal in question.

        4. **index**: The index of the token that corresponds to this terminal.
            The index is 0-based.

        If the sentence has not yet been parsed, or no parse tree was found
        for it, this property is ``None``.

        Example::

            from reynir import Reynir
            r = Reynir()
            s = r.parse_single("Þórgnýr fór út og fékk sér ís.")
            for t in s.terminals:
                print("{0:8s} {1:8s} {2:8s} {3}"
                    .format(t.text, t.lemma, t.category,
                        ", ".join(t.variants)))


        outputs:

        .. code-block:: none

            Þórgnýr  Þórgnýr  person   nf, kk
            fór      fara     so       0, et, fh, gm, p3, þt
            út       út       ao
            og       og       st
            fékk     fá       so       2, þgf, þf, et, fh, gm, p3, þt
            sér      sig      abfn     þgf
            ís       ís       no       et, kk, þf
            .        .


        (The line for *fékk* means that this is the verb (``so``) *fá*,
        having two arguments (``2``) in dative case (``þgf``) and
        accusative case (``þf``); it is singular (``et``), indicative (``fh``),
        active voice (``gm``), in the third person (``p3``),
        and in past tense (``þt``). See :ref:`variants` for a detailed explanation.)

    .. py:attribute:: lemmas

        Returns a ``list`` of the lemmas of the words in the sentence, or
        the text of the token for non-word tokens. ``sent.lemmas`` is a shorthand for
        ``[ t.lemma for t in sent.terminals ]``.

        Lemmas of composite words include hyphens ``-`` at the component boundaries.
        Examples: ``borgar-stjórnarmál``, ``skugga-kosning``.

        If the sentence has not yet been parsed, or no parse tree was found
        for it, this property is ``None``.

    .. py:attribute:: terminal_nodes

        Returns a ``list`` of the subtrees (:py:class:`SimpleTree` instances)
        that correspond to terminals in the parse tree for this
        sentence, in the order in which they occur (token order).

        If the sentence has not yet been parsed, or no parse tree was found
        for it, this property is ``None``.



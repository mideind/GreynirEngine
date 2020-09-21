.. _reference:

Reference
=========

The following sections describe the available classes, methods
and properties of Greynir.

Separate sections describe grammar :ref:`nonterminals` and :ref:`terminals`.

The following classes are documented herein:

* The :py:class:`Greynir` class
* The :py:class:`_Job` class
* The :py:class:`_Paragraph` class
* The :py:class:`_Sentence` class
* The :py:class:`NounPhrase` class
* The :py:class:`SimpleTree` class

Initializing Greynir
--------------------

After installing the ``reynir`` package (see :ref:`installation`),
use the following code to import it and initialize an instance of
the :py:class:`Greynir` class::

    from reynir import Greynir
    g = Greynir()

Now you can use the ``g`` instance to parse text, by calling
the :py:meth:`Greynir.submit()`, :py:meth:`Greynir.parse()` and/or
:py:meth:`Greynir.parse_single()` methods on it. To tokenize
text without parsing it, you can call :py:meth:`Greynir.tokenize()`.

If you are only going to be using the :py:class:`NounPhrase` class,
you don't need to initialize a :py:class:`Greynir` instance.

.. topic:: The Greynir instance

    It is recommended to initialize **only one instance** of the Greynir class for
    the duration of your program/process, since each instance needs to read
    its own configuration data. This includes the compressed
    *Database of Modern Icelandic Inflection (BÍN)* which occupies about 60 megabytes
    of memory. However, if you run Greynir in multiple processes, BÍN will
    -- under most operating systems -- only be mapped once into the
    computer's physical address space.

The Greynir class
-----------------

.. py:class:: Greynir

    .. py:method:: __init__(self, **options)

        :param options: Tokenizer options can be passed via keyword arguments,
            as in ``g = Greynir(convert_numbers=True)``. See the documentation
            for the `Tokenizer <https://github.com/mideind/Tokenizer>`__
            package for further information.

            Additionally, if the parameter ``parse_foreign_sentences=True``
            is given, the parser will attempt to parse
            all sentences, even those that seem to be in a foreign language.
            The default is not to try to parse sentences where >= 50% of
            the tokens are not found in DMII/BÍN.

        Initializes the :py:class:`Greynir` instance.

    .. py:method:: tokenize(self, text: StringIterable) -> Iterable[Tok]

        :param StringIterable text: A string or an iterable of strings, containing
            the text to tokenize.

        :return: A generator of `tokenizer.Tok <https://github.com/mideind/Tokenizer>`__
            instances.

        Tokenizes a string or an iterable of strings, returning a generator
        of `tokenizer.Tok <https://github.com/mideind/Tokenizer>`__
        instances. The returned tokens include a ``val`` attribute populated
        with word meanings, lemmas and inflection paradigms from DMII/BÍN,
        or, in the case of person names, information about gender and case.

        The tokenizer options given in the class constructor are automatically
        passed to the tokenizer.

    .. py:method:: parse_single( \
        self, sentence: str, *, \
        max_sent_tokens: int=90 \
        ) -> Optional[_Sentence]

        :param str sentence: The single sentence to parse.

        :param int max_sent_tokens: If given, this specifies the maximum number
            of tokens that a sentence may contain for Greynir to attempt to parse it.
            The default is 90 tokens. In practice, sentences longer than this are
            expensive to parse in terms of memory use and processor time.
            This parameter can be used to make Greynir more brave in its parsing
            attempts, by specifying a higher number than 90. Setting it to ``None``
            or zero disables the length limit. Note that the default may be
            increased from 90 in future versions of Greynir.

        :return: A :py:class:`_Sentence` object, or ``None`` if
            no sentence could be extracted from the string.

        Parses a single sentence from a string and returns a corresponding
        :py:class:`_Sentence` object.

        The given sentence string is tokenized. An internal parse
        job is created and the first sentence found in the string is parsed.
        Paragraph markers are ignored.

        A single :py:class:`_Sentence` object is returned. If the sentence
        could not be parsed, :py:attr:`_Sentence.tree` is ``None`` and
        :py:attr:`_Sentence.combinations` is zero.

        Example::

            from reynir import Greynir
            g = Greynir()
            my_text = "Litla gula hænan fann fræ"
            sent = g.parse_single(my_text)
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


    .. py:method:: parse_tokens( \
        self, tokens: Iterable[Tok], *, \
        max_sent_tokens: int=90 \
        ) -> Optional[_Sentence]

        :param Iterable[Tok] tokens: An iterable of tokens to parse.

        :param int max_sent_tokens: A maximum number of tokens to attempt
            to parse. For longer sentences, an empty :py:class:`_Sentence`
            object is returned, i.e. one where the ``tree`` attribute is ``None``.

        :return: A :py:class:`_Sentence` object, or ``None`` if
            no sentence could be extracted from the token iterable.

        Parses a single sentence from an iterable of tokens,
        and returns a corresponding :py:class:`_Sentence` object. Except
        for the input parameter type, the functionality is identical to
        :py:meth:`parse_single`.

    .. py:method:: submit( \
        self, text: str, parse: bool=False, *, \
        split_paragraphs: bool=False, \
        progress_func: Callable[[float], None]=None, \
        max_sent_tokens: int=90 \
        ) -> _Job

        Submits a text string to Greynir for parsing and returns
        a :py:class:`_Job` object.

        :param str text: The text to parse. Can be a single sentence
            or multiple sentences.

        :param bool parse: Controls whether the text is parsed immediately or
            upon demand. Defaults to ``False``.

        :param bool split_paragraphs: Indicates that the text should be
            split into paragraps, with paragraph breaks at newline
            characters (``\n``). Defaults to ``False``.

        :param Callable[[float],None] progress_func: If given, this function will be called
            periodically during the parse job. The call will have a single
            ``float`` parameter, ranging from ``0.0`` at the beginning of the parse
            job, to ``1.0`` at the end. Defaults to ``None``.

        :param int max_sent_tokens: If given, this specifies the maximum number of
            tokens that a sentence may contain for Greynir to attempt to parse it.
            The default is 90 tokens. In practice, sentences longer than this are
            expensive to parse in terms of memory use and processor time.
            This parameter can be used to make Greynir more brave in its parsing
            attempts, by specifying a higher number than 90. Setting it to ``None``
            or zero disables the length limit. Note that the default may be
            increased from 90 in future versions of Greynir.

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


    .. py:method:: parse( \
        self, text: str, *, \
        progress_func: Callable[[float], None] = None, \
        max_sent_tokens: int=90 \
        ) -> dict

        Parses a text string and returns a dictionary with the parse job results.

        :param str text: The text to parse. Can be a single sentence
            or multiple sentences.

        :param Callable[[float],None] progress_func: If given, this function will be called
            periodically during the parse job. The call will have a single
            ``float`` parameter, ranging from ``0.0`` at the beginning of the parse
            job, to ``1.0`` at the end. Defaults to ``None``.

        :param int max_sent_tokens: If given, this specifies the maximum number
            of tokens that a sentence may contain for Greynir to attempt to parse it.
            The default is 90 tokens. In practice, sentences longer than this are
            expensive to parse in terms of memory use and processor time.
            This parameter can be used to make Greynir more brave in its parsing
            attempts, by specifying a higher number than 90. Setting it to ``None``
            or zero disables the length limit. Note that the default may be
            increased from 90 in future versions of Greynir.

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

            from reynir import Greynir
            g = Greynir()
            my_text = "Litla gula hænan fann fræ. Það var hveitifræ."
            d = g.parse(my_text)
            print("{0} sentences were parsed".format(d["num_parsed"]))
            for sent in d["sentences"]:
                print("The parse tree for '{0}' is:\n{1}"
                    .format(
                        sent.tidy_text,
                        "[Null]" if sent.tree is None else sent.tree.flat
                    )
                )

    .. py:method:: dumps_single(self, sent: _Sentence, **kwargs) -> str

        :param _Sentence sent: The :py:class:`_Sentence` object to dump
            in JSON format.

        :param kwargs: Optional keyword parameters to be passed to the
            standard library's ``json.dumps()`` function.

        :return: A JSON string.

        Dumps a :py:class:`_Sentence` object to a JSON string. Use
        :py:meth:`Greynir.loads_single()` to re-create a
        :py:class:`_Sentence` instance from a JSON string.

    .. py:method:: loads_single(self, json_str: str, **kwargs) -> _Sentence

        :param str json_str: The JSON string to load back into a :py:class:`_Sentence`
            object.

        :param kwargs: Optional keyword parameters to be passed to the
            standard library's ``json.loads()`` function.

        :return: A :py:class:`_Sentence` object constructed from the JSON string.

        Constructs a :py:class:`_Sentence` instance from a JSON string.

    .. py:classmethod:: cleanup(cls)

        Deallocates memory resources allocated by :py:meth:`__init__`.

        If your code has finished using Greynir and you want to free up the
        memory allocated for its resources, including the 60 megabytes for the
        *Database of Modern Icelandic Inflection (BÍN)*,
        call :py:meth:`Greynir.cleanup()`.

        After calling :py:meth:`Greynir.cleanup()` the functionality of Greynir is
        no longer available via existing instances of :py:class:`Greynir`.
        However, you can initialize new instances (via ``g = Greynir()``),
        causing the configuration to be re-read and memory to be allocated again.


The _Job class
----------------

Instances of this class are returned from :py:meth:`Greynir.submit()`.
You should not need to instantiate it yourself, hence the leading underscore
in the class name.

.. py:class:: _Job

    .. py:method:: paragraphs(self) -> Iterable[_Paragraph]

        Returns a generator of :py:class:`_Paragraph` objects, corresponding
        to paragraphs in the parsed text. Paragraphs are assumed to be delimited by
        ``[[`` and ``]]`` markers in the text, surrounded by whitespace.
        These markers are optional and not required. If they are not present,
        the text is assumed to be one contiguous paragraph.

        Example::

            from reynir import Greynir
            g = Greynir()
            my_text = ("[[ Þetta er fyrsta efnisgreinin. Hún er stutt. ]] "
                "[[ Hér er önnur efnisgreinin. Hún er líka stutt. ]]")
            j = g.submit(my_text)
            for pg in j.paragraphs():
                for sent in pg:
                    print(sent.tidy_text)
                print()


        Output::

            Þetta er fyrsta efnisgreinin.
            Hún er stutt.

            Hér er önnur efnisgreinin.
            Hún er líka stutt.


    .. py:method:: sentences(self) -> Iterable[_Sentence]

        Returns a generator of :py:class:`_Sentence` objects. Each object
        corresponds to a sentence in the parsed text. If the sentence has
        already been successfully parsed, its :py:attr:`_Sentence.tree`
        property will contain its (best) parse tree. Otherwise, the property is
        ``None``.

    .. py:method:: __iter__(self) -> Iterable[_Sentence]

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

    .. py:method:: sentences(self) -> Iterable[_Sentence]

        Returns a generator of :py:class:`_Sentence` objects. Each object
        corresponds to a sentence within the paragraph in the parsed text.
        If the sentence has
        already been successfully parsed, its :py:attr:`_Sentence.tree`
        property will contain its (best) parse tree. Otherwise, the property is
        ``None``.

    .. py:method:: __iter__(self) -> Iterable[_Sentence]

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

            from reynir import Greynir
            g = Greynir()
            s = g.parse_single("Jón - faðir Ásgeirs - átti 2/3 hluta "
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

            from reynir import Greynir
            g = Greynir()
            s = g.parse_single("Jón - faðir Ásgeirs - átti 2/3 hluta "
                "af landinu árin 1944-1950.")
            print(s.tidy_text)


        Output (note the dashes and the period at the end)::

            Jón — faðir Ásgeirs — átti 2/3 hluta af landinu árin 1944–1950.


    .. py:attribute:: tokens

        Returns a ``list`` of tokens in the sentence. Each token is represented
        by a ``Tok`` ``namedtuple`` instance from the ``Tokenizer`` package.

        Example::

            from reynir import Greynir, TOK
            g = Greynir()
            s = g.parse_single("5. janúar sá Ása 5 sólir.")
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

    .. py:attribute:: error

        Returns a ``ParseError`` instance if an error was found during the
        parsing of the sentence, or ``None`` otherwise. ``ParseError`` is
        an exception class, derived from ``Exception``. It can be converted
        to ``str`` to obtain a human-readable error message.

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
        got from the scoring heuristics of Greynir. The score is ``0`` if
        the sentence has not been successfully parsed.

    .. py:attribute:: tree

        Returns a :py:class:`SimpleTree` object representing the best
        (highest-scoring) parse tree for the sentence,
        in a *simplified form* that is easy to work with.

        If the sentence has not yet been parsed, or no parse tree was found
        for it, this property is ``None``.

    .. py:attribute:: deep_tree

        Returns the best (highest-scoring) parse tree for the sentence,
        in a *detailed form* corresponding directly to Greynir's context-free grammar
        for Icelandic.

        If the sentence has not yet been parsed, or no parse tree was found
        for it, this property is ``None``.

        Example::

            from reynir import Greynir
            g = Greynir()
            s = g.parse_single("Ása sá sól.")
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

        Example::

            from reynir import Greynir
            g = Greynir()
            s = g.parse_single("Seldum fasteignum hefur fjölgað.")
            print(s.flat_tree)

        Output:

        .. code-block:: none

            S0 S-MAIN IP NP-SUBJ lo_þgf_ft_kvk no_ft_þgf_kvk /NP-SUBJ VP VP-AUX so_et_p3 /VP-AUX VP so_sagnb /VP /VP /IP /S-MAIN p /S0


    .. py:attribute:: terminals

        Returns a ``list`` of the terminals in the best parse tree for the
        sentence, in the order in which they occur in the sentence (token order).
        Each terminal corresponds to a token in the sentence. The entry for each
        terminal is a ``typing.NamedTuple`` called ``Terminal``, having five fields:

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

            from reynir import Greynir
            g = Greynir()
            s = g.parse_single("Þórgnýr fór út og fékk sér ís.")
            for t in s.terminals:
                print("{0:8s} {1:8s} {2:8s} {3}"
                    .format(t.text, t.lemma, t.category,
                        ", ".join(t.variants)))


        Output:

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

        Example::

            from reynir import Greynir
            g = Greynir()
            s = g.parse_single(
                "Gullsópur ehf. keypti árið 1984 verðlaunafasteignina "
                "að Laugavegi 26."
            )
            print(s.lemmas)

        Output:

        .. code-block:: none

            ['gullsópur', 'ehf.', 'kaupa', 'árið 1984', 'verðlauna-fasteign',
            'að', 'Laugavegur', '26', '.']


    .. py:attribute:: categories

        Returns a ``list`` of the categories of the words in the sentence, or
        ``""`` for non-word tokens. ``sent.categories`` is a shorthand for
        ``[ d.cat for d in sent.terminal_nodes ]``.

        The categories returned are those of the token associated with each
        terminal, according to BÍN's category scheme. Nouns (including person names)
        thus have categories of ``kk``, ``kvk`` or ``hk``, for masculine, feminine
        and neutral gender, respectively. Unrecognized words have the ``entity``
        category.

        If the sentence has not yet been parsed, or no parse tree was found
        for it, this property is ``None``.

        Example::

            from reynir import Greynir
            g = Greynir()
            s = g.parse_single(
                "Gullsópur ehf. keypti árið 1984 verðlaunafasteignina "
                "að Laugavegi 26."
            )
            print(s.categories)

        Output:

        .. code-block:: none

            ['kk', 'hk', 'so', '', 'kvk', 'fs', 'kk', '', '']


    .. py:attribute:: lemmas_and_cats

        Returns a ``list`` of (lemma, category) tuples corresponding to the 
        tokens in the sentence. ``sent.lemmas_and_cats`` is a shorthand for
        ``[ (d.lemma, d.lemma_cat) for d in sent.terminal_nodes ]``.

        For non-word tokens, the lemma is the original token text and the
        category is an empty string (``""``).

        For person names, the category is ``person_kk``, ``person_kvk`` or
        ``person_hk`` for masculine, feminine or neutral gender names,
        respectively. For unknown words, the category is ``entity``.

        Lemmas of composite words include hyphens ``-`` at the component boundaries.
        Examples: ``borgar-stjórnarmál``, ``skugga-kosning``.

        This property is intended to be useful *inter alia* for topic indexing
        of text. A good strategy for that purpose could be to index all lemmas having
        a non-empty category, perhaps also discarding some less significant
        categories (such as conjunctions).

        If the sentence has not yet been parsed, or no parse tree was found
        for it, this property is ``None``.

        Example::

            from reynir import Greynir
            g = Greynir()
            s = g.parse_single(
                "Hallbjörn borðaði ísinn kl. 14 meðan Icelandair át 3 teppi "
                "frá Íran og Xochitl var tilbeðin."
            )
            print(s.lemmas_and_cats)

        Output:

        .. code-block:: none

            [('Hallbjörn', 'person_kk'), ('borða', 'so'), ('ís', 'kk'),
            ('kl. 14', ''), ('meðan', 'st'), ('Icelandair', 'entity'),
            ('éta', 'so'), ('3', ''), ('teppi', 'hk'), ('frá', 'fs'),
            ('Íran', 'hk'), ('og', 'st'), ('Xochitl', 'entity'),
            ('vera', 'so'), ('tilbiðja', 'so'), ('.', '')]


    .. py:attribute:: terminal_nodes

        Returns a ``list`` of the subtrees (:py:class:`SimpleTree` instances)
        that correspond to terminals in the parse tree for this
        sentence, in the order in which they occur (token order).

        If the sentence has not yet been parsed, or no parse tree was found
        for it, this property is ``None``.

    .. py:method:: is_foreign(self, min_icelandic_ratio: float=0.5) -> bool

        :param float min_icelandic_ratio: The minimum ratio of word tokens that must
            be found in BÍN for a sentence to be considered Icelandic.
            Defaults to ``0.5``.

        Returns ``True`` if the sentence is probably in a foreign language,
        i.e. not Icelandic. A sentence is probably foreign if it contains
        at least three word tokens and, out of those, less than 50% are found
        in the BÍN database. The 50% threshold is adjustable by overriding
        the ``min_icelandic_ratio`` parameter.


The NounPhrase class
--------------------

The :py:class:`NounPhrase` class conveniently encapsulates an Icelandic
noun phrase (*nafnliður*), making it easy to obtain correctly inflected
forms of the phrase, as required in various contexts.

.. py:class:: NounPhrase

    .. py:method:: __init__(self, np_string: str, *, force_number: str = None)

        Creates a :py:class:`NounPhrase` instance.

        :param str np_string: The text string containing the noun phrase
            (*nafnliður*). The noun phrase must conform to the grammar
            specified for the ``Nl`` nonterminal in ``Greynir.grammar``.
            This grammar allows e.g. number, adjective and adverb prefixes,
            referential phrases (*...sem...*) and prepositional
            phrases (*...í...*). Examples of valid noun phrases include:

            * *stóri kraftalegi maðurinn sem ég sá í bænum*,
            * *ofboðslega bragðgóði lakkrísinn í nýju umbúðunum*, and
            * *rúmlega 20 millilítrar af kardemommudropum með vanillu*.

            If the noun phrase cannot be parsed or is empty, the
            :py:attr:`NounPhrase.parsed` property will be ``False`` and all
            inflection properties will return ``None``.

        :param str force_number: An optional string that can contain
            ``"et"`` or ``"singular"``, or ``"ft"`` or ``"plural"``.
            If given, it forces the parsing of the noun phrase to be
            constrained to singular or plural forms, respectively.
            As an example, ``NounPhrase("eyjar", force_number="ft")``
            yields a plural result (nominative ``"eyjar"``),
            while ``NounPhrase("eyjar")`` without forcing
            yields a singular result (nominative ``"ey"``).

    .. py:method:: __str__(self) -> str

        Returns the original noun phrase string as passed to the constructor.

    .. py:method:: __len__(self) -> int

        Returns the length of the original noun phrase string.

    .. py:method:: __format__(self, spec: str) -> str

        Formats a noun phrase in the requested inflection form.
        Works with Python's ``format()`` function as well as in f-strings
        (available starting with Python 3.6).

        :param str spec: An inflection specification for the string
            to be returned. This can be one of the following:

            * ``nf`` or ``nom``: Nominative case (*nefnifall*).
            * ``þf`` or ``acc``: Accusative case (*þolfall*).
            * ``þgf`` or ``dat``: Dative case (*þágufall*).
            * ``ef`` or ``gen``: Genitive case (*eignarfall*).
            * ``ángr`` or ``ind``: Indefinite, nominative form
              (*nefnifall án greinis*).
            * ``stofn`` or ``can``: Canonical, nominative singular form
              without attached prepositions or referential phrases
              (*nefnifall eintölu án greinis, án forsetningarliða*
              *og tilvísunarsetninga*).

        :return: The noun phrase in the requested inflection form,
            as a string.

        Example::

            from reynir import NounPhrase as Nl

            nl = Nl("blesóttu hestarnir mínir")

            print("Hér eru {nl:nf}.".format(nl=nl))
            print("Mér þykir vænt um {nl:þf}.".format(nl=nl))
            print("Ég segi öllum frá {nl:þgf}.".format(nl=nl))
            print("Ég vil tryggja velferð {nl:ef}.".format(nl=nl))
            print("Já, {nl:ángr}, þannig er það.".format(nl=nl))
            print("Umræðuefnið hér er {nl:stofn}.".format(nl=nl))

            # Starting with Python 3.6, f-strings are supported:
            print(f"Hér eru {nl:nf}.")  # etc.


        Output::

            Hér eru blesóttu hestarnir mínir.
            Mér þykir vænt um blesóttu hestana mína.
            Ég segi öllum frá blesóttu hestunum mínum.
            Ég vil tryggja velferð blesóttu hestanna minna.
            Já, blesóttir hestar mínir, þannig er það.
            Umræðuefnið hér er blesóttur hestur minn.


    .. py:attribute:: parsed

        Returns ``True`` if the noun phrase was successfully parsed,
        or ``False`` if not.

    .. py:attribute:: tree

        Returns a :py:class:`SimpleTree` object encapsulating the parse
        tree for the noun phrase.

    .. py:attribute:: case

        Returns a string denoting the case of the noun phrase, as originally passed
        to the constructor. The case is one of ``"nf"``, ``"þf"``, ``"þgf"``
        or ``"ef"``, denoting nominative, accusative, dative or genitive
        case, respectively. If the noun phrase could not be parsed,
        the property returns ``None``.

    .. py:attribute:: number

        Returns a string denoting the number (singular/plural) of the noun phrase,
        as originally passed to
        the constructor. The number is either ``"et"`` (singular, *eintala*) or
        ``"ft"`` (plural, *fleirtala*). If the noun phrase could not be parsed,
        the property returns ``None``.

    .. py:attribute:: person

        Returns a string denoting the person (1st, 2nd, 3rd) of the noun phrase,
        as originally passed to
        the constructor. The returned string is one of ``"p1"``, ``"p2"`` or
        ``"p3"`` for first, second or third person, respectively.
        If the noun phrase could not be parsed, the property returns ``None``.

    .. py:attribute:: gender

        Returns a string denoting the gender (masculine, feminine, neutral) of
        the noun phrase, as originally passed to
        the constructor. The returned string is one of ``"kk"``, ``"kvk"`` or
        ``"hk"`` for masculine (*karlkyn*), feminine (*kvenkyn*) or
        neutral (*hvorugkyn*), respectively.
        If the noun phrase could not be parsed, the property returns ``None``.

    .. py:attribute:: nominative

        Returns a string with the noun phrase in nominative case (*nefnifall*),
        or ``None`` if the noun phrase could not be parsed.

    .. py:attribute:: accusative

        Returns a string with the noun phrase in accusative case (*þolfall*),
        or ``None`` if the noun phrase could not be parsed.

    .. py:attribute:: dative

        Returns a string with the noun phrase in dative case (*þágufall*),
        or ``None`` if the noun phrase could not be parsed.

    .. py:attribute:: genitive

        Returns a string with the noun phrase in genitive case (*eignarfall*),
        or ``None`` if the noun phrase could not be parsed.

    .. py:attribute:: indefinite

        Returns a string with the noun phrase in indefinite form,
        nominative case (*nefnifall án greinis*),
        or ``None`` if the noun phrase could not be parsed.

    .. py:attribute:: canonical

        Returns a string with the noun phrase in singular, indefinite form,
        nominative case, where referential phrases (*...sem...*) and
        prepositional phrases (*...í...*) have been removed.
        If the noun phrase could not be parsed, ``None`` is returned.



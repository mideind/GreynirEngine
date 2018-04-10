.. _reference:

Reference
=========

The following sections describe the available classes, methods and properties of Reynir.

Initializing Reynir
-------------------

After installing the ``reynir`` package (see :ref:`installation`), use the following
code to import it and initialize an instance of the :py:class:`Reynir` class::

    from reynir import Reynir
    r = Reynir()

Now you can use the ``r`` instance to parse text, by calling the :py:meth:`Reynir.submit()`
and/or :py:meth:`Reynir.parse()` methods on it.

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

    .. py:method:: __init__(self)

        Initializes the :py:class:`Reynir` instance.

    .. py:method:: submit(self, text : string, parse : bool = False) -> _Job

        Submits a text string to Reynir for parsing and returns a :py:class:`_Job` object.

        :param str text: The text to parse. Can be a single sentence or multiple sentences.
        :param bool parse: Controls whether the text is parsed immediately or upon demand.
            Defaults to ``False``.
        :return: A fresh parse job object.

        The given text string is tokenized and split into sentences.
        If the ``parse`` parameter is ``True``, the sentences are parsed
        immediately, before returning from the method.
        Otherwise, parsing should be done explicitly by
        calling :py:meth:`_Sentence.parse()` on each sentence.

        Returns a :py:class:`_Job` object which supports iteration through
        the sentences of the parse job.

    .. py:method:: parse(self, text : string) -> dict

        Parses a text string and returns a dictionary with the parse job results.

        :param str text: The text to parse. Can be a single sentence or multiple sentences.
        :return: A dictionary containing the parse results as well as statistics
            from the parse job.

        The given text string is tokenized and split into sentences. A parse
        job is created and the sentences are parsed. The resulting :py:class:`_Sentence`
        objects are returned in a list in the ``sentences`` field in the dictionary.

        The resulting dictionary contains the following keys:

        * ``sentences``: A list of :py:class:`_Sentence` objects corresponding
            to the sentences found in the text.

        * ``num_sentences``: The number of sentences found in the text.

        * ``num_parsed``: The number of sentences that were successfully parsed.

        * ``ambiguity``: A weighted average of the ambiguity of the parsed
            sentences. Ambiguity is defined as the *n*-th root of the number
            of possible parse trees for the sentence, where *n* is the number
            of tokens in the sentence.

        Example *(try it!)*::

            from reynir import Reynir
            r = Reynir()
            my_text = "Litla gula hænan átti fræ. Það var hveitifræ."
            d = r.parse(my_text)
            print("{0} sentences were parsed".format(d["num_parsed"]))
            for sent in d["sentences"]:
                print("The parse tree for '{0}' is:\n{1}"
                    .format(sent.tidy_text, sent.tree.flat))


    .. py:classmethod:: cleanup(cls)

        Deallocates memory resources allocated by :py:meth:`__init__`.

        If your code has finished using Reynir and you want to free up the
        memory allocated for its resources, including the 60 megabytes for the
        *Database of Modern Icelandic Inflection (BÍN)*, call :py:meth:`Reynir.cleanup()`.

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
        ``[[`` and ``]]`` markers in the text. These markers are optional
        and not required. If they are not present, the text is assumed to be
        one contiguous paragraph.

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

        Returns a ``float`` with the weighted average ambiguity factor of the sentences that
        have been successfully parsed via this job. The ambiguity factor
        of a sentence is defined as the *n*-th root of the total number
        of parse tree combination for the sentence, where *n* is the number
        of tokens in the sentence. The average across sentences is weighted
        by token count.

    .. py:attribute:: parse_time

        Returns a ``float`` with the accumulated wall clock time, in seconds, that has been
        spent parsing sentences via this job.

The _Paragraph class
--------------------

Instances of this class are returned from :py:meth:`_Job.paragraphs()`.
You should not need to instantiate it yourself,
hence the leading underscore in the class name.

.. py:class:: _Paragraph

    .. py:method:: sentences(self)

        Returns a generator of :py:class:`_Sentence` objects. Each object
        corresponds to a sentence in the parsed text. If the sentence has
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

    .. py:attribute:: text

        Returns a ``str`` with the raw text representation of the sentence, with spaces
        between all tokens. For a more correctly formatted version of the text,
        use the :py:attr:`_Sentence.tidy_text` property instead.

    .. py:method:: __str__(self) -> str

        Returns a ``str`` with the raw text representation of the sentence, with spaces
        between all tokens. For a more correctly formatted version of the text,
        use the :py:attr:`_Sentence.tidy_text` property instead.

    .. py:attribute:: tidy_text

        Returns a ``str`` with a text representation of the sentence, with
        correct spacing between tokens.

    .. py:attribute:: tokens

        Returns a ``list`` of tokens in the sentence. Each token is represented
        by a ``Tok`` ``namedtuple`` instance from the ``Tokenizer`` package.

    .. py:method:: parse(self) -> bool

        Parses the sentence (unless it has already been parsed) and returns
        ``True`` if at least one parse tree was found, or ``False`` otherwise.
        For successfully parsed sentences, :py:attr:`_Sentence.tree` contains
        the best parse tree. Otherwise, :py:attr:`_Sentence.tree` is ``None``.
        If the parse is not successful, the 0-based index of the token where
        the parser gave up is stored in :py:attr:`_Sentence.err_index`.

.. _simpletree:

The SimpleTree class
--------------------

Instances of this class are returned from :py:attr:`_Sentence.tree`.
They describe a simplified parse tree or a part (subtree) thereof.
The tree can be queried in various ways for information about its
head (top) node, as well as about its children and contained subtrees.

.. py:class:: SimpleTree

    .. py:attribute:: is_terminal

        Returns ``True`` if this subtree corresponds to a grammar
        terminal (in which case it has no child subtrees),
        or ``False`` otherwise.

    .. py:attribute:: tag

        Returns a ``str`` with the name of the :ref:`nonterminal <nonterminals>`
        corresponding to the root of this tree or subtree. The tag may
        have subcategories, separated by a hyphen, e.g. ``NP-OBJ``.

    .. py:attribute:: terminal

        Returns a ``str`` with the :ref:`terminal <terminals>` corresponding to this
        subtree. The terminal contains a category followed by eventual
        :ref:`variants <variants>`, separated by underscores, e.g. ``no_ef_ft_hvk`` for
        a noun, possessive case, plural, neutral gender.

    .. py:attribute:: variants

        Returns a ``list`` of the :ref:`grammatical variants <variants>`
        specified in the :ref:`terminal <terminals>` corresponding to this
        subtree.

        For example, if the terminal is ``no_ft_ef_hvk`` this property is
        ``[ 'ft', 'ef', 'hvk' ]`` for plural, possessive case,
        neutral gender.

        This property only returns the variants that occur in the terminal
        name in the context-free grammar, and are thus significant in the
        parse. To obtain *all* applicable variants (features) of the associated word form,
        augmented with data from the *Database of Modern Icelandic Inflection (BÍN)*,
        use the :py:attr:`SimpleTree.all_variants` property.

    .. py:attribute:: all_variants

        Returns a ``list`` of all :ref:`grammatical variants <variants>`
        (features) associated with this word form, as inferred from its
        associated grammar terminal and as augmented from the
        *Database of Modern Icelandic Inflection (BÍN)*.

        Example::

            from reynir import Reynir
            r = Reynir()
            s = r.parse_single("Ása sá sól.")
            print(s.tree.S.IP.VP[0].all_variants)

        Output (the variants of the verb *sá* in the verb phrase)::

            ['1', 'þf', 'et', 'p3', 'fh', 'gm', 'þt']

        These are all the variants (features) of the verb form *sá*, in this case
        specifying that it has one argument in accusative case (``þf``), and
        that the verb itself is singular (``et``), third person (``p3``), indicative (``fh``),
        active voice (``gm``), past tense (``þt``).

        The last three variants are only returned from the :py:attr:`SimpleTree.all_variants`
        property, not from the :py:attr:`SimpleTree.variants` property, as they are not
        present in the terminal name in the grammar and are not significant when deriving
        the parse tree.

    .. py:attribute:: tcat

        Returns a ``str`` with the terminal :ref:`category <categories>` corresponding to this
        subtree, e.g. ``no`` for nouns or ``dags`` for dates.

    .. py:method:: match_tag(self, item : str) -> bool

        Checks whether the root nonterminal of the tree matches the given
        :ref:`nonterminal identifier <nonterminals>`.

        :param str item: The nonterminal identifier to match. The match can
            be partial, i.e. the item ``NP`` matches the roots ``NP-OBJ`` and
            ``NP-SUBJ`` as well as plain ``NP``.

        :return: ``True`` if the root nonterminal matches, or ``False`` if not.

    .. py:attribute:: children

        Returns a generator for the (immediate) child subtrees of this tree.
        The generator returns a :py:class:`SimpleTree` instance for
        every child.

    .. py:attribute:: descendants

        Returns a generator for all descendants of this tree. This returns
        a :py:class:`SimpleTree` instance for every child, recursively,
        using left-first traversal.

    .. py:attribute:: view

        Returns a ``str`` representation of this subtree, in an easily
        viewable indented format with nodes separated by newlines.

        Example::

            from reynir import Reynir
            r = Reynir()
            s = r.parse_single("Ása sá sól.")
            print(s.tree.view)

        outputs::

            P
            +-S-MAIN
              +-IP
                +-NP-SUBJ
                  +-no_et_nf_kvk: 'Ása'
                +-VP
                  +-so_1_þf_et_p3: 'sá'
                  +-NP-OBJ
                    +-no_et_þf_kvk: 'sól'
            +-'.'

    .. py:attribute:: flat

        Returns this subtree, simplified and flattened to a text string.
        :ref:`Nonterminal <nonterminals>` scopes are
        delimited like so: ``NAME ... /NAME`` where ``NAME`` is the name of
        the nonterminal, for example ``NP`` for noun phrases and ``VP`` for
        verb phrases. :ref:`terminals` have lower-case identifiers with their
        various :ref:`grammar variants <variants>` separated by underscores, e.g.
        ``no_þf_kk_et`` for a noun, accusative case, masculine gender, singular.

        Example::

            from reynir import Reynir
            r = Reynir()
            s = r.parse_single("Jón greiddi bænum 10 milljónir króna.")
            print(s.tree.flat)

        Output (line breaks inserted)::

            P S-MAIN IP NP-SUBJ person_nf_kk /NP-SUBJ VP so_2_þgf_þf_et_p3
                NP-IOBJ no_et_þgf_kk /NP-IOBJ NP-OBJ tala_ft_þf_kvk
                no_ft_þf_kvk NP-POSS no_ft_ef_kvk /NP-POSS /NP-OBJ /VP /IP
                /S-MAIN p /P

    .. py:method:: __getitem__(self, item) -> SimpleTree

        Returns the specified child subtree of this tree.

        :param str/int item:  This can be either a :ref:`nonterminal identifier <nonterminals>`
            (e.g. ``"S-MAIN"``),
            in which case the first child having that nonterminal as its root
            is returned, or an ``int``, in which case the child having the specified
            0-based index is returned. A nonterminal match
            can be partial, i.e. the item ``NP`` matches the roots ``NP-OBJ`` and
            ``NP-SUBJ`` as well as plain ``NP``.

        :return: A :py:class:`SimpleTree` instance for the indicated child subtree.
            If no such subtree is found, the exception ``KeyError`` (in the case
            of a nonterminal identifier) or ``IndexError`` (in the case of an integer
            index) are raised.

        Example::

            from reynir import Reynir
            r = Reynir()
            my_text = "Prakkarinn Ása í Garðastræti sá tvær gular sólir."
            s = r.parse_single(my_text)
            print(s.tree[0]["IP"][1].lemmas)

        outputs (the lemmas of the verb phrase)::

            ['sjá', 'tveir', 'gulur', 'sól']

    .. py:method:: __getattr__(self, name) -> SimpleTree

        Returns the specified child subtree of this tree.

        :param str name:  A :ref:`nonterminal identifier <nonterminals>` (e.g. ``"NP"``).
            The first child having that nonterminal as its root is returned. A nonterminal
            match can be partial, i.e. the item ``NP`` matches the roots ``NP-OBJ`` and
            ``NP-SUBJ`` as well as plain ``NP``. An underscore in the identifier
            name matches a hyphen in the root nonterminal name.

        :return: A :py:class:`SimpleTree` instance for the indicated child subtree.
            If no such subtree is found, the exception ``KeyError`` is raised.

        Example::

            from reynir import Reynir
            r = Reynir()
            my_text = "Prakkarinn Ása í Garðastræti sá sól."
            s = r.parse_single(my_text)
            print(s.tree.S_MAIN.IP.NP_SUBJ.lemmas)

        outputs (the lemmas of the sentence's subject, *frumlag*)::

            ['prakkari', 'Ása', 'í', 'Garðastræti']

    .. py:attribute:: text

        Returns a ``str`` with the raw text corresponding to this subtree,
        including its children, with spaces between tokens.

    .. py:attribute:: own_text

        Returns a ``str`` with the raw text corresponding to the root
        of this subtree only, i.e. not including its children. For nonterminals,
        this is always an empty string. For terminals, it is the text of the
        corresponding token.

    .. py:attribute:: lemmas

        Returns a ``list`` of the word lemmas corresponding to terminals contained
        within this subtree. For terminals that correspond to non-word tokens,
        the original token text is included in the list.

        Lemmas of composite words include hyphens ``-`` at the component boundaries.
        Examples: ``borgar-stjórnarmál``, ``skugga-kosning``.

    .. py:attribute:: lemma

        Returns a ``str`` containing a concatenation of the word lemmas corresponding
        to terminals contained within this subtree. For terminals that correspond
        to non-word tokens, the original token text is included in the string. The
        lemmas are separated by spaces.

        Lemmas of composite words include hyphens ``-`` at the component boundaries.
        Examples: ``borgar-stjórnarmál``, ``skugga-kosning``.

    .. py:attribute:: own_lemma

        Returns a ``str`` containing the word lemma corresponding to the root
        of this subtree only. For nonterminal roots, this returns an empty string.

        Lemmas of composite words include hyphens ``-`` at the component boundaries.
        Examples: ``borgar-stjórnarmál``, ``skugga-kosning``.

    .. py:attribute:: nominative

        Returns a ``str`` containing the *nominative* form, if it exists, of the word
        corresponding to the root of this subtree only. If no nominative form exists,
        the word or token text is returned unchanged. For nonterminal
        roots, an empty string is returned.

        Example::

            from reynir import Reynir
            r = Reynir()
            s = r.parse_single("Góðglaða karlana langar í hest.")
            print(" ".join(n.nominative for n in s.tree.descendants if n.is_terminal))

        outputs::

            Góðglaðir karlarnir langar í hestur .

    .. py:attribute:: indefinite

        Returns a ``str`` containing the *indefinite nominative* form, if it exists, of the word
        corresponding to the root of this subtree only. If no such form exists,
        the word or token text is returned unchanged. For nonterminal
        roots, an empty string is returned.

        Example::

            from reynir import Reynir
            r = Reynir()
            s = r.parse_single("Góðglaða karlana langar í hest.")
            print(" ".join(n.indefinite for n in s.tree.descendants if n.is_terminal))

        outputs::

            Góðglaðir karlar langar í hestur .

    .. py:attribute:: canonical

        Returns a ``str`` containing the *singular indefinite nominative* form,
        if it exists, of the word corresponding to the root of this subtree only.
        If no such form exists, the word or token text is returned unchanged.
        For nonterminal roots, an empty string is returned.

        Example::

            from reynir import Reynir
            r = Reynir()
            s = r.parse_single("Góðglaða karlana langar í hest.")
            print(" ".join(n.canonical for n in s.tree.descendants if n.is_terminal))

        outputs::

            Góðglaður karl langar í hestur .

    .. py:attribute:: nominative_np

        Returns a ``str`` containing the text within the subtree, except that if the
        subtree root is a noun phrase (``NP``) nonterminal, that phrase is converted to
        *nominative* form (*nefnifall*).

        Example::

            from reynir import Reynir
            r = Reynir()
            s = r.parse_single("Ótrúlega frábærum bílstjórum þriggja góðglöðu alþingismannanna "
                "sem fóru út þykir þetta leiðinlegt.")
            print(s.tree.S_MAIN.IP.NP_SUBJ.nominative_np)
            print(s.tree.S_MAIN.IP.NP_SUBJ.NP_POSS.nominative_np)

        outputs::

            Ótrúlega frábærir bílstjórar þriggja góðglöðu alþingismannanna sem fóru út
            þrír góðglöðu alþingismennirnir sem fóru út

    .. py:attribute:: indefinite_np

        Returns a ``str`` containing the text within the subtree, except that if the
        subtree root is a noun phrase (``NP``) nonterminal, that phrase is converted to *indefinite nominative* form
        (*nefnifall án greinis*). The determiner (*laus greinir*) and any demonstrative pronouns
        (*ábendingarfornöfn*) are cut off the front of the noun phrases in the conversion, if present.
        Adjectives are converted from definite (*veik beyging*) to indefinite forms (*sterk beyging*).

        Example::

            from reynir import Reynir
            r = Reynir()
            s = r.parse_single("Hinum ótrúlega frábæru bílstjórum þriggja góðglöðu alþingismannanna "
                "sem fóru út þykir þetta leiðinlegt.")
            print(s.tree.S_MAIN.IP.NP_SUBJ.indefinite_np)
            print(s.tree.S_MAIN.IP.NP_SUBJ.NP_POSS.indefinite_np)

        outputs::

            ótrúlega frábærir bílstjórar þriggja góðglöðu alþingismannanna sem fóru út
            þrír góðglaðir alþingismenn sem fóru út

    .. py:attribute:: canonical_np

        Returns a ``str`` containing the text within the subtree, except that if the
        subtree root is a noun phrase (``NP``) nonterminal, that phrase is converted to
        *singular indefinite nominative* form
        (*nefnifall eintölu án greinis*). The determiner (*laus greinir*) and any demonstrative pronouns
        (*ábendingarfornöfn*) are cut off the front of the noun phrases in the conversion, if present.
        Also, associated possessive phrases and referential sentences are removed
        (*mennina sem ég þekkti vel* -> *maður*). Adjectives are converted from definite
        (*veik beyging*) to indefinite forms (*sterk beyging*).

        Example::

            from reynir import Reynir
            r = Reynir()
            s = r.parse_single("Hinum ótrúlega frábæru bílstjórum þriggja góðglöðu alþingismannanna "
                "sem fóru út þykir þetta leiðinlegt.")
            print(s.tree.S_MAIN.IP.NP_SUBJ.canonical_np)
            print(s.tree.S_MAIN.IP.NP_SUBJ.NP_POSS.canonical_np)

        outputs::

            ótrúlega frábær bílstjóri
            góðglaður alþingismaður

    .. py:attribute:: nouns

        Returns a ``list`` of the lemmas of all *nouns* within this subtree, i.e. the
        root and all its descendants, recursively. The list is in left-traversal
        order.

        Lemmas of composite words include hyphens ``-`` at the component boundaries.
        Examples: ``borgar-stjórnarmál``, ``skugga-kosning``.

    .. py:attribute:: verbs

        Returns a ``list`` of the lemmas of all *verbs* within this subtree, i.e. the
        root and all its descendants, recursively. The list is in left-traversal
        order.

        Lemmas of composite words include hyphens ``-`` at the component boundaries.
        Examples: ``borgar-stjórnarmál``, ``skugga-kosning``.

    .. py:attribute:: persons

        Returns a ``list`` of the lemmas (the nominative case) of all *person names*
        within this subtree, i.e. the root and all its descendants, recursively.
        The list is in left-traversal order.

        Example::

            from reynir import Reynir
            r = Reynir()
            my_text = "Eftir síðustu kosningar ræddi " \
                "Bjarni Benediktsson við Katrínu Jakobsdóttur " \
                "um myndun ríkisstjórnar."
            s = r.parse_single(my_text)
            print(s.tree.persons)

        outputs::

            ['Bjarni Benediktsson', 'Katrín Jakobsdóttir']

    .. py:attribute:: entities

        Returns a ``list`` of the lemmas (the nominative case, as far as that can
        be established and is applicable) of all *entity names*
        within this subtree, i.e. the root and all its descendants, recursively.
        The list is in left-traversal order.

    .. py:attribute:: proper_names

        Returns a ``list`` of the lemmas (the nominative case, as far as that can
        be established and is applicable) of all *proper names (sérnöfn*)
        within this subtree, i.e. the root and all its descendants, recursively.
        The list is in left-traversal order.

    .. py:method:: match(self, pattern : str) -> bool

        Checks whether this subtree matches the given pattern.

        :param str pattern: The pattern to match against. For information
            about pattern specifications, see :ref:`patterns`.

        :return: ``True`` if this subtree matches the pattern,
            or ``False`` if not.

    .. py:method:: first_match(self, pattern : str) -> SimpleTree

        Finds the first match of the given pattern within this subtree.
        The first match may be the subtree itself. If no match is found,
        returns ``None``.

        :param str pattern: The pattern to match against. For information
            about pattern specifications, see :ref:`patterns`.

        :return: A :py:class:`SimpleTree` instance that matches the given
            pattern, or ``None``.

        Example::

            from reynir import Reynir
            r = Reynir()
            s = r.parse_single("Kristín málaði hús Steingríms")
            # Show the first possessive noun phrase ('Steingríms')
            print(s.tree.first_match("NP-POSS").nominative_np)

        outputs::

            Steingrímur

    .. py:method:: all_matches(self, pattern : str) -> generator[SimpleTree]

        Returns a generator of all matches of the given pattern within this subtree.
        The generator may yield the subtree itself, if it matches the pattern.
        Note that the search is recursive and exhaustive, so that matches within matching
        subtrees (for instance noun phrases within noun phrases) will also be returned.

        :param str pattern: The pattern to match against. For information
            about pattern specifications, see :ref:`patterns`.

        :return: A generator of :py:class:`SimpleTree` instances that match the given
            pattern.

        Example::

            from reynir import Reynir
            r = Reynir()
            s = r.parse_single("Stóri feiti jólasveinninn beislaði "
                "fjögur sætustu hreindýrin og ók rauða vagninum "
                "með fjölda gjafa til spenntu barnanna sem biðu "
                "milli vonar og ótta.")
            print("\n".join(n.nominative_np for n in s.tree.all_matches("NP")))

        outputs::

            Stóri feiti jólasveinninn
            fjögur sætustu hreindýrin
            rauði vagninn með fjölda pakka til spenntu barnanna sem biðu milli vonar og ótta
            fjöldi gjafa til spenntu barnanna sem biðu milli vonar og ótta
            gjafir til spenntu barnanna sem biðu milli vonar og ótta
            spenntu börnin sem biðu milli vonar og ótta

        Note that *milli vonar og ótta* is parsed as a fixed adverbial phrase. The nouns
        *von* and *ótti* are thus not included in the list of noun phrases.

        Also note that *rauði vagninn með fjölda gjafa til spenntu barnanna sem biðu milli vonar og ótta*
        is a noun phrase containing two nested noun phrases. :py:meth:`SimpleTree.all_matches()` returns
        all three noun phrases, also the nested ones. If you only want the outermost (top) matching subtree
        for a pattern, use :py:meth:`SimpleTree.top_matches()` instead.

    .. py:method:: top_matches(self, pattern : str) -> generator[SimpleTree]

        Returns a generator of all topmost (enclosing) matches of the given pattern within this subtree.
        The generator may yield the subtree itself (only), if it matches the pattern. This
        search is different from :py:meth:`SimpleTree.all_matches()` in that it is
        recursive but not exhaustive, i.e. does not return matches within matches.

        :param str pattern: The pattern to match against. For information
            about pattern specifications, see :ref:`patterns`.

        :return: A generator of :py:class:`SimpleTree` instances that match the given
            pattern.

        Example::

            from reynir import Reynir
            r = Reynir()
            s = r.parse_single("Stóri feiti jólasveinninn beislaði "
                "fjögur sætustu hreindýrin og ók rauða vagninum "
                "með fjölda gjafa til spenntu barnanna sem biðu "
                "milli vonar og ótta.")
            print("\n".join(n.nominative_np for n in s.tree.top_matches("NP")))

        outputs::

            Stóri feiti jólasveinninn
            fjögur sætustu hreindýrin
            rauði vagninn með fjölda gjafa til spenntu barnanna sem biðu milli vonar og ótta

        Note that *rauði vagninn með fjölda gjafa til spenntu barnanna sem biðu milli vonar og ótta*
        is a single noun phrase containing two nested noun phrases. If you want all matching phrases for a
        pattern, including nested ones, use :py:meth:`SimpleTree.all_matches()` instead.


.. _patterns:

Patterns
========

This section describes matching patterns that can be used with the
:py:meth:`SimpleTree.match()`, :py:meth:`SimpleTree.first_match()`,
:py:meth:`SimpleTree.all_matches()` and :py:meth:`SimpleTree.top_matches()`
methods.

Overview
--------

The above mentioned methods can be used to find trees and subtrees that match
a specific grammatical pattern. This pattern can include conditions that apply
to the root of each subtree as well as its children, direct or indirect.

The patterns are given as strings, with pattern tokens separated by whitespace.
:ref:`examples` are given below.

See the documentation of each method for a further explanation of how the
given pattern is matched in each case, and how results are returned.

Simple matches
--------------

* A ``"literal"`` within *double quotes* matches a subtree that covers exactly
  the given literal text, although using a case-neutral comparison.
  ``"Icelandic"`` thus matches ``"icelandic"`` and ``"ICELANDIC"``.
  The literal may have multiple words, separated by spaces:
  ``"borgarstjóri reykjavíkur"`` matches a subtree that covers these two
  word forms.

* A ``'literal'`` within *single quotes* matches a subtree that covers exactly
  the given word lemma(s), using a case-neutral comparison.
  ``'hestur'`` thus matches ``"hests"`` and ``"Hestinum"``.
  The literal may have multiple words, separated by spaces:
  ``'borgarstjóri reykjavík'`` matches a subtree that covers these
  two lemmas. (``'borgarstjóri reykjavíkur'`` would never match anything
  as ``"reykjavíkur"`` is not the lemma of any word form.)

* A ``NONTERMINAL`` identifier in upper case matches nodes associated with
  that nonterminal, as well as subcategories thereof. ``NP`` thus matches
  ``NP`` as well as ``NP-OBJ`` and ``NP-SUBJ``. ``NP-OBJ`` only matches
  ``NP-OBJ`` and subcategories thereof.

* A ``terminal`` identifier in lower case matches nodes associated with
  the specified category of terminal, and having at least the variants given, if any.
  ``no`` thus matches all noun terminals, while ``no_nf_et`` only matches
  noun terminals in nominative case, singular (but any gender, since a gender
  variant is not specified).

Wildcard match
--------------

* A dot ``.`` matches any single tree node.

OR match
--------

* ``(Any1 | Any2 | ...)`` matches if anything between the parentheses matches.
  The options are separated by vertical bars ``|``.

Sequence matches
----------------

* ``Any1 Any2 Any3`` matches the given sequence of matches if each
  element matches in exactly the given order. The match must be exhaustive,
  i.e. no child nodes may be left unmatched at the end of the list.

* ``Any+`` matches one or more sequential instances of the given ``Any`` match.

* ``Any*`` matches zero or more sequential instances of the given ``Any`` match.

* ``Any?`` matches zero or one instances of the given ``Any`` match.

* ``.*`` thus matches any number of any nodes and is an often-used construct.

* ``[ Any1 Any2 ]`` matches any node sequence that starts with the two given
  matches. It does not matter whether the sequence contains more nodes.

* ``[ Any1 Any2 $ ]`` matches any node sequence where ``Any1`` and ``Any2`` match
  and there are no further nodes in the sequence. The ``$`` sign is an
  end-of-sequence marker.

* ``[ Any1 .* Any2 $ ]`` matches only sequences that start with ``Any1`` and
  end with ``Any2``.

Hierarchical matches
--------------------

* ``Any1 > { Any2 Any3 ... }`` matches if ``Any1`` matches and has *immediate*
  (direct) children that include ``Any2``, ``Any3`` *and* other given arguments
  (irrespective of order). This is a *set-like* operator.

* ``Any1 >> { Any2 Any3 ... }`` matches if ``Any1`` matches and has children
  *at any sublevel* that include ``Any2``, ``Any3`` *and* other given arguments
  (irrespective of order). This is a *set-like* operator.

* ``Any1 > [ Any2 Any3 ... ]`` matches if ``Any1`` matches and has immediate
  children that include ``Any2``, ``Any3`` *and* other given arguments
  *in the order specified*. This is a *list-like* operator.

.. _examples:

Examples
--------

This pattern will match the root subtree of any sentence that has a verb phrase
that refers to a person as an argument::

    "S >> { VP >> { NP-OBJ >> person }}"

This pattern will match any sentence that has a verb phrase that refers to
a male person as an argument::

    "S >> { VP >> { NP-OBJ >> person_kk }}"

Here is a short program using some of the matching features::

    from reynir import Reynir
    r = Reynir()
    my_text = ("Reynt er að efla áhuga ungs fólks á borgarstjórnarmálum "
        "með framboðsfundum og skuggakosningum en þótt kjörstaðirnir "
        "í þeim séu færðir inn í framhaldsskólana er þátttakan lítil.")
    s = r.parse_single(my_text)
    print("Parse tree:")
    print(s.tree.view)
    print("All subjects:")
    for d in s.tree.descendants:
        if d.match_tag("NP-SUBJ"):
            print(d.text)
    print("All masculine noun and pronoun phrases:")
    for m in s.tree.all_matches("NP > { (no_kk | pfn_kk) } "):
        print(m.canonical_np)

Output::

    Parse tree:
    P
    +-S-MAIN
      +-VP
        +-so_0_sagnb: 'Reynt'
        +-so_et_p3: 'er'
        +-nhm: 'að'
        +-so_1_þf_nh: 'efla'
        +-NP-OBJ
          +-no_et_þf_kk: 'áhuga'
          +-NP-POSS
            +-lo_ef_et_hk: 'ungs'
            +-no_et_ef_hk: 'fólks'
            +-PP
              +-fs_þgf: 'á'
              +-NP
                +-no_ft_þgf_hk: 'borgarstjórnarmálum'
                +-PP
                  +-fs_þgf: 'með'
                  +-NP
                    +-no_ft_þgf_kk: 'framboðsfundum'
                    +-st: 'og'
                    +-no_ft_þgf_kvk: 'skuggakosningum'
    +-st: 'en'
    +-S-MAIN
      +-S-ADV-ACK
        +-st: 'þótt'
        +-IP
          +-NP-SUBJ
            +-no_ft_nf_kk: 'kjörstaðirnir'
            +-PP
              +-fs_þgf: 'í'
              +-NP
                +-pfn_hk_ft_þgf: 'þeim'
          +-VP
            +-so_ft_p3: 'séu'
            +-so_0_lhþt_ft_kk: 'færðir'
      +-IP
        +-PP
          +-ao: 'inn'
          +-fs_þf: 'í'
          +-NP
            +-no_ft_þf_kk: 'framhaldsskólana'
        +-VP
          +-so_et_p3: 'er'
          +-NP-SUBJ
            +-no_et_nf_kvk: 'þátttakan'
          +-ADJP
            +-lo_sb_nf_et_kvk: 'lítil'
    +-'.'
    All subjects:
    kjörstaðirnir í þeim
    þátttakan
    All masculine noun and pronoun phrases:
    áhugi
    framboðsfundur og skuggakosning
    kjörstaður
    framhaldsskóli


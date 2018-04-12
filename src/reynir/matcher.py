"""
    Reynir: Natural language processing for Icelandic

    Matcher module

    Copyright (c) 2018 Miðeind ehf.
    Author: Vilhjálmur Þorsteinsson

       This program is free software: you can redistribute it and/or modify
       it under the terms of the GNU General Public License as published by
       the Free Software Foundation, either version 3 of the License, or
       (at your option) any later version.
       This program is distributed in the hope that it will be useful,
       but WITHOUT ANY WARRANTY; without even the implied warranty of
       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
       GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see http://www.gnu.org/licenses/.


    This module contains a wrapper class for "simple trees" with
    tree pattern matching operations.

    The match patterns are as follows:
    ----------------------------------

    `.` matches any tree node

    `"literal"` matches a subtree covering exactly the given literal text,
        albeit case-neutral

    `'lemma'` matches a subtree covering exactly the given word lemma(s)

    `NONTERMINAL` matches the given nonterminal

    `terminal` matches the given terminal
    `terminal_var1_var2` matches a terminal having at least the given variants

    `Any1 Any2 Any3` matches the given sequence as-is, in-order

    `Any+` matches one or more sequential instances of Any

    `Any*` matches zero or more sequential instances of Any

    `Any?` matches zero or one sequential instances of Any

    `.*` matches any number of any nodes (as an example)

    `(Any1 | Any2 | ...)` matches if anything within the parentheses matches

    `Any1 > { Any2 Any3 ... }` matches if Any1 matches and has immediate children
        that include Any2, Any3 *and* other given arguments (irrespective of order).
        This is a set-like operator.

    `Any1 >> { Any2 Any3 ... }` matches if Any1 matches and has children at any
        sublevel that include Any2, Any3 *and* other given arguments
        (irrespective of order). This is a set-like operator.

    `Any1 > [ Any2 Any3 ...]` matches if Any1 matches and has immediate children
        that include Any2, Any3 *and* other given arguments in the order specified.
        This is a list-like operator.

    `Any1 >> [ Any2 Any3 ...]` matches if Any1 matches and has children at any sublevel
        that include Any2, Any3 *and* other given arguments in the order specified.
        This is a list-like operator.

    `[ Any1 Any2 ]` matches any node sequence that starts with the two given items.
        It does not matter whether the sequence contains more items.

    `[ Ant1 Any2 $ ]` matches only sequences where Any1 and Any2 match and there are
        no further nodes in the sequence

    `[ Any1 .* Any2 $ ]` matches only sequences that start with Any1 and end with Any2

    NOTE: The repeating operators * + ? are meaningless within { sets }; their
        presence will cause an exception.


    Examples:
    ---------

    All sentences having verb phrases that refer to a person as an argument:

    `S >> { VP >> { NP >> person }}`

    All sentences having verb phrases that refer to a male person as an argument:

    `S >> { VP >> { NP >> person_kk }}`

"""


import re
from pprint import pformat
from itertools import chain


# Default tree simplifier configuration maps

_DEFAULT_NT_MAP = {
    "S0" : "P",
    "HreinYfirsetning" : "S-MAIN",
    "Setning" : "S",
    "SetningSo" : "VP-SEQ",
    "SetningLo" : "S",
    "SetningÁnF" : "S",
    "SetningAukafall" : "S",
    "SetningAukafallForgangur" : "S",
    "SetningSkilyrði" : "S",
    "SetningUmAðRæða" : "S",
    "StViðtenging" : "S",
    "Tengiliður" : "S-REF",
    "OgTengisetning" : "S-REF",
    "Skilyrði" : "S-COND",
    "Afleiðing" : "S-CONS",
    "NlSkýring" : "S-EXPLAIN",
    "Útskýring" : "S-EXPLAIN",
    "FrumlagsInnskot" : "S-EXPLAIN",
    "Tilvitnun" : "S-QUOTE",
    "Forskeyti" : "S-PREFIX",
    #"EfÞegar" : "S-PREFIX",
    "Tíðarsetning" : "S-ADV-TEMP",
    "Tilgangssetning" : "S-ADV-PURP",
    "Viðurkenningarsetning" : "S-ADV-ACK",
    "Afleiðingarsetning" : "S-ADV-CONS",
    "Orsakarsetning" : "S-ADV-CAUSE",
    "Skilyrðissetning" : "S-ADV-COND",
    "Skýringarsetning" : "S-THT",
    "Spurnaraukasetning" : "S-QUE",
    "Spurnarsetning" : "S-QUE",
    "Nl" : "NP",
    "EfLiður" : "NP-POSS",
    "EfLiðurForskeyti" : "NP-POSS",
    "OkkarFramhald" : "NP-POSS",
    "LoEftirNlMeðÞgf" : "NP-DAT",
    "Heimilisfang" : "NP-ADDR",
    "Titill" : "NP-TITLE",
    "Frumlag" : "NP-SUBJ",
    "NlFrumlag" : "NP-SUBJ",
    "NlBeintAndlag" : "NP-OBJ",
    "NlÓbeintAndlag" : "NP-IOBJ",
    "NlSagnfylling" : "NP-PRD",
    "FsMeðFallstjórn" : "PP",
    "SagnInnskot" : "ADVP",
    "FsAtv" : "ADVP",
    "AtvFs" : "ADVP",
    "Atviksliður" : "ADVP",
    "LoAtviksliðir" : "ADVP",
    "Dagsetning" : "ADVP-DATE",
    "Tímasetning" : "ADVP-DATE",
    "SagnRuna" : "VP-SEQ",
    "Sagnliður" : "VP",
    "SagnliðurMeðF" : "VP",
    "So" : "VP",
    # "SagnFramhald" : "VP",
    "SögnLhNt" : "VP-PP", # Present participle, lýsingarháttur nútíðar
    "SögnErLoBotn" : "NP-PRD", # Show '(Hann er) góður / 18 ára' as a predicate argument
    "NhLiðir" : "VP",
    "SagnliðurÁnF" : "VP",
    "ÖfugurSagnliður" : "VP",
    "SagnHluti" : "VP-SEQ",
    "SagnliðurVh" : "VP",
    "LoTengtSögn" : "ADJP",
    "BeygingarliðurÁnF" : "IP",
    "BeygingarliðurÁnUmröðunar" : "IP",
    "BeygingarliðurMeðUmröðun" : "IP",
}

# subject_to: don't push an instance of this if the
# immediate parent is already the subject_to nonterminal

# overrides: we cut off a parent node in favor of this one
# if there are no intermediate nodes

_DEFAULT_ID_MAP = {
    "P" : dict(name = "Málsgrein"),
    "S-MAIN" : dict(name = "Setning", overrides = "S",
        subject_to = { "S-MAIN" }),
    "S" : dict(name = "Setning",
        subject_to = { "S", "S-EXPLAIN", "S-REF", "IP" }),
    "S-COND" : dict(name = "Skilyrði", overrides = "S"), # Condition
    "S-CONS" : dict(name = "Afleiðing", overrides = "S"), # Consequence
    "S-REF" : dict(name = "Tilvísunarsetning", overrides = "S",
        subject_to = { "S-REF" }), # Reference
    "S-EXPLAIN" : dict(name = "Skýring"), # Explanation
    "S-QUOTE" : dict(name = "Tilvitnun"), # Quote at end of sentence
    "S-PREFIX" : dict(name = "Forskeyti"), # Prefix in front of sentence
    "S-ADV-TEMP" : dict(name = "Tíðarsetning"), # Adverbial temporal phrase
    "S-ADV-PURP" : dict(name = "Tilgangssetning"), # Adverbial purpose phrase
    "S-ADV-ACK" : dict(name = "Viðurkenningarsetning"), # Adverbial acknowledgement phrase
    "S-ADV-CONS" : dict(name = "Afleiðingarsetning"), # Adverbial consequence phrase
    "S-ADV-CAUSE" : dict(name = "Orsakarsetning"), # Adverbial causal phrase
    "S-ADV-COND" : dict(name = "Skilyrðissetning"), # Adverbial conditional phrase
    "S-THT" : dict(name = "Skýringarsetning"), # Complement clause
    "S-QUE" : dict(name = "Spurnarsetning"), # Question clause
    "VP-SEQ" : dict(name = "Sagnliður"),
    "VP" : dict(name = "Sögn", overrides = "VP-SEQ",
        subject_to = { "VP" }),
    "VP-PP" : dict(name = "Sögn", overrides = "PP"),
    "NP" : dict(name = "Nafnliður",
        subject_to = { "NP-SUBJ", "NP-OBJ", "NP-IOBJ", "NP-PRD" }),
    "NP-POSS" : dict(name = "Eignarfallsliður", overrides = "NP"),
    "NP-DAT" : dict(name = "Þágufallsliður", overrides = "NP"),
    "NP-ADDR" : dict(name = "Heimilisfang", overrides = "NP"),
    "NP-TITLE" : dict(name = "Titill", overrides = "NP"),
    "NP-SUBJ" : dict(name = "Frumlag",
        subject_to = { "NP-SUBJ" }),
    "NP-OBJ" : dict(name = "Beint andlag"),
    "NP-IOBJ" : dict(name = "Óbeint andlag"),
    "NP-PRD" : dict(name = "Sagnfylling"),
    "ADVP" : dict(name = "Atviksliður",
        subject_to = { "ADVP" }),
    "ADVP-DATE" : dict(name = "Tímasetning", overrides = "ADVP",
        subject_to = { "ADVP-DATE" }),
    "PP" : dict(name = "Forsetningarliður", overrides = "ADVP"),
    "ADJP" : dict(name = "Lýsingarliður",
        subject_to = { "ADJP" }),
    "IP" : dict(name = "Beygingarliður"),   # Inflectional phrase
}

_DEFAULT_TERMINAL_MAP = {
    # Empty
}


class MultiReplacer:

    """ Utility class to do multiple replacements on a string
        in a single pass. The replacements are defined in a dict,
        i.e. { "toReplace" : "byString" }
    """

    def __init__(self, replacements):
        self._replacements = replacements
        substrs = sorted(replacements, key=len, reverse=True)
        # Create a big OR regex that matches any of the substrings to replace
        self._regexp = re.compile('|'.join(map(re.escape, substrs)))

    def replace(self, string):
        # For each match, look up the new string in the replacements
        return self._regexp.sub(
            lambda match: self._replacements[match.group(0)],
            string)


class SimpleTree:

    """ A wrapper for a simple parse tree, returned from the
        TreeUtils.simple_parse() function """

    _NEST = {
        '(' : ')',
        '[' : ']',
        '{' : '}'
    }
    _FINISHERS = frozenset(_NEST.values())
    _NOT_ITEMS = frozenset(( '>', '*', '+', '?', '[', '(', '{', ']', ')', '}', '$' ))

    _pattern_cache = dict()

    def __init__(self, pgs, stats = None, register = None, parent = None):
        # Keep a link to the original parent SimpleTree
        self._parent = parent
        if parent is not None:
            assert stats is None
            assert register is None
        self._stats = stats
        self._register = register
        # Flatten the paragraphs into a sentence array
        sents = []
        if pgs:
            for pg in pgs:
                sents.extend(pg)
        self._sents = sents
        self._len = len(sents)
        self._head = sents[0] if self._len == 1 else { }
        self._sent_cache = None
        self._children = self._head.get("p")
        self._children_cache = None
        self._variants = None
        self._tcat = None
        self._text_cache = None
        self._lemma_cache = None
        self._tag_cache = None

    def __str__(self):
        """ Return a pretty-printed representation of the contained trees """
        return pformat(self._sents)

    def __repr__(self):
        """ Return a compact representation of this subtree """
        len_self = len(self)
        if len_self == 0:
            if self._head.get("k") == "PUNCTUATION":
                x = self._head.get("x")
                return "<SimpleTree object for punctuation '{0}'>".format(x)
            return "<SimpleTree object for terminal {0}>".format(self.terminal)
        return "<SimpleTree object with tag {0} and length {1}>".format(self.tag, len_self)

    @property
    def parent(self):
        """ The original topmost parent of this subtree """
        return self if self._parent is None else self._parent

    @property
    def stats(self):
        return self.parent._stats

    @property
    def register(self):
        return self.parent._register

    @property
    def tag(self):
        """ The simplified tag of this subtree, i.e. P, S, NP, VP, ADVP... """
        return self._head.get("i")

    def match_tag(self, item):
        """ Return True if the given item matches the tag of this subtree
            either fully or partially """
        tag = self.tag
        if tag is None:
            return False
        if self._tag_cache is None:
            tags = self._tag_cache = tag.split("-")
        else:
            tags = self._tag_cache
        if isinstance(item, str):
            item = re.split(r"[_\-]", item) # Split on both _ and -
        if not isinstance(item, list):
            raise ValueError("Argument to match_tag() must be a string or a list")
        return tags[0:len(item)] == item

    @property
    def terminal(self):
        """ The terminal matched by this subtree """
        return self._head.get("t")

    @property
    def variants(self):
        """ The set of variants associated with this subtree's terminal, if any """
        if self._variants is None:
            t = self.terminal
            if t is None:
                self._variants = set()
            else:
                self._variants = set(t.split("_")[1:])
        return self._variants

    @property
    def tcat(self):
        """ The word category associated with this subtree's terminal, if any """
        if self._tcat is None:
            t = self.terminal
            if t is None:
                self._tcat = ""
            else:
                self._tcat = t.split("_")[0]
        return self._tcat

    @property
    def sentences(self):
        """ Generator for the contained sentences """
        if self._sent_cache is None:
            self._sent_cache = [ SimpleTree([[ sent ]], parent = self.parent) for sent in self._sents ]
        return self._sent_cache

    @property
    def has_children(self):
        """ Does this subtree have (proper) children? """
        return bool(self._children)

    @property
    def is_terminal(self):
        """ Is this a terminal node? """
        return self._len == 1 and not self._children

    @property
    def _gen_children(self):
        """ Generator for children of this tree """
        if self._len > 1:
            # More than one sentence: yield'em
            yield from self.sentences
        elif self._children:
            # Proper children: yield'em
            for child in self._children:
                yield SimpleTree([[ child ]], parent = self.parent)

    @property
    def children(self):
        """ Cached generator for children of this tree """
        if self._children_cache is None:
            self._children_cache = tuple(self._gen_children)
        yield from self._children_cache

    @property
    def descendants(self):
        """ Generator for all descendants of this tree, in-order """
        for child in self.children:
            yield child
            yield from child.descendants

    @property
    def deep_children(self):
        """ Generator of generators of children of this tree and its subtrees """
        yield self.children
        for ch in self.children:
            yield from ch.deep_children

    def _tree(self, level):
        """ Return a string containing an indented map of this subtree """
        if level == 0:
            indent = ""
        else:
            indent = "  " * (level - 1) + "+-"
        if self._len > 1 or self._children:
            # Children present: Array or nonterminal
            return indent + (self.tag or "[]") + "".join(
                "\n" + child._tree(level + 1) for child in self.children)
        # No children
        if self._head.get("k") == "PUNCTUATION":
            # Punctuation
            return "{0}'{1}'".format(indent, self.text)
        # Terminal
        return "{0}{1}: '{2}'".format(indent, self.terminal, self.text)

    @property
    def tree(self):
        """ Return a nicely formatted string showing this subtree """
        return self._tree(0)

    # Convert literal terminals that did not have word category specifiers
    # in the grammar (now corrected)
    _replacer = MultiReplacer({
        "\"hans\"" : "pfn_kk_et_ef",
        "\"hennar\"" : "pfn_kvk_et_ef",
        "\"einnig\"" : "ao",
        "\"hinn\"" : "gr_kk_et_þf",
        "'það'_nf_et" : "pfn_hk_et_nf",
        "'hafa'_nh" : "so_nh"
    })

    def _flat(self, level):
        """ Return a string containing an a flat representation of this subtree """
        if self._len > 1 or self._children:
            # Children present: Array or nonterminal
            tag = self.tag or "X" # Unknown tag (should not occur)
            return tag + " " + " ".join(
                child._flat(level + 1) for child in self.children) + " /" + tag
        # No children
        if self._head.get("k") == "PUNCTUATION":
            # Punctuation
            return "p"
        # Terminal
        numwords = self._text.count(" ")
        if not numwords:
            return self._replacer.replace(self.terminal)
        # Multi-word phrase
        if self.tcat == "fs":
            # fs phrase:
            # Return a sequence of ao prefixes before the terminal itself
            return " ".join([ "ao" ] * numwords + [ self.terminal ])
        # Repeat the terminal name for each component word
        # !!! TODO: Potentially divide composite tokens such as
        # !!! dates into more detailed terminals, such as tala, raðnr, etc.
        return " ".join([ self.terminal ] * (numwords + 1))

    @property
    def flat(self):
        """ Return a flat representation of this subtree """
        return self._flat(0)

    def __getattr__(self, name):
        """ Return the first child of this subtree having the given tag """
        name = name.replace("_", "-") # Convert NP_POSS to NP-POSS
        index = 1
        # Check for NP1, NP2 etc., i.e. a tag identifier followed by a number
        s = re.match(r"^(\D+)(\d+)$", name)
        if s:
            name = s.group(1)
            index = int(s.group(2)) # Should never fail
            if index < 1:
                raise AttributeError("Subtree indices start at 1")
        multi = index
        # NP matches NP-POSS, NP-OBJ, etc.
        # NP-OBJ matches NP-OBJ-PRIMARY, NP-OBJ-SECONDARY, etc.
        names = name.split("-")
        for ch in self.children:
            if ch.match_tag(names):
                # Match: check whether it's the requested index
                index -= 1
                if index == 0:
                    # Yes, it is
                    return ch
        # No match
        if multi > index:
            raise AttributeError("Subtree has {0} {1} but index {2} was requested"
                .format(multi - index, name, multi))
        raise AttributeError("Subtree has no {0}".format(name))

    def __getitem__(self, index):
        """ Return the appropriate child subtree """
        if isinstance(index, str):
            # Handle tree['NP']
            try:
                return self.__getattr__(index)
            except AttributeError:
                raise KeyError("Subtree has no {0}".format(index))
        # Handle tree[1]
        if self._children_cache is not None:
            return self._children_cache[index]
        if self._len > 1:
            return SimpleTree([[ self._sents[index] ]], parent = self.parent)
        if self._children:
            return SimpleTree([[ self._children[index] ]], parent = self.parent)
        raise IndexError("Subtree has no children")

    def __len__(self):
        """ Return the length of this subtree, i.e. the last usable child index + 1 """
        if self._len > 1:
            return self._len
        return len(self._children) if self._children else 0

    @property
    def _text(self):
        """ Return the original text within this node only, if any """
        return self._head.get("x", "")

    @property
    def _lemma(self):
        """ Return the lemma of this node only, if any """
        if self._lemma_cache is None:
            lemma = self._head.get("s", self._text)
            if isinstance(lemma, tuple):
                # We have a lazy-evaluation function tuple:
                # call it to obtain the lemma
                f, args = lemma
                lemma = f(*args)
            self._lemma_cache = lemma
        return self._lemma_cache

    @property
    def _cat(self):
        """ Return the word category of this node only, if any """
        return self._head.get("c")

    @property
    def text(self):
        """ Return the original text contained within this subtree """
        if self._text_cache is None:
            if self.is_terminal:
                # Terminal node: return own text
                self._text_cache = self._text
            else:
                # Concatenate the text from the children
                t = []
                for ch in self.children:
                    x = ch.text
                    if x:
                        t.append(x)
                self._text_cache = " ".join(t)
        return self._text_cache

    @property
    def own_text(self):
        return self._text

    def _list(self, filter_func):
        """ Return a list of word lemmas that meet the filter criteria within this subtree """
        if self._len > 1 or self._children:
            # Concatenate the text from the children
            t = []
            for ch in self.children:
                t.extend(ch._list(filter_func))
            return t
        # Terminal node: return own lemma if it matches the given category
        if filter_func(self):
            lemma = self._lemma
            return [ lemma ] if lemma else []
        return []

    @property
    def nouns(self):
        """ Returns the lemmas of all nouns in the subtree """
        return self._list(lambda t: t._cat in {"kk", "kvk", "hk"})

    @property
    def verbs(self):
        """ Returns the lemmas of all verbs in the subtree """
        return self._list(lambda t: t._cat == "so")

    @property
    def persons(self):
        """ Returns all person names occurring in the subtree """

        def is_person(t):
            terminal = t._head.get("t")
            return terminal.split("_")[0] == "person" if terminal else False

        return self._list(is_person)

    @property
    def entities(self):
        """ Returns all entity names occurring in the subtree """

        def is_entity(t):
            terminal = t._head.get("t")
            return terminal.split("_")[0] == "entity" if terminal else False

        return self._list(is_entity)

    @property
    def proper_names(self):
        """ Returns all proper names occurring in the subtree """

        def is_proper_name(t):
            terminal = t._head.get("t")
            return terminal.split("_")[0] == "sérnafn" if terminal else False

        return self._list(is_proper_name)

    @property
    def lemmas(self):
        """ Returns the lemmas of all words in the subtree """
        return self._list(lambda t: True)

    @property
    def lemma(self):
        """ Return the lemmas of this subtree as a string """
        if self.is_terminal:
            # Shortcut for terminal node
            return self._lemma
        return " ".join(self.lemmas)

    @property
    def own_lemma(self):
        return self._lemma if self.is_terminal else ""

    def _all_matches(self, items):
        """ Return all subtree roots, including self, that match the given items,
            compiled from a pattern """
        for subtree in chain([ self ], self.descendants):
            if subtree._match(items):
                yield subtree

    def all_matches(self, pattern):
        """ Return all subtree roots, including self, that match the given pattern """
        items = self._compile(pattern)
        return self._all_matches(items)

    def first_match(self, pattern):
        """ Return the first subtree root, including self, that matches the given
            pattern. If no subtree matches, return None. """
        try:
            return next(iter(self.all_matches(pattern)))
        except StopIteration:
            return None

    class _NestedList(list):

        def __init__(self, kind, content):
            self._kind = kind
            super().__init__()
            if kind == '(':
                # Validate a ( x | y | z ...) construct
                if any(content[i] != '|' for i in range(1, len(content), 2)):
                    raise ValueError("Missing '|' in pattern")
            super().extend(content)

        @property
        def kind(self):
            return self._kind

        def __repr__(self):
            return "<Nested('{0}') ".format(self._kind) + super().__repr__() + ">"

    @classmethod
    def _compile(cls, pattern):

        def nest(items):
            """ Convert any embedded subpatterns, delimited by NEST entries,
                into nested lists """
            len_items = len(items)
            i = 0
            while i < len_items:
                item1 = items[i]
                if item1 in cls._NEST:
                    finisher = cls._NEST[item1]
                    j = i + 1
                    stack = 0
                    while j < len_items:
                        item2 = items[j]
                        if item2 == finisher:
                            if stack > 0:
                                stack -= 1
                            else:
                                nested = cls._NestedList(item1, nest(items[i+1:j]))
                                for n in nested:
                                    if isinstance(n, str) and n in cls._FINISHERS:
                                        raise ValueError("Mismatched '{0}' in pattern".format(n))
                                items = items[0:i] + [ nested ] + items[j+1:]
                                len_items = len(items)
                                break
                        elif item2 == item1:
                            stack += 1
                        j += 1
                    else:
                        # Did not find the starting symbol again
                        raise ValueError("Mismatched '{0}' in pattern".format(item1))
                i += 1
            return items

        # Check whether we've parsed this pattern before, and if so,
        # re-use the result
        if pattern in cls._pattern_cache:
            return cls._pattern_cache[pattern]

        # Not parsed before: do it and cache the result

        def gen1():
            """ First generator: yield non-null strings from a regex split of the pattern """
            for item in re.split(r"\s+|([\.\|\(\)\{\}\[\]\*\+\?\>\$])", pattern):
                if item:
                    yield item

        def gen2():
            gen = gen1()
            while True:
                item = next(gen)
                if item.startswith("'") or item.startswith('"'):
                    # String literal item: merge with subsequent items
                    # until we encounter a matching end quote
                    q = item[0]
                    s = item
                    while not item.endswith(q):
                        item = next(gen)
                        s += " " + item
                    yield s
                else:
                    yield item

        items = nest(list(gen2()))
        # !!! TODO: Limit the cache size, for example by LRU or a periodic purge
        cls._pattern_cache[pattern] = items
        return items

    def match(self, pattern):
        """ Return True if this subtree matches the given pattern """
        return self._match(self._compile(pattern))

    def _match(self, items):
        """ Returns True if this subtree matchs the given items,
            compiled from a string pattern """
        len_items = len(items)

        def single_match(item, tree):
            """ Does the subtree match with item, in and of itself? """
            if isinstance(item, self._NestedList):
                if item.kind == '(':
                    # A list of choices separated by '|': OR
                    for i in range(0, len(item), 2):
                        if single_match(item[i], tree):
                            return True
                return False
            assert isinstance(item, str)
            assert item
            if item in self._NOT_ITEMS:
                raise ValueError("Spurious '{0}' in pattern".format(item))
            if item == ".":
                # Wildcard: always matches
                return True
            if item.startswith('"'):
                # Literal string
                if not tree.is_terminal:
                    return False
                if not item.endswith('"'):
                    raise ValueError("Missing double quote at end of literal")
                # Case-neutral compare
                return item[1:-1].lower() == tree.own_text.lower()
            if item.startswith("'"):
                # Word lemma(s)
                if not tree.is_terminal:
                    return False
                if not item.endswith("'"):
                    raise ValueError("Missing single quote at end of word lemma")
                # !!! Note: the following will also match nonterminal
                # !!! nodes that contain exactly the given lemma
                return item[1:-1] == tree.own_lemma
            if tree.terminal:
                if tree.terminal == item:
                    return True
                ilist = item.split("_")
                # First parts must match (i.e., no_xxx != so_xxx)
                if ilist[0] != tree.tcat:
                    return False
                # Remaining variants must be a subset of those in the terminal
                return set(ilist[1:]) <= tree.variants
            # Check nonterminal tag
            # NP matches NP as well as NP-POSS, etc.,
            # while NP-POSS only matches NP-POSS
            return tree.match_tag(item)

        def unpack(items, ix):
            """ Unpack an argument for the '>' or '>>' containment operators.
                These are usually lists or sets but may be single items, in
                which case they are interpreted as a set having that single item only. """
            item = items[ix]
            if isinstance(item, self._NestedList) and item.kind in { '[', '{' }:
               return item, item.kind
            return items[ix:ix+1], '{' # Single item: assume set

        # noinspection PyUnreachableCode
        def contained(tree, items, pc, deep):
            """ Returns True if the tree has children that match the subsequence
                in items[pc], either directly (deep = False) or at any deeper
                level (deep = True) """

            subseq, kind = unpack(items, pc)
            # noinspection PyUnreachableCode
            if not deep:
                if kind == '[':
                    return run_sequence(tree.children, subseq)
                if kind == '{':
                    return run_set(tree.children, subseq)
                assert False
                return False

            # Deep containment: iterate through deep_children, which is
            # a generator of children generators(!)
            if kind == '[':
                return any(run_sequence(gen_children, subseq) for gen_children in tree.deep_children)
            if kind == '{':
                return any(run_set(gen_children, subseq) for gen_children in tree.deep_children)
            assert False
            return False

        def run_sequence(gen, items):
            """ Match the child nodes of gen with the items, in sequence """
            len_items = len(items)
            # Program counter (index into items)
            pc = 0
            try:
                tree = next(gen)
                while pc < len_items:
                    item = items[pc]
                    pc += 1
                    repeat = None
                    stopper = None
                    if pc < len_items:
                        if items[pc] in { '*', '+', '?', '>' }:
                            # Repeat specifier
                            repeat = items[pc]
                            pc += 1
                            if item == '.' and repeat in { '*', '+', '?' }:
                                # Limit wildcard repeats if the following item
                                # is concrete, i.e. non-wildcard and non-end
                                if pc < len_items:
                                    if isinstance(items[pc], self._NestedList):
                                        if items[pc].kind == '(':
                                            stopper = items[pc]
                                    elif items[pc] not in { '.', '$' }:
                                        stopper = items[pc]
                    if item == '$':
                        # Only matches at the end of the list
                        result = pc >= len_items
                    else:
                        result = single_match(item, tree)
                    if repeat is None:
                        # Plan item-for-item match
                        if not result:
                            return False
                        tree = next(gen)
                    elif repeat == '+':
                        if not result:
                            return False
                        while result:
                            tree = next(gen)
                            if stopper is not None:
                                result = not single_match(stopper, tree)
                            else:
                                result = single_match(item, tree)
                    elif repeat == '*':
                        if stopper is not None:
                            result = not single_match(stopper, tree)
                        while result:
                            tree = next(gen)
                            if stopper is not None:
                                result = not single_match(stopper, tree)
                            else:
                                result = single_match(item, tree)
                    elif repeat == '?':
                        if stopper is not None:
                            result = not single_match(stopper, tree)
                        if result:
                            tree = next(gen)
                    elif repeat == '>':
                        if not result:
                            # No containment if the head item does not match
                            return False
                        op = '>'
                        if pc < len_items and items[pc] == '>':
                            # '>>' operator: arbitrary depth containment
                            pc += 1
                            op = '>>'
                        if pc >= len_items:
                            raise ValueError("Missing argument to '{0}' operator".format(op))
                        result = contained(tree, items, pc, op == '>>')
                        if not result:
                            return False
                        pc += 1
                        tree = next(gen)
            except StopIteration:
                # Skip any nullable items
                while pc + 1 < len_items and items[pc + 1] in {'*', '?'}:
                    item = items[pc]
                    # Do error checking while we're at it
                    if isinstance(item, str) and item in self._NOT_ITEMS:
                        raise ValueError("Spurious '{0}' in pattern".format(item))
                    pc += 2
                if pc < len_items:
                    if items[pc] == '$':
                        # Iteration done: move past the end-of-list marker, if any
                        pc += 1
                else:
                    if pc > 0 and items[pc - 1] == '$':
                        # Gone too far: back up
                        pc -= 1
            else:
                if len_items and items[-1] == '$':
                    # Found end marker but the child iterator is not
                    # complete: return False
                    return False
            return pc >= len_items

        def run_set(gen, items):
            """ Run through the subtrees (children) yielded by gen,
                matching them set-wise (unordered) with the items.
                If all items are eventually matched, return True,
                otherwise False. """
            len_items = len(items)
            # Keep a set of items that have not yet been matched
            # by one or more tree nodes
            unmatched = set(range(len_items))
            for tree in gen:
                pc = 0
                while pc < len_items:
                    item_pc = pc
                    item = items[pc]
                    pc += 1
                    result = single_match(item, tree)
                    if pc < len_items and items[pc] == '>':
                        # Containment: Not a match unless the children match as well
                        pc += 1
                        op = '>'
                        if pc < len_items and items[pc] == '>':
                            # Deep match
                            op = '>>'
                            pc += 1
                        if pc >= len_items:
                            raise ValueError("Missing argument to '{0}' operator".format(op))
                        if result:
                            # Further constrained by containment
                            result = contained(tree, items, pc, op == '>>')
                        pc += 1
                        # Always cut away the 'dummy' extra items corresponding
                        # to the '>' (or '>>') and its argument
                        unmatched -= { pc - 1, pc - 2 }
                        if op == '>>':
                            unmatched -= { pc - 3 }
                    if result:
                        # We have a match
                        unmatched -= { item_pc }
                    if not unmatched:
                        # We have a complete match already: Short-circuit
                        return True
            # Return True if all items got matched at some point
            # by a tree node, otherwise False
            return False

        return run_set(iter([ self ]), items)


class SimpleTreeBuilder:

    """ A class for building a simplified tree from a full
        parse tree. The simplification is done according to the
        maps provided in the constructor. """

    def __init__(self, nt_map = None, id_map = None, terminal_map = None):
        self._nt_map = nt_map or _DEFAULT_NT_MAP
        self._id_map = id_map or _DEFAULT_ID_MAP
        self._terminal_map = terminal_map or _DEFAULT_TERMINAL_MAP
        self._result = []
        self._stack = [ self._result ]
        self._scope = [ NotImplemented ] # Sentinel value
        self._pushed = []

    def push_terminal(self, d):
        """ At a terminal (token) node. The d parameter is normally a dict
            containing a canonicalized token. """
        # Check whether this terminal should be pushed as a nonterminal
        # with a single child
        cat = d["t"].split("_")[0] if "t" in d else None
        mapped_t = self._terminal_map.get(cat)
        if mapped_t is None:
            # No: add as a child of the current node in the condensed tree
            self._stack[-1].append(d)
        else:
            # Yes: create an intermediate nonterminal with this terminal
            # as its only child
            self._stack[-1].append(dict(k = "NONTERMINAL",
                n = mapped_t, i = mapped_t, p = [ d ]))

    def push_nonterminal(self, nt_base):
        """ Entering a nonterminal node. Pass None if the nonterminal is
            not significant, e.g. an interior or optional node. """
        self._pushed.append(False)
        if not nt_base:
            return
        mapped_nt = self._nt_map.get(nt_base)
        if not mapped_nt:
            return
        # We want this nonterminal in the simplified tree:
        # push it (unless it is subject to a scope we're already in)
        mapped_id = self._id_map[mapped_nt]
        subject_to = mapped_id.get("subject_to")
        if subject_to is not None and self._scope[-1] in subject_to:
            # We are already within a nonterminal to which this one is subject:
            # don't bother pushing it
            return
        # This is a significant and noteworthy nonterminal
        children = []
        self._stack[-1].append(dict(k = "NONTERMINAL",
            n = mapped_id["name"], i = mapped_nt, p = children))
        self._stack.append(children)
        self._scope.append(mapped_nt)
        self._pushed[-1] = True

    def pop_nonterminal(self):
        """ Exiting a nonterminal node. Calls to pop_nonterminal() must correspond
            to calls to push_nonterminal(). """
        if not self._pushed.pop():
            # Didn't push anything significant in push_nonterminal(): nothing to be done
            return
        children = self._stack.pop()
        mapped_nt = self._scope.pop()
        # Check whether this nonterminal has only one child, which is again
        # the same nonterminal - or a nonterminal which the parent overrides
        if len(children) == 1:

            ch0 = children[0]

            def collapse_child(d):
                """ Determine whether to cut off a child and connect directly
                    from this node to its children """
                if ch0["i"] == d:
                    # Same nonterminal category: do the cut
                    return True
                # If the child is a nonterminal that this one 'overrides',
                # cut off the child
                override = self._id_map[d].get("overrides")
                return ch0["i"] == override

            def replace_parent(d):
                """ Determine whether to replace the parent with the child """
                # If the child overrides the parent, replace the parent
                override = self._id_map[ch0["i"]].get("overrides")
                return d == override

            if ch0["k"] == "NONTERMINAL":
                if collapse_child(mapped_nt):
                    # If so, we eliminate one level and move the children of the child
                    # up to be children of this node
                    self._stack[-1][-1]["p"] = ch0["p"]
                elif replace_parent(mapped_nt):
                    # The child subsumes the parent: replace
                    # the parent by the child
                    self._stack[-1][-1] = ch0

    @property
    def result(self):
        return self._result[0]

    @property
    def tree(self):
        return SimpleTree([[ self.result ]])


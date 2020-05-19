"""

    Reynir: Natural language processing for Icelandic

    Matcher module

    Copyright (c) 2020 Miðeind ehf.

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


    This module exports the function match_pattern() which can determine
    whether a SimpleTree instance matches a pattern string.

    The match patterns are as follows:
    ----------------------------------

    `.` matches any tree node

    `"literal"` matches a subtree covering exactly the given literal text,
        albeit case-neutral

    `'lemma'` matches a subtree covering exactly the given word lemma(s)

    `NONTERMINAL` matches the given nonterminal

    `terminal` matches the given terminal
    `terminal_var1_var2` matches a terminal having at least the given variants

    `%macro` is resolved by looking up the key 'macro' in the context
    dictionary, which is an optional parameter to match_pattern(). The corresponding
    value can be either a string, in which case the string is used as the pattern,
    or a callable (function) which is then called with a tree node as an argument.
    If the function returns a bool, that is the result of the match. Otherwise, it
    should return a string, which is used as the pattern.

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

from typing import Dict
import re


class _NestedList(list):

    """ Quick-and-dirty container for nested lists """

    def __init__(self, kind, content):
        self._kind = kind
        super().__init__()
        if kind == "(":
            # Validate a ( x | y | z ...) construct
            if any(content[i] != "|" for i in range(1, len(content), 2)):
                raise ValueError("Missing '|' in pattern")
        super().extend(content)

    @property
    def kind(self):
        return self._kind

    def __repr__(self):
        return "<Nested('{0}') ".format(self._kind) + super().__repr__() + ">"


# Reserved strings in matching expressions
_NOT_ITEMS = frozenset((">", "*", "+", "?", "[", "(", "{", "]", ")", "}", "$"))


class _CompiledPattern:

    """ This class encapsulates a matching pattern that has
        been parsed into a nested list of matching items """

    _NEST = {"(": ")", "[": "]", "{": "}"}
    _FINISHERS = frozenset(_NEST.values())

    _pattern_cache = dict()  # type: Dict[str, _CompiledPattern]

    @classmethod
    def compile(cls, pattern):
        """ Check whether we've parsed this pattern before, and if so,
            re-use the result """
        if pattern in cls._pattern_cache:
            return cls._pattern_cache[pattern]
        # Not already in cache: compile the pattern and cache it
        cp = cls._pattern_cache[pattern] = cls(pattern)
        return cp

    def __init__(self, pattern):
        self._items = self._compile(pattern)

    @property
    def items(self):
        """ Return the embedded nested list of matching items """
        return self._items

    def _compile(self, pattern):
        """ Compile a matching pattern into a nested list of matching items """

        NEST = self._NEST
        FINISHERS = self._FINISHERS

        def nest(items):
            """ Convert any embedded subpatterns, delimited by NEST entries,
                into nested lists """
            len_items = len(items)
            i = 0
            while i < len_items:
                # Look for symbols that open a nested structure
                item1 = items[i]
                finisher = NEST.get(item1)
                if finisher is not None:
                    # item1 is an opening symbol for a nested structure,
                    # finishing with the finisher symbol
                    j = i + 1
                    stack = 0
                    while j < len_items:
                        item2 = items[j]
                        if item2 == finisher:
                            if stack > 0:
                                # Finishing a nested occurrence of the
                                # same opening symbol
                                stack -= 1
                            else:
                                # Finishing the sequence started by the
                                # current opening symbol
                                nested = _NestedList(item1, nest(items[i + 1 : j]))
                                # Check for nesting errors
                                for n in nested:
                                    if isinstance(n, str) and n in FINISHERS:
                                        raise ValueError(
                                            "Mismatched '{0}' in pattern".format(n)
                                        )
                                # Assemble the resulting nested list
                                items = items[0:i] + [nested] + items[j + 1 :]
                                len_items = len(items)
                                # ...and continue the outer loop
                                break
                        elif item2 == item1:
                            # Nested occurrence of the same opening symbol
                            stack += 1
                        j += 1
                    else:
                        # Did not find the starting symbol again
                        raise ValueError("Mismatched '{0}' in pattern".format(item1))
                i += 1
            return items

        def gen1():
            """ First generator: yield non-null strings from a
                regex split of the pattern """
            for item in re.split(r"\s+|([\.\|\(\)\{\}\[\]\*\+\?\>\$])", pattern):
                if item:
                    yield item

        def gen2():
            gen = gen1()
            while True:
                try:
                    item = next(gen)
                except StopIteration:
                    # Generators should not raise StopIteration,
                    # so we just break out of the loop normally
                    break
                if item.startswith("'") or item.startswith('"'):
                    # String literal item: merge with subsequent items
                    # until we encounter a matching end quote
                    q = item[0]
                    s = item
                    while not item.endswith(q):
                        item = next(gen)
                        s += " " + item
                    if len(s) < 3 or s[0] != s[-1]:
                        raise ValueError("Malformed literal in pattern")
                    yield s
                else:
                    yield item

        return nest(list(gen2()))


def single_match(item, tree, context):
    """ Does the subtree match with item, in and of itself? """
    if isinstance(item, _NestedList):
        if item.kind == "(":
            # A list of choices separated by '|': OR
            return any(
                single_match(item[i], tree, context) for i in range(0, len(item), 2)
            )
        return False
    assert isinstance(item, str)
    if context is not None and item.startswith("%"):
        # The item has the form %identifier (it's a macro-type item):
        # Look it up in the context dictionary, which can either return a
        # string directly, or a function to call with the tree
        # as an argument. This function can either return a bool result, or
        # a string that we use for the item.
        result = context.get(item[1:])
        if callable(result):
            # The macro resolves to a function: call it with the tree as an argument
            result = result(tree)
            if isinstance(result, bool):
                # The function yielded a bool result: return it
                return result
        if result is None:
            raise ValueError("Macro '{0}' not found in context".format(item[1:]))
        if not isinstance(result, str):
            raise ValueError(
                "Macro '{0}' must yield a callable or string".format(item[1:])
            )
        # Use the string retrieved from the context as the item to match
        item = result
    if item in _NOT_ITEMS:
        raise ValueError("Spurious '{0}' in pattern".format(item))
    if item == ".":
        # Wildcard: always matches
        return True
    if item.startswith('"'):
        # Double quote: literal string
        # Note that this is a case-neutral compare
        return item[1:-1].casefold() == tree.text.casefold()
    if item.startswith("'"):
        # Single quote: match word lemma(s) of the subtree
        # Note that this is a case-significant compare
        return item[1:-1] == tree.lemma
    if tree.terminal:
        if tree.terminal == item:
            return True
        ilist = item.split("_")
        # First parts must match (i.e., no_xxx != so_xxx)
        if ilist[0] != tree.tcat:
            return False
        # Remaining variants must be a subset of those in the terminal
        return set(ilist[1:]) <= set(tree.variants)
    # Check nonterminal tag
    # NP matches NP as well as NP-POSS, etc.,
    # while NP-POSS only matches NP-POSS
    return tree.match_tag(item)


def unpack(items, ix):
    """ Unpack an argument for the '>' or '>>' containment operators.
        These are usually lists or sets but may be single items, in
        which case they are interpreted as a set having
        that single item only. """
    item = items[ix]
    if isinstance(item, _NestedList) and item.kind in {"[", "{"}:
        return item, item.kind
    return items[ix : ix + 1], "{"  # Single item: assume set


def contained(tree, items, pc, deep, context):
    """ Returns True if the tree has children that match the subsequence
        in items[pc], either directly (deep = False) or at any deeper
        level (deep = True) """
    subseq, kind = unpack(items, pc)
    if kind == "[":
        f_run = run_sequence
    elif kind == "{":
        f_run = run_set
    else:
        assert False
        return False
    # Deep containment: iterate through deep_children, which is
    # a generator of children generators(!)
    if deep:
        return any(
            f_run(gen_children, subseq, context)
            for gen_children in tree.deep_children
        )
    # Shallow containment: iterate through direct children
    return f_run(tree.children, subseq, context)


def run_sequence(gen, items, context):
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
                if items[pc] in {"*", "+", "?", ">"}:
                    # Repeat specifier
                    repeat = items[pc]
                    pc += 1
                    if item == "." and repeat in {"*", "+", "?"}:
                        # Limit wildcard repeats if the following item
                        # is concrete, i.e. non-wildcard and non-end
                        if pc < len_items:
                            if isinstance(items[pc], _NestedList):
                                if items[pc].kind == "(":
                                    stopper = items[pc]
                            elif items[pc] not in {".", "$"}:
                                stopper = items[pc]
            if item == "$":
                # Only matches at the end of the list
                result = pc >= len_items
            else:
                result = single_match(item, tree, context)
            if repeat is None:
                # Plain item-for-item match
                if not result:
                    return False
                tree = next(gen)
            elif repeat == "+":
                if not result:
                    return False
                while result:
                    tree = next(gen)
                    if stopper is not None:
                        result = not single_match(stopper, tree, context)
                    else:
                        result = single_match(item, tree, context)
            elif repeat == "*":
                if stopper is not None:
                    result = not single_match(stopper, tree, context)
                while result:
                    tree = next(gen)
                    if stopper is not None:
                        result = not single_match(stopper, tree, context)
                    else:
                        result = single_match(item, tree, context)
            elif repeat == "?":
                if stopper is not None:
                    result = not single_match(stopper, tree, context)
                if result:
                    tree = next(gen)
            elif repeat == ">":
                if not result:
                    # No containment if the head item does not match
                    return False
                op = ">"
                if pc < len_items and items[pc] == ">":
                    # '>>' operator: arbitrary depth containment
                    pc += 1
                    op = ">>"
                if pc >= len_items:
                    raise ValueError(
                        "Missing argument to '{0}' operator".format(op)
                    )
                result = contained(tree, items, pc, op == ">>", context)
                if not result:
                    return False
                pc += 1
                tree = next(gen)
    except StopIteration:
        # Skip any nullable items
        # Note: we are deliberately not using a set here; items[] may be non-hashable
        while pc + 1 < len_items and items[pc + 1] in ("*", "?"):
            item = items[pc]
            # Do error checking while we're at it
            if isinstance(item, str) and item in _NOT_ITEMS:
                raise ValueError("Spurious '{0}' in pattern".format(item))
            pc += 2
        if pc < len_items:
            if items[pc] == "$":
                # Iteration done: move past the end-of-list marker, if any
                pc += 1
        else:
            if pc > 0 and items[pc - 1] == "$":
                # Gone too far: back up
                pc -= 1
    else:
        if len_items and items[-1] == "$":
            # Found end marker but the child iterator is not
            # complete: return False
            return False
    return pc >= len_items


def run_set(gen, items, context):
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
            result = single_match(item, tree, context)
            if pc < len_items and items[pc] == ">":
                # Containment: Not a match unless the children match as well
                pc += 1
                op = ">"
                if pc < len_items and items[pc] == ">":
                    # Deep match
                    op = ">>"
                    pc += 1
                if pc >= len_items:
                    raise ValueError(
                        "Missing argument to '{0}' operator".format(op)
                    )
                if result:
                    # Further constrained by containment
                    result = contained(tree, items, pc, op == ">>", context)
                pc += 1
                # Always cut away the 'dummy' extra items corresponding
                # to the '>' (or '>>') and its argument
                unmatched -= {pc - 1, pc - 2}
                if op == ">>":
                    unmatched -= {pc - 3}
            if result:
                # We have a match
                unmatched -= {item_pc}
            if not unmatched:
                # We have a complete match already: Short-circuit
                return True
    # Return True if all items got matched at some point
    # by a tree node, otherwise False
    return False


def match_pattern(tree, pattern, context=None):
    """ Return the result of a pattern match on a SimpleTree instance """
    cp = _CompiledPattern.compile(pattern)
    return run_set(iter([tree]), cp.items, context)

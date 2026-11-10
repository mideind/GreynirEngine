"""

    Greynir: Natural language processing for Icelandic

    Reducer module

    Copyright © 2026 Miðeind ehf.
    Original author: Vilhjálmur Þorsteinsson

    This software is licensed under the MIT License:

        Permission is hereby granted, free of charge, to any person
        obtaining a copy of this software and associated documentation
        files (the "Software"), to deal in the Software without restriction,
        including without limitation the rights to use, copy, modify, merge,
        publish, distribute, sublicense, and/or sell copies of the Software,
        and to permit persons to whom the Software is furnished to do so,
        subject to the following conditions:

        The above copyright notice and this permission notice shall be
        included in all copies or substantial portions of the Software.

        THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
        EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
        MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
        IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
        CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
        TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
        SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

    The classes within this module reduce a parse forest containing
    multiple possible parses of a sentence to a single most likely
    parse tree.

    The reduction uses five methods:

  * First, a dictionary of preferred token interpretations (fetched
    from config/Prefs.conf), where words like 'ekki' are classified
    as being more likely to be from one category than another
    (in this case adverb rather than noun);

  * Second, a set of general heuristics (adverbs being by default less
    preferred than other categories, etc.);

  * Third, production priorities within nonterminals, as specified
    using > signs between productions in Greynir.grammar;

  * Fourth, scores explicitly assigned to nonterminals in Greynir.grammar
    and verb forms in Verbs.conf using the $score() pragma;

  * Fifth, verb-preposition matching where particular combinations
    of prepositions with verbs (eventually including verb objects
    in particular cases) receive bonus scores. For instance,
    "Dómarinn frestaði mótinu vegna veðurs" ("The referee postponed
    the competition due to weather") will attach the preposition
    "vegna veðurs" to the verb "fresta" with an argument in the
    dative case, instead of to the noun "mótinu".

    The verb-preposition matching is driven by the configuration file
    config/Verbs.conf. (This file was originally generated from data
    generously provided by Eiríkur Rögnvaldsson, professor emeritus
    of linguistics at the University of Iceland, whom we thank).

    The parse forest is created by the enhanced Earley parser in
    fastparser.py. It is packed in an SPPF (Shared Packed Parse Forest)
    structure, where identical subtrees (with identical token spans)
    are shared rather than being duplicated throughout the parse forest.

    When calculating scores for different productions (families of children)
    of nonterminals, we take advantage of the SPPF data structure to minimize
    parse forest navigation via memoization. In other words, we only calculate
    the score of each shared packed subtree once, memoizing the result for
    subsequent lookup.

    However, verb-preposition matching limits this optimization. A shared
    packed preposition phrase subtree may have different scores depending
    on its verb - or non-verb - contexts. We must thus be careful to
    memoize the score of these nodes by context, so that the scores
    between contexts can be different.

    This is done by memoizing subtree scores on the tuple (node, context
    signature), where the context signature captures the two pieces of
    reducer state that a subtree score can depend on: the preposition
    bonus verbs in effect (established by nodes tagged "enable_prep_bonus",
    typically SagnInnskot) and the current verb (which an enclosed
    "enable_prep_bonus" node would capture). Nodes that reset both on
    entry - those tagged "begin_prep_scope", and noun phrase nonterminals
    ("Nl_*") - are context-independent and get a neutral signature,
    preserving full sharing of their memoized scores. The preposition
    nodes that actually receive different scores depending on the context
    are terminal nodes whose names have the form fs_*.

    The scoring and reduction described above is normally not done by the
    Python code in this module, but by C++ code that replicates it exactly
    (ereducer.cpp), working on the parse forest before any Python objects
    are created for it; see Reducer.parse_and_reduce(). The Python code is
    the reference for the C++ code, and is used when the C++ code can't
    be (see Reducer._native_allowed()). The two must be kept in step: a
    change to the logic here must be made in ereducer.cpp as well, and
    verified with the environment variable GREYNIR_REDUCER_PARITY set.

"""

from typing import (
    Callable,
    Dict,
    DefaultDict,
    Iterable,
    List,
    Set,
    Tuple,
    Optional,
    Any,
    cast,
)
from typing_extensions import TypedDict, Required

import os
from collections import defaultdict
from threading import Lock
from types import MappingProxyType

from tokenizer import Tok
from tokenizer.definitions import BIN_Tuple

from .grammar import Grammar, Production
from .fastparser import (
    Fast_Parser,
    Node,
    ParseForestNavigator,
    ParseJob,
    eparser,
    ffi,
    ffi_NULL,
)
from .settings import Preferences, NounPreferences
from .verbframe import VerbFrame
from .binparser import BIN_Token, BIN_Terminal


# Types for data used in the reduction process

VerbTuple = Tuple[BIN_Terminal, BIN_Token]
VerbList = List[VerbTuple]


class ResultDict(TypedDict, total=False):
    # Score
    sc: Required[int]
    # Verb scope information
    so: VerbList
    sl: VerbList
    # Text of an adverb matched by a literal terminal (only at token nodes)
    ao: str
    # Text of a verb particle (SagnÖgn), passed to the enclosing verb phrase
    pcl: str


VerbStack = List[Optional[VerbList]]
ChildDict = DefaultDict[int, ResultDict]
ScoreDict = Dict[int, Dict[BIN_Terminal, int]]
BonusCache = Dict[Tuple[BIN_Terminal, str, BIN_Terminal, BIN_Token], int]
FinalsDict = Dict[int, Set[BIN_Terminal]]
TokensDict = Dict[int, BIN_Token]
# Winning family index and the (child, context signature) pairs
# that the reduction pass should descend into
DecisionTuple = Tuple[int, List[Tuple[Node, Any]]]

# Reducer result dictionary with a null score, shared between
# empty nodes; wrapped in a read-only proxy so that it cannot
# be corrupted by accidental modification
NULL_SC: ResultDict = cast(ResultDict, MappingProxyType({"sc": 0}))

_VERB_PREP_BONUS = 7  # Give 7 extra points for a verb/preposition match
_VERB_PREP_PENALTY = -2  # Subtract 2 points for a non-match
# Bonus for a verb particle (SagnÖgn) preceding the object, e.g. 'bjó til hús',
# if the particle is listed for the verb in Verbs.conf (*til); otherwise
# a penalty, which must outweigh _VERB_PREP_PENALTY so that a preposition
# reading is preferred for verbs that do not take the particle
_VERB_PARTICLE_BONUS = 7
_VERB_PARTICLE_PENALTY = -6
# Penalty for a verb terminal whose argument cases are only licensed by
# frames with a reflexive pronoun ('eiga sér |þf' -> eiga_þgf_þf), so that
# a reading with arbitrary objects in those cases is discouraged
_VERB_WEAK_ONLY_PENALTY = -6
_LENGTH_BONUS_FACTOR = 10  # For length bonus, multiply number of tokens by this factor

_CASES_SET = BIN_Token.CASES_SET

# Penalties for verb forms with a cliticized subject ('ertu', 'viltu')
# when the token also has an adjective reading ('næstu', 'mestu') or
# a regular verb reading ('áttu', 'yrðu')
_CLITIC_ADJECTIVE_PENALTY = -40
_CLITIC_VERB_PENALTY = -6
_CONTAINED_VERBS_SET = frozenset(("begin_prep_scope", "purge_verb"))

# BÍN categories ('fl') of person and entity names
_NAMED_ENTITY_FL = frozenset(
    ("ism", "erm", "gæl", "nafn", "föð", "móð", "ætt", "entity")
)


# Flags that describe nonterminals and terminals to the C++ reducer
# (see the RN_* and RT_* constants in eparser.h)
_NT_TAG_FLAGS = (
    ("enable_prep_bonus", 0x0001),
    ("begin_prep_scope", 0x0002),
    ("verb_particle", 0x0008),
    ("apply_particle_bonus", 0x0010),
    ("apply_length_bonus", 0x0020),
    ("apply_prep_bonus", 0x0040),
    ("pick_up_verb", 0x0080),
    ("purge_verb", 0x0100),
    ("no_reduce", 0x0200),
)
_NT_FLAG_NOUN_PHRASE = 0x0004
_T_FLAG_AO_LITERAL = 0x01
_T_FLAG_FS = 0x02
_T_FLAG_SO = 0x04


class _ReductionScope:

    """Class to accumulate information about a nonterminal and its
    child productions during reduction"""

    __slots__ = ("reducer", "sc", "keys", "pushed_prep_bonus", "start_verb", "nt")

    def __init__(self, reducer: "ParseForestReducer", node: Node) -> None:
        self.reducer = reducer
        # Child tree scores
        self.sc: ChildDict = defaultdict(lambda: {"sc": 0})
        # Content-based tie-break keys, by family index
        self.keys: Dict[int, Any] = {}
        # We are only interested in completed nonterminals
        nt = node.nonterminal if node.is_completed else None
        self.nt = nt
        # Verb/preposition matching stuff
        self.pushed_prep_bonus = False
        verb = reducer.get_current_verb()
        if nt:
            if nt.has_tag("enable_prep_bonus"):
                # SagnInnskot has this tag
                reducer.push_prep_bonus(None if verb is None else verb[:])
                self.pushed_prep_bonus = True
            elif nt.has_tag("begin_prep_scope") or nt.is_noun_phrase:
                # Setning and SetningÁnF have this tag, and we also
                # enter a new prep bonus scope in noun phrases
                reducer.push_prep_bonus(None)
                self.pushed_prep_bonus = True
                verb = None
        reducer.push_current_verb(verb)
        self.start_verb = verb

    def start_family(
        self, ix: int, prod: Production, children: Iterable[Optional[Node]]
    ) -> None:
        """Start the processing of a production (numbered ix) of a nonterminal"""
        # Initialize the score of this family of children, so that productions
        # with higher priorities (more negative prio values) get a starting bonus
        self.sc[ix]["sc"] = -10 * prod.priority
        # Remember a content-based key for this family, used to break
        # ties between equally scored families deterministically.
        # The family index itself reflects the order in which the Earley
        # parser completed the derivations, which shifts with unrelated
        # grammar edits. Instead, the production that appears first in
        # the grammar wins, and between derivations of the same
        # production, the one with the longest leading children wins.
        self.keys[ix] = (
            -prod.index,
            tuple((ch.start, ch.end) for ch in children if ch is not None),
        )
        self.reducer.set_current_verb(self.start_verb)

    def add_child(self, ix: int, rd: ResultDict) -> None:
        """Add a child node's score to the parent family's score,
        where the parent family has index ix (0..n)"""
        d = self.sc[ix]
        d["sc"] += rd.get("sc", 0)
        if "ao" in rd and self.nt is not None and self.nt.has_tag("verb_particle"):
            # A verb particle (SagnÖgn): note its text so that the enclosing
            # verb phrase can check it against the verb's frames
            d["pcl"] = rd["ao"]
        elif "pcl" in rd:
            # Carry the particle up to the enclosing verb phrase
            d["pcl"] = rd["pcl"]
        # Carry information about contained verbs ("so") up the tree
        for key in ("so", "sl"):
            if key in rd:
                if key in d:
                    d[key].extend(rd[key])  # type: ignore
                else:
                    d[key] = rd[key][:]  # type: ignore
                if key == "sl":
                    self.reducer.set_current_verb(rd["sl"])

    def process(self, node: Node) -> Tuple[ResultDict, int]:
        """After accumulating scores for all possible productions
        of this nonterminal (families of children), find the
        highest scoring one and return its result dict along with
        its family index. The actual reduction of the tree is
        deferred to a separate pass, once all contexts in which
        this node occurs have been scored."""
        try:

            csc = self.sc
            if not csc:
                # Empty node
                return NULL_SC, 0

            nt = node.nonterminal if node.is_completed else None

            if nt is not None and nt.has_tag("apply_particle_bonus"):
                # Sögn_1 & co.: adjust the score of each family containing
                # a verb particle (SagnÖgn) by whether the verb(s) take it
                for d in csc.values():
                    pcl = d.pop("pcl", None)
                    if pcl is not None:
                        d["sc"] += self.reducer.verb_particle_bonus(pcl, d.get("so"))

            if len(csc) == 1:
                # Not ambiguous: only one result, do a shortcut
                # Will raise an exception if not exactly one item
                [(ix, sc)] = csc.items()
            else:
                # Find the best scoring family, breaking ties by the
                # content-based family key (see start_family()) and
                # only as a last resort by the family index
                keys = self.keys
                ix, sc = max(
                    csc.items(), key=lambda x: (x[1]["sc"], keys[x[0]], -x[0])
                )

            if nt is not None:
                # Adjust the winning family's score. Note that sc is this
                # node's own accumulator dict (created in add_child()),
                # not a child's memoized dict, so we can modify it freely.
                # Get score adjustment for this nonterminal, if any
                # (This is the $score(+/-N) pragma from Greynir.grammar)
                sc["sc"] += self.reducer._score_adj.get(nt, 0)

                if nt.has_tag("apply_length_bonus"):
                    # Give this nonterminal a bonus depending on how many tokens
                    # it encloses
                    bonus = (node.end - node.start - 1) * _LENGTH_BONUS_FACTOR
                    sc["sc"] += bonus

                if (
                    nt.has_tag("apply_prep_bonus")
                    and self.reducer.get_prep_bonus() is not None
                ):
                    # This is a nonterminal that we like to see in a verb/prep context
                    # An example is Dagsetning which we like to be associated
                    # with a verb rather than a noun phrase
                    sc["sc"] += _VERB_PREP_BONUS

                if nt.has_tag("pick_up_verb"):
                    verb = sc.get("so")
                    if verb is not None:
                        sc["sl"] = verb[:]

                if nt.has_any_tag(_CONTAINED_VERBS_SET):
                    # Delete information about contained verbs
                    # SagnRuna, EinSetningÁnF, SagnHluti, NhFyllingAtv
                    # and Setning have this tag
                    sc.pop("so", None)  # Simpler than if "so" in sc: del sc["so"]
                    sc.pop("sl", None)
                    sc.pop("pcl", None)

            return sc, ix

        finally:
            # Make sure we pop everything that was pushed in __init__()
            if self.pushed_prep_bonus:
                self.reducer.pop_prep_bonus()
            self.reducer.pop_current_verb()


class ParseForestReducer:

    """Subclass to navigate a parse forest and reduce it
    so that the highest-scoring alternative production of a nonterminal
    (family of children) survives at each point of ambiguity"""

    def __init__(self, grammar: Grammar, scores: ScoreDict) -> None:
        super().__init__()
        # scores contains the token-terminal matching scores
        self._scores = scores
        self._grammar = grammar
        self._score_adj = grammar._nt_scores
        self._prep_bonus_stack: VerbStack = [None]
        self._current_verb_stack: VerbStack = [None]
        self._bonus_cache: BonusCache = dict()

    def push_prep_bonus(self, val: Optional[VerbList]) -> None:
        self._prep_bonus_stack.append(val)

    def pop_prep_bonus(self) -> None:
        self._prep_bonus_stack.pop()

    def get_prep_bonus(self) -> Optional[VerbList]:
        return self._prep_bonus_stack[-1]

    def push_current_verb(self, val: Optional[VerbList]) -> None:
        self._current_verb_stack.append(val)

    def pop_current_verb(self) -> None:
        self._current_verb_stack.pop()

    def get_current_verb(self) -> Optional[VerbList]:
        return self._current_verb_stack[-1]

    def set_current_verb(self, val: Optional[VerbList]) -> None:
        self._current_verb_stack[-1] = val

    def verb_prep_bonus(
        self,
        prep_terminal: BIN_Terminal,
        prep_token: str,
        verb_terminal: BIN_Terminal,
        verb_token: BIN_Token,
    ) -> int:
        """Return a verb/preposition match bonus, as and if applicable"""
        # Only do this if the prepositions match the verb being connected to
        m = verb_token.match_with_meaning(verb_terminal)
        assert isinstance(m, BIN_Tuple)
        verb = m.stofn
        if "MM" in m.beyging:
            # Use MM-NH nominal form for MM verbs,
            # i.e. "eignast" instead of "eiga" for a verb such as "eignaðist"
            verb = BIN_Token.mm_verb_stem(verb)
        verb_with_cases = verb + verb_terminal.verb_cases
        if prep_terminal.num_variants:
            # Normal terminal, such as fs_ef
            prep_case = prep_terminal.variant(0)
            if prep_case in _CASES_SET:
                prep_with_case = prep_token + "_" + prep_case
            else:
                # Probably fs_nh: match all cases (note: _nh is hereby cut off)
                prep_with_case = prep_token
        else:
            # Literal terminal, such as "á:fs" - match all cases
            prep_with_case = prep_token
        # Do a lookup in the verb/preposition lexicon from the settings
        # (typically stored in VerbPrepositions.conf)
        if VerbFrame.matches_preposition(verb_with_cases, prep_with_case):
            # If the verb clicks with the given preposition in the
            # given case, give a healthy bonus
            return _VERB_PREP_BONUS
        # If no match, discourage
        return _VERB_PREP_PENALTY

    def verb_particle_bonus(self, particle: str, verbs: Optional[VerbList]) -> int:
        """Return a bonus if any of the given verbs takes the particle
        according to its frames in Verbs.conf, otherwise a penalty"""
        if verbs:
            for verb_terminal, verb_token in verbs:
                m = verb_token.match_with_meaning(verb_terminal)
                assert isinstance(m, BIN_Tuple)
                verb = m.stofn
                if "MM" in m.beyging:
                    verb = BIN_Token.mm_verb_stem(verb)
                verb_with_cases = verb + verb_terminal.verb_cases
                if VerbFrame.matches_particle(verb_with_cases, "*" + particle):
                    return _VERB_PARTICLE_BONUS
        return _VERB_PARTICLE_PENALTY

    def native_prep_bonus(
        self,
        job: ParseJob,
        prep_terminal: int,
        prep_token: int,
        verb_terminal: int,
        verb_token: int,
    ) -> int:
        """Called from the C++ reducer (via fastparser.prep_bonus_func())
        to obtain a verb/preposition match bonus, where the terminals and
        the tokens are referenced by their indices"""
        terminals = job.terminals
        tokens = job.tokens
        # The same lookup, with the same cache, as in visit_token()
        key = (
            cast(BIN_Terminal, terminals[prep_terminal]),
            tokens[prep_token].lower,
            cast(BIN_Terminal, terminals[verb_terminal]),
            tokens[verb_token],
        )
        bonus = self._bonus_cache.get(key)
        if bonus is None:
            bonus = self._bonus_cache[key] = self.verb_prep_bonus(*key)
        return bonus

    def native_particle_bonus(
        self, job: ParseJob, particle_token: int, verbs: List[Tuple[int, int]]
    ) -> int:
        """Called from the C++ reducer (via fastparser.particle_bonus_func())
        to obtain a verb particle bonus, where the particle is referenced
        by the index of its token, and the verbs by pairs of
        (terminal index, token index)"""
        terminals = job.terminals
        tokens = job.tokens
        return self.verb_particle_bonus(
            tokens[particle_token].lower,
            [(cast(BIN_Terminal, terminals[t]), tokens[k]) for t, k in verbs],
        )

    def visit_token(self, node: Node) -> ResultDict:
        """At token node"""
        # Return the score of this token/terminal match
        d: ResultDict = {"sc": 0}
        nt = cast(BIN_Terminal, node.terminal)
        sc = self._scores[node.start][nt]
        if nt.matches_category("ao") and nt.is_literal:
            # Adverb matched by a literal terminal such as "upp:ao":
            # note its text, in case it is a verb particle (SagnÖgn)
            d["ao"] = cast(BIN_Token, node.token).lower
        if nt.matches_category("fs"):
            # Preposition terminal - this is either a normal fs_case terminal
            # or a literal terminal such as "á:fs"
            prep_bonus = self.get_prep_bonus()
            if prep_bonus is not None:
                # We are inside a preposition bonus zone:
                # give bonus points if this preposition terminal matches
                # an enclosing verb
                # Iterate through enclosing verbs
                final_bonus = None
                # pylint: disable=not-an-iterable
                for terminal, token in prep_bonus:
                    # Attempt to find the preposition matching bonus in the cache
                    key = (nt, cast(BIN_Token, node.token).lower, terminal, token)
                    bonus = self._bonus_cache.get(key)
                    if bonus is None:
                        bonus = self._bonus_cache[key] = self.verb_prep_bonus(*key)
                    # Found a bonus, which can be positive or negative
                    if final_bonus is None:
                        final_bonus = bonus
                    else:
                        # Give the highest bonus that is available
                        final_bonus = max(final_bonus, bonus)
                if final_bonus is not None:
                    sc += final_bonus
        elif nt.matches_category("so"):  # !!! Was .startswith("so")
            # Verb terminal: pick up the verb
            d["so"] = [(nt, cast(BIN_Token, node.token))]
        d["sc"] = node.score = sc
        return d

    def go(self, root_node: Node) -> ResultDict:
        """Perform the reduction, scoring shared packed subtrees
        separately for each distinct verb context they occur in"""

        # Memoization/caching dict, keyed by node and context signature
        visited: Dict[Tuple[Node, Any], ResultDict] = dict()
        # Signature of a context-independent subtree
        NEUTRAL: Tuple[Any, Any] = (None, None)

        def vsig(vl: Optional[VerbList]) -> Any:
            """Hashable identity signature of a verb list"""
            return (
                None
                if vl is None
                else tuple((id(t), id(tok)) for t, tok in vl)
            )

        def context_sig(w: Node) -> Any:
            """Return the part of the reducer state that the score of
            the subtree rooted at w can depend on. Subtrees that are
            shared between different verb contexts must be scored
            separately for each context, since preposition terminals
            within them receive different verb/preposition bonuses."""
            if w._token is not None:
                # A token score depends only on the active
                # preposition bonus verbs (and only for fs terminals,
                # but the signature is cheap enough to include always)
                pb = self.get_prep_bonus()
                return None if pb is None else vsig(pb)
            if w.is_completed:
                nt = w.nonterminal
                if nt is not None and (
                    nt.has_tag("begin_prep_scope") or nt.is_noun_phrase
                ):
                    # This node resets both the prep bonus zone and the
                    # current verb on entry, so its score is the same
                    # in all contexts
                    return NEUTRAL
                if w.is_empty:
                    # Explicitly nullable nonterminal with no child
                    return NEUTRAL
            # The score may depend both on the enclosing prep bonus zone
            # (for enclosed fs terminals) and on the current verb (which
            # an enclosed enable_prep_bonus node would capture)
            return (vsig(self.get_prep_bonus()), vsig(self.get_current_verb()))

        # Winning family index and per-family child lists (with the
        # context signatures they were scored under), keyed like visited.
        # This records the scoring pass's decisions so that the actual
        # reduction can be deferred until all contexts have been scored.
        decisions: Dict[Tuple[Node, Any], DecisionTuple] = dict()

        def calc_score(w: Node, sig: Any) -> ResultDict:
            """Calculate the score of the subtree rooted at w within
            the current verb context, memoized on (node, context).
            The sig parameter is context_sig(w), computed by the caller.
            This pass does not modify the forest; it only scores it
            and records the winning family of each (node, context)."""
            # Has this (node, context) combination been memoized?
            v = visited.get((w, sig))
            if v is not None:
                # Yes: return the previously calculated result
                return v
            if w._token is not None:
                # Return the score of this terminal option
                v = self.visit_token(w)
            elif w.is_span and w._families:
                # We have a nonempty nonterminal node with one or more families
                # of children, i.e. multiple possible derivations:
                # Init container for family results
                scope = _ReductionScope(self, w)
                fam_children: List[List[Tuple[Node, Any]]] = []
                # Go through each family and calculate its score
                for family_ix, (prod, children) in enumerate(w._families):
                    scope.start_family(family_ix, prod, children)
                    this_fam: List[Tuple[Node, Any]] = []
                    for ch in children:
                        if ch is not None:
                            chsig = context_sig(ch)
                            this_fam.append((ch, chsig))
                            scope.add_child(family_ix, calc_score(ch, chsig))
                    fam_children.append(this_fam)
                # Obtain a dict describing the winning family of children
                # (derivation), including an "sc" field for its score,
                # along with the winning family index
                v, chosen_ix = scope.process(w)
                nt = w.nonterminal if w.is_completed else None
                if nt is not None and nt.no_reduce:
                    # This node will not be reduced: the reduction pass
                    # descends into the children of every family
                    decisions[(w, sig)] = (
                        chosen_ix,
                        [pair for fam in fam_children for pair in fam],
                    )
                elif len(fam_children) > 1 or any(
                    chsig is not None and chsig != NEUTRAL
                    for _, chsig in fam_children[0]
                ):
                    # Only record what the reduction pass can't infer:
                    # an actual choice between families, or children
                    # scored in a context-sensitive signature. For a
                    # single-family node whose children are all
                    # context-free, the walk derives the same
                    # information from the node itself, saving the
                    # memory of recording it here.
                    decisions[(w, sig)] = (chosen_ix, fam_children[chosen_ix])
            else:
                v = NULL_SC
            # Memoize the result for this (node, context) combination
            visited[(w, sig)] = v
            w.score = v["sc"]
            return v

        # Nodes already reduced in the reduction pass. A node shared
        # between contexts can only be physically reduced one way; the
        # first context to reach it in the winning tree decides.
        reduced: Set[Node] = set()

        def apply_reduction(w: Node, sig: Any) -> None:
            """Second pass: walk the winning tree, reducing each node
            to the family that won in the context the node is actually
            used in, as recorded by the scoring pass"""
            if w in reduced:
                return
            reduced.add(w)
            entry = decisions.get((w, sig))
            if entry is None:
                if w._token is not None or not w.is_span or not w._families:
                    # Token or empty node: nothing to reduce
                    return
                # Single-family node with context-free children, not
                # recorded by the scoring pass: nothing to reduce, and
                # each child's signature can be derived from its kind
                # (None for tokens, NEUTRAL for everything else - see
                # the storage condition in calc_score)
                _, children0 = w._families[0]
                for ch0 in children0:
                    if ch0 is not None:
                        apply_reduction(
                            ch0, None if ch0._token is not None else NEUTRAL
                        )
                return
            chosen_ix, children = entry
            nt = w.nonterminal if w.is_completed else None
            if nt is None or not nt.no_reduce:
                # The key action of the reducer:
                # eliminate all families except the winning one.
                # (Nonterminals tagged no_reduce keep all their child
                # families; this feature is used in query processing.)
                w.reduce_to(chosen_ix)
            for ch, chsig in children:
                apply_reduction(ch, chsig)

        # First pass: score the forest without modifying it
        root_sig = context_sig(root_node)
        result = calc_score(root_node, root_sig)
        # Second pass: reduce the forest to the winning tree
        apply_reduction(root_node, root_sig)
        return result


class OptionFinder(ParseForestNavigator):

    """Subclass to navigate a parse forest and populate the set
    of terminals that match each token"""

    def __init__(self, finals: FinalsDict, tokens: TokensDict) -> None:
        super().__init__()
        self._finals = finals
        self._tokens = tokens

    def visit_token(self, level: int, w: Node) -> Any:
        """At token node"""
        # assert node.terminal is not None
        self._finals[w.start].add(cast(BIN_Terminal, w.terminal))
        self._tokens[w.start] = cast(BIN_Token, w.token)
        return None


def same_forest(a: Optional[Node], b: Optional[Node]) -> bool:
    """Return True if two trees (or forests) of nodes are the same in
    every respect: shape, sharing of nodes, grammar items, tokens and
    scores. Used to verify the C++ reducer against the Python one."""
    a_to_b: Dict[int, int] = dict()
    b_to_a: Dict[int, int] = dict()
    stack: List[Tuple[Optional[Node], Optional[Node]]] = [(a, b)]
    while stack:
        x, y = stack.pop()
        if x is None or y is None:
            if x is not y:
                return False
            continue
        ix, iy = id(x), id(y)
        if ix in a_to_b or iy in b_to_a:
            # Seen before: must have been seen together
            if a_to_b.get(ix) != iy or b_to_a.get(iy) != ix:
                return False
            continue
        a_to_b[ix] = iy
        b_to_a[iy] = ix
        if (
            x._start != y._start
            or x._end != y._end
            or x._nonterminal is not y._nonterminal
            or x._terminal is not y._terminal
            or x._token is not y._token
            or x._completed != y._completed
            or x._highest_prio != y._highest_prio
            or x.score != y.score
        ):
            return False
        fx, fy = x._families, y._families
        if fx is None or fy is None:
            if fx is not fy:
                return False
            continue
        if len(fx) != len(fy):
            return False
        for (px, cx), (py, cy) in zip(fx, fy):
            if px is not py or len(cx) != len(cy):
                return False
            stack.extend(zip(cx, cy))
    return True


class Reducer:

    """Reduces parse forests to a single most likely parse tree"""

    # Set to False in a derived class to make parse_and_reduce() do all
    # of its work in Python, as do the environment variable
    # GREYNIR_DISABLE_CPP_REDUCER and overriding the methods that the
    # C++ reducer stands in for. If the environment variable
    # GREYNIR_REDUCER_PARITY is set, the work is done both in C++ and in
    # Python, the results are compared, and the Python one is returned.
    _USE_CPP_REDUCER = True

    # The number of sentences where the C++ reducer and the Python one
    # disagreed (only counted in parity mode)
    parity_mismatches = 0

    # Protects the installation of the tables of the C++ reducer in a
    # parser, and the parity mismatch counter
    _native_lock = Lock()

    # The class that scores and reduces a forest in Python, and that
    # answers the questions of the C++ reducer about verbs, prepositions
    # and particles
    _forest_reducer_class = ParseForestReducer

    def __init__(self, grammar: Grammar) -> None:
        self._grammar = grammar

    def _find_options(
        self, forest: Node, finals: FinalsDict, tokens: TokensDict
    ) -> None:
        """Find token-terminal match options in a parse forest with a root in w"""
        OptionFinder(finals, tokens).go(forest)

    def _calc_terminal_scores(self, w: Node) -> ScoreDict:
        """Calculate the score for each possible terminal/token match"""

        # First pass: for each token, find the possible terminals that
        # can correspond to that token
        finals: FinalsDict = defaultdict(set)
        tokens: TokensDict = dict()
        self._find_options(w, finals, tokens)
        # Second pass: score the terminals
        return self._score_options(finals, tokens, w.start, w.end)

    def _score_options(
        self, finals: FinalsDict, tokens: TokensDict, start: int, end: int
    ) -> ScoreDict:
        """Calculate the score for each possible terminal/token match,
        given the terminals that each token can correspond to in a forest
        that spans the tokens from start to end"""

        # Find a (partial) ordering by scoring
        # the terminal alternatives for each token
        scores: ScoreDict = dict()
        noun_prefs = NounPreferences.DICT

        # Loop through the indices of the tokens spanned by this tree
        for i in range(start, end):

            s = finals[i]
            # Initially, each alternative has a score of 0
            scores[i] = {terminal: 0 for terminal in s}

            if len(s) <= 1:
                # No ambiguity to resolve here
                continue

            token = tokens[i]
            # More than one terminal in the option set for the token at index i
            # Calculate the relative scores
            # Find out whether the first part of all the terminals are the same
            same_first = len(set(terminal.first for terminal in s)) == 1
            txt = txt_last = token.lower
            composite = False
            # Get the last part of a composite word (e.g. 'jaðar-áhrifin' -> 'áhrifin')
            if (
                token.is_word
                and token.has_meanings
                and "-" in token.meanings[0].ordmynd
            ):
                composite = True
                txt_last = token.meanings[0].ordmynd.rsplit("-", maxsplit=1)[-1]
            # No need to check preferences if the first parts of
            # all possible terminals are equal
            # Look up the preference ordering from GreynirEngine.conf, if any
            prefs = None if same_first else Preferences.get(txt_last)
            sc = scores[i]
            if prefs:
                adj_worse: Dict[BIN_Terminal, int] = defaultdict(int)
                adj_better: Dict[BIN_Terminal, int] = defaultdict(int)
                for worse, better, factor in prefs:
                    for wt in s:
                        if wt.first in worse:
                            for bt in s:
                                if wt is not bt and bt.first in better:
                                    if bt.is_literal:
                                        # Literal terminal:
                                        # be even more aggressive in promoting it
                                        adj_w = -2 * factor
                                        adj_b = +6 * factor
                                    else:
                                        adj_w = -2 * factor
                                        adj_b = +4 * factor
                                    adj_worse[wt] = min(adj_worse[wt], adj_w)
                                    adj_better[bt] = max(adj_better[bt], adj_b)
                for wt, adj in adj_worse.items():
                    sc[wt] += adj
                for bt, adj in adj_better.items():
                    sc[bt] += adj

            # Apply heuristics to each terminal that potentially matches this token
            for t in s:

                if t.is_literal:
                    # Give a bonus for exact or semi-exact matches with
                    # literal terminals
                    sc[t] += 2

                tfirst = t.first
                if tfirst == "ao" or tfirst == "eo":
                    # Subtract from the score of all ao and eo
                    sc[t] -= 1
                elif tfirst == "no":
                    if t.is_singular:
                        # Add to singular nouns relative to plural ones
                        sc[t] += 1
                    elif t.is_abbrev:
                        # Punish abbreviations in favor of other more specific terminals
                        sc[t] -= 1
                    if token.is_word and token.is_upper and token.t2:
                        # Punish connection of normal noun terminal to an
                        # uppercase word that can be a person or entity name and
                        # would thus normally be matched with person or entity
                        # terminal
                        if any(m.fl in _NAMED_ENTITY_FL for m in token.meanings):
                            # logging.info(
                            #     "Punishing connection of {0} with 'no' terminal"
                            #     .format(tokens[i].t1))
                            sc[t] -= 5
                    # Noun priorities, i.e. between different genders
                    # of the same word form (for example "ára" which can refer to
                    # three stems with different genders)
                    if txt_last in noun_prefs and t.gender is not None:
                        np = noun_prefs[txt_last].get(t.gender, 0)
                        sc[t] += np
                elif tfirst == "fs":
                    if t.has_variant("nf"):
                        # Reduce the weight of the 'artificial' nominative prepositions
                        # 'næstum', 'sem', 'um'
                        # Make other cases outweigh the Nl_nf bonus of +4 (-2 -3 = -5)
                        sc[t] -= 10
                        if txt == "sem":
                            # Further subtraction for 'sem:fs'_nf
                            sc[t] -= 8
                    elif txt == "við" and t.has_variant("þgf"):
                        # Smaller bonus for við + þgf (is rarer than við + þf)
                        sc[t] += 1
                    elif txt == "sem" and t.has_variant("þf"):
                        sc[t] -= 4
                    elif txt == "á" and t.has_variant("þgf"):
                        # Larger bonus for á + þgf to resolve conflict with verb 'eiga'
                        sc[t] += 4
                    elif txt == "í" and t.has_variant("þgf"):
                        # Slightly larger bonus for í + þgf (location) than
                        # í + þf (direction), to resolve ties where the noun
                        # form is the same in both cases ("í umdæmi")
                        sc[t] += 3
                    else:
                        # Else, give a bonus for each matched preposition
                        sc[t] += 2
                elif tfirst == "lo":
                    if composite:
                        # If this is a composite word, it's less likely
                        # to be an adjective, so give it a penalty
                        sc[t] -= 3
                    # For adjectives ending with 'andi', we strongly prefer verbs in
                    # present participle (lýsingarháttur nútíðar)
                    if txt.endswith("andi") and any(
                        (m.ordfl == "so" and m.beyging in {"LH-NT", "LHNT"})
                        for m in token.meanings
                    ):
                        sc[t] -= 50
                elif tfirst == "so":
                    if t.num_variants > 0 and t.variant(0) in "012":
                        # Consider verb arguments
                        # Normally, we give a bonus for verb arguments:
                        # the more matched, the better
                        numcases = int(t.variant(0))
                        adj = 2 * numcases
                        # Apply score adjustments for verbs with particular
                        # object cases, as specified by $score(n) pragmas in Verbs.conf
                        # In the (rare) cases where there are conflicting scores,
                        # apply the most positive adjustment
                        adjmax: Optional[int] = None
                        # Is the terminal only licensed by weak frames?
                        weak_only: Optional[bool] = None
                        for m in token.meanings:
                            if m.ordfl == "so":
                                key = m.stofn + t.verb_cases
                                score = VerbFrame.verb_score(key)
                                if score is not None:
                                    if adjmax is None:
                                        adjmax = score
                                    else:
                                        adjmax = max(adjmax, score)
                                if numcases > 0 and VerbFrame.matches_arguments(key):
                                    wo = VerbFrame.weak_only(key)
                                    weak_only = wo if weak_only is None else (weak_only and wo)
                        sc[t] += adj + (adjmax or 0)
                        if weak_only:
                            sc[t] += _VERB_WEAK_ONLY_PENALTY
                    if t.has_variant("sp"):
                        # Interrogative form with a cliticized subject
                        # ('ertu', 'viltu'). BÍN lists such forms for many
                        # verbs whose clitic form coincides with a common
                        # adjective ('næstu', 'mestu', 'elstu') or with a
                        # regular verb form ('áttu', 'yrðu', 'máttu'): in
                        # those cases, discourage the clitic reading
                        if any(m.ordfl == "lo" for m in token.meanings):
                            sc[t] += _CLITIC_ADJECTIVE_PENALTY
                        elif any(
                            m.ordfl == "so" and "SP" not in m.beyging
                            for m in token.meanings
                        ):
                            sc[t] += _CLITIC_VERB_PENALTY
                    if t.is_bh:
                        # Discourage 'boðháttur'
                        sc[t] -= 4
                    elif t.is_sagnb:
                        # We like sagnb and lh, it means that more
                        # than one piece clicks into place
                        sc[t] += 6
                    elif t.is_lh:
                        # sagnb is preferred to lh, but vb (veik beyging) is discouraged
                        if t.has_variant("vb"):
                            sc[t] -= 2
                        else:
                            sc[t] += 3
                    elif t.is_lh_nt:
                        sc[t] += 12  # Encourage LHNT rather than LO
                    elif t.is_mm:
                        # Encourage mm forms. The encouragement should be better than
                        # the score for matching a single case, so we pick so_0_mm
                        # rather than so_1_þgf, for instance.
                        sc[t] += 3
                    elif t.is_vh:
                        # Encourage vh forms
                        sc[t] += 2
                    if t.is_subj:
                        # Give a small bonus for subject matches
                        if t.has_variant("none"):
                            # ... but a punishment for subj_none
                            sc[t] -= 3
                        else:
                            sc[t] += 1
                    if t.is_nh:
                        if (i > 0) and any(pt.first == "nhm" for pt in finals[i - 1]):
                            # Give a bonus for adjacent nhm + so_nh terminals
                            sc[t] += 4  # Prop up the verb terminal with the nh variant
                            for pt in scores[i - 1].keys():
                                if pt.first == "nhm":
                                    # Prop up the nhm terminal
                                    scores[i - 1][pt] += 2
                                    break
                        if any(
                            pt.first == "no" and pt.has_variant("ef") and pt.is_plural
                            for pt in s
                        ):
                            # If this is a so_nh and an alternative no_ef_ft exists,
                            # choose this one (for example, 'hafa', 'vera', 'gera',
                            # 'fara', 'mynda', 'berja', 'borða')
                            sc[t] += 4
                    if (i > 0) and token.is_upper:
                        # The token is uppercase and not at the start of a sentence:
                        # discourage it from being a verb
                        sc[t] -= 4
                elif tfirst == "tala":
                    if t.has_variant("ef"):
                        # Try to avoid interpreting plain numbers as possessive phrases
                        sc[t] -= 4
                elif tfirst == "person":
                    if t.has_variant("nf"):
                        # Prefer person names in the nominative case
                        sc[t] += 2
                elif tfirst == "sérnafn":
                    if not token.t2:
                        # If there are no BÍN meanings, we had no choice but
                        # to use sérnafn, so alleviate some of the penalty given
                        # by the grammar
                        sc[t] += 12
                    else:
                        # BÍN meanings are available: discourage this
                        # print(f"Discouraging sérnafn {txt}, "
                        #     "BÍN meanings are {tokens[i].t2}")
                        sc[t] -= 10
                        if i == start:
                            # First token in sentence, and we have BÍN meanings:
                            # further discourage this
                            sc[t] -= 6
                elif tfirst == "fyrirtæki":
                    # We encourage company names to be interpreted as such,
                    # so we give company abbreviations ('hf.', 'Corp.', 'Limited')
                    # a high priority
                    sc[t] += 24
                elif tfirst == "st" or (tfirst == "sem" and t.colon_cat == "st"):
                    if txt == "sem":
                        # Discourage "sem" as a pure conjunction (samtenging)
                        # (it does not get a penalty when occurring as
                        # a connective conjunction, 'stt')
                        sc[t] -= 6
                elif tfirst == "abfn":
                    # If we have number and gender information with the reflexive
                    # pronoun, that's good: encourage it
                    sc[t] += 6 if t.num_variants > 1 else 2
                elif tfirst == "gr":
                    # Encourage separate definite article rather than pronoun
                    sc[t] += 2
                elif tfirst == "nhm":
                    # Encourage the infinitive
                    sc[t] += 4

        return scores

    def _reduce(self, w: Node, scores: ScoreDict) -> ResultDict:
        """Reduce a forest with a root in w based on subtree scores"""
        return self._forest_reducer_class(self._grammar, scores).go(w)

    def go_with_score(self, forest: Optional[Node]) -> Tuple[Optional[Node], int]:
        """Returns the argument forest after pruning it down to a single tree"""
        if forest is None:
            return None, 0
        scores = self._calc_terminal_scores(forest)
        # Third pass: navigate the tree bottom-up, eliminating lower-rated
        # options (subtrees) in favor of higher rated ones
        score = self._reduce(forest, scores)
        return forest, score["sc"]

    def go(self, forest: Optional[Node]) -> Optional[Node]:
        """Return only the reduced forest, without its score"""
        w, _ = self.go_with_score(forest)
        return w

    @staticmethod
    def _install_native_tables(parser: Fast_Parser) -> bool:
        """Give the C++ parser object of the given parser the tables
        that the C++ reducer needs: what it has to know about each
        nonterminal and terminal of the grammar. Returns False if the
        grammar is not one that the C++ reducer can work with."""
        grammar = parser.grammar
        num_nt = grammar.num_nonterminals
        num_t = grammar.num_terminals
        nt_flags = [0] * num_nt
        nt_scores = [0] * num_nt
        nt_score_adj = grammar._nt_scores
        for ix, nt in grammar.nonterminals_by_ix.items():
            # Nonterminal indices are negative: -1 is the first one
            i = -1 - ix
            if not 0 <= i < num_nt:
                return False
            flags = 0
            for tag, flag in _NT_TAG_FLAGS:
                if nt.has_tag(tag):
                    flags |= flag
            if nt.is_noun_phrase:
                flags |= _NT_FLAG_NOUN_PHRASE
            nt_flags[i] = flags
            nt_scores[i] = nt_score_adj.get(nt, 0)
        # Terminal indices are positive, starting with 1
        t_flags = bytearray(num_t + 1)
        for ix, t in grammar.terminals_by_ix.items():
            if not 0 < ix <= num_t:
                return False
            matches_category = getattr(t, "matches_category", None)
            if matches_category is None:
                # Not a terminal that the reducer knows how to handle
                return False
            flags = 0
            if matches_category("ao") and t.is_literal:
                flags |= _T_FLAG_AO_LITERAL
            if matches_category("fs"):
                flags |= _T_FLAG_FS
            if matches_category("so"):
                flags |= _T_FLAG_SO
            t_flags[ix] = flags
        eparser.setReducerTables(  # type: ignore
            parser._c_parser,
            ffi.new("UINT[]", nt_flags),
            ffi.new("INT[]", nt_scores),
            num_nt,
            ffi.new("BYTE[]", bytes(t_flags)),
            num_t + 1,
            eparser.prep_bonus_func,  # type: ignore
            eparser.particle_bonus_func,  # type: ignore
            _VERB_PREP_BONUS,
            _LENGTH_BONUS_FACTOR,
        )
        return True

    def _native_allowed(self, parser: Fast_Parser) -> bool:
        """Return True if the C++ reducer can be used with the given
        parser: it replicates what the methods of Fast_Parser, Node and
        this class do, so it must stand aside if any of them has been
        overridden - or if it has been turned off."""
        cls = type(self)
        if not cls._USE_CPP_REDUCER or os.environ.get("GREYNIR_DISABLE_CPP_REDUCER"):
            return False
        if (
            cls.go_with_score is not Reducer.go_with_score
            or cls._reduce is not Reducer._reduce
            or cls._calc_terminal_scores is not Reducer._calc_terminal_scores
            or cls._find_options is not Reducer._find_options
            or cls._forest_reducer_class is not ParseForestReducer
        ):
            return False
        pcls = type(parser)
        if (
            not isinstance(parser, Fast_Parser)
            or pcls.go is not Fast_Parser.go
            or pcls.num_combinations.__func__  # type: ignore
            is not Fast_Parser.num_combinations.__func__  # type: ignore
            or parser.grammar is not self._grammar
        ):
            return False
        # Install the tables of the C++ reducer in the parser, on first use
        installed: Optional[bool] = getattr(parser, "_reducer_tables", None)
        if installed is None:
            with Reducer._native_lock:
                installed = getattr(parser, "_reducer_tables", None)
                if installed is None:
                    installed = self._install_native_tables(parser)
                    setattr(parser, "_reducer_tables", installed)
        return installed

    def _native_reduce(
        self, job: ParseJob, c_forest: Any
    ) -> Optional[Tuple[Node, int, int]]:
        """Count the trees in a parse forest that is still in its C++
        form, reduce it to its highest-scoring tree, and create Python
        objects for the nodes of that tree only. Returns None if the C++
        reducer declines to handle the forest."""
        red: Any = eparser.reduceStart(job.c_parser, c_forest)  # type: ignore
        if red == ffi_NULL:
            return None
        # The number of trees in the forest, which can be huge
        num = int.from_bytes(ffi.buffer(red.pbComb, red.nCombBytes), "little")
        score = 0
        if num > 1:
            # The forest is ambiguous. Collect the terminals that each
            # token is matched with in the forest, in the order in which
            # OptionFinder would find them, and score those matches.
            options: List[int] = ffi.unpack(red.pnOptions, 2 * red.nOptions)
            terminals = job.terminals
            tokens = job.tokens
            finals: FinalsDict = defaultdict(set)
            token_dict: TokensDict = dict()
            for i in range(0, len(options), 2):
                token_ix = options[i]
                finals[token_ix].add(cast(BIN_Terminal, terminals[options[i + 1]]))
                token_dict[token_ix] = tokens[token_ix]
            scores = self._score_options(finals, token_dict, red.nStart, red.nEnd)
            c_scores: Any = ffi.new(
                "INT[]",
                [
                    scores[options[i]][cast(BIN_Terminal, terminals[options[i + 1]])]
                    for i in range(0, len(options), 2)
                ],
            )
            # The C++ reducer calls back into this object when it needs
            # to know whether a verb takes a preposition or a particle
            job.reducer = self._forest_reducer_class(self._grammar, scores)
            ok = eparser.reduceFinish(red, c_scores, job.handle)  # type: ignore
            if job.exc is not None:
                # An exception was raised in a callback: re-raise it
                raise job.exc
            score = red.nScore
        else:
            # Unambiguous: there is nothing to reduce
            ok = eparser.reduceFinish(red, ffi_NULL, job.handle)  # type: ignore
        if not ok:
            return None
        tree = Node.from_serialized(job, ffi.unpack(red.pnOut, red.nOut))
        assert tree is not None
        return tree, num, score

    def _python_reduce(self, forest: Node) -> Tuple[Node, int, int]:
        """Count the trees in a parse forest and reduce it to its
        highest-scoring tree, working in Python on Python objects"""
        num = Fast_Parser.num_combinations(forest)
        score = 0
        if num > 1:
            # Reduce the parse forest to a single
            # "best" (highest-scoring) parse tree
            w, score = self.go_with_score(forest)
            assert w is not None
            forest = w
        return forest, num, score

    def parse_and_reduce(
        self,
        parser: Fast_Parser,
        tokens: Iterable[Tok],
        *,
        root: Optional[str] = None,
        on_parsed: Optional[Callable[[], None]] = None,
    ) -> Tuple[Node, int, int]:
        """Parse the tokens with the given parser, and reduce the
        resulting parse forest to its highest-scoring tree. Returns the
        tree, the number of trees that were in the forest, and the score
        of the tree. If there was only one tree in the forest, it is
        returned as it is, with a score of 0.

        This gives the same result as calling parser.go(),
        Fast_Parser.num_combinations() and Reducer.go_with_score() in turn,
        but is much faster, since the forest is processed in the C++
        module (see ereducer.cpp), and Python objects are only created
        for the nodes of the resulting tree.

        If on_parsed is given, it is called when the parser has completed
        its work and the reduction is about to start."""
        if not self._native_allowed(parser):
            forest = parser.go(tokens, root=root)
            if on_parsed is not None:
                on_parsed()
            return self._python_reduce(forest)
        with parser.parse_forest(tokens, root=root) as (job, c_forest):
            if on_parsed is not None:
                on_parsed()
            result = self._native_reduce(job, c_forest)
            if result is not None and not os.environ.get("GREYNIR_REDUCER_PARITY"):
                return result
            # The C++ reducer declined to handle this forest,
            # or we are checking its work: reduce the forest in Python
            py_forest = Node.from_c_node(job, c_forest)
        assert py_forest is not None
        py_result = self._python_reduce(py_forest)
        if result is not None and not (
            result[1] == py_result[1]
            and result[2] == py_result[2]
            and same_forest(result[0], py_result[0])
        ):
            with Reducer._native_lock:
                Reducer.parity_mismatches += 1
        return py_result

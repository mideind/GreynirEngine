"""
    Greynir: Natural language processing for Icelandic

    Verb frame class module

    Copyright © 2023 Miðeind ehf.

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

    This module reads and interprets the GreynirPackage.conf
    configuration file. The file can include other files using the $include
    directive, making it easier to arrange configuration sections into logical
    and manageable pieces.

    Sections are identified like so: [ section_name ]

    Comments start with # signs.

    Sections are interpreted by section handlers.

"""

from typing import (
    Iterable,
    Optional,
    Union,
    Dict,
    Tuple,
    Set,
    List,
)

from collections import defaultdict
from functools import lru_cache

from .basics import (
    ConfigError,
    ALL_CASES,
    SUBCLAUSES,
    REFLPRN,
    REFLPRN_CASE,
    REFLPRN_SET,
)


# Key type for preposition frames
PrepKey = str
# Type of set of zero-verb arguments
VerbZeroArgSet = Set[str]
# Type of dict of verbs with arguments (1 or 2),
# where each entry is a list of argument lists
VerbWithArgErrorDict = Dict[str, Dict[str, str]]


SKIP_VARS = frozenset(("gr", "ft", "est", "mst", "et", "kk", "kvk", "hk"))
VALID_ARGS = ALL_CASES | SUBCLAUSES | REFLPRN_SET


class VerbErrors:

    """A container class for verb error data, for instance wrong
    verb forms and wrong preposition attachment"""

    ERRORS: List[Union[VerbZeroArgSet, VerbWithArgErrorDict]] = [
        set(),
        defaultdict(dict),
        defaultdict(dict),
    ]
    VERB_PARTICLES_ERRORS: Dict[str, Dict[str, str]] = defaultdict(dict)
    PREPOSITIONS_ERRORS: Dict[str, Dict[str, str]] = defaultdict(dict)
    WRONG_VERBS: Dict[str, str] = dict()
    OBJ_ERRORS: Dict[str, Dict[str, str]] = defaultdict(dict)

    @staticmethod
    def check_args(args: Iterable[str]) -> None:
        for kind in args:
            if kind not in VALID_ARGS:
                spl = kind.split("_")
                # Allow the last variant to be _gr, if the
                # next-to-last one is a case
                if spl and spl[-1] == "gr":
                    spl = spl[:-1]
                if not spl or spl[-1] not in ALL_CASES:
                    raise ConfigError("Invalid verb argument: '{0}'".format(kind))

    @staticmethod
    def add_error(
        verb: str,
        args: List[str],
        prepositions: List[Tuple[str, str]],
        particle: Optional[str],
        corr: str,
    ) -> None:
        """Take note of a verb object specification with an $error pragma"""
        corrlist = corr.split(",")
        # errlist = corrlist[0].split("-")
        # errkind = errlist[0].strip()
        verb_with_cases = "_".join([verb] + args)
        if corrlist[0] == "OBJ-CASE":
            pobj = corrlist[1].strip()
            VerbErrors.check_args(args)
            if pobj not in ALL_CASES and pobj not in SUBCLAUSES:
                pobj = pobj.split(" ")[0].strip()
                pobj = REFLPRN.get(pobj, pobj)
                assert pobj is not None
                spl = pobj.split("_")
                while spl and spl[-1].strip() in SKIP_VARS:
                    spl = spl[:-1]
                if spl[-1] not in ALL_CASES:
                    raise ConfigError(
                        "Direct object must have a case as its last variant"
                    )
                pobj = spl[-1]
            VerbErrors.OBJ_ERRORS[verb][args[0]] = pobj

        # elif errkind == "OBJ":
        #     vargs = cast(VerbWithArgErrorDict, VerbErrors.ERRORS[len(args)])
        #     arglists = vargs[verb]
        #     arglists[verb_with_cases] = corr
        elif corrlist[0].strip() == "PP":
            d = VerbErrors.PREPOSITIONS_ERRORS[verb_with_cases]
            for p, kind in prepositions:
                d[p] = corr
                d[p + "_" + kind] = corr
        # elif errkind == "PRTCL":
        #     # !!! TODO: Parse the corr string
        #     if particle is None:
        #         raise ConfigError("Particle error specification must specify particle")
        #     VerbErrors.VERB_PARTICLES_ERRORS[verb_with_cases][particle] = corr
        # elif errkind == "ALL":
        #     # !!! TODO: Implement this (store specification of a
        #     # !!! TODO: replacement of the entire construct)
        #     pass
        # elif errkind == "PREDS":
        #     # !!! TODO: Implement this
        #     pass
        # elif errkind == "WRONG":
        #     wrong_kind = errlist[1].strip()
        #     if wrong_kind == "VERB":
        #         # Wrong verb, must point to completely different verb + args
        #         if len(corrlist) != 2:
        #             raise ConfigError("WRONG-VERB must specify correct verb")
        #         if particle:
        #             verb_with_cases += "*" + particle
        #         if verb_with_cases in VerbErrors.WRONG_VERBS:
        #             pass
        #             # raise ConfigError("WRONG-VERB has already been specified for this verb, argument list and particle")
        #         VerbErrors.WRONG_VERBS[verb_with_cases] = corrlist[1]
        #     elif wrong_kind == "OBJ":
        #         # !!! TODO: Implement this
        #         pass
        #     else:
        #         raise ConfigError("Unknown type of WRONG-XXX in $error pragma")
        # else:
        #     raise ConfigError(
        #         "Unknown error type in $error pragma: '{0}'".format(errkind)
        #     )


class PrepositionFrame:

    """A class containing information about a preposition frame,
    i.e. a preposition controlling a particular case and eventually
    with associated nouns and particles."""

    # Dictionary of all preposition frames, avoiding duplicates
    FRAMES: Dict[PrepKey, "PrepositionFrame"] = dict()

    def __init__(
        self,
        prep: str,
        case: str,
    ) -> None:
        self.prep = prep
        self.case = case

    @classmethod
    def make_key(cls, prep: str, case: str) -> PrepKey:
        return prep + "_" + case

    @property
    def key(self) -> PrepKey:
        return self.make_key(self.prep, self.case)

    @classmethod
    def obtain(cls, prep: str, case: str) -> "PrepositionFrame":
        """Obtain a preposition frame for the given preposition and argument case,
        either by returning a previously encountered identical frame,
        or by creating a new one"""
        key = cls.make_key(prep, case)
        pf = cls.FRAMES.get(key)
        if pf is None:
            # Not already encountered: Create new
            pf = cls(prep, case)
            cls.FRAMES[key] = pf
        return pf


class VerbFrame:

    """A class containing information about a verb frame,
    i.e. a verb with arguments and associated prepositions
    and particles."""

    # Verb frames by key, where the key is 'lemma[_argcase1[_argcase2]]',
    # e.g. 'skrifa_þgf_þf'
    CASE_FRAMES: Dict[str, List["VerbFrame"]] = defaultdict(list)
    ALL_FRAMES: Dict[str, List["VerbFrame"]] = defaultdict(list)
    WRONG_CASE_FRAMES: Dict[str, List["VerbFrame"]] = defaultdict(list)
    # All known verb lemmas
    VERBS: Set[str] = set()

    def __init__(
        self,
        verb: str,
        obj: str,
        iobj: str,
        args: List[str],
        preps: Iterable[Tuple[str, str]],
        particle: Optional[str],
        score: Optional[int],
    ) -> None:
        self.verb = verb
        # All arguments
        self.args = args
        self.obj = obj
        self.iobj = iobj
        # Only case arguments
        self.cases = [arg for arg in args if arg in ALL_CASES]
        assert 0 <= len(self.cases) <= 2
        pfs = [PrepositionFrame.obtain(prep, case) for prep, case in preps]
        self.preps: Dict[PrepKey, PrepositionFrame] = {pf.key: pf for pf in pfs}
        self.particle = particle
        self.score = score

    @property
    def key(self) -> str:
        """Return a key string containing all args of the verb frame"""
        return "_".join([self.verb] + self.args)

    @property
    def case_key(self) -> Optional[str]:
        """Return a key string containing the cases of the verb frame,
        or None if this is not a frame with only case arguments"""
        if len(self.cases) < len(self.args):
            # This verb frame has non-case arguments: return None
            return None
        return "_".join([self.verb] + self.cases)

    def matches_pp(self, prep_with_case: str) -> bool:
        """Does this verb frame agree with the given preposition[+case]?"""
        return prep_with_case in self.preps

    def matches_pcl(self, particle: str) -> bool:
        """Does this verb frame agree with the given particle?"""
        return particle == self.particle

    @classmethod
    def create_from_config(cls, s: str) -> None:
        """Handle verb object specifications in the settings section"""
        # Format: verb [arg1] [arg2] [/preposition arg]... [*particle] [$pragma(txt)]

        complex = False

        def get_score(s: str) -> Tuple[str, Optional[int]]:
            """Handle the $score() pragma, if present"""
            score: Optional[int] = None
            ix = s.rfind("$score(")  # Must be at the end
            if ix >= 0:
                sc = s[ix:]
                s = s[0:ix].strip()
                if not sc.endswith(")"):
                    raise ConfigError("Invalid score pragma; form should be $score(n)")
                # There is an associated score with this verb form, to be taken
                # into consideration by the reducer
                sc = sc[7:-1].strip()
                try:
                    score = int(sc)
                except ValueError:
                    raise ConfigError("Invalid score ('{0}') for verb form".format(sc))
            return s, score

        def get_error(s: str) -> Tuple[str, Optional[str]]:
            """Handle the $error() pragma, if present"""
            error = None
            ix = s.rfind("$error(")
            if ix >= 0:
                if not s.endswith(")"):
                    raise ConfigError(
                        "Invalid error pragma; form should be $error(...)"
                    )
                error = s[ix + 7 : -1].strip()
                s = s[0:ix].strip()
                if not error:
                    raise ConfigError("Expected error specification in $error(...)")
            return s, error

        def get_particle(s: str) -> Tuple[str, Optional[str]]:
            """Process particles, should only be one in each line"""
            particle = None
            ix = s.rfind("*")
            if ix >= 0:
                particle = s[ix:].strip()
                s = s[:ix].strip()
                if not particle:
                    raise ConfigError("Particle should be at least one letter")
                if " " in particle or "\t" in particle:
                    raise ConfigError("Particle should only be one word")
            return s, particle

        def get_prepositions(s: str) -> Tuple[str, List[Tuple[str, str]]]:
            """Process preposition arguments, if any"""
            prepositions: List[Tuple[str, str]] = []
            ap = s.split("/")
            s = ap[0]
            ix = 1
            while ix < len(ap):
                # We expect something like 'af þgf', or possibly
                # 'fyrir_hönd þf' (where the underscore needs to be replaced by a space)
                # or 'milli ef_ft' (detailing the plural)
                p = ap[ix].strip()
                parg = p.split()
                # if len(parg) != 2:
                #    raise ConfigError("Preposition should have exactly one argument")
                case = get_case_and_kind(parg[1])
                prepositions.append((parg[0].replace("_", " "), case))
                ix += 1
            return s, prepositions

        def get_direct_object(s: str) -> Tuple[str, str]:
            """Process direct object argument"""
            op = s.split("|")
            s = op[0]
            if not 1 <= len(op) <= 2:
                raise ConfigError("Verb should have zero or one direct object")
            case = ""
            if len(op) == 2:
                case = get_case_and_kind(op[1].strip())
            return s, case

        def get_indirect_object(s: str) -> Tuple[str, str]:
            """Process indirect object argument"""
            a = s.split()
            if len(a) < 1:
                raise ConfigError("Verb should have zero or one indirect objects")
            verb = a[0]
            if not verb.isalpha():
                raise ConfigError("Verb '{0}' is not a valid word".format(verb))
            case = ""
            if len(a) > 1:
                case = get_case_and_kind((" ".join(a[1:])))
            return verb, case

        def get_case_and_kind(w: str) -> str:
            """Get case of argument for the case key,
            along with the argument type."""
            # Argument denotes:
            # 1: a case (nf, þf, þgf, ef) - default value
            # 2: a reflexive pronoun (sig, sér, sín)
            # 3: a fixed phrase ([halda] hlífiskjöldur_kk_et_þgf)
            # 4: a multiword fixed phrase ([eiga] góður_lo_kk_et_þf dagur_kk_et_þf)
            # 5: an infinitival clause with the infinitival marker ([eiga] nh)
            # 6: an infinitival clause without the infinitival marker ([mega] nhx)
            # 7: a complement clause ([halda] falls)
            # 8: an interrogative clause ([spyrja] spurns)
            if not w:
                raise ConfigError("Argument must have a case as a variant")
            case = ""
            # kind: int = 1    # Default value
            refl = REFLPRN_CASE.get(w, "")
            nonlocal complex
            if w in ALL_CASES:
                # Case 1
                case = w
                # kind = 1
            elif refl and refl in ALL_CASES:
                # Case 2
                case = refl
                # kind = 2
                complex = True
            elif w in SUBCLAUSES:
                # Cases 5-8
                case = w
                # kind = 5
                complex = True
            elif " " in w:
                # Cases 4
                w = w.split(" ")[0].strip()
                spl = w.split("_")
                while spl and spl[-1].strip() in SKIP_VARS:
                    spl = spl[:-1]
                if not spl or spl[-1] not in ALL_CASES:
                    raise ConfigError("Argument must have a case as a variant")
                complex = True
                return spl[-1]
            elif "_" in w:
                # Case 3
                spl = w.split("_")
                while spl and spl[-1].strip() in SKIP_VARS:
                    spl = spl[:-1]
                if not spl or spl[-1] not in ALL_CASES:
                    raise ConfigError("Argument must have a case as a variant")
                complex = True
                return spl[-1]
            return case

        # Pick off specifications from the right hand side of the string s
        s, score = get_score(s)
        s, error = get_error(s)
        s, particle = get_particle(s)
        s, prepositions = get_prepositions(s)
        s, obj = get_direct_object(s)
        verb, iobj = get_indirect_object(s)
        args: List[str] = []
        if iobj:
            args.append(iobj)
        if obj:
            args.append(obj)
        # Add frame to verb database, if this construct is supported (not 'complex')
        if complex:
            return
        vf = cls(
            verb=verb,
            args=args,
            preps=prepositions,
            particle=particle,
            score=score,
            obj=obj,
            iobj=iobj,
        )
        case_key = vf.case_key
        if error:
            # Add this to the error database
            VerbErrors.add_error(verb, args, prepositions, particle, error)
            # Note: In order to parse verbs with wrong arguments,
            # the frame needs to be present as an extra VerbFrame instance
            # that is then marked as an error in GreynirCorrect
            if case_key is not None:
                # This erroneous verb frame has cases as arguments
                cls.WRONG_CASE_FRAMES[vf.key].append(vf)
        # Create a VerbFrame instance
        else:
            if case_key is not None:
                # This verb frame has cases as arguments
                cls.CASE_FRAMES[case_key].append(vf)
            # Add to the dictionary of all verb frames
            cls.ALL_FRAMES[vf.key].append(vf)
            # Add to the set of known verb lemmas
            cls.VERBS.add(verb)

    @classmethod
    def known(cls, verb: str) -> bool:
        """Return True if this is a known verb, i.e. described in Verbs.conf"""
        return verb in cls.VERBS

    @classmethod
    def matches_arguments(cls, verb_with_cases: str) -> bool:
        """Does the given key, e.g. 'skrifa_þgf_þf', match the verb
        with its configured arguments?"""
        return verb_with_cases in cls.CASE_FRAMES

    @classmethod
    def matches_error_arguments(cls, verb_with_cases: str) -> bool:
        """Does the given key match any erroneous verb frames?"""
        return verb_with_cases in cls.WRONG_CASE_FRAMES

    @classmethod
    def matches_preposition(cls, verb_with_cases: str, prep_with_case: str) -> bool:
        """Does the given key - i.e. verb with argument cases -
        match the preposition [+case]?"""
        verb_frames = cls.CASE_FRAMES.get(verb_with_cases)
        if not verb_frames:
            # No frames for this verb with its argument cases
            return False
        # Check the frames one by one and return True if any matches are found
        return any(vf.matches_pp(prep_with_case) for vf in verb_frames)

    @classmethod
    def matches_particle(cls, verb_with_cases: str, particle: str) -> bool:
        """Does the given key - i.e. verb with argument cases - match the particle?"""
        verb_frames = cls.CASE_FRAMES.get(verb_with_cases)
        if not verb_frames:
            # No frames for this verb with its argument cases
            return False
        # Check the frames one by one and return True if any matches are found
        return any(vf.matches_pcl(particle) for vf in verb_frames)

    @classmethod
    @lru_cache(maxsize=1024)
    def verb_score(cls, verb_with_cases: str) -> Optional[int]:
        """Return the score of a verb frame with particular argument cases"""
        verb_frames = cls.CASE_FRAMES.get(verb_with_cases)
        if verb_frames is None:
            # No such verb frame, hence no score
            return None
        # Return the highest score associated with a verb frame with the
        # given arguments, or None if no score was given
        score = None
        for vf in verb_frames:
            if vf.score is not None:
                if score is None:
                    score = vf.score
                else:
                    score = max(score, vf.score)
        return score

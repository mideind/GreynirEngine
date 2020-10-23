"""
    Greynir: Natural language processing for Icelandic

    Verb frame class module

    Copyright (C) 2020 Miðeind ehf.

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
    cast,
    Iterable,
    Iterator,
    Optional,
    Union,
    Dict,
    Tuple,
    Set,
    FrozenSet,
    List,
    Callable,
)

from collections import defaultdict
from functools import lru_cache

from .basics import (
    ConfigError,
    ALL_CASES,
    ALL_GENDERS,
    ALL_NUMBERS,
    SUBCLAUSES,
    REFLPRN,
    REFLPRN_SET,
)


# Key type for preposition frames
PrepKey = str


class PrepositionFrame:

    """ A class containing information about a preposition frame,
        i.e. a preposition controlling a particular case and eventually
        with associated nouns and particles. """

    # Dictionary of all preposition frames, avoiding duplicates
    FRAMES: Dict[PrepKey, "PrepositionFrame"] = dict()

    def __init__(
        self, prep: str, case: str,
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
        """ Obtain a preposition frame for the given preposition and argument case,
            either by returning a previously encountered identical frame,
            or by creating a new one """
        key = cls.make_key(prep, case)
        pf = cls.FRAMES.get(key)
        if pf is None:
            # Not already encountered: Create new
            pf = cls(prep, case)
            cls.FRAMES[key] = pf
        return pf


class VerbFrame:

    """ A class containing information about a verb frame,
        i.e. a verb with arguments and associated prepositions
        and particles. """

    # Verb frames by key, where the key is 'lemma[_argcase1[_argcase2]]',
    # e.g. 'skrifa_þgf_þf'
    CASE_FRAMES: Dict[str, List["VerbFrame"]] = defaultdict(list)
    ALL_FRAMES: Dict[str, List["VerbFrame"]] = defaultdict(list)
    # All known verb lemmas
    VERBS: Set[str] = set()

    def __init__(
        self, verb: str, args: List[str], preps: Iterable[Tuple[str, str]],
        particle: Optional[str], score: Optional[int],
    ) -> None:
        self.verb = verb
        assert 0 <= len(args) <= 2
        # All arguments
        self.args = args
        # Only case arguments
        self.cases = [arg for arg in args if arg in ALL_CASES]
        pfs = [PrepositionFrame.obtain(prep, case) for prep, case in preps]
        self.preps: Dict[PrepKey, PrepositionFrame] = {pf.key: pf for pf in pfs}
        self.particle = particle
        self.score = score

    @property
    def key(self) -> str:
        """ Return a key string containing all args of the verb frame """
        return "_".join([self.verb] + self.args)

    @property
    def case_key(self) -> Optional[str]:
        """ Return a key string containing the cases of the verb frame,
            or None if this is not a frame with only case arguments """
        if len(self.cases) < len(self.args):
            # This verb frame has non-case arguments: return None
            return None
        return "_".join([self.verb] + self.cases)

    def matches(self, prep_with_case: str) -> bool:
        """ Does this verb frame agree with the given preposition[+case]? """
        return prep_with_case in self.preps

    @classmethod
    def create_from_config(cls, s: str) -> None:
        """ Handle verb object specifications in the settings section """
        # Format: verb [arg1] [arg2] [/preposition arg]... [*particle] [$pragma(txt)]
        # arg can be nf, þf, þgf, ef, nh, falls, sig/sér/sín, bági_kk_ft_þf

        # Start by handling the $score() pragma, if present
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

        # Check for $error
        error = None
        ix = s.rfind("$error(")
        if ix >= 0:
            if not s.endswith(")"):
                raise ConfigError("Invalid error pragma; form should be $error(...)")
            error = s[ix + 7 : -1].strip()
            s = s[0:ix].strip()
            if not error:
                raise ConfigError("Expected error specification in $error(...)")

        # Process particles, should only be one in each line
        particle = None
        ix = s.rfind("*")
        if ix >= 0:
            particle = s[ix:].strip()
            s = s[0:ix].strip()
            if " " in particle:
                raise ConfigError("Particle should only be one word")
            elif len(particle) < 2:
                raise ConfigError("Particle should be at least one letter")

        # Process preposition arguments, if any
        prepositions: List[Tuple[str, str]] = []
        ap = s.split("/")
        s = ap[0]
        ix = 1
        while ix < len(ap):
            # We expect something like 'af þgf', or possibly
            # 'fyrir_hönd þf' (where the underscore needs to be replaced by a space)
            p = ap[ix].strip()
            parg = p.split()
            if len(parg) != 2:
                raise ConfigError("Preposition should have exactly one argument")
            if parg[1] not in ALL_CASES and parg[1] not in SUBCLAUSES:
                parg[1] = REFLPRN.get(parg[1], parg[1])
                spl = parg[1].split("_")
                if spl[-1] == "gr":
                    spl = spl[:-1]
                if spl[-1] not in ALL_CASES:
                    raise ConfigError(
                        "Preposition argument must have a case as its last variant"
                    )
            prepositions.append((parg[0].replace("_", " "), parg[1]))
            ix += 1

        # Process verb arguments
        a = s.split()
        if len(a) < 1 or len(a) > 3:
            raise ConfigError("Verb should have zero, one or two arguments")
        verb = a[0]
        if not verb.isalpha():
            raise ConfigError("Verb '{0}' is not a valid word".format(verb))

        args = a[1:]
        # Add to verb database
        if error:
            # VerbObjects.add_error(verb, args, prepositions, particle, error)
            pass
        else:
            # Create a VerbFrame instance
            vf = cls(verb, args, prepositions, particle, score)
            case_key = vf.case_key
            if case_key is not None:
                # This verb frame has cases as arguments
                cls.CASE_FRAMES[case_key].append(vf)
            # Add to the dictionary of all verb frames
            cls.ALL_FRAMES[vf.key].append(vf)
            # Add to the set of known verb lemmas
            cls.VERBS.add(verb)

    @classmethod
    def known(cls, verb: str) -> bool:
        """ Return True if this is a known verb, i.e. described in Verbs.conf """
        return verb in cls.VERBS

    @classmethod
    def matches_arguments(cls, verb_with_cases: str) -> bool:
        """ Does the given key, e.g. 'skrifa_þgf_þf', match the verb
            with its configured arguments? """
        return verb_with_cases in cls.CASE_FRAMES

    @classmethod
    def matches_preposition(cls, verb_with_cases: str, prep_with_case: str) -> bool:
        """ Does the given key - i.e. verb with argument cases -
            match the preposition [+case]? """
        verb_frames = cls.CASE_FRAMES.get(verb_with_cases)
        if not verb_frames:
            # No frames for this verb with its argument cases
            return False
        # Check the frames one by one and return True if any matches are found
        return any(vf.matches(prep_with_case) for vf in verb_frames)

    @classmethod
    @lru_cache(maxsize=1024)
    def verb_score(cls, verb_with_cases: str) -> Optional[int]:
        """ Return the score of a verb frame with particular argument cases """
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

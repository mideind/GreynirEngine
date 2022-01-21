"""
    Greynir: Natural language processing for Icelandic

    Settings module

    Copyright (C) 2021 Miðeind ehf.

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
    Any,
    DefaultDict,
    cast,
    Iterable,
    Optional,
    Union,
    Dict,
    Tuple,
    Set,
    FrozenSet,
    List,
    Callable,
)

import threading

from collections import defaultdict
from tokenizer import BIN_Tuple, BIN_TupleList

from .basics import (
    ConfigError,
    LineReader,
    ALL_CASES,
    ALL_GENDERS,
)
from .verbframe import VerbFrame


# Type for static phrases: ordfl, fl, beyging
StaticPhraseTuple = Tuple[str, str, str]
# Type for preference specifications
PreferenceTuple = Tuple[List[str], List[str], int]


class VerbSubjects:

    """ Wrapper around dictionary of verbs and their subjects,
        initialized from the config file """

    # Dictionary of verbs and their associated set of subject cases
    VERBS: Dict[str, Set[str]] = defaultdict(set)
    _CASE = "þgf"  # Default subject case
    # dict { verb : (wrong_case, correct_case) }
    VERBS_ERRORS: Dict[str, Dict[str, str]] = defaultdict(dict)

    @staticmethod
    def set_case(case: str) -> None:
        """ Set the case of the subject for the following verbs """
        # if case not in { "þf", "þgf", "ef", "none", "lhþt" }:
        #     raise ConfigError("Unknown verb subject case '{0}' in verb_subjects".format(case))
        VerbSubjects._CASE = case  # type: ignore

    @staticmethod
    def add(verb: str) -> None:
        """ Add a verb and its arguments. Called from the config file handler. """
        VerbSubjects.VERBS[verb].add(VerbSubjects._CASE)

    @staticmethod
    def add_error(verb: str, corr: str) -> None:
        """ Add a verb and the correct case. Called from the config file handler. """
        corrlist = corr.split(",")
        errlist = corrlist[0].split("-")
        errkind = errlist[0].strip()
        if errkind == "SUBJ":
            if len(errlist) != 2:
                raise ConfigError("Expected $error(SUBJ-XXX, ...)")
            subj_type = errlist[1].strip()
            if subj_type == "CASE":
                corr_case = corrlist[1].strip()
                VerbSubjects.VERBS_ERRORS[verb][VerbSubjects._CASE] = corr_case
            else:
                raise ConfigError(
                    "Unknown subject specification: 'SUBJ-{0}'".format(subj_type)
                )
        else:
            raise ConfigError(
                "Unknown error type in $error pragma: '{0}'".format(errkind)
            )

    @staticmethod
    def is_strictly_impersonal(verb: str) -> bool:
        """ Returns True if the given verb is only impersonal, i.e. if it appears
            with an $error() pragma in the subject = nf section of verb_subjects
            and cannot be used with a nominative subject: ?'ég dreymdi þig' """
        return "nf" in VerbSubjects.VERBS_ERRORS.get(verb, dict())


class Prepositions:

    """ Wrapper around dictionary of prepositions, initialized from the config file """

    # Dictionary of prepositions: preposition -> { set of cases that it controls }
    PP: Dict[str, Set[str]] = defaultdict(set)
    # Prepositions that can be followed by an infinitive verb phrase
    # 'Beiðnin um að handtaka manninn var send lögreglunni'
    PP_NH: Set[str] = set()
    # Set of common, 'plain' prepositions that require matching with BÍN meanings,
    # cf. logic in matcher_fs() in binparser.py. If filtering according to Phrases.conf
    # is important for a preposition, include it here.
    PP_COMMON: Set[str] = set()
    # A dictionary containing information from $error() pragmas associated
    # with the preposition. Each entry is again a dict of {case: error} specifications,
    # where each error spec is usually a tuple.
    PP_ERRORS: Dict[str, Dict[str, Tuple[Any, ...]]] = defaultdict(dict)

    @staticmethod
    def add(prep: str, case: str, nh: bool) -> None:
        """ Add a preposition and its case. Called from the config file handler. """
        if prep.endswith("*"):
            # Star-marked prepositions are 'plain'
            prep = prep[:-1]
            if not prep:
                raise ConfigError("Asterisk should be affixed to a preposition")
            if " " in prep:
                raise ConfigError(
                    "An asterisk-marked preposition must be a single word"
                )
            # Add to set of 'common'/'plain' prepositions
            Prepositions.PP_COMMON.add(prep)
        Prepositions.PP[prep].add(case)
        if nh:
            Prepositions.PP_NH.add(prep)

    @staticmethod
    def add_error(prep: str, case: str, corr: Tuple[Any, ...]) -> None:
        """ Add an error correction entry for a preposition and a case.
            An error correction entry is usually a tuple. """
        Prepositions.PP_ERRORS[prep][case] = corr


class DisallowedNames:

    """ Wrapper around list of disallowed person name forms """

    # Dictionary of name stems : sets of cases
    STEMS: Dict[str, Set[str]] = {}

    @classmethod
    def add(cls, name: str, cases: Iterable[str]) -> None:
        """ Add an adjective ending and its associated form. """
        cls.STEMS[name] = set(cases)


class UndeclinableAdjectives:

    """ Wrapper around list of undeclinable adjectives """

    # Set of adjectives
    ADJECTIVES: Set[str] = set()

    @classmethod
    def add(cls, wrd: str) -> None:
        """ Add an adjective """
        cls.ADJECTIVES.add(wrd)


class StaticPhrases:

    """ Wrapper around dictionary of static phrases, initialized from the config file """

    # Default meaning for static phrases
    MEANING: StaticPhraseTuple = ("ao", "frasi", "-")
    # Dictionary of the static phrases with their meanings
    MAP: Dict[str, BIN_Tuple] = {}
    # Dictionary of the static phrases with their IFD tags and lemmas
    # { static_phrase : (tag string, lemma string) }
    DETAILS: Dict[str, Tuple[str, str]] = {}
    # List of all static phrases and their meanings
    LIST: List[Tuple[str, BIN_Tuple]] = []
    # Parsing dictionary keyed by first word of phrase
    DICT: DefaultDict[str, List[Tuple[List[str], int]]] = defaultdict(list)
    # Error dictionary:
    # { phrase : (error_code, right_phrase, right_tag_string, right_lemma_string) }
    ERROR_DICT: Dict[str, Tuple[str, str, str, str]] = {}

    @staticmethod
    def add(spec: str) -> None:
        """ Add a static phrase to the dictionary. Called from the config file handler. """
        parts = spec.split(",")
        if len(parts) not in {1, 3}:
            raise ConfigError("Static phrase must include IFD tag list and lemmas")

        phrase = parts[0].strip()

        if len(phrase) < 3 or phrase[0] != '"' or phrase[-1] != '"':
            raise ConfigError("Static phrase must be enclosed in double quotes")

        phrase = phrase[1:-1]

        if phrase in StaticPhrases.MAP:
            raise ConfigError(
                "Static phrase '{0}' is defined more than once".format(phrase)
            )

        # First add to phrase list
        ix = len(StaticPhrases.LIST)
        m = StaticPhrases.MEANING

        mtuple = BIN_Tuple(phrase, 0, m[0], m[1], phrase, m[2])

        # Append the phrase as well as its meaning in tuple form
        StaticPhrases.LIST.append((phrase, mtuple))

        # Add to the main phrase dictionary
        StaticPhrases.MAP[phrase] = mtuple

        # If details are supplied, store them
        if len(parts) == 3:
            tags = parts[1].strip()
            lemmas = parts[2].strip()
            if len(tags) < 3 or tags[0] != '"' or tags[-1] != '"':
                raise ConfigError("IFD tag list must be enclosed in double quotes")
            if len(lemmas) < 3 or lemmas[0] != '"' or lemmas[-1] != '"':
                raise ConfigError("Lemmas must be enclosed in double quotes")
            StaticPhrases.DETAILS[phrase] = (tags[1:-1], lemmas[1:-1])

        # Dictionary structure: dict { firstword: [ (restword_list, phrase_index) ] }

        # Split phrase into words
        wlist = phrase.split()
        # Dictionary is keyed by first word
        StaticPhrases.DICT[wlist[0]].append((wlist[1:], ix))

    @staticmethod
    def add_errors(words: str, error: Tuple[str, str, str, str]) -> None:
        # Dictionary structure:
        # { phrase : (error_code, right_phrase, right_tag_string, right_lemma_string) }
        StaticPhrases.ERROR_DICT[words] = error

    @staticmethod
    def set_meaning(meaning: StaticPhraseTuple) -> None:
        """ Set the default meaning for static phrases """
        StaticPhrases.MEANING = meaning  # type: ignore

    @staticmethod
    def get_meaning(ix: int) -> BIN_TupleList:
        """ Return the meaning of the phrase with index ix """
        return [StaticPhrases.LIST[ix][1]]

    @staticmethod
    def get_length(ix: int) -> int:
        """ Return the length of the phrase with index ix """
        return len(StaticPhrases.LIST[ix][0].split())

    @staticmethod
    def lookup(phrase: str) -> Optional[BIN_Tuple]:
        """ Lookup an entire phrase """
        return StaticPhrases.MAP.get(phrase)

    @staticmethod
    def has_details(phrase: str) -> bool:
        """ Return True if tag and lemma details are available for this phrase """
        return phrase in StaticPhrases.DETAILS

    @staticmethod
    def tags(phrase: str) -> Optional[List[str]]:
        """ Lookup a list of IFD tags for a phrase, if available """
        details = StaticPhrases.DETAILS.get(phrase)
        return None if details is None else details[0].split()

    @staticmethod
    def lemmas(phrase: str) -> Optional[List[str]]:
        """ Lookup a list of lemmas for a phrase, if available """
        details = StaticPhrases.DETAILS.get(phrase)
        return None if details is None else details[1].split()


class AmbigPhrases:

    """ Wrapper around dictionary of potentially ambiguous phrases,
        initialized from the config file """

    # List of tuples of ambiguous phrases and their word category lists,
    # i.e. (words, cats) where words and cats are tuples
    LIST: List[Tuple[List[str], Tuple[FrozenSet[str], ...]]] = []
    # Parsing dictionary keyed by first word of phrase
    DICT: DefaultDict[str, List[Tuple[List[str], int]]] = defaultdict(list)
    # Error dictionary, { phrase : (error_code, right_phrase, right_parts_of_speech) }
    ERROR_DICT: Dict[str, List[List[str]]] = defaultdict(list)

    @staticmethod
    def add(words: List[str], cats: Tuple[FrozenSet[str], ...]) -> None:
        """ Add an ambiguous phrase to the dictionary.
            Called from the config file handler. """

        # First add to phrase list
        ix = len(AmbigPhrases.LIST)

        # Append the phrase as well as its meaning in tuple form
        AmbigPhrases.LIST.append((words, cats))

        # Dictionary structure: dict { firstword: [ (restword_list, phrase_index) ] }
        AmbigPhrases.DICT[words[0]].append((words[1:], ix))

    @staticmethod
    def add_error(words: str, error: List[str]) -> None:
        # Dictionary structure:
        # dict { phrase : (error_code, right_phrase, right_parts_of_speech) }
        AmbigPhrases.ERROR_DICT[words].append(error)

    @staticmethod
    def get_cats(ix: int) -> Tuple[FrozenSet[str], ...]:
        """ Return the word categories for the phrase with index ix """
        return AmbigPhrases.LIST[ix][1]

    @staticmethod
    def get_words(ix: int) -> List[str]:
        """ Return the words for the phrase with index ix """
        return AmbigPhrases.LIST[ix][0]


class NoIndexWords:

    """ Wrapper around set of word stems and categories that should
        not be indexed """

    # Set of (stem, cat) tuples
    SET: Set[Tuple[str, str]] = set()
    # Default category
    _CAT = "so"

    # The word categories that are indexed in the words table
    CATEGORIES_TO_INDEX: FrozenSet[str] = frozenset(
        ("kk", "kvk", "hk", "person_kk", "person_kvk", "entity", "lo", "so")
    )

    @staticmethod
    def set_cat(cat: str) -> None:
        """ Set the category for the following word stems """
        NoIndexWords._CAT = cat  # type: ignore

    @staticmethod
    def add(stem: str) -> None:
        """ Add a word stem and its category. Called from the config file handler. """
        NoIndexWords.SET.add((stem, NoIndexWords._CAT))


class Topics:

    """ Wrapper around topics, represented as a dict (name: set) """

    # Dict of topic name: set
    DICT: Dict[str, Set[str]] = defaultdict(set)
    # Dict of identifier: topic name
    ID: Dict[str, str] = dict()
    # Dict of identifier: threshold (as a float)
    THRESHOLD: Dict[str, Optional[float]] = dict()
    _name: Optional[str] = None

    @staticmethod
    def set_name(name: str) -> None:
        """ Set the topic name for the words that follow """
        a = name.split("|")
        Topics._name = tname = a[0].strip()
        identifier = a[1].strip() if len(a) > 1 else None
        if identifier is None or not identifier.isidentifier():
            raise ConfigError(
                "Topic identifier ('{0}') must be a valid Python identifier".format(
                    identifier or ""
                )
            )
        try:
            threshold = float(a[2].strip()) if len(a) > 2 else None
        except ValueError:
            raise ConfigError("Topic threshold must be a floating point number")
        Topics.ID[tname] = identifier
        Topics.THRESHOLD[tname] = threshold

    @staticmethod
    def add(word: str) -> None:
        """ Add a word stem and its category. Called from the config file handler. """
        if Topics._name is None:
            raise ConfigError(
                "Must set topic name (topic = X) before specifying topic words"
            )
        if "/" not in word:
            raise ConfigError(
                "Topic words must include a slash '/' and a word category"
            )
        cat = word.split("/", maxsplit=1)[1]
        if cat not in {
            "kk",
            "kvk",
            "hk",
            "lo",
            "so",
            "entity",
            "person",
            "person_kk",
            "person_kvk",
        }:
            raise ConfigError(
                "Topic words must be nouns, verbs, adjectives, entities or persons"
            )
        # Add to topic set, after replacing spaces with underscores
        Topics.DICT[Topics._name].add(word.replace(" ", "_"))


class AdjectivePredicates:

    """ A set of arguments and prepositions associated with
        adjectives, for instance 'tengdur þgf', typically read from
        the [adjective_predicates] section of AdjectivePredicates.conf """

    # dict { adjective lemma : set of possible argument cases }
    ARGUMENTS: Dict[str, Set[str]] = defaultdict(set)
    # dict { adjective lemma : set of (preposition, case) }
    PREPOSITIONS: Dict[str, Set[Tuple[str, str]]] = defaultdict(set)

    # dict { adjective lemma : [ (argument case, error code) ] }
    ERROR_DICT: Dict[str, List[Tuple[str, List[str]]]] = defaultdict(list)

    # dict { adjective lemma : set of (preposition, case) }
    ERROR_PREPOSITIONS: Dict[str, Set[Tuple[str, str]]] = defaultdict(set)

    @staticmethod
    def add(
        adj: str, arg: Iterable[str], prepositions: Iterable[Tuple[str, str]]
    ) -> None:
        if arg:
            # Add a case that is associated with an adjective
            AdjectivePredicates.ARGUMENTS[adj].update(arg)
        if prepositions:
            # Add a (preposition, case) tuple that is associated with an adjective
            AdjectivePredicates.PREPOSITIONS[adj].update(prepositions)

    @staticmethod
    def add_error(
        adj: str,
        arg: Iterable[str],
        prepositions: Iterable[Tuple[str, str]],
        error: List[str],
    ) -> None:
        if arg and error:
            for a in arg:
                AdjectivePredicates.ERROR_DICT[adj].append((a, error))
        if prepositions:
            AdjectivePredicates.ERROR_PREPOSITIONS[adj].update(prepositions)


class Preferences:

    """ Wrapper around disambiguation hints, initialized from the config file """

    # Dictionary keyed by word containing a list of tuples (worse, better)
    # where each is a list of terminal prefixes
    DICT: Dict[str, List[PreferenceTuple]] = defaultdict(list)

    @staticmethod
    def add(word: str, worse: List[str], better: List[str], factor: int) -> None:
        """ Add a preference to the dictionary. Called from the config file handler. """
        Preferences.DICT[word].append((worse, better, factor))

    @staticmethod
    def get(word: str) -> Optional[List[PreferenceTuple]]:
        """ Return a list of (worse, better, factor) tuples for the given word """
        return Preferences.DICT.get(word, None)


class NounPreferences:

    """ Wrapper for noun preferences, i.e. to assign priorities to different
        noun stems that can have identical word forms. """

    # This is a dict of noun word forms, giving the relative priorities
    # of different genders
    DICT: Dict[str, Dict[str, int]] = defaultdict(dict)

    @staticmethod
    def add(word: str, worse: str, better: str) -> None:
        """ Add a preference to the dictionary. Called from the config file handler. """
        if worse not in ALL_GENDERS or better not in ALL_GENDERS:
            raise ConfigError("Noun priorities must specify genders (kk, kvk, hk)")
        d = NounPreferences.DICT[word]
        worse_score = d.get(worse)
        better_score = d.get(better)
        if worse_score is not None:
            if better_score is not None:
                raise ConfigError("Conflicting priorities for noun {0}".format(word))
            better_score = worse_score + 4
        elif better_score is not None:
            worse_score = better_score - 4
        else:
            worse_score = -2
            better_score = 2
        d[worse] = worse_score
        d[better] = better_score


class NamePreferences:

    """ Wrapper around well-known person names, initialized from the config file """

    SET: Set[str] = set()

    @staticmethod
    def add(name: str) -> None:
        """ Add a preference to the dictionary. Called from the config file handler. """
        NamePreferences.SET.add(name)


class Settings:

    """ Global settings """

    _lock = threading.Lock()
    loaded: bool = False
    DEBUG: bool = False

    # Configuration settings from the GreynirPackage.conf file

    @staticmethod
    def _handle_settings(s: str) -> None:
        """ Handle config parameters in the settings section """
        a = s.lower().split("=", maxsplit=1)
        par = a[0].strip().lower()
        sval = a[1].strip()
        val: Union[None, str, bool] = sval
        if sval.lower() == "none":
            val = None
        elif sval.lower() == "true":
            val = True
        elif sval.lower() == "false":
            val = False
        try:
            if par == "debug":
                Settings.DEBUG = bool(val)  # type: ignore
            else:
                raise ConfigError("Unknown configuration parameter '{0}'".format(par))
        except ValueError:
            raise ConfigError("Invalid parameter value: {0} = {1}".format(par, val))

    @staticmethod
    def _handle_static_phrases(s: str) -> None:
        """ Handle static phrases in the settings section """
        if "=" not in s:
            ix = s.rfind("$error(")  # Must be at the end
            e: Optional[List[str]] = None
            if ix >= 0:
                # A typical format is
                # $error(error_code, right_phrase, right_parts_of_speech)
                e = s[ix + 7 :].lstrip().rstrip(" )").split(",")
                if len(e) != 4:
                    raise ConfigError("Error pragma should have four parameters")
                s = s[:ix].strip()
            StaticPhrases.add(s)
            if e is not None:
                StaticPhrases.add_errors(s.split(",")[0], (e[0], e[1], e[2], e[3]))
            return
        # Check for a meaning spec
        a = s.split("=", maxsplit=1)
        par = a[0].strip()
        val = a[1].strip()
        if par.lower() == "meaning":
            m = val.split()
            if len(m) == 3:
                StaticPhrases.set_meaning(cast(StaticPhraseTuple, tuple(m)))
            else:
                raise ConfigError("Meaning in static_phrases should have 3 arguments")
        else:
            raise ConfigError(
                "Unknown configuration parameter '{0}' in static_phrases".format(par)
            )

    @staticmethod
    def _handle_verb_objects(s: str) -> None:
        """ Handle verb object specifications in the settings section """
        VerbFrame.create_from_config(s)

    @staticmethod
    def _handle_verb_subjects(s: str) -> None:
        """ Handle verb subject specifications in the settings section """
        # Format: subject = [case] followed by verb list
        a = s.lower().split("=", maxsplit=1)
        if len(a) == 2:
            par = a[0].strip()
            val = a[1].strip()
            if par == "subject":
                VerbSubjects.set_case(val)
            else:
                raise ConfigError("Unknown setting '{0}' in verb_subjects".format(par))
            return
        assert len(a) == 1
        par = s.strip()
        # Check for $error
        e = None
        ix = par.rfind("$error(")
        if ix >= 0:
            if par[-1] != ")":
                raise ConfigError("Missing right parenthesis in $error()")
            e = par[ix + 7 : -1].strip()
            par = par[0:ix].strip()

        if e is not None:
            VerbSubjects.add_error(par, e)
        else:
            VerbSubjects.add(par)

    @staticmethod
    def _handle_undeclinable_adjectives(s: str) -> None:
        """ Handle list of undeclinable adjectives """
        s = s.lower().strip()
        if not s.isalpha():
            raise ConfigError(
                "Expected word but got '{0}' in undeclinable_adjectives".format(s)
            )
        UndeclinableAdjectives.add(s)

    @staticmethod
    def _handle_noindex_words(s: str) -> None:
        """ Handle no index instructions in the settings section """
        # Format: category = [cat] followed by word stem list
        a = s.lower().split("=", maxsplit=1)
        par = a[0].strip()
        if len(a) == 2:
            val = a[1].strip()
            if par == "category":
                NoIndexWords.set_cat(val)
            else:
                raise ConfigError("Unknown setting '{0}' in noindex_words".format(par))
            return
        assert len(a) == 1
        NoIndexWords.add(par)

    @staticmethod
    def _handle_topics(s: str) -> None:
        """ Handle topic specifications """
        # Format: name = [topic name] followed by word stem list in the form word/cat
        a = s.split("=", maxsplit=1)
        par = a[0].strip()
        if len(a) == 2:
            val = a[1].strip()
            if par.lower() == "topic":
                Topics.set_name(val)
            else:
                raise ConfigError("Unknown setting '{0}' in topics".format(par))
            return
        assert len(a) == 1
        Topics.add(par)

    @staticmethod
    def _handle_prepositions(s: str) -> None:
        """ Handle preposition specifications in the settings section """
        # Format: pw1 pw2... case [nh|nhx]  [$error(X)]
        error = False
        corr: Optional[Tuple[str, Optional[str]]] = None
        ix = s.rfind("$error(")  # Must be at the end
        if ix >= 0:
            # A typical format is $error(FORM-inn_á)
            error = True
            e = s[ix + 7 :].lstrip().rstrip(" )").split("-")
            if len(e) == 2:
                # Probably $error(FORM-xxx_xxx)
                corr = (e[0], " ".join(e[1].split("_")))
            elif len(e) == 1:
                # Probably $error(COMPOUND)
                corr = (e[0], None)
            else:
                raise ConfigError(
                    "$error() pragma should have the form XXX[-yyy] "
                    "where XXX is a category and yyy is a phrase"
                )
            s = s[:ix].strip()
        a = s.split()
        if len(a) < 2:
            raise ConfigError("Preposition must specify a word and a case argument")
        c = a[-1]  # Case or 'nh'
        nh = c == "nh"
        if nh:
            # This is a preposition that can be followed by an infinitive verb phrase:
            # 'Beiðnin um að handtaka manninn var send lögreglunni'
            a = a[:-1]
            if len(a) < 2:
                raise ConfigError(
                    "Preposition must specify a word, case and 'nh' argument"
                )
            c = a[-1]
        if c not in {"nf", "þf", "þgf", "ef"}:  # Not a valid case
            raise ConfigError("Preposition must have a case argument (nf/þf/þgf/ef)")
        # Preposition, possibly multi-word, and possibly suffixed by an asterisk
        pp = " ".join(a[:-1])
        Prepositions.add(pp, c, nh)
        if error:
            assert corr is not None
            Prepositions.add_error(pp, c, corr)

    @staticmethod
    def _handle_preferences(s: str) -> None:
        """ Handle ambiguity preference hints in the settings section """
        # Format: word worse1 worse2... < better
        # If two less-than signs are used, the preference is even stronger (tripled)
        # If three less-than signs are used, the preference is super strong (nine-fold)
        factor = 9
        a = s.lower().split("<<<", maxsplit=1)
        if len(a) != 2:
            factor = 3
            a = s.lower().split("<<", maxsplit=1)
            if len(a) != 2:
                # Not doubled preference: try a normal one
                a = s.lower().split("<", maxsplit=1)
                factor = 1
        if len(a) != 2:
            raise ConfigError("Ambiguity preference missing less-than sign '<'")
        w = a[0].split()
        if len(w) < 2:
            raise ConfigError(
                "Ambiguity preference must have at least one 'worse' category"
            )
        b = a[1].split()
        if len(b) < 1:
            raise ConfigError(
                "Ambiguity preference must have at least one 'better' category"
            )
        Preferences.add(w[0], w[1:], b, factor)

    @staticmethod
    def _handle_noun_preferences(s: str) -> None:
        """ Handle noun preference hints in the settings section """
        # Format: noun worse1 worse2... < better
        # The worse and better specifiers are gender names (kk, kvk, hk)
        a = s.lower().split("<", maxsplit=1)
        if len(a) != 2:
            raise ConfigError("Noun preference missing less-than sign '<'")
        w = a[0].split()
        if len(w) != 2:
            raise ConfigError("Noun preference must have exactly one 'worse' gender")
        b = a[1].split()
        if len(b) != 1:
            raise ConfigError("Noun preference must have exactly one 'better' gender")
        NounPreferences.add(w[0], w[1], b[0])

    @staticmethod
    def _handle_name_preferences(s: str) -> None:
        """ Handle well-known person names in the settings section """
        NamePreferences.add(s)

    @staticmethod
    def _handle_ambiguous_phrases(s: str) -> None:
        """ Handle ambiguous phrase guidance in the settings section """
        # Format: "word1 word2..." cat1 cat2...
        error = False
        if s[0] != '"':
            raise ConfigError("Ambiguous phrase must be enclosed in double quotes")
        ix = s.rfind("$error(")  # Must be at the end
        e: List[str] = []
        if ix >= 0:
            error = True
            # A typical format is
            # $error(error_code, right_phrase, right_parts_of_speech)
            e = s[ix + 7 :].lstrip().rstrip(" )").split(", ")
            s = s[:ix].strip()
        q = s.rfind('"')
        if q <= 0:
            raise ConfigError("Ambiguous phrase must be enclosed in double quotes")
        # Obtain a list of the words in the phrase
        words = s[1:q].strip().lower().split()
        if any("*" in word and not word.endswith("*") for word in words):
            raise ConfigError("An asterisk is only allowed at the end of lemmas")
        if len(words) < 2:
            raise ConfigError("Ambiguous phrase must contain at least two words")
        # Obtain a list of the corresponding word categories
        cats = s[q + 1 :].strip().lower().split()
        if len(words) != len(cats):
            raise ConfigError(
                "Ambiguous phrase has {0} words but {1} category sets".format(
                    len(words), len(cats)
                )
            )
        # Convert the list of category specifiers to a tuple of frozensets of
        # word categories
        cats_t: Tuple[FrozenSet[str], ...] = tuple(
            frozenset(cat.split("/")) for cat in cats
        )
        # Check for something like ao/ or so//fs
        if any("" in cats_set for cats_set in cats_t):
            raise ConfigError("Empty category set not allowed")
        # Check for something like ao/*
        if any("*" in cats_set and len(cats_set) > 1 for cats_set in cats_t):
            raise ConfigError("Redundant category specified alongside wildcard '*'")
        AmbigPhrases.add(words, cats_t)
        if error:
            AmbigPhrases.add_error(s[1:q].strip().lower(), e)

    @staticmethod
    def _handle_disallowed_names(s: str) -> None:
        """ Handle disallowed person name forms from the settings section """
        # Format: Name-stem case1 case2...
        a = s.split()
        if len(a) < 2:
            raise ConfigError(
                "Disallowed names must specify a name and at least one case"
            )
        DisallowedNames.add(a[0], a[1:])

    @staticmethod
    def _handle_adjective_predicates(s: str) -> None:
        # Process preposition arguments, if any
        error = False
        ix = s.rfind("$error(")  # Must be at the end
        e: List[str] = []
        if ix >= 0:
            error = True
            # A typical format is
            # $error(error_code, right_phrase, right_parts_of_speech)
            e = s[ix + 7 :].lstrip().rstrip(" )").split(",")
            s = s[:ix].strip()

        prepositions: List[Tuple[str, str]] = []
        ap = s.split("/")
        s = ap[0]
        ix = 1
        while len(ap) > ix:
            # We expect something like 'af þgf'
            p = ap[ix].strip()
            parg = p.split()
            if len(parg) != 2:
                raise ConfigError("Preposition should have exactly one argument")
            if parg[1] not in ALL_CASES:
                raise ConfigError("Unknown argument case for preposition")
            prepositions.append((parg[0], parg[1]))
            ix += 1
        a = s.split()
        adj = a[0]
        if error:
            AdjectivePredicates.add_error(adj, a[1:], prepositions, e)
        else:
            AdjectivePredicates.add(adj, a[1:], prepositions)

    @staticmethod
    def read(fname: str, force: bool=False) -> None:
        """ Read configuration file """

        with Settings._lock:

            if Settings.loaded and not force:
                return

            CONFIG_HANDLERS: Dict[str, Callable[[str], None]] = {
                "settings": Settings._handle_settings,
                "static_phrases": Settings._handle_static_phrases,
                "verb_objects": Settings._handle_verb_objects,
                "verb_subjects": Settings._handle_verb_subjects,
                "prepositions": Settings._handle_prepositions,
                "preferences": Settings._handle_preferences,
                "noun_preferences": Settings._handle_noun_preferences,
                "name_preferences": Settings._handle_name_preferences,
                "ambiguous_phrases": Settings._handle_ambiguous_phrases,
                "undeclinable_adjectives": Settings._handle_undeclinable_adjectives,
                "disallowed_names": Settings._handle_disallowed_names,
                "noindex_words": Settings._handle_noindex_words,
                "topics": Settings._handle_topics,
                "adjective_predicates": Settings._handle_adjective_predicates,
            }
            handler: Optional[Callable[[str], None]] = None  # Current section handler

            rdr: Optional[LineReader] = None
            try:
                rdr = LineReader(fname, package_name=__name__)
                for s in rdr.lines():
                    # Ignore comments
                    ix = s.find("#")
                    if ix >= 0:
                        s = s[0:ix]
                    s = s.strip()
                    if not s:
                        # Blank line: ignore
                        continue
                    if s[0] == "[" and s[-1] == "]":
                        # New section
                        section = s[1:-1].strip().lower()
                        if section in CONFIG_HANDLERS:
                            handler = CONFIG_HANDLERS[section]
                            continue
                        raise ConfigError("Unknown section name '{0}'".format(section))
                    if handler is None:
                        raise ConfigError("No handler for config line '{0}'".format(s))
                    # Call the correct handler depending on the section
                    try:
                        handler(s)
                    except ConfigError as e:
                        # Add file name and line number information to the exception
                        # if it's not already there
                        e.set_pos(rdr.fname(), rdr.line())
                        raise e

            except ConfigError as e:
                # Add file name and line number information to the exception
                # if it's not already there
                if rdr:
                    e.set_pos(rdr.fname(), rdr.line())
                raise e

            Settings.loaded = True

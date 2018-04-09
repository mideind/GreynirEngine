.. _overview:

Overview
========

**Reynir** parses sentences of Icelandic text into **parse trees**.
A parse tree recursively describes the grammatical structure
of the sentence, including its noun phrases, verb phrases,
prepositional phrases, etc.

The individual tokens (words, numbers, punctuation, etc.) of the sentence
correspond to leaves in the parse tree.

By examining and processing the parse tree, information and meaning
can be extracted from the sentence.

Example
-------

Here is a short example of what can be done with Reynir::

	>>> from reynir import Reynir
	>>> r = Reynir()
	>>> job = r.submit("Ása sá sól.")
	>>> sent = next(job.sentences())
	>>> sent.parse()
	True
	>>> sent.tree.nouns
	['Ása', 'sól']
	>>> sent.tree.verbs
	['sjá']
	>>> # Show the subject noun phrase
	>>> sent.tree.S.IP.NP_SUBJ.stems
	['Ása']
	>>> # Show the verb phrase
	>>> sent.tree.S.IP.VP.stems
	['sjá', 'sól']
	>>> # Show the object of the verb
	>>> sent.tree.S.IP.VP.NP_OBJ.stems
	['sól']


What Reynir does
----------------

Reynir starts by **tokenizing** your text, i.e. dividing it up onto individual words,
numbers, punctuation and other tokens. For this, it uses the separate
`Tokenizer <https://github.com/vthorsteinsson/Tokenizer>`_ package, which is automatically
installed with Reynir.

After tokenization, Reynir proceeds to **parse** the text according to a *context-free grammar* for the
modern Icelandic language. This grammar contains rules describing how sentences and the various
subparts thereof can be validly constructed.

Almost all sentences are **ambiguous**. This means that there multiple parse trees
that can validly describe the sentence according to the grammar rules. Reynir thus has
to choose a single best tree from the forest of possible trees. It does this with a scoring
heuristic which assigns higher scores to common word forms and grammatical constructs, and lower
scores to rare word forms and uncommon constructs. The parse tree with the highest overall
score wins and is returned from the ``parse()`` function.

Once the best parse tree has been found, it is available for various kinds of **queries**.
You can access word stems, extract noun and verb phrases as shown above, look for
patterns via wildcard matching, and much more. This is described in detail in the
:ref:`reference`.


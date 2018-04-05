===============================================================
Reynir: A fast, efficient natural language parser for Icelandic
===============================================================

********
Overview
********
**Reynir** parses sentences of Icelandic text into **parse trees**.
A parse tree recursively describes the grammatical structure
of the sentence, including its noun phrases, verb phrases,
prepositional phrases, etc.

The individual tokens (words and punctuation) of the sentence
correspond to leaves in the parse tree.

By examining and processing the parse tree, information and meaning
can be extracted from the sentence.

*******
Example
*******
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
>>> sent.tree.flat
'P S-MAIN IP NP-SUBJ no_et_nf_kvk /NP-SUBJ VP so_1_þf_et_p3 NP-OBJ no_et_þf_kvk /NP-OBJ /VP /IP /S-MAIN p /P'
>>> sent.tree.S.IP.NP_SUBJ.stems # The subject noun phrase (S.IP.NP also works)
['Ása']
>>> sent.tree.S.IP.VP.stems # The verb phrase
['sjá', 'sól']
>>> sent.tree.S.IP.VP.NP_OBJ.stems # The object within the verb phrase (S.IP.VP.NP also works)
['sól']

*************
Prerequisites
*************
This package runs on CPython 3.4 or newer, and on PyPy 3.5
or newer. PyPy is recommended for best performance.

You need to have ``python3-dev`` installed on your system::

	# Debian or Ubuntu:
	sudo apt-get install python3-dev

************
Installation
************
To install this package::

	pip3 install reynir

*****
Usage
*****
To use::

	from reynir import Reynir

	my_text = ("Hér er verið að þátta íslenskan texta."
		" Það er skemmtilegt.")

	r = Reynir()
	job = r.submit(my_text)

	# Iterate through sentences and parse each one:
	for sent in job:
		if sent.parse():
			# sentence parsed successfully
			# do something with sent.tree
			print("Successfully parsed '{0}'".format(s.tidy_text))
		else:
			# an error occurred in the parse
			# the error token index is at sent.err_index
			print("Could not parse '{0}'".format(sent.tidy_text))

	# Alternatively, split into paragraphs first:
	job = r.submit(my_text)
	for p in job.paragraphs(): # Yields paragraphs
		for sent in p.sentences(): # Yields sentences
			if sent.parse():
				# sentence parsed successfully
				# do something with sent.tree
				print("Successfully parsed '{0}'".format(s.tidy_text))
			else:
				# an error occurred in the parse
				# the error token index is at sent.err_index
				print("Could not parse '{0}'".format(sent.tidy_text))

	# After parsing all sentences in a job, the following
	# statistics are available:
	num_sentences = job.num_sentences   # Total number of sentences
	num_parsed = job.num_parsed         # Thereof successfully parsed
	ambiguity = job.ambiguity           # Average ambiguity factor
	parse_time = job.parse_time         # Elapsed time since job was created

*********
Reference
*********

lorem ipsum

#!/usr/bin/env python

import os
import pathlib
import subprocess
from reynir.simpletree import SimpleTree
import annotald.util as util

EVALBCOMMAND = ' -p ./stillingar.prm' # handpsd is first argument, then genpsd
ICENLP = pathlib.Path("/home/hulda/github/icenlp/IceNLPCore/bat")
IPFOLDER = ICENLP / 'iceparser'
ICEPARSER = './iceparser.sh'
TAGFOLDER = ICENLP / 'icetagger'
TAGGER = './icetagger.sh'  # TODO change to another tagger, IceStagger or ABLtagger


SKIP_LINES = set(["(META", "(ID-CORPUS", "(ID-LOCAL", "(URL", "(COMMENT"])
SKIP_SEGS = set(["lemma", "exp"])

# Phrases from Greynir schema not included in the general schemas
NOT_INCLUDED = set(["P", "TO"])

# Phrases from Greynir schema not included in the partial general schema
NOT_PARTIAL = set([
	"IP",
	"IP-INF",
	"CP",
	"CP-ADV-ACK",
	"CP-ADV-CAUSE",
	"CP-ADV-COND",
	"CP-ADV-PURP",
	"CP-ADV-TEMP",
	"CP-ADV-CMP",
	"CP-QUE",
	"CP-REL",
	"CP-THT",
	"CP-QUOTE",
	"S0",
	"S0-X",
	"S",
	"S-MAIN",
	"S-HEADING",
	"S-PREFIX"
	"S-QUE",
	])

# Map phrases and leaves in Greynir and IceNLP to the generalized schema
GENERALIZE = {
	# terminals in Greynir
	"no" : "n",
	"kvk" : "n",
	"kk" : "n",
	"hk" : "n",
	"person" : "n",
	"sérnafn" : "n",
	"entity" : "n",
	"fyrirtæki" : "n",
	"gata" : "n",
	"so" : "s",
	"ao" : "a",
	"eo" : "a",
	"fs" : "a",
	"lo" : "l",
	"fn" : "f",
	"pfn" : "f",
	"abfn" : "f",
	"gr" : "g",
	"st" : "c",
	"stt" : "c",
	"nhm" : "c",
	"abbrev" : "k",
	"to" : "t",
	"töl" : "t",
	"tala" : "t",
	"talameðbókstaf" : "t",
	"prósenta" : "t",
	"raðnr" : "t",
	"ártal" : "t",
	"dagsafs" : "a",
	"dagsföst" : "a",
	"tími" : "t",
	"tímapunkturafs" : "a",
	"tímapunkturfast" : "a",
	"uh" : "u",
	"myllumerki" : "v",
	"grm" : "p",
	"lén" : "v",
	"notandanafn" : "v",
	"vefslóð" : "v",
	"tölvupóstfang" : "v",
	"sameind" : "m",
	"mælieining" : "t",
	"símanúmer" : "t",
	"kennitala" : "t",
	"vörunúmer" : "t",
	"entity" : "e",
	"foreign" : "e",
	"x" : "x",
	# Non-terminals in Greynir and IceNLP
	"AdvP" : "ADVP",
	"MWE_AdvP" : "ADVP",
	"MWE_AdvP-OBJ" : "ADVP", # Skoða dæmin
	"TIMEX" : "ADVP",
	"InjP" : "ADVP",
	"ADVP" : "ADVP",
	"ADVP-DATE" : "ADVP",
	"ADVP-DATE-ABS" : "ADVP",
	"ADVP-DATE-REL" : "ADVP",
	"ADVP-DIR" : "ADVP",
	"ADVP-DUR-ABS" : "ADVP",
	"ADVP-DUR-REL" : "ADVP",
	"ADVP-DUR-TIME" : "ADVP",
	"ADVP-TIMESTAMP-ABS" : "ADVP",
	"ADVP-TIMESTAMP-REL" : "ADVP",
	"ADVP-TMP-SET" : "ADVP",
	"ADVP-PCL" : "ADVP",
	"ADVP-LOC" : "ADVP",
	"AP" : "ADJP",
	"APs" : "ADJP",
	"AP-SUBJ" : "ADJP-SUBJ",
	"APs-SUBJ" : "ADJP-SUBJ",
	"AP-OBJ" : "ADJP-OBJ",
	"APs-OBJ" : "ADJP-OBJ",
	"AP-IOBJ" : "ADJP-IOBJ",
	"APs-IOBJ" : "ADJP-IOBJ",
	"AP-COMP" : "ADJP-PRD",
	"APs-COMP" : "ADJP-PRD",
	"ADJP" : "ADJP",
	"NPs" : "NP",
	"MWE_AP" : "ADJP",
	"NP-OBJAP" : "NP-ADP",
	"NPs-OBJAP" : "NP-ADP",
	"NP-QUAL" : "NP-POSS",
	"NPs-QUAL" : "NP-POSS",
	"NP-QUAL-SUBJ" : "NP-SUBJ", # Skoða betur
	"NP-COMP" : "NP-PRD",
	"NP-QUAL-COMP" : "NP-COMP", # Skoða betur
	"NPs-COMP" : "NP-PRD",
	"NP-OBJNOM" : "NP",
	"NPs-OBJNOM" : "NP",
	"NP-TIMEX" : "NP",
	"NP" : "NP",
	"NP-SUBJ" : "NP-SUBJ",
	"NPs-SUBJ" : "NP-SUBJ",
	"NP-OBJ" : "NP-OBJ",
	"NPs-OBJ" : "NP-OBJ",
	"NP-QUAL-OBJ" : "NP-OBJ", # Skoða betur
	"NP-IOBJ" : "NP-IOBJ",
	"NPs-IOBJ" : "NP-IOBJ",
	"NP-PRD" : "NP-PRD",
	"NP-POSS" : "NP-POSS",
	"NP-ADP" : "NP-ADP",
	"NP-ES" : "NP",
	"NP-DAT" : "NP",
	"NP-ADDR" : "NP",
	"NP-AGE" : "NP",
	"NP-MEASURE" : "NP",
	"NP-COMPANY" : "NP",
	"NP-TITLE" : "NP",
	"NP-SOURCE" : "NP",
	"NP-PREFIX" : "NP",
	"MWE_PP" : "PP",
	"PP" : "PP",
	"PP-SUBJ" : "PP", # Skoða betur
	"PP-DIR" : "PP",
	"PP-LOC" : "PP",
	"VPi" : "VP",
	"VPb" : "VP",
	"VPs" : "VP",
	"VPp" : "VP",
	"VPp-COMP" : "VP-PRD",
	"VPg" : "VP",
	"VP?Vn?" : "VP",   # This shouldn't happen
	"VP" : "VP",
	"VP-AUX" : "VP-AUX",
	"SCP" : "C",
	"CP" : "C",
	"MWE_CP" : "C",
	"C" : "C",
	"FRW" : "FOREIGN",
	"FRWs" : "FOREIGN",
	"FOREIGN" : "FOREIGN",

	"IP" : "IP",
	"IP-INF" : "IP",
	"CP-ADV" : "CP-ADV",
	"CP-ADV-ACK" : "CP-ADV",
	"CP-ADV-CAUSE" : "CP-ADV",
	"CP-ADV-COND" : "CP-ADV",
	"CP-ADV-CONS" : "CP-ADV",
	"CP-ADV-PURP" : "CP-ADV",
	"CP-ADV-TEMP" : "CP-ADV",
	"CP-ADV-CMP" : "CP-ADV",
	"CP-QUOTE" : "CP",
	"CP-SOURCE" : "CP",
	"CP-QUE" : "CP-QUE",
	"CP-REL" : "CP-REL",
	"CP-THT" : "CP-THT",
	"CP-EXPLAIN" : "CP",
	"S0" : "S0",
	"S0-X" : "S0",
	"S-MAIN" : "S",
	"S-HEADING" : "S",
	"S-PREFIX" : "ADVP",
	"S-QUE" : "S",
	"S-QUOTE" : "S",
	"S-EXPLAIN" : "S",

	"P" : "",
	"TO" : "",
	"FOREIGN" : "",
}

PUNCT = "?!:.,;/+*-\"\'$%&()"

def get_annoparse(infolder, outfolder, insuffix=".txt", outsuffix=".psd", overwrite=False):
	# Fær inn möppu með textum, mögulega einhver skilyrði um suffix eða stem sem á að velja
	# Skilar þáttuðum skjölum í tiltekna möppu
	# Og tiltaka endingu!
	for p in infolder.iterdir():
		# Útbúa skipunina
		ptext = p.stem + insuffix
		ptext = infolder / ptext
		pout = p.stem + outsuffix
		pout = outfolder / pout
		
		if pout.exists() and not overwrite:
			continue

		command = "annoparse -i {} -o {}".format(ptext, pout)
		skil = subprocess.Popen([command], shell=True, stdout=subprocess.PIPE).communicate()[0]
		print(skil)

def get_ipparse(infolder, outfolder, insuffix=".txt", outsuffix=".ippsd", overwrite=False):
	# Fær inn möppu með textum, mögulega einhver skilyrði um suffix eða stem sem á að velja
	# Sækir IceNLP-þáttun fyrir hvert skjal og skrifar í skjal í tiltekna möppu
	
	origpath = pathlib.Path().absolute()

	# Nauðsynlegt til að IceTagger virki rétt
	os.chdir(TAGFOLDER)
	tagsuffix = '.tagged'
	tagfolder = origpath / 'gentag'

	for p in infolder.iterdir():
		ptext = p.stem + insuffix
		ptext = infolder / ptext
		ptag = p.stem + tagsuffix
		ptag = tagfolder / ptag

		if ptag.exists() and not overwrite:
			continue

		command = "{} -i {} -o {} -lf 2 -of 2".format(TAGGER, ptext, ptag)
		skil = subprocess.Popen([command], shell=True, stdout=subprocess.PIPE).communicate()[0]
		print(skil)


	# Nauðsynlegt til að IceParser virki rétt
	os.chdir(IPFOLDER)

	for p in infolder.iterdir():
		ptext = p.stem + tagsuffix
		ptext = tagfolder / ptext
		pout = p.stem + outsuffix
		pout = outfolder / pout

		if pout.exists() and not overwrite:
			continue

		command = "{} -i {} -o {} -f -m".format(ICEPARSER, ptext, pout)
		skil = subprocess.Popen([command], shell=True, stdout=subprocess.PIPE).communicate()[0]
		print(skil)

	# Back to original
	os.chdir(origpath)

def annotald_to_general(infolder, outfolder, insuffix, outsuffix, deep=True, overwrite=False):
	for p in infolder.iterdir():
		if p.suffix != insuffix:
			# File has other suffix
			continue

		pin = p.stem + insuffix
		pin = infolder / pin
		pout = p.stem + outsuffix
		pout = outfolder / pout
		

		if pout.exists() and not overwrite:
			continue

		print("Transforming file: {}".format(p.stem+p.suffix))

		# Að mestu eins og readTrees() í annotald.treedrawing
		treetext = pin.read_text()
		treetext = util.scrubText(treetext)
		trees = treetext.strip().split("\n\n")

		outtrees = general_clean(trees, deep)
		pout.write_text(outtrees)

# Deprecated
def greynir_to_both_general(infolder, outfolder, insuffix=".grgld", deepsuffix =".grdbr", partialsuffix=".grpbr", overwrite=False):
	# Fær inn möppu með þáttuðum skjölum á Annotaldsforminu
	# Býr til skjöl á almenna þáttunarforminu á svigaformi, bæði djúp- og hlutþáttun
	# Setur í tiltekna möppu
	for p in infolder.iterdir():
		if p.suffix != insuffix:
			# File has other suffix
			continue

		pin = p.stem + insuffix
		pin = infolder / pin
		pdeep = p.stem + deepsuffix
		pdeep = outfolder / pdeep
		ppart = p.stem + partialsuffix
		ppart = outfolder / ppart
		

		if pdeep.exists() and not overwrite:
			continue
		if ppart.exists() and not overwrite:
			continue

		print("Transforming Greynir: {}".format(p.stem))

		# Að mestu eins og readTrees() í annotald.treedrawing
		treetext = pin.read_text()
		treetext = util.scrubText(treetext)
		trees = treetext.strip().split("\n\n")

		deeptrees = general_clean(trees, True)
		partialtrees = general_clean(trees, False)
		pdeep.write_text(deeptrees)
		ppart.write_text(partialtrees)

def general_clean(trees, deep=True):
	# Forvinnsla 
	outtrees = "" # All partial trees for file
	text = []
	phrases = Stack()
	numwrongs = 0
	for tree in trees:
		skips = 0
		cleantree = ""
		# We know there is only one leaf in each line
		for line in tree.split("\n"):
			if not line:
				continue
			text = [] # Text in each leaf
			segs = False # Segs found, should skip content of brackets
			# 1. (META, (COMMENT, ... in SKIP_LINES -- skip line altogether
			# 2. Single ( -- extra bracket around tree, won't collect
			# 3. (PP -- collect "(PP" and push one; except if not included
			# 4. (no_kvk_nf_et -- collect "(no_kvk_nf_et" and push one
			# 5. (lemma, (exp_seg, (exp_abbrev -- in SKIP_SEGS, increase numofskipsegs by one. Ignore rest of sentence except for )) or more.
			# 6. ) or )))))) -- look at numofskipsegs, otherwise just add
			# 7. word -- single word. Collect in text, until find (lemma
			# 7B. word))) --- If numofskipphrases, check that.
			# 8. (grm -- no lemma here, can mess things up.
			# 9. \) -- escaped parentheses. Opening parentheses, \(, are not a problem. Is the word.
			for item in line.lstrip().split():
				#print("\tA.:{}".format(cleantree))
				#print("\tskips:{}, text:{}".format(skips, text))
				#print(item)
				if item.startswith("\\)"):
					item = item.replace("\\)", "&#41;")
				elif item.startswith("\\()") or item.startswith("\\("): # Latter case for unknown tokens
					item = item.replace("\\(", "&#40;")
				if not item:
					continue
				elif item in SKIP_LINES: # Case 1
					#print("\t0:{}".format(cleantree))
					break	# Don't collect anything in line					
				elif "(" in item:  # Byrja nýjan lið
					#print("\t1A:{}".format(cleantree))
					if text: # Write before do anything else
						#print("\t1B:{}".format(cleantree))
						cleantree = cleantree + "_".join(text)
						#print("\t1C:{}".format(cleantree))
						text = []
					phrase = item.replace("(", "").split("_")[0]  
					if not phrase: # Stakur (, vil ekki fá í cleantree 
						#print("\t1D:{}".format(cleantree))
						skips +=1
						phrases.push("")
						continue					
					if phrase in SKIP_SEGS:
						#print("\t1E:{}".format(cleantree))
						skips +=1
						segs = True
						phrases.push(phrase)
						continue
					phrase = GENERALIZE[phrase]
					if not phrase or phrase in NOT_INCLUDED:
						#print("\t1F:{}".format(cleantree))
						skips +=1
						phrases.push(phrase)
						continue
					if not deep and phrase in NOT_PARTIAL:
						skips +=1
						phrases.push(phrase)
						continue
					phrases.push(phrase)
					#print("\t1G:{}".format(cleantree))
					cleantree = cleantree + "(" + phrase + " "
					#print("\t1H:{}".format(cleantree))
				elif ")" in item:
					#print("\t2A:{}".format(cleantree))
					if segs:
						segs = False
						text = []
					else:
						wordinleaf = item.replace(")", "")
						text.append(wordinleaf)
					brackets = item.count(")")
					bwrite = ""
					for x in range(brackets):
						phrase = phrases.pop()
						#print("Popping:{}".format(phrase))
						if not phrase or phrase in NOT_INCLUDED or phrase in SKIP_SEGS: # Hendi samsvarandi )
							skips -=1
							#print("\t2B:{}".format(cleantree))
						elif not deep and phrase in NOT_PARTIAL:
							skips -=1
						else:
							#print("\t2C:{}".format(cleantree))
							bwrite = bwrite + ")"
					#print("\t2D:{}".format(cleantree))
					cleantree = cleantree + "_".join(text) + bwrite + " "
					#print("\t2E:{}".format(cleantree))
					text = []
				else:
					#print("\t3A:{}".format(cleantree))
					text.append(item)

		#print("\tB.:{}".format(cleantree))
		cleantree = cleantree.rstrip().replace(" )", ")")

		#print("\tC.:{}".format(cleantree))
		if cleantree.count("(")  != cleantree.count(")"):
			numwrongs +=1
		outtrees = outtrees + cleantree + "\n" 
	#print("numwrongs: {}".format(numwrongs))
	return outtrees

def ip_to_general(infolder, outfolder, insuffix=".ippsd", outsuffix=".ippbr", overwrite=False):
	for p in infolder.iterdir():
		if p.suffix != insuffix:
			# File has other suffix
			continue

		pin = p.stem + insuffix
		pin = infolder / pin
		pout = p.stem + outsuffix
		pout = outfolder / pout

		if pout.exists() and not overwrite:
			continue

		print("Transforming IceParser: {}".format(p.stem))
		treetext = pin.read_text()
		treetext = treetext.replace("\n \n", "\n") # Remove (almost) empty lines
		trees = treetext.strip().split("\n") # One tree per line
		outtrees = general_ipclean(trees)
		pout.write_text(outtrees)

def general_ipclean(trees):
	# Forvinnsla 
	outtrees = "" # All partial trees for file
	text = []
	phrases = Stack()
	numwrongs = 0
	for tree in trees:
		skips = 0
		cleantree = ""
		text = [] # Text in each leaf
		next_is_tag = False
		for item in tree.lstrip().split():
			#print("\tA.:{}".format(cleantree))
			#print("\tskips:{}, text:{}".format(skips, text))
			#print(item)
			if not item:
				continue
			if item.startswith("\)"):
				item = item.replace("\)", "&#41;")
			elif item.startswith("\("):
				item = item.replace("\(", "&#40;")
			elif "[" in item:  # Byrja nýjan lið
				#print("\t1A:{}".format(cleantree))
				if text: # Write before do anything else
					#print("\t1B:{}".format(cleantree))
					cleantree = cleantree + "_".join(text)
					#print("\t1C:{}".format(cleantree))
					text = []
				phrase = item.replace("[", "").replace("<", "").replace(">", "") 
				if not phrase:  # Empty "[ "! Should be escaped in parsing/tagging
					skips+=1
					continue
				phrase = GENERALIZE[phrase]
				#print("\t1G:{}".format(cleantree))
				cleantree = cleantree + "(" + phrase + " "
				#print("\t1H:{}".format(cleantree))
			elif "]" in item:
				#print("\t2A:{}".format(cleantree))
				wordinleaf = item.replace("]", "")
				if text:
					text.append(wordinleaf)
				#print("\t2D:{}".format(cleantree))
				if skips < 0:
					skips-=1
					cleantree = cleantree + "_".join(text)
				else:
					cleantree = cleantree + "_".join(text) + ") "
				#print("\t2E:{}".format(cleantree))
				text = []
			elif next_is_tag:  # Mark fyrir fyrra orð fundið
				#print("\t3A:{}".format(cleantree))
				if item in PUNCT:
					item = "p"
				cleantree = cleantree + "(" + item[0] + " " + "_".join(text) + ") "
				next_is_tag = False
				text = []
			else:  # Stakt orð fundið
				text.append(item)
				next_is_tag = True

		#print("\tB.:{}".format(cleantree))
		cleantree = cleantree.rstrip().replace(") )", "))")

		#print("\tC.:{}".format(cleantree))
		if cleantree.count("(")  != cleantree.count(")"):
			numwrongs +=1
		outtrees = outtrees + cleantree + "\n" 
	#print("numwrongs: {}".format(numwrongs))
	return outtrees

# Not used in Corpusmanager anymore but useful in other cases
def greynir_to_brackets(infolder, outfolder, insuffix='.psd', outsuffix='.psd', overwrite=False):
	# Býr til skjöl á svigaformi
	# Setur í tiltekna möppu
	# Ætti að ganga óháð þáttunarskemanu, endurskoða ef annað kemur í ljós

	for p in infolder.iterdir():
		pin = p.stem + insuffix
		pin = infolder / pin
		pout = p.stem + outsuffix
		pout = outfolder / pout
		
		if not pin.exists():
			# File has other suffix
			continue

		if pout.exists() and not overwrite:
			continue

		print("Bracketing: {}".format(pin))

		# Að mestu eins og readTrees() í annotald.treedrawing
		treetext = pin.read_text()
		treetext = util.scrubText(treetext)
		trees = treetext.strip().split("\n\n")

		outtrees = clean(trees)
		print("Writing to file {}".format(pout))
		pout.write_text(outtrees)		

# Not used in Corpusmanager anymore but useful in other cases
def clean(trees):
	# Forvinnsla 
	outtrees = "" # All  trees for file
	cleantree = "" # A single  tree for sentence
	text = []
	skip_brackets = 0
	grm = False
	for tree in trees:
		grm = False
		cleantree = ""
		# We know there is only one leaf in each line
		for line in tree.split("\n"):
			if not line:
				continue
			text = [] # Text in each leaf
			# 1. (META, (COMMENT, ... in SKIP_LINES -- skip line altogether
			# 2. Single ( -- extra bracket around tree, won't collect
			# 3. (PP -- collect "(PP" and push one
			# 4. (no_kvk_nf_et -- collect "(no_kvk_nf_et" and push one
			# 5. (lemma, (exp_seg, (exp_abbrev -- in SKIP_SEGS, increase numofskipsegs by one. Ignore rest of sentence except for )) or more.
			# 6. ) or )))))) -- look at numofskipsegs, otherwise just add
			# 7. word -- single word. Collect in text, until find (lemma
			# 8. (grm -- no lemma here, can mess things up.
			# 9. \) -- escaped parentheses. Opening parentheses, \(, are not a problem. Is the word.
			for item in line.lstrip().split():
				#print("\tA.:{}".format(cleantree))
				#print("\tT:{}".format(text))
				#print(item)
				if not item or item == " ":
					#print("\t0A:{}".format(cleantree))
					continue
				if item in SKIP_LINES: # Case 1
					#print("\t0B:{}".format(cleantree))
					break	# Don't collect anything in line
				if item == "(grm": # Case 8
					grm = True
					#print("\t8A:{}".format(cleantree))
					cleantree = cleantree + " " + item
					#print("\t8B:{}".format(cleantree))
				elif item == "(": # Case 2
					#print("\t2A:{}".format(cleantree))
					if text:
						cleantree = cleantree + " " + "_".join(text)
						text = []
					#print("\t2B:{}".format(cleantree))
					skip_brackets +=1
					#print("skip_brackets:{}".format(skip_brackets))
					continue	# Don't collect
				elif item in SKIP_SEGS: # Case 5
					# Check end of line
					if text:
						#print("\t5A:{}".format(cleantree))
						cleantree = cleantree + " " + "_".join(text)
						#print("\t5B:{}".format(cleantree))
						text = []
					numofskipsegs = 0
					for seg in SKIP_SEGS:
						numofskipsegs += line.count(seg)
					rest = line.split()[-1]
					if rest == ")": # More segments in next line, don't do anything more
						if numofskipsegs > 1: # Something went wrong
							print("Fann of marga skipsegs!")
							continue
						continue
					elif "))" in rest: # Case 6
						#print("\t6A:{}".format(cleantree))
						#print("Rest:{}".format(rest))
						bcount = rest.count(")") - numofskipsegs
						#print("numofskipsegs:{}".format(numofskipsegs))
						#print("bracketcount:{}".format(rest.count(")")))
						bpart = line[-bcount:]
						cleantree = cleantree + bpart
						#print("\t6B:{}".format(cleantree))
						numofskipsegs = 0
						break # Ignore other stuff in rest, just the lemma etc.
				elif item.startswith("("): # Case 3 and 4
					# If lo_kvk_nf_et, delete all but lo
					item = item.split("_")[0]
					if text:
						item = "_".join(text) + " " + item
						text = []
					if not cleantree:
						cleantree = item
					else:
						#print("\t3A:{}".format(cleantree))
						cleantree = cleantree + " " + item
						#print("\t3B:{}".format(cleantree))
				elif item == "\\()":
					#print("\t8C:{}".format(cleantree))
					cleantree = cleantree + " " + "ZZ-11)"
					grm = False
					#skip_brackets +=1
					text = []
					#print("\t8D:{}".format(cleantree))
				elif item.startswith("\\)"): # Case 9
					if grm:
						grm = False
					#print("\t9A:{}".format(cleantree))
					text.append("ZZ-22")  # evalb can't handle escaped brackets!
					if len(item) > 2: # More closing brackets, EOL
						restcount = item[2:].count(")")
						#print(restcount)
						if restcount == len(item[2:]): # Only brackets left
							bcount = restcount - numofskipsegs
							bpart = ""
							if text:
								bpart = "_".join(text) + item[2:]
								if numofskipsegs >0:
									bpart = bpart[:-numofskipsegs]
							else:
								bpart = item[2:-bcount]
								if numofskipsegs >0:
									bpart = bpart[:-numofskipsegs]
							text = []
							#print("\t9B:{}".format(cleantree))
							cleantree = cleantree + " " + bpart
							#print("\t9C:{}".format(cleantree))
							numofskipsegs = 0
						else:
							#print("Hvað gerist hér???")
							#print("\t9D:{}".format(cleantree))
							#print(item)
							pass
				elif ")" in item and grm: # Rest of case 8
					#print("\t8E:{}".format(cleantree))
					cleantree = cleantree + " " + item
					#print("\t8F:{}".format(cleantree))
					grm = False
				else: # Case 7
					text.append(item)

		#print("\tEA:{}".format(cleantree))
		if text:
			cleantree = cleantree + " " + item
			text = []
		#print("\tEB:{}".format(cleantree))
		parts = cleantree.split(" ")
		#print("skip_brackets:{}".format(skip_brackets))
		cleantree = cleantree[:-skip_brackets]	# Delete brackets around whole tree, can be 1 or 2
		#print("\tEC:{}".format(cleantree))
		skip_brackets = 0
		outtrees = outtrees + cleantree + "\n" 
	return outtrees

def get_results(goldfolder, testfolder, reportfolder, tests):
	evalbpath = pathlib.Path().absolute() / 'EVALB' / 'evalb'
	if not evalbpath.exists:
		print("Evalb cannot be found. Exiting.")
		return

	for pgold in goldfolder.iterdir():
		# (testsuffix, goldsuffix, outsuffix)
		for tri in tests:	
			if pgold.suffix == tri[1]:
				ptest = pgold.stem + tri[0]
				ptest = testfolder / ptest
				pout = pgold.stem + tri[2]
				pout = reportfolder / pout
				#print("{}".format(ptest))

				evalbcmd = str(evalbpath) + EVALBCOMMAND + " {} {} > {}".format(pgold, ptest, pout)
				print("Comparing {}\n\t and {}".format(pgold, ptest))
				skil = subprocess.Popen([evalbcmd], shell=True, stdout=subprocess.PIPE).communicate()[0]
				print(skil)

def combine_reports(reportfolder, suffixes, genres):
	# TODO:
	# Telja hve margar setningar byrja á S0-X
	# Bæta við víddum fyrir hvern textaflokk -- news, science, parliament, literature
	# Telja öll eigindi líka fyrir hvern flokk, eftir því hvort preport.stem inniheldur rétt nafn
	# Bæta við víddum fyrir ólík þáttunarskemu -- greynir, icenlp, generic
	# Telja öll eigindi eftir p.suffix
	# Bæta við skoðun á setningarhlutverki -- NP-OBJ, ... En þarf sérniðurstöður fyrir það, sérútgáfu af to_brackets...
	numsents = []
	numerrorsents = []
	br = []  # Bracketing recall
	bp = []  # Bracketing precision
	bf = []  # Bracketing F-measure
	cm = []  # Complete match
	ta = []  # Tagging accuracy
	ac = []  # Average crossing
	filenames = []
	filepath = pathlib.Path().absolute() / reportfolder / 'overallresults.out'

	# Sækja nauðsynlegar grunnupplýsingar
	for preport in reportfolder.iterdir():
		with preport.open(mode='r') as pin:
			filenames.append(preport)
			for line in pin.readlines():
				if line.startswith("Number of sentence "):
					numsents.append(float(line.split(" ")[-1]))
				if line.startswith("Number of Error sentence "):
					numerrorsents.append(float(line.split(" ")[-1]))
				if line.startswith("Bracketing Recall "):
					br.append(float(line.split(" ")[-1]))
				if line.startswith("Bracketing Precision "):
					bp.append(float(line.split(" ")[-1]))
				if line.startswith("Bracketing FMeasure "):
					if "nan" in line.split(" ")[-1]:
						bf.append(0.0)
					else:	
						bf.append(float(line.split(" ")[-1]))
				if line.startswith("Complete match "):
					cm.append(float(line.split(" ")[-1]))
				if line.startswith("Average crossing "):
					ac.append(float(line.split(" ")[-1]))
				if line.startswith("Tagging accuracy "):
					ta.append(float(line.split(" ")[-1]))
					break # No information needed after this
	
	# Birta réttar upplýsingar
	# Geri ráð fyrir að það séu 10 setningar í hverju skjali
	# til að forðast of lágar tölur sem hverfa
	textblob = []
	for suff in suffixes:
		numfilesoverall, numsentsoverall, numerrorsentsoverall = 0, 0.0, 0.0
		broverall, bpoverall, bfoverall, cmoverall, acoverall, taoverall = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
		textblob.append("\n\n")
		for genre in genres:
			fileid = genre+suff
			filestrings = []
			numfiles = 0
			numsentsall, numerrorsentsall = 0.0, 0.0
			brall, bpall, bfall, cmall, acall, taall = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
			allnums = zip(filenames, numsents, numerrorsents, br, bp, bf, cm, ac, ta)
			for filenow, numsentsnow, numerrorsentsnow, brnow, bpnow, bfnow, cmnow, acnow, tanow in allnums:
				if filenow.suffix != suff:
					#print(filenow)
					continue
				if not filenow.stem.startswith(genre):
					#print(filenow)
					continue
				filestrings.append(str(filenow))
				numfiles+=1
				numsentsall+=numsentsnow
				numerrorsentsall+=numerrorsentsnow
				brall+=brnow
				bpall+=bpnow
				bfall+=bfnow
				cmall+=cmnow
				acall+=acnow
				taall+=tanow

			#filepath = pathlib.Path().absolute() / reportfolder / fileid
			numfilesoverall+=numfiles
			numsentsoverall+=numsentsall
			numerrorsentsoverall+=numerrorsentsall
			broverall+=brall
			bpoverall+=bpall
			bfoverall+=bfall
			cmoverall+=cmall
			acoverall+=acall
			taoverall+=taall

			textblob.append("=== {} ===\n".format(fileid))
			if numfiles == 0:
				textblob.append("Engin skjöl í flokki\n")
				continue

			textblob.append("Fjöldi setninga:{}\n".format(numsentsall))
			textblob.append("Fjöldi villusetninga:{}\n".format(numerrorsentsall))
			textblob.append("Recall:{:.2f}\n".format(brall/numfiles))
			textblob.append("Precision:{:.2f}\n".format(bpall/numfiles))
			textblob.append("Fskor:{:.2f}\n".format(bfall/numfiles))
			textblob.append("Alveg eins:{:.2f}\n".format(cmall/numfiles))
			textblob.append("Average crossing: {:.2f}\n".format(acall/numfiles))
			textblob.append("Tagging accuracy:{:.2f}\n\n\t".format(taall/numfiles))
			textblob.append("\n\t".join(filestrings))
			textblob.append("\n\n")
		textblob.append("\n\n|||||||||||||||||||||||||||||||||||||||||||||\n\n")
		textblob.append("=== Heildin{} ===\n".format(suff))

		if numfilesoverall == 0:
			textblob.append("Engin skjöl í flokki\n")
			

		textblob.append("Fjöldi setninga:{}\n".format(numsentsoverall))
		textblob.append("Fjöldi villusetninga:{}\n".format(numerrorsentsoverall))
		textblob.append("Recall:{:.2f}\n".format(broverall/numfilesoverall))
		textblob.append("Precision:{:.2f}\n".format(bpoverall/numfilesoverall))
		textblob.append("Fskor:{:.2f}\n".format(bfoverall/numfilesoverall))
		textblob.append("Alveg eins:{:.2f}\n".format(cmoverall/numfilesoverall))
		textblob.append("Average crossing: {:.2f}\n".format(acoverall/numfilesoverall))
		textblob.append("Tagging accuracy:{:.2f}\n\n\n".format(taoverall/numfilesoverall))


	print("Writing overall report")
	filepath.write_text("".join(textblob))



class Stack:
     def __init__(self):
         self.items = []

     def isEmpty(self):
         return self.items == []

     def push(self, item):
         self.items.append(item)

     def pop(self):
         return self.items.pop()

     def peek(self):
         return self.items[len(self.items)-1]

     def size(self):
         return len(self.items)


if __name__ == "__main__":
	print(" ")

#!/usr/bin/env python

import pathlib
import subprocess
from reynir.simpletree import SimpleTree
import annotald.util as util

EVALBCOMMAND = ' -p ./stillingar.prm' # handpsd is first argument, then genpsd

SKIP_PHRASES = set(["(META", "(ID-CORPUS", "(ID-LOCAL", "(URL", "(COMMENT"])
SKIP_SEGS = set(["(lemma", "(exp_seg", "(exp_abbrev"])

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
	pass

def map_to_icenlp():
	# Fær inn möppu með greynisþáttuðum skjölum á Annotaldsforminu
	# Býr til skjöl á IceNLP-forminu fyrir Annotald
	# Setur í tiltekna möppu
	pass

def map_to_general():
	# Fær inn möppu með greynisþáttuðum skjölum á Annotaldsforminu
	# Býr til skjöl á almenna þáttunarforminu fyrir Annotald
	# Setur í tiltekna möppu
	pass

def to_brackets(infolder, outfolder, insuffix='.psd', outsuffix='.psd', overwrite=False):
	# Fær inn möppu með þáttuðum skjölum á Annotaldsforminu
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

def clean(trees):
	# Forvinnsla 
	outtrees = "" # Whole trees
	cleantree = "" # Each tree
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
			# 1. (META, (COMMENT, ... in SKIP_PHRASES -- skip line altogether
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
				if item in SKIP_PHRASES: # Case 1
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

def get_results(goldfolder, testfolder, reportfolder, reportsuffix):
	evalbpath = pathlib.Path().absolute() / 'EVALB' / 'evalb'
	if not evalbpath.exists:
		print("Evalb cannot be found. Exiting.")
		return

	for pgold in goldfolder.iterdir():
		ptest = pgold.stem + pgold.suffix
		ptest = testfolder / ptest
		pout = pgold.stem + reportsuffix
		pout = reportfolder / pout


		evalbcmd = str(evalbpath) + EVALBCOMMAND + " {} {} > {}".format(pgold, ptest, pout)
		print("Comparing {}\n\t and {}".format(pgold, ptest))
		skil = subprocess.Popen([evalbcmd], shell=True, stdout=subprocess.PIPE).communicate()[0]
		print(skil)

def combine_reports(reportfolder, suffixlist):
	# byrja á að safna saman eftirfarandi eigindum
	# Number of sentences
	# Number of error sentences
	# Bracketing recall
	# Bracketing precision
	# Bracketing Fmeasure
	# Tagging accuracy

	# Síðar:
	# Telja hve margar setningar byrja á S0-X
	# Bæta við víddum fyrir hvern textaflokk -- news, science, parliament, literature
	# Telja öll eigindi líka fyrir hvern flokk, eftir því hvort preport.stem inniheldur rétt nafn
	# Bæta við víddum fyrir ólík þáttunarskemu -- greynir, icenlp, generic
	# Telja öll eigindi eftir p.suffix
	# Bæta við skoðun á setningarhlutverki -- NP-OBJ, ... En þarf sérniðurstöður fyrir það, sérútgáfu af to_brackets...
	numsents = []
	numerrorsents = []
	br = []
	bp = []
	bf = []
	cm = []
	ta = []
	filenames = []

	numsentsall = 0.0
	numerrorsentsall = 0.0
	brall = 0.0
	bpall = 0.0
	bfall = 0.0
	cmall = 0.0
	taall = 0.0

	for preport in reportfolder.iterdir():
		# Sækja nauðsynlegar upplýsingar.
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
					bf.append(float(line.split(" ")[-1]))
				if line.startswith("Complete match "):
					cm.append(float(line.split(" ")[-1]))					
				if line.startswith("Tagging accuracy "):
					ta.append(float(line.split(" ")[-1]))
					break # No information needed after this
	# Birta réttar upplýsingar
	# Geri ráð fyrir að það séu 10 setningar í hverju skjali
	# til að forðast of lágar tölur sem hverfa
	files = len(filenames)
	for i in numsents:
		numsentsall +=i
	for i in numerrorsents:
		numerrorsentsall +=i

	for i in br:
		brall +=i

	for i in bp:
		bpall +=i

	for i in bf:
		bfall +=i

	for i in cm:
		cmall +=i

	for i in ta:
		taall +=i

	print("==== Niðurstöður ====")
	print("Fjöldi setninga:{}".format(numsentsall))
	print("Fjöldi villusetninga:{}".format(numerrorsentsall))
	print("Recall:{}".format(brall/files))
	print("Precision:{}".format(bpall/files))
	print("Fskor:{}".format(bfall/files))
	print("Alveg eins:{}".format(cmall/files))
	print("Tagging accuracy:{}".format(taall/files))

if __name__ == "__main__":
	print(" ")

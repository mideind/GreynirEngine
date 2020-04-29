#!/usr/bin/env python

import pathlib
import subprocess
from reynir.simpletree import SimpleTree
import annotald.util as util

EVALBCOMMAND = ' -p ./stillingar.prm' # handpsd is first argument, then genpsd


def get_annoparse(infolder, outfolder, insuffix=".txt", outsuffix=".psd"):
	# Fær inn möppu með textum, mögulega einhver skilyrði um suffix eða stem sem á að velja
	# Skilar þáttuðum skjölum í tiltekna möppu
	# Og tiltaka endingu!
	print("Ég kemst hingað!")
	for p in infolder.iterdir():
		# Útbúa skipunina
		ptext = p.stem + insuffix
		ptext = infolder / ptext
		pout = p.stem + outsuffix
		pout = outfolder / pout

		command = "annoparse -i {} -o {}".format(ptext, pout)
		skil = subprocess.Popen([command], shell=True, stdout=subprocess.PIPE).communicate()[0]
		print(skil)


def map_to_iceparser():
	# Fær inn möppu með greynisþáttuðum skjölum á Annotaldsforminu
	# Býr til skjöl á IceNLP-forminu fyrir Annotald
	# Setur í tiltekna möppu
	pass

def map_to_general():
	# Fær inn möppu með greynisþáttuðum skjölum á Annotaldsforminu
	# Býr til skjöl á almenna þáttunarforminu fyrir Annotald
	# Setur í tiltekna möppu
	pass

def to_brackets(infolder, outfolder, insuffix='.psd', outsuffix='.psd'):
	# Fær inn möppu með þáttuðum skjölum á Annotaldsforminu
	# Býr til skjöl á svigaformi
	# Setur í tiltekna möppu
	# Ætti að ganga óháð þáttunarskemanu, endurskoða ef annað kemur í ljós
	# Skoða samsvarandi föll í simpletree.py, reynir.py og treeutil.py
	# og auðvitað upprunalega cmp_parse.py!

	# Spyrja hvort eigi að yfirskrifa skjöl sem þegar eru tilbúin
	ans = input("Do you want to overwrite existing files? (y/n)\n")	


	for p in infolder.iterdir():
		pin = p.stem + insuffix
		pin = infolder / pin
		pout = p.stem + outsuffix
		pout = outfolder / pout
		
		if not pin.exists():
			# File has other suffix
			continue

		if pout.exists() and ans == "n":
			continue
		print("Looking at file {}".format(pin))

		# Að mestu eins og readTrees() í annotald.treedrawing
		treetext = pin.read_text()
		treetext = util.scrubText(treetext)
		trees = treetext.strip().split("\n\n")
		outtrees = ""

		for each in trees:
			seen = False
			for line in each.split("\n"):
				# Clean metadata and put all in one line
				if "S0" in line:
					seen = True
				if not seen:
					continue
				outtrees = outtrees + " " + line.strip(" ")
				# Þarf ekki að hreinsa lemma, exp_seg og abbrev_seg, hunsa það í prófununum.
			outtrees = outtrees + "\n"

		print("Writing to file {}".format(pout))
		pout.write_text(outtrees)		



	"""
	if not pclean.exists():
		print("{} doesn't exist".format(pclean))
		continue
	"""


def get_results(goldfolder, testfolder, reportfolder, reportsuffix):
	print("Goldfolder is {}".format(goldfolder))
	evalbpath = pathlib.Path().absolute() / 'EVALB' / 'evalb'
	if not evalbpath.exists:
		print("Evalb cannot be found. Exiting.")
		return

	for pgold in goldfolder.iterdir():
		ptest = testfolder / pgold
		pout = pgold.stem + reportsuffix
		pout = reportfolder / pout

		evalbcmd = str(evalbpath) + EVALBCOMMAND + " {} {} > {}".format(pgold, ptest, pout)
		print("{} is being evaluated".format(pgold.stem))
		skil = subprocess.Popen([evalbcmd], shell=True, stdout=subprocess.PIPE).communicate()[0]
		#print(skil)

def combine_reports(reportfilder, suffixlist):
	pass


if __name__ == "__main__":
	print("Hello World")


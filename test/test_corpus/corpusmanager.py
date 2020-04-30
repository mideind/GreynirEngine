#!/usr/bin/env python

# Originally cmp_parse.py, adapted to needs here
# Read in text files from test_corpus/clean, one by one
# Generate parse with Annotald, keep in test_corpus/genpsd
# To start with, only files starting with reynir_corpus
# Compare each file to its counterpart in test_corpus/handpsd, remember they end with .gld
# Generate evalb report for each file, in evalb_reports
# Read in results for each file, combine into one report with only results, by genre and overall


import pathlib
from timeit import default_timer as timer
import subprocess

from reynir import Settings
from reynir.simpletree import SimpleTree
from reynir import Greynir
import helpers

# from reynir import _BIN_Session  # Skoða vel, þetta er í bindb.py

#Settings.read(os.path.join(basepath, "config", "Greynir.conf"))
Settings.DEBUG = False

HANDPSD = pathlib.Path().absolute() / 'handpsd'
GENPSD = pathlib.Path().absolute() / 'genpsd'
CLEAN = pathlib.Path().absolute() / 'clean'
BRACKETS = pathlib.Path().absolute() / 'brackets'
TESTFILES = pathlib.Path().absolute() / 'testfiles'
REPORTS = pathlib.Path().absolute() / 'reports'


class Comparison():
	def __init__(self):
		self.results = {}

	def start(self):

		# Hef (1)
		# Útbý (2) með annoparse, eins og í Maker
		helpers.get_annoparse(CLEAN, GENPSD, ".txt", ".psd")
		
		# Hef (2)
		# Útbý (5B) með map_to_iceparser()
		# TODO

		# Hef (2)
		# Útbý (5C) með map_to_general()
		# TODO

		# Hef (2), (5B) og (5C)
		# Útbý (6A), (6B) og (6C) með to_brackets()
		# helpers.to_brackets(GENPSD, TESTFILES, '.psd', '.grbr')
		#helpers.to_brackets(GENPSD, TESTFILES, '.ippsd', '.ipbr')
		#helpers.to_brackets(GENPSD, TESTFILES, '.afpsd', '.afbr')

		# Hef (4A), (4B) og (4C) úr Maker
		# Og (6A), (6B) og (6C) héðan
		# Útbý (7A)
		#helpers.get_results(BRACKETS, TESTFILES, REPORTS, ".out")
		
		# Hef (7A)
		# Útbý (7B)
		# suffixlist = [".grbr"]
		# helpers.combine_reports(REPORTS, suffixlist)





	# Þáttar skjölin, útbýr vélþáttað skjal á slóðinni pgen

class Maker():

	def start(self):
		# Hef (1)
		# Bý til (2) vélþáttuð skjöl á Annotaldsformi
		# fyrir hvert skjal í /clean
		# Taka út þau sem eru með öllum setningunum! Fyrir hvert genre, setja í /original
		# bý til annoparse skjal með helpers.get_annoparse()
		# tiltek rétta möppu -- /genpsd og endinguna .psd
		# helpers.get_annoparse(CLEAN, GENPSD, '.txt', '.psd')

		# hef þá (2)
		# Útbý (3A) með handþáttun, geymi í /handpsd .grgld


		# Hef (3A)
		# Útbúa (3B) með map_to_iceparser
		# TODO

		# Hef (3A)
		# Útbúa (3C) með map_to_general
		# TODO

		# Hef þá (3B) og (3C)
		# Handþátta og lagfæra helstu villur
		# TODO

		# Hef þá (3A), (3B) og (3C)
		# Fæ (4A), (4B) og (4C) með to_brackets
		# Passa að setja réttar endingar á allt, þarf mögulega að gera í 3 fallaköllum
		helpers.to_brackets(HANDPSD, BRACKETS, '.grgld', '.grbr')
		#helpers.to_brackets(HANDPSD, BRACKETS, '.ipgld', '.ipbr')
		#helpers.to_brackets(HANDPSD, BRACKETS, '.afgld', '.afbr')

		# Þá ætti allt að vera tilbúið fyrir þróunarmálheildina!
		# Passa í hverju skrefi að ef skjalið er þegar til á ekki að yfirskrifa það.


if __name__ == "__main__":
	start = timer()
	#maker = Maker()
	#maker.start()

	comp = Comparison()
	comp.start()
	end = timer()
	duration = end - start
	print("")
	print("Keyrslan tók {:f} sekúndur, eða {:f} mínútur.".format(duration, (duration / 60.0)))

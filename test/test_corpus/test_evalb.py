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
		# Útbý (13A) með annoparse, eins og í Maker
		#helpers.get_annoparse(CLEAN, GENPSD, ".txt", ".psd")
		
		# Hef (13A)
		# Útbý (13B) með map_to_iceparser()
		# TODO

		# Hef (13A)
		# Útbý (13C) með map_to_general()
		# TODO

		# Hef (13A), (13B) og (13C)
		# Útbý (9), (10) og (11) með to_brackets()
		#helpers.to_brackets(GENPSD, TESTFILES, '.psd', '.grbr')
		#helpers.to_brackets(GENPSD, TESTFILES, '.ippsd', '.ipbr')
		#helpers.to_brackets(GENPSD, TESTFILES, '.afpsd', '.afbr')

		# Hef (6), (7) og (8) úr Maker
		# Og (9), (10) og (11) héðan
		# Útbý (12A)
		helpers.get_results(BRACKETS, TESTFILES, REPORTS, ".out")
		
		# Hef (12A)
		# Útbý (12B)
		suffixlist = [".grbr"]
		# helpers.combine_reports(REPORTS, suffixlist)





	# Þáttar skjölin, útbýr vélþáttað skjal á slóðinni pgen
	def parse(self, pclean, pgen, grbr):
		parses = []
		for line in pclean.open():
			print(line)
			sent = g.parse_single(line)
			brackets = sent.tree.bracket_form if sent.tree else ""
			# Safna saman
			# Ath. hvort lendi í setningum sem fleiri en ein setning
			# len(sent) > 1 virkar ekki, hvað virkar?
			# Hér set ég inn forvinnsluna ef hún á að vera til staðar
			parses.append(brackets)
		pgen.write_text("\n".join(parses))


class Maker():

	def start(self):
		# Hef (1)
		# Bý til (2) vélþáttuð skjöl á Annotaldsformi
		# fyrir hvert skjal í /clean
		# Taka út þau sem eru með öllum setningunum! Fyrir hvert genre, setja í /original
		# bý til annoparse skjal með helpers.get_annoparse()
		# tiltek rétta möppu -- /genpsd og endinguna .psd
		helpers.get_annoparse(CLEAN, GENPSD, '.txt', '.psd')

		# hef þá (2)
		# Handþátta skjölin, geymi í /handpsd .grgld
		# Komið að miklu leyti

		# Hef (3)
		# Útbúa (4) með map_to_iceparser
		# TODO

		# Hef (3)
		# Útbúa (5) með map_to_general
		# TODO

		# Hef þá (4) og (5)
		# Handþátta og lagfæra helstu villur
		# TODO

		# Hef þá (3), (4) og (5)
		# Fæ (6), (7) og (8) með to_brackets
		# Passa að setja réttar endingar á allt, þarf mögulega að gera í 3 fallaköllum
		helpers.to_brackets(HANDPSD, BRACKETS, '.grgld', '.grbr')
		#helpers.to_brackets(HANDPSD, BRACKETS, '.ipgld', '.ipbr')
		#helpers.to_brackets(HANDPSD, BRACKETS, '.afgld', '.afbr')

		# Þá ætti allt að vera tilbúið fyrir þróunarmálheildina!
		# Passa í hverju skrefi að ef skjalið er þegar til á ekki að yfirskrifa það.


if __name__ == "__main__":
	#maker = Maker()
	#maker.start()

	start = timer()
	comp = Comparison()
	comp.start()
	end = timer()
	duration = end - start
	print("")
	print("Keyrslan tók {:f} sekúndur, eða {:f} mínútur.".format(duration, (duration / 60.0)))

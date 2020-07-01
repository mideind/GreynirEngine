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


class Maker():

	def start(self, overwrite=False):
		# Hef (1)
		# Bý til (2) véldjúpþáttuð Greynisskjöl á Annotaldsformi
		# fyrir hvert skjal í /clean
		# bý til annoparse skjal með helpers.get_annoparse()
		# tiltek rétta möppu -- /genpsd og endinguna .psd
		#helpers.get_annoparse(CLEAN, GENPSD, '.txt', '.psd', False)

		# hef þá (2)
		# Útbý (3A) með handþáttun, geymi í /handpsd .grgld

		# Hef (3A)
		# Útbý (3B) og (3C) handþáttanir á almennu skema á svigaformi
		# með annotald_to_general()
		print("Transforming goldfiles")
		helpers.annotald_to_general(HANDPSD, BRACKETS, '.dgld', '.dbr', True, True)
		#helpers.annotald_to_general(HANDPSD, BRACKETS, '.pgld', '.pbr', False, True)

		# Hef þá (3B) og (3C)
		# Lagfæra helstu villur

		# Þá ætti allt að vera tilbúið fyrir þróunarmálheildina!


class Comparison():
	def __init__(self):
		self.results = {}

	def start(self, overwrite=False):

		# Hef (1)
		# Útbý (2) með annoparse, eins og í Maker
		helpers.get_annoparse(CLEAN, GENPSD, ".txt", ".psd", False)
		
		# Hef (2)
		# Útbý (5B) með get_ipparse()
		# Ath. í Maker() er þetta útbúið með vörpun úr Greynisskemanu
		#helpers.get_ipparse(CLEAN, GENPSD, '.txt', '.ippsd', True)

		# Hef (2)
		# Útbý (5C) með map_to_general()
		print("Transforming greynir testfiles")
		helpers.annotald_to_general(GENPSD, TESTFILES, '.psd', '.grdbr', True, True)
		#print("Transforming IceParser testfiles")
		#helpers.ip_to_general(GENPSD, TESTFILES, ".ippsd", ".ippbr", True)


		tests = [
			#(".ippbr", ".pbr", ".ippout"), 
			#(".grpbr", ".pbr", ".grpout"), 
			(".grdbr", ".dbr", ".grdout")
		]
		helpers.get_results(BRACKETS, TESTFILES, REPORTS, tests)

		suffixes = [".grdout"]  # ".ippout", ".grpout", 
		genres = ["reynir_corpus", "althingi", "visindavefur", "textasafn"]
		# Hef (7A)
		# Útbý (7B)
		helpers.combine_reports(REPORTS, suffixes, genres)


if __name__ == "__main__":
	# Spyrja hvort eigi að yfirskrifa skjöl sem þegar eru tilbúin
	#ans = input("Do you want to overwrite existing files? (y/n)\n")	
	# TODO eftir að breyta ans í True/False gildi
	ans = False
	start = timer()
	maker = Maker()
	maker.start(ans)


	comp = Comparison()
	comp.start(ans)
	end = timer()
	duration = end - start
	print("")
	print("Keyrslan tók {:f} sekúndur, eða {:f} mínútur.".format(duration, (duration / 60.0)))

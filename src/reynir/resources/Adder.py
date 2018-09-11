#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Les ord.csv til síunar og skilar úttaki í systematic_errors.csv.
# other_errors.csv inniheldur tilfallandi atriði, þar er hægt að bæta inn hlutum.
# systematic_errors.csv inniheldur kerfisbundin atriði sem eru skilgreind í Adder.add_systematic().
# Þessum skjölum, other_errors.csv, systematic_errors.csv og systematic_additions.csv, 
# þarf að bæta við ord.csv fyrir DAWG-gerðina.
# Koma líka inn í orðasafnið, sem er búið til undir reynirpackage.
# Formið á fl er "MARK_err_rétt orðmynd_ordfl_idnúmer"


PARADIGM = {}
UPPERS = "AÁBDÐEÉFGHIÍJKLMNOÓPRSTUÚVXYÝZÞÆÖ"

class Adder():
    def __init__(self):
        pass
    def main(self):
        # Heldur utan um ferlið.

        # Bætir við kerfisbundnum hlutum
        self.add_systematic("ord.csv")
        self.add_systematic("ord.add.csv")
        self.add_systematic("ord.auka.csv")

    def add_systematic(self, filename):
        prevlemma = ""
        previd = ""
        prev = []

        with open(filename, "r") as source:
            for line in source:
                split = line.split(";")
                if len(split) < 2 or split[2] not in ["hk", "kk", "kvk", "lo", "so"]:
                    #print("NOT GOTT:{}".format(line))
                    continue
                else:
                    currlemma = split[0]
                    currid = split[1]
                    if not prevlemma:    # Byrjun lúppu
                        prevlemma = currlemma
                        previd = currid
                        prev = split
                    if prevlemma != currlemma or previd != currid:
                        # Búin að finna allt, komin á nýtt
                        #print("BYRJA AFTUR:{}".format(line))
                        self.check_paradigm(prevlemma, prev[2], previd)
                        # Hreinsa allt
                        prevlemma = currlemma
                        previd = currid
                        prev = split
                        PARADIGM.clear()
                        PARADIGM[split[5].strip()] = split[4].strip()
                    else:
                        #print("\tSAFNA ÞESSU:{}".format(line))
                        PARADIGM[split[5].strip()] = split[4].strip()
            # Síðasta beygingardæmið
            self.check_paradigm(prevlemma, prev[2], previd)

    def check_paradigm(self, lemma, pos, idnum):
        errors = {} # Geymir rangar myndir fyrir hvert beygingardæmi til að bæta við í other_errors.csv
        newforms = {}
        #print("Lemma:{}\tOrðflokkur:{}".format(lemma, pos))
        #for item in PARADIGM:
        #    print("\tMark:{}\tOrðmynd:{}".format(item, PARADIGM[item]))
        dentals = {
            "l": "d", 
            "m" : "d", 
            "n" : "d", 
            "p" : "t", 
            "k" : "t", 
            "f" : "ð",
            "r" : "ð",
            "ó" : "ð",
            "ú" : "ð",
            "á" : "ð"
            }
        if pos == "kvk":
            #for mark in PARADIGM:
            #    print("{}:{}".format(mark, PARADIGM[mark]))
            if not "NFET" in PARADIGM:  # Bara fleirtöluorð eða bara til með greini, engin mynstur miðast við það.
                return
            # kvk no -ing → -ingu, -ingunnar
            if PARADIGM["NFET"].endswith("ing"):
                #print("FANN!\t{}".format(PARADIGM["NFET"]))
                errors["EFET_err"] = PARADIGM["EFET"][:-2] + "u"
                if "EFETgr" in PARADIGM:
                    errors["EFETgr_err"] = PARADIGM["EFET"][:-2] + "unnar"
                # Réttar orðmyndir í fleirtölu ef vantar í orðasafn
                if not "NFFT" in PARADIGM and not self.is_uppercase(lemma):
                    newforms["NFFT"] = PARADIGM["EFET"][:-2] + "ar"
                    newforms["NFFTgr"] = PARADIGM["EFET"][:-2] + "arnar"
                    newforms["ÞFFT"] = PARADIGM["EFET"][:-2] + "ar"
                    newforms["ÞFFTgr"] = PARADIGM["EFET"][:-2] + "arnar"
                    newforms["ÞGFFT"] = PARADIGM["EFET"][:-2] + "um"
                    newforms["ÞGFFTgr"] = PARADIGM["EFET"][:-2] + "unum"
                    newforms["EFFT"] = PARADIGM["EFET"][:-2] + "a"
                    newforms["EFFTgr"] = PARADIGM["EFET"][:-2] + "anna"
            # kvk no -un → -unnar (stofnunnar)
            # kvk no -un → uninnar (stofnunarinnar → stofnuninnar)
            elif PARADIGM["NFET"].endswith("un") and not PARADIGM["NFET"].endswith("aun"):
                errors["EFET_err"] = PARADIGM["EFET"][:-2] + "nar"
                if "EFETgr" in PARADIGM:
                    errors["EFETgr_err"] = PARADIGM["EFET"][:-2] + "innar"
                # Réttar orðmyndir í fleirtölu ef vantar í orðasafn
                if not "NFFT" in PARADIGM and not self.is_uppercase(lemma):
                    if "ö" in PARADIGM["NFET"][-6:] and not lemma.endswith("vun"):  # ölvun, glöggvun, heldur -ö- í öllum myndum
                        st = PARADIGM["NFET"][:-2]
                        ast = st[:st.rfind('ö')] + "a" + st[st.rfind('ö')+1:]
                        newforms["NFFT"] = ast + "anir"
                        newforms["NFFTgr"] = ast + "anirnar"
                        newforms["ÞFFT"] = ast + "anir"
                        newforms["ÞFFTgr"] = ast + "anirnar"
                        newforms["ÞGFFT"] = st + "unum"
                        newforms["ÞGFFTgr"] = st + "ununum"
                        newforms["EFFT"] = ast + "ana"
                        newforms["EFFTgr"] = ast + "ananna"

                    else:
                        newforms["NFFT"] = PARADIGM["NFET"][:-2] + "anir"
                        newforms["NFFTgr"] = PARADIGM["NFET"][:-2] + "anirnar"
                        newforms["ÞFFT"] = PARADIGM["NFET"][:-2] + "anir"
                        newforms["ÞFFTgr"] = PARADIGM["NFET"][:-2] + "anirnar"
                        newforms["ÞGFFT"] = PARADIGM["NFET"][:-2] + "unum"
                        newforms["ÞGFFTgr"] = PARADIGM["NFET"][:-2] + "ununum"
                        newforms["EFFT"] = PARADIGM["NFET"][:-2] + "ana"
                        newforms["EFFTgr"] = PARADIGM["NFET"][:-2] + "ananna"

            # kvk no -ur beygjast rétt (brúðurina → brúðina, brúðurin → brúðin...)
            elif PARADIGM["NFET"].endswith("ur"):
                stofn = PARADIGM["NFET"][:-2]
                errors["ÞFET_err"] = stofn + "ur"   # brúði → brúður
                errors["ÞGFET_err"] = stofn + "ur"   # brúði → brúður
                errors["EFET_err"] = stofn + "ur"   # brúðar → brúður
                if "NFETgr" in PARADIGM and not lemma.endswith("fjöður"):    # Útiloka nöfn
                    errors["NFETgr_err"] = stofn + "in" # brúðurin → brúðin
                    errors["ÞFETgr_err"] = stofn + "urina"   # brúðina → brúðurina
                    errors["ÞGFETgr_err"] = stofn + "urinni"   # brúðinni → brúðurinni
                    errors["EFETgr_err"] = stofn + "innar"   # brúðarinnar → brúðinnar

            #   Endingarlausar bara?: efet -arinnar → -innar (íbúðinnar, vegagerðinnar)
            else:
                if "EFETgr" in PARADIGM and not "EFETgr2" in PARADIGM:
                    if PARADIGM["EFETgr"].endswith("varinnar") or PARADIGM["EFETgr"].endswith("jarinnar"):
                        errors["EFETgr_err"] = PARADIGM["EFETgr"][:-8] + "innar"  # stöðvarinnar → stöðinnar; nauðsynjarinnar → nauðsyninnar
                    elif PARADIGM["EFETgr"].endswith("arinnar"):
                        errors["EFETgr_err"] = PARADIGM["EFETgr"][:-7] + "innar" # sveitarinnar → sveitinnar
        elif pos == "kk":
            if not "NFET" in PARADIGM: # Bara fleirtöluorð eða bara til með greini
                return
            # kk no -num → -inum (bátnum → bátinum)
            # kk no -ur → -inum/-num (heimur, geimur, gámur, hestur, klerkur, liður ...)
            if "ÞGFETgr" in PARADIGM and not "ÞGFETgr2" in PARADIGM:
                if lemma.endswith("ill") or lemma.endswith("ull") or lemma.endswith("all") or lemma == PARADIGM["ÞFET"]: # sökkull, lykill, staðall, gróður
                    errors["ÞGFET_err"] = PARADIGM["ÞFET"]
                    errors["ÞGFETgr_err"] = PARADIGM["ÞFET"] + "num"
                elif PARADIGM["ÞGFETgr"].endswith("inum") and not PARADIGM["ÞGFETgr"].endswith("ninum"): # hestinum → hestnum
                    errors["ÞGFETgr_err"] = PARADIGM["ÞGFETgr"][:-4] + "num"
                    if not "ÞGFET2" in PARADIGM and PARADIGM["ÞGFET"].endswith("i"): # hesti → hest
                        errors["ÞGFET_err"] = PARADIGM["ÞGFET"][:-1]
                elif PARADIGM["ÞGFETgr"].endswith("num") and not PARADIGM["ÞGFETgr"].endswith("anum") and not PARADIGM["ÞGFETgr"].endswith("inum"): # bátnum → bátinum
                    errors["ÞGFETgr_err"] = PARADIGM["ÞGFETgr"][:-3] + "inum"
            # kk no -ur ef.et -ar → -s (lækjar→læks, lækjarins→læksins, Hæstaréttar→Hæstarétts, eldiviður)
            # kk no -sins → ins (leiksins → leikins)
            if "EFETgr" in PARADIGM and not "EFET2" in PARADIGM and not lemma.endswith("s"):
                if PARADIGM["EFETgr"].endswith("arins"):  # Lækjarins → læksins
                    if PARADIGM["EFET"].endswith("jar"):    # Lækjar → læks
                        errors["EFET_err"] = PARADIGM["EFET"][:-3] + "s"
                        errors["EFETgr_err"] = PARADIGM["EFETgr"][:-6] + "ins"
                    elif lemma.endswith("köttur") or lemma.endswith("fjörður") or lemma.endswith("völlur") or lemma.endswith("dagur") or lemma.endswith("fótur"):
                        errors["EFET_err"] = lemma[:-2] + "s"
                    else:  # eldiviðar → eldiviðs
                        errors["EFETgr_err"] = PARADIGM["EFETgr"][:-5] + "ins"
                        errors["EFET_err"] = PARADIGM["EFET"][:-2] + "s"
                elif PARADIGM["EFETgr"].endswith("sins") and not lemma.endswith("s") and not lemma.endswith("ir"):  # leiksins → leikins
                    errors["EFETgr_err"] = PARADIGM["EFET"][:-1] + "ins"
                    if PARADIGM["EFETgr"][-5] in "kg" and "NFFT" in PARADIGM and not PARADIGM["NFFT"].endswith("ar"):  # leiksins → leikjarins
                        errors["EFETgr_err2"] = PARADIGM["EFET"][:-1] + "jarins"
                    elif lemma.endswith("köttur") or lemma.endswith("fjörður") or lemma.endswith("völlur") or lemma.endswith("dagur") or lemma.endswith("fótur"):
                        errors["EFET_err"] = lemma[:-2] + "sins"
                    else:   # dalsins → dalarins
                        errors["EFETgr_err2"] = PARADIGM["EFET"][:-1] + "arins"
            # kk no -ingi → -inga (kunningja → kunninga)
            if lemma.endswith("ingi"):
                errors["NFET_err"] = lemma[:-1] + "ji"
                errors["ÞFET_err"] = lemma[:-1] + "a"
                errors["ÞGFET_err"] = lemma[:-1] + "a"
                errors["EFET_err"] = lemma[:-1] + "a"
            # kk nafn -arr, aukaföll -r (Óttarr→Óttarri/Óttarrs, Steinarr)
            elif lemma.endswith("arr"): 
                errors["ÞFET_err"] = lemma
                errors["ÞGFET_err"] = lemma + "i"
                errors["EFET_err"] = lemma + "s"
            # kk no -ir heldur -r (læknis→læknirs)
            elif lemma.endswith("ir") and not lemma.endswith("eir"):  # læknir, steypir
                errors["ÞFET_err"] = lemma
                errors["ÞGFET_err"] = lemma + "i"
                errors["EFET_err"] = lemma + "s"
                if "ÞFETgr" in PARADIGM:
                    errors["ÞFETgr_err"] = lemma + "inn"
                    errors["ÞGFETgr_err"] = lemma + "inum"
                    errors["ÞGFETgr_err2"] = lemma + "num"
                    errors["EFETgr_err"] = lemma + "sins"
            # kk no -inn → inn í þf (himinn, arinn)
            elif lemma.endswith("inn") and not lemma.endswith("einn"):
                errors["ÞFET_err"] = lemma
            # kk no -ann → -ann í þf (aftann)
            elif lemma.endswith("ann"):
                errors["ÞFET_err"] = lemma
            # koss, foss → kosss, fosss
            elif lemma.endswith("ss"):
                errors["EFET_err"] = lemma + "s"
            # kk no -ur → Ø/-i (bátur bát/báti) -- gæti verið ÞGFET2
            elif not "ÞGFET2" in PARADIGM:
                p = PARADIGM["ÞGFET"]
                if not p[-1] in "aáeéiíoóuúyýæö":
                    errors["ÞGFET_err"] = p + "i"
        elif pos == "hk":
            if "NFET" not in PARADIGM:  # Bara fleirtöluorð eða bara til með greini, engin mynstur miða við það
                return
            # hk no -sins → ins (ársins → árins)
            if "EFETgr" in PARADIGM and not "EFET2" in PARADIGM:
                if lemma.endswith("ss"):
                    errors["EFET_err"] = lemma + "s"    # pláss → plásss
                    errors["EFETgr_err"] = PARADIGM["EFETgr"][:-3] + "ins"
                elif PARADIGM["EFETgr"].endswith("sins") and not PARADIGM["EFETgr"].endswith("isins"):
                    errors["EFETgr_err"] = PARADIGM["EFETgr"][:-4] + "ins"
        elif pos == "lo":
            mst = [x for x in PARADIGM if "MST" in x ]

            # lo -aður → -aðari/-aðri (þróaður)
            if lemma.endswith("aður"):
                for item in mst:
                    if "aðr" in PARADIGM[item]:
                        s = PARADIGM[item].replace("aðr", "aðar")
                        if not s in PARADIGM:
                            errors[item + "_err"] = s
            # lo -ugur → ugari/-ugri (gráðugur, göfugur)
            elif lemma.endswith("ugur"):
                for item in mst:
                    if "ugr" in PARADIGM[item]:
                        s = PARADIGM[item].replace("ugr", "ugar")
                        if not s in PARADIGM:
                            errors[item + "_err"] = s
            # lo -nn/-ll → -nni/nari -/lli/lari (einrænn, friðsæll)
            elif lemma.endswith("ll"):
                for item in mst:
                    if PARADIGM[item].endswith("lli") or PARADIGM[item].endswith("lla") and not lemma.endswith("eill"):
                        s = PARADIGM[item].replace("ll", "lar")
                        if not s in PARADIGM:
                            errors[item + "_err"] = s
            elif lemma.endswith("nn"):
                for item in mst:
                    if (PARADIGM[item].endswith("nni") or PARADIGM[item].endswith("nna")) and not lemma.endswith("einn"):
                        s = PARADIGM[item].replace("nn", "nar")
                        if not s in PARADIGM:
                            errors[item + "_err"] = s

            # lo -r → -rri/-ari (frír... nýr??)
            elif lemma.endswith("r") and not lemma.endswith("ur") and not lemma.endswith("hár") and not lemma.endswith("fár") and not lemma.endswith("smár") and not lemma.endswith("stór"):
                for item in mst:
                    if PARADIGM[item].endswith("rri") or PARADIGM[item].endswith("rra"):
                        s = PARADIGM[item].replace("rr", "ar")
                        s = s.replace("ýa", "ýja")
                        s = s.replace("æa", "æja")
                        if not s in PARADIGM:
                            errors[item + "_err"] = s
        elif pos == "so":
            # sagnbót í miðmynd -- alltaf merkt "MM"
            mm = "MM-SAGNB"
            if mm in PARADIGM and not PARADIGM[mm].endswith("ast") and not PARADIGM[mm].endswith("ist"):
                if lemma.endswith("sta") or lemma.endswith("stast"):    # verður "st" í mm-sagnb
                    errors[mm + "_err"] = PARADIGM[mm] + "st"

                elif lemma.endswith("tta") or lemma.endswith("ttast"):  # verður "st" í mm-sagnb
                    errors[mm + "_err"] = PARADIGM[mm][:-2] + "tst"
                    errors[mm + "_err2"] = PARADIGM[mm][:-2] + "ttst"
                    errors[mm + "_err3"] = PARADIGM[mm][:-2] + "ttstst"
                    errors[mm + "_err4"] = PARADIGM[mm][:-2] + "sst"
                    errors[mm + "_err4"] = PARADIGM[mm][:-2] + "zt"

                elif lemma.endswith("ta") or lemma.endswith("tast"):    # verður "st" í mm-sagnb
                    errors[mm + "_err"] = PARADIGM[mm][:-2] + "tst"
                    errors[mm + "_err2"] = PARADIGM[mm][:-2] + "ttst"
                    errors[mm + "_err3"] = PARADIGM[mm][:-2] + "ttstst"
                    errors[mm + "_err3"] = PARADIGM[mm][:-2] + "zt"

                elif lemma.endswith("nda") or lemma.endswith("ndast"):  # verður "nst" í mm-sagnb
                    errors[mm + "_err"] = PARADIGM[mm][:-2] + "dst"
                    errors[mm + "_err"] = PARADIGM[mm][:-2] + "zt"

                elif lemma.endswith("lda") or lemma.endswith("ldast"):  # verður "lst" í mm-sagnb
                    errors[mm + "_err"] = PARADIGM[mm][:-2] + "dst"
                    errors[mm + "_err"] = PARADIGM[mm][:-2] + "zt"

                elif lemma.endswith("setja") or lemma.endswith("flytja"):
                    errors[mm + "_err"] = PARADIGM[mm][:-2] + "tst"
                    errors[mm + "_err2"] = PARADIGM[mm][:-2] + "ttst"
                    errors[mm + "_err3"] = PARADIGM[mm][:-2] + "ttstst"
                    errors[mm + "_err4"] = PARADIGM[mm][:-2] + "sst"
                    errors[mm + "_err4"] = PARADIGM[mm][:-2] + "zt"
            if "LHÞT-SB-KK-NFET" in PARADIGM and PARADIGM["LHÞT-SB-KK-NFET"].endswith("inn"):
                lhþt = PARADIGM["LHÞT-SB-KK-NFET"]
                strong = "LHÞT-SB-"
                if PARADIGM["LHÞT-SB-KK-ÞGFFT"][-3] == "n":
                    if lhþt[-4] in dentals:
                        dent = dentals[lhþt[-4]]
                        stem1 = lhþt[:-3]
                        if lhþt[-5] == "n": # brunnum → brunn, ekki brun
                            stem2 = PARADIGM["LHÞT-SB-KK-ÞGFFT"][:-2] # Nauðsynlegt ef hljóðvarp í stofni
                        else:
                            stem2 = PARADIGM["LHÞT-SB-KK-ÞGFFT"][:-3] # Nauðsynlegt ef hljóðvarp í stofni
                        errors[strong + "KK-NFET" + "_err"] = stem1 + dent + "ur"     # skafður
                        errors[strong + "KVK-NFET" + "_err"] = stem2 + dent           # sköfð
                        if lhþt[-4] in "áóú":
                            errors[strong + "HK-NFET" + "_err"] = stem1 + dent        # skaft, knúð, ...
                        else:
                            errors[strong + "HK-NFET" + "_err"] = stem1 + "t"         # skaft, knúð, ...

                        errors[strong + "KK-ÞFET" + "_err"] = stem1 + dent + "an"
                        errors[strong + "KVK-ÞFET" + "_err"] = stem2 + dent + "a"
                        
                        errors[strong + "KK-ÞGFET" + "_err"] = stem2 + dent + "um"
                        errors[strong + "KVK-ÞGFET" + "_err"] = stem1 + dent + "ri"
                        errors[strong + "HK-ÞGFET" + "_err"] = stem2 + dent + "u"
                        
                        errors[strong + "KK-EFET" + "_err"] = stem1 + dent + "s"
                        errors[strong + "KVK-EFET" + "_err"] = stem1 + dent + "rar"
                        errors[strong + "HK-EFET" + "_err"] = stem1 + dent + "s"
                        
                        errors[strong + "KK-NFFT" + "_err"] = stem1 + dent + "ir"
                        errors[strong + "KVK-NFFT" + "_err"] = stem1 + dent + "ar"
                        errors[strong + "HK-NFFT" + "_err"] = stem2 + dent
                        
                        errors[strong + "KK-ÞFFT" + "_err"] = stem1 + dent + "ir"
                        errors[strong + "KVK-ÞFFT" + "_err"] = stem1 + dent + "ar"
                        errors[strong + "HK-ÞFFT" + "_err"] = stem2 + dent
                        
                        errors[strong + "KK-ÞGFFT" + "_err"] = stem2 + dent + "um"
                        errors[strong + "KVK-ÞGFFT" + "_err"] = stem2 + dent + "um"
                        errors[strong + "HK-ÞGFFT" + "_err"] = stem2 + dent + "um"

                        errors[strong + "KK-EFFT" + "_err"] = stem1 + dent + "ra"
                        errors[strong + "KVK-EFFT" + "_err"] = stem1 + dent + "ra"
                        errors[strong + "HK-EFFT" + "_err"] = stem1 + dent + "ra"

                        for mark in PARADIGM:
                            if "LHÞT-VB" in mark and not "2" in mark and not mark + "2" in PARADIGM:
                                if PARADIGM[mark][:-1].endswith("nn"):
                                    errors[mark + "_err"] = PARADIGM[mark][:-1] + dent + PARADIGM[mark][-1]  #skafði, skafða
                                else:
                                    errors[mark + "_err"] = PARADIGM[mark][:-2] + dent + PARADIGM[mark][-1]  #skafði, skafða

                # d: l, m, n (skilinn, taminn, þaninn)
                # t: p, k (glapinn, hrakinn)
                # ð: ø, f, r (knúinn, vafinn, barinn)
                dent = PARADIGM["LHÞT-SB-KK-ÞGFFT"][-3]
                if dent in "dðt":   
                    stem1 = lhþt[:-3]
                    stem2 = PARADIGM["LHÞT-SB-KK-ÞGFFT"][:-3]
                    errors[strong + "KK-NFET" + "_err"] = stem1 + dent + "ur"
                    errors[strong + "KK-ÞFET" + "_err"] = stem1 + dent + "an"
                    errors[strong + "KK-EFET" + "_err"] = stem1 + dent + "s"
                    errors[strong + "KK-EFFT" + "_err"] = stem1 + dent + "ra"

                    errors[strong + "KVK-NFET" + "_err"] = stem2 + dent
                    errors[strong + "KVK-ÞGFET" + "_err"] = stem1 + dent + "ri"
                    errors[strong + "KVK-EFET" + "_err"] = stem1 + dent + "rar"
                    errors[strong + "KVK-EFFT" + "_err"] = stem1 + dent + "ra"

                    errors[strong + "HK-EFET" + "_err"] = stem1 + dent + "s"
                    errors[strong + "HK-NFFT" + "_err"] = stem2 + dent
                    errors[strong + "HK-ÞFFT" + "_err"] = stem2 + dent
                    errors[strong + "HK-EFFT" + "_err"] = stem1 + dent + "ra"

                    errors[strong + "KK-ÞGFET" + "_err"] = stem2 + "num"
                    errors[strong + "KK-NFFT" + "_err"] = stem1 + "nir"
                    errors[strong + "KK-ÞFFT" + "_err"] = stem1 + "na"
                    errors[strong + "KK-ÞGFFT" + "_err"] = stem2 + "num"

                    errors[strong + "KVK-ÞFET" + "_err"] = stem1 + "na"
                    errors[strong + "KVK-NFFT" + "_err"] = stem1 + "nar"
                    errors[strong + "KVK-ÞFFT" + "_err"] = stem1 + "nar"
                    errors[strong + "KVK-ÞGFFT" + "_err"] = stem2 + "num"

                    errors[strong + "HK-NFET" + "_err"] = stem1 + dent
                    errors[strong + "HK-ÞFET" + "_err"] = stem1 + dent
                    errors[strong + "HK-ÞGFET" + "_err"] = stem2 + "nu"
                    errors[strong + "HK-ÞGFFT" + "_err"] = stem2 + "num"
                    for mark in PARADIGM:
                        if "LHÞT-VB" in mark and not "2" in mark and not mark + "2" in PARADIGM:
                            errors[mark + "_err"] = PARADIGM[mark][:-2] + "n" + PARADIGM[mark][-1]   # vafni, vafna

        else:
            #print("Fann eitthvað óeðlilegt!")
            #print("\t{}-{}".format(lemma, pos))
            pass
        # Bæta við skjalið!
        with open("systematic_errors.csv", "a") as toadd:
            for errormark in errors:
                corrmark = errormark.replace("_err4", "")
                corrmark = corrmark.replace("_err3", "")
                corrmark = corrmark.replace("_err2", "")
                corrmark = corrmark.replace("_err1", "")
                corrmark = corrmark.replace("_err", "")
                if not corrmark in PARADIGM:
                    print("{}-{}".format(errormark, errors[errormark]))
                else:
                    errfl = "err_" + PARADIGM[corrmark] + "_" + pos + "_" + idnum + "_" + corrmark
                    toadd.write("{};{};{};{};{};{}\n".format(lemma, idnum, pos, errfl, errors[errormark], errormark))
        with open("systematic_additions.csv", "a") as addnew:
            for newmark in newforms:
                addnew.write("{};{};{};alm;{};{}\n".format(lemma, idnum, pos, newforms[newmark], newmark))

    def is_uppercase(self, word):
        return word[0] in UPPERS

if __name__ == "__main__":
    start = Adder()
    start.main()


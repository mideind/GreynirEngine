#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Býr til orðasöfnin sem þarf til samsetningar.


import os
import sys

OPEN_CLASSES = ("kk", "kvk", "hk", "so", "lo", "ao")

# Hlutar BÍN sem leyfast ekki sem fyrri hlutar
FORBIDDEN_CATEGORIES = ("föð", "móð", "ætt", "dyr", "göt", "fyr", "ism")

# Orðflokkar sem leyfast hvergi í samsetningum
# Atviksorð sem geta staðið í samsetningum eru svo fá að best er að handvelja þau 
FORBIDDEN_CLASSES = ("pfn", "fn", "st", "uh", "gr", "ao")

# Lítil, sjaldgæf orð sem rugla samsetningu með mun algengari orðum
FORBIDDEN_FORMS = (
    "afbragð", "afdrátta", "afgang", "aflóa", "afnám", "afrek", "afrétta", "afréttir", "afréttum", "afs", 
    "afslátta", "afvega", "ag", "agan", "agata", "agg", "agi", "agl", "ak", "aki", "akstur", "akt", "al", 
    "ala", "alba", "ald ", "aldna", "aldæla", "alfata", "alger", "algjör", "ali", "alkunnu", "alls", 
    "allskonar", "allskyns", "als", "alt", "alþings", "alþjóðar", "am", "amb", "amen", "ami", "aminn", 
    "amm", "amma", "amri", "an", "ana", "andrúm", "andur", "ang", "ani", "ank", "anker", "annar", "annars", 
    "ans", "ansa", "ansi", "ap", "apal", "apur", "ar", "ara", "ari", "arins", "arir", "ark", "arks", "arl", 
    "arlið", "arr", "ars", "arsins", "art", "arí", "arða", "arðar", "as", "asar", "ask", "asm", "ass", "assa", 
    "at", "ata", "athafnar", "atl", "ats", "att", "aug", "aul", "austu", "ax", "aða", "aðallega", "aðalvar", 
    "aðgang", "aðl", "aðstoð", "bag", "bakki", "bal", "ban", "bara", "barnavernd", "bas", "bat", "bats", 
    "bel", "ben", "bensla", "bent", "berm", "bers", "beru", "bet", "bils", "birkis", "bis", "bisa", "biss", 
    "bjó", "bjóðs", "bla", "bliks", "blæðingar", "blóms", "blóðrás", "blóðs", "bogi", "bot", "bran", 
    "Breiðholt", "breiðs", "brennivín", "brigðar", "brottræk", "bráðabirgðar", "bró", "bun", "buna", "bur", 
    "burn", "burs", "bus", "byrj", "bænar", "bé", "bí", "bílds", "bílu", "bís", "bísa", "bóm", "bós", "búlur", 
    "bús", "búu", "cent", "ces", "cess", "cé", "dagskrárgerð", "dagskrárlið", "dam", "dang", "dank", "Danmörku", 
    "dar", "dari", "darr", "dars", "das", "dass", "dast", "deigs", "deilar", "deilis", "del", "der", "dera", 
    "ders", "des", "desja", "dess", "dettis", "dig", "dign", "dignar", "dings", "dipló", "dis", "djúps", "dok", 
    "doktor", "dol", "dolla", "don", "doni", "dorru", "dottir", "draf", "drena", "dræ", "drés", "dula", "dumb", 
    "dump", "dun", "dus", "dys", "dyst", "dárs", "dé", "dés", "dómnefnd", "dón", "dónsk", "döbb?", "döf", "dú", 
    "dý", "dýn", "eefum", "ef", "eff", "efi", "efn", "efs", "eftirlit", "eggjar", "egn", "ei", "eig", "einasta", 
    "eind", "eini", "einkarétt", "einleik", "eins", "einsleit", "eira", "eirð", "eis", "eist", "ek", "eka", 
    "ekk", "ekl", "ekt", "ektar", "ektum", "el", "eldflaug", "elf", "elg", "elga", "ell", "ells", "elsk", "elt", 
    "em", "emi", "emin", "end", "eng", "engingu", "enn", "ennþá", "er", "erf", "erg", "erils", "erji", "erl", 
    "erlan", "ern", "err", "ert", "eru", "es", "esa", "esi", "esp", "espi", "essa", "essen", "essing", "est", 
    "esta", "et", "eta", "eten", "eti", "etj", "etjan", "etti", "ettu", "ettum", "etu", "evr", "Evrópusamband", 
    "ex", "exi", "eyg", "eyr", "eyð", "eís", "eð", "eða", "fal", "fallvalt", "farsótt", "fau", "fel", "feldu", 
    "fern", "ferð", "fes", "fik", "fil", "fim", "fimmt", "fin", "fina", "finu", "fip", "firð", "fis", "fjallhá", 
    "fjarvídd", "fjárhag", "fjárhald", "fjárlag", "fjármálapólitík", "fjöld", "flas", "flytj", "flæsan", "flæsum", 
    "fol", "forsetafrú", "framboðshlið", "frý", "fuar", "fum", "fun", "fyl", "fyrrahaust", "fyrrahausts", 
    "fyrrasumar", "fyrrasumars", "fyrravetur", "fál", "fæl", "fær", "færð", "félag", "félagsá", "fés", "fí", 
    "fíi", "fís", "físa", "fó", "fór", "fós", "fótaaðgerð", "fóu", "fön", "föndr", "fú", "fún", "fúu", "fýl", 
    "fýs", "gag", "gaga", "gal", "gali", "gan", "gans", "gar", "garfi", "garri", "gart", "ge", "gea", "gefn", 
    "gei", "ges", "gess", "gibb", "gibba", "gibbu", "gim", "ginn", "ginu", "gis", "gistu", "glang", "glat", 
    "glot", "goli", "gop", "gor", "Grensá", "grimmd", "græ", "grú", "gum", "gur", "gus", "guður", "gál", "gár", 
    "gæ", "gæt", "gæð", "gé", "géa", "gés", "gím", "gín", "gísa", "gó", "gömmu", "gön", "gönguá", "gör", "göru", 
    "gú", "gúl", "gúla", "gúll", "gúllinn", "gúm", "gúr", "gúu", "hak", "hal", "halló", "han", "hann", "har", 
    "hara", "has", "hasi", "hat", "hef", "heilda", "heill", "heiður", "hem", "hemar", "hemi", "heng", "herst", 
    "hes", "hev", "heygj", "hjúk", "hlust", "hop", "horst", "hos", "hrin", "hul", "hulla", "hundruð", "huns", 
    "hupp", "huss", "Hvalá", "hvað", "hve", "hvit", "hví", "hái", "hálfu", "hæ", "hæk", "hær", "hæs", "hæsi", 
    "hél", "hí", "hír", "hís", "hít", "hó", "höld", "höm", "höð", "húf", "húk", "húl", "hún", "if", "ifa", "ifi", "ifl", 
    "igl", "il", "im", "imi", "imp", "ims", "In", "ing", "ingi", "ingum", "innenda", "innis", "ism", "isma", "ið", 
    "jaf", "jag", "jan", "jani", "jans ", "jap", "jar", "jas", "jasa", "jast", "jat", "jav", "je", "jea", "jes", 
    "juku", "jul", "jung", "junga", "já", "jáeind", "jæja", "jó", "jóg", "jón", "jóðs", "jú", "júr", "kaf", "kag", 
    "kaj", "kak", "kali", "kam", "kamal", "kami", "kan", "kanir", "kann", "kapara", "kari", "kas", "kask", "kat", 
    "katar", "kað", "kaðs", "kef", "keif", "kel", "kepp", "ker", "kerri", "kik", "kim", "kimb", "king", "kins", 
    "kip", "kipa", "kips", "kirj", "kis", "kisa", "kj", "kjannar", "kjó", "kland", "klandi", "kodd", "kof", "kog", 
    "kom", "kon", "koni", "kons", "konst", "kop", "kops", "korter", "korðu", "kos", "kosningaspá", "krí", "krú", 
    "krús", "kus", "kusar", "kut", "kyl", "ká", "káa", "kák", "kás", "kæl", "kí", "kíl", "Kíl", "kíla", "kís", 
    "kíss", "kó", "kód", "kón", "kóper", "kós", "köpp", "kör", "kös", "kú", "kúr", "kús", "kúð", "lam", "lamann", 
    "lamanna", "lami", "lander", "langlíf", "langveik", "lanir", "lap", "lar", "larar", "lask", "last", "lat", 
    "lausn", "laver", "lef", "lei", "leif", "Leikn", "leis", "lengd", "ler", "leri", "leruð", "less", "let", "leys", 
    "lin", "linn", "lip", "loggs", "logna", "logs", "lol", "lon", "loni", "lons", "lord", "lot", "lum", "lur", 
    "lussu", "lá", "læ", "lækja", "lækjunni", "læn", "lé", "léa", "líkan", "lít", "líð", "ló", "lóf", "lóg", "lögun", 
    "löm", "lön", "lötur", "löð", "lú", "lúi", "lún", "lúr", "lúser", "lúx", "lúð", "lý", "mag", "mak", "mal", 
    "man", "markmið", "mas", "mask", "matt", "max", "meg", "meint", "men", "mennt", "mer", "mestu", "mill", "mist", 
    "mjá", "moj", "mol", "mor", "mul", "mull", "mur", "mura", "murr", "musl", "musli", "must", "myr", "mys", "má", 
    "mæm", "mær", "míl", "mög", "mön", "mún", "mýt", "naf", "nakri", "nam", "nanna", "nap", "napar", "nar", "narr", 
    "nas", "nat", "nei", "neit", "ner", "Netá", "neyt", "nip", "niss", "nista", "nix", "nos", "nuf", "nus", "nusuð", 
    "nás", "næ", "næf", "næl", "næt", "né", "nít", "nó", "nók", "nór", "nót", "nóu", "núi", "nýj", "nýr", "nýt", 
    "ofi", "ofs", "ofu", "og", "oj", "oji", "ojs", "ok", "oks", "olí", "op", "opi", "or", "orar", "ordr", "ordra", 
    "ordru", "orf", "ori", "orn", "orr", "ors", "orti", "ortið", "ost", "ot", "otl", "ox", "oðr", "pari", "past", 
    "pastor", "pastur", "pat", "pata", "patt", "patti", "pells", "pen", "per", "pers", "pes", "pil", "pip", "por", 
    "pora", "pos", "prí", "pul", "pur", "pus", "put", "pá", "pák", "pál", "pás", "pæ", "pæj", "pé", "pí", "pít", 
    "pólitík", "pú", "púk", "púð", "rad", "rada", "rag", "rak", "ram", "ran", "rara", "rari", "ras", "rat", "rats", 
    "raut", "refl", "rekstur", "rella", "rem", "ren", "rendi", "reykj", "reytu", "rifj", "rig", "rillu", "rim", 
    "ringur", "rjáa", "rog", "rol", "ront", "rop", "ros", "rost", "rum", "rur", "rusk", "ryt", "rá", "rár", "ræ", 
    "ræk", "ræs", "ræt", "ré", "réið", "rés", "réttn", "rí", "ríinu", "rílinn", "rín", "rít", "ró", "róa", "róman", 
    "rón", "röm", "rú", "rúbb", "rús", "sakkað", "samn", "samtal", "samúð", "sandset", "sar", "sari", "Sauðá", "sed", 
    "seg", "seinnipart", "sell", "sem", "sen", "sendur", "sep", "setj", "seð", "sifj", "sift", "sil", "sili", "sim", 
    "simir", "sin", "sinki", "sinn", "sis", "sissi", "sjálfvirk", "ske", "skei", "Skeiðará", "Skeiðá", "skilda", 
    "sko", "skons", "skurk", "skuð", "skú", "skýl", "slaug", "slundi", "slundur", "slá", "slíf", "sló", "snýting", 
    "snýtingar", "snýtingu", "som", "sond", "sor", "stag", "stari", "staðreynd", "ster", "stjórnarskrá", "stjörnuspá", 
    "strim", "stum", "stí", "stímum", "stöð", "stú", "sug", "sum", "svensk", "svinnu", "svo", "sví", "syn", "syrnu", 
    "sá", "sám", "sán", "sæm", "sé", "séf", "sén", "sés", "sík", "símat", "sís", "sítrón", "só", "sód", "sói", "sós", 
    "sög", "sú", "súa", "súm", "súp", "súrn", "sý", "sýl", "sýr", "sýs", "taf", "tag", "tam", "tan", "tans", "tast", 
    "tasta", "tastaða", "teg", "tega", "teit", "tel", "tem", "tes", "tex", "tigs", "tila", "till", "tin", "tingla", 
    "tinu", "tips", "titt", "tjó", "tjóir", "tjóður", "tof", "tor", "torn", "tot", "tram", "tran", "trók", "tsar", 
    "tut", "tvenn", "tæj", "té", "tí", "tíf", "tífu", "tín", "tís", "tísk", "tít", "tó", "tóf", "tóg", "tór", "túb", 
    "túl", "túlkan", "tút", "tý", "týp", "ufs", "ugl", "uma", "umb", "umi", "umr", "umtal", "un", "una", "uni", "urg", 
    "urn", "urna", "urninn", "urninum", "urt", "urðu", "uss", "uxa", "vall", "vans", "vaplan", "var", "Varsjá", "vas", 
    "vasi", "vass", "vat", "vaðstu", "vei", "vek", "ven", "vent", "venta", "ventan", "verj", "vernd", "Vestu", "vila", 
    "vilni", "vim", "virð", "vis", "visin", "vok", "vol", "vos", "vá", "vár", "væm", "væma", "væmdir", "væmt", "værð", 
    "vé", "vés", "ví", "vía", "vísk", "yli", "ym", "yr", "yrr", "ys", "yssi", "zar", "zet", "ábyrgð", "áhrif", "Ák", 
    "Ál", "ál", "ála", "álag", "álút", "ám", "Án", "án", "árekstur", "ári", "ásýnd", "áta", "átu", "áð", "æf", "æg", 
    "æj", "æja", "æji", "æju", "æl", "æp", "æs", "æsla", "æt", "ætl", "æxl", "ég", "él", "élj", "ét", "íbú", "Íd", 
    "íl", "íla", "ílu", "ím", "Ím", "ími", "ímu", "Ín", "Ír", "ískar", "Ísrael", "ít", "ítur", "Ív", "íð", "íðin", 
    "óa", "óbyggð", "Ód", "óf", "óg", "ógi", "ói", "ól", "Ól", "óla", "óleum", "óli", "Óm", "ón", "ónar", "óp", "ór", 
    "Ór", "óri", "Ós", "ósi", "óvænt", "óx", "öfg", "öfrar", "ökkum", "ölv", "öngur", "örnin", "örninni", "örs", "ört", 
    "ös", "ötu", "öx", "öðru", "Ú", "ú", "úa", "údíla", "údíls", "úf", "úll", "úlla", "úrval", "úttekt", "úð", "ý", 
    "ýf", "ýg", "ýi", "ýj", "ýl", "Ýr", "ýr", "ýs", "ýt", "þannig", "þaðan", "þeg", "þet", "þin", "þrenn", "þur", 
    "Þverá", "því", "þá", "þáar", "þág", "þái", "þár", "þær", "þé", "þéi", "þér", "þó", "Þó", "þú", "þúi", "þý", "þýs", 
    "efana", "sjálfumglað", "sagð", "afar", "írak", "auk", "snjal", "titr", "komment", "afþreyinga", "akk", "akks", 
    "aldehýð", "aldehýðs", "alfat", "alfats", "aml", "amls", "amr", "amrs", "arg", "args", "aís", "aíss", "aðstand", 
    "aðstands", "bagl", "bagls", "bang", "bangs", "bank", "banks", "bos", "boss", "bram", "brams", "braml", "bramls", 
    "brikk", "brikks", "brok", "broks", "brús", "dark", "darks", "dif", "difs", "dik", "diks", "doll", "dolls", "emm", 
    "emms", "eymsl", "eymsls", "glan", "glans", "glim", "glims", "gúmm", "gúmms", "gúmí", "gúmís", "hrey", "hreys", 
    "hý", "hýs", "krabb", "krabbs", "krit", "krits", "kron", "krons", "kvikk", "kvikks", "larm", "larms", "mang", 
    "mangs", "morr", "morrs", "mosk", "mosks", "nipp", "nipps", "nurr", "nurrs", "okkur", "okkurs", "pel", "pels", 
    "pell", "pells", "pent", "pents", "perm", "pint", "plút", "pren", "prop", "pólití", "pút", "raukn", "regg", "risl", 
    "ruð", "sems", "serum", "setur", "sigt", "skilm", "skopt", "skrof", "slum", "smug", "snap", "snudd", "snudds", 
    "sprit", "stop", "strú", "stuf", "stufs", "stull", "stulls", "stím", "stíms", "suml", "sumls", "sundl", "sundls", 
    "svarf", "svarfs", "takl", "takls", "talk", "talks", "tigl", "tigls", "traf", "trafs", "trix", "urr", "urrs", 
    "usl", "usls", "vaf", "vafs", "vag", "vags", "vast", "vasts", "vell", "vells", "vigl", "vigls", "vipp", "vipps", 
    "vitt", "vitts", "voll", "volls", "vígl", "vígls", "vím", "víms", "ósig", "ósigs", "ótal", "ótals", "þrem", 
    "þrems", "þvogl", "þvogls", "þyrl", "þyrls", "þám", "þáms", "efnahaga", "pubb", "pubbs", "alvald", "þránd", 
    "hegg", "heggs", "glugg", "gluggs", "þorn", "þorns", "kukk", "kukks", "drukk", "drukks", "park", "parks", "fork", 
    "forks", "spel", "spels", "kafl", "kafls", "setil", "setils", "snertil", "snertils", "gistil", "gistils", "deil", 
    "deils", "haul", "hauls", "fyll", "fylls", "fordóm", "fordóms", "róman", "dragon", "dragons", "tamp", "tamps", 
    "stjór", "stjórs", "bumb", "bumbs", "damm", "damms", "skálp", "skálps", "leist", "leists", "dritt", "dritts", 
    "Tút", "trjámáv", "anka", "alba", "aða", "brigðar", "brigða", "arða", "arðar", "banga", "bjá", "rjá", "strind", 
    "und", "undar", "reik", "eink", "visk")    

# ID-númer beygingardæma sem eiga ekki að taka þátt í samsetningu sem síðasti hluti
FORBIDDEN_IDS = (
    "100647", "1007", "101227", "10176", "10178", "10189", "10197", "10203", "10223", "10229", "10230", "10249", "10250", 
    "10256", "10319", "10347", "10351", "10361", "10363", "10394", "10395", "10399", "10404", "10414", "10421", "10428", 
    "10440", "104540", "10472", "10532", "10540", "10555", "10575", "10578", "10617", "1063", "10630", "10660", "10665", 
    "10701", "10704", "10707", "10713", "10726", "10727", "10737", "10744", "10751", "10757", "107586", "10766", "10767", 
    "10781", "107875", "10795", "10802", "10806", "10845", "10850", "10860", "10900", "10941", "10943", "10955", "10958", 
    "10971", "110001", "11006", "11008", "11010", "11012", "11015", "1104", "11066", "110757", "11077", "11094", "11099", 
    "111373", "11162", "111814", "11222", "1125", "11304", "11308", "11316", "11339", "11361", "11454", "11473", "115437", 
    "1190", "119030", "1195", "120566", "12087", "121236", "12127", "12191", "12192", "12212", "122597", "12265", "12274", 
    "12279", "12280", "12290", "12291", "12299", "12312", "12433", "125045", "125252", "1264", "127201", "127364", "1275", 
    "12895", "12965", "12973", "130271", "1303", "131552", "134788", "135273", "135925", "13663", "1370", "13754", "13759", 
    "13763", "13767", "13770", "13773", "13797", "13819", "1386", "13887", "13888", "13890", "13898", "13899", "13914", 
    "13951", "13955", "13964", "13985", "13994", "14044", "14072", "14074", "14136", "14137", "141441", "14171", "14225", 
    "14249", "14253", "14268", "1428", "14307", "14326", "14343", "14345", "14347", "143618", "14372", "14394", "14442", 
    "145089", "14514", "14515", "14520", "14526", "145278", "14575", "145771", "14580", "145830", "145869", "14597", 
    "14643", "14645", "14658", "146913", "146970", "14699", "14706", "14711", "14712", "14720", "14726", "1473", "1476", 
    "147763", "147764", "14777", "14785", "14788", "14791", "14799", "148057", "14806", "14820", "14825", "14828", "14838", 
    "14839", "14842", "14859", "148671", "14875", "14889", "14890", "14892", "14938", "14979", "14989", "14994", "1500", 
    "15012", "15013", "1502", "15090", "15096", "151100", "15180", "15293", "15313", "15330", "15340", "153477", "15373", 
    "15381", "15409", "15415", "1542", "15431", "15436", "15447", "15457", "15485", "15494", "15496", "1562", "1568", 
    "15691", "1570", "15700", "1571", "15744", "1576", "15802", "158105", "15826", "15833", "15835", "15869", "15870", 
    "15885", "15897", "159012", "15924", "15925", "15927", "15938", "15944", "15953", "15959", "15964", "16014", "16015", 
    "16023", "16029", "16043", "16046", "16047", "16065", "16069", "16082", "16089", "16099", "16101", "16105", "16183", 
    "16258", "1627", "16271", "16289", "16291", "16296", "16299", "16302", "16304", "16323", "16324", "1633", "16343", 
    "16373", "16384", "16387", "16415", "16434", "1644", "16446", "16451", "16464", "16468", "16471", "16480", "164859", 
    "164892", "165010", "165044", "165047", "165059", "165069", "165074", "165130", "165131", "165142", "165155", "165172", 
    "165180", "165182", "165188", "165205", "165211", "165223", "165241", "165261", "165275", "165308", "165313", "165333", 
    "165366", "165392", "165397", "165440", "165446", "165479", "165500", "165506", "165507", "165510", "165529", "165538", 
    "165569", "165570", "165606", "165642", "165669", "165670", "165776", "165806", "165843", "165861", "165869", "16588", 
    "16607", "166151", "166171", "166187", "166216", "166232", "166248", "166258", "166401", "166413", "16681", "16694", 
    "167009", "167031", "1688", "170661", "170664", "171639", "175094", "175679", "175692", "175820", "1776", "1777", "1779", 
    "1781", "1785", "178571", "180558", "1807", "1816", "1817", "1819", "1820", "1825", "182720", "183052", "1831", "183195", 
    "1834", "184549", "1846", "1856", "1877", "1891", "190685", "190851", "190893", "191136", "191190", "1925", "1938", "19876", 
    "2048", "2109", "211159", "2195", "2207", "2213", "2224", "2244", "2263", "2281", "2358", "2360", "2363", "2368", "23831", 
    "2395", "2400", "2418", "2422", "2424", "2430", "2446", "2466", "2483", "2501", "2515", "2524", "2546", "2556", "2567", 
    "2601", "2613", "2623", "2626", "2627", "2697", "27564", "2866", "2868", "2872", "2876", "2888", "2894", "2895", "2908", 
    "2911", "2923", "2930", "2931", "293279", "2938", "2949", "29559", "2960", "29667", "297151", "2989", "29993", "3004", 
    "3036", "3070", "3073", "3080", "3092", "3156", "3158", "3160", "3161", "3176", "3197", "321123", "3230", "324273", "3243", 
    "326581", "327218", "328035", "3292", "329954", "332242", "332343", "3335", "3336", "3340", "334706", "3351", "3363", "3372", 
    "337527", "337834", "337885", "337886", "337887", "337888", "337893", "337895", "337909", "337956", "3386", "3389", "342413", 
    "342970", "3445", "3485", "349380", "3528", "3530", "3534", "3538", "3540", "3556", "3575", "3611", "3626", "3664", "3679", 
    "3684", "3714", "372678", "3727", "372711", "372712", "372763", "372771", "372887", "3758", "376", "3774", "380321", "3808", 
    "381239", "3815", "3817", "3820", "3830", "3837", "3842", "384268", "384355", "384657", "384747", "384857", "3852", "385296", 
    "385308", "385622", "385761", "385887", "386067", "386193", "386206", "386239", "386692", "386713", "386889", "386952", 
    "3870", "387210", "387449", "387492", "387501", "387610", "387622", "387636", "387645", "387681", "387709", "3879", "387918", 
    "388679", "389290", "3893", "389525", "389551", "389702", "390856", "391214", "391314", "391354", "391370", "392132", "3927", 
    "3934", "393421", "393699", "393723", "393737", "393788", "394274", "3944", "3952", "395788", "395838", "3964", "3965", 
    "3972", "3974", "3987", "3988", "3989", "3992", "4011", "4012", "4021", "4025", "403704", "403833", "403834", "403835", 
    "403838", "403839", "403852", "404033", "404364", "406176", "406177", "406663", "4068", "406918", "408194", "408196", 
    "4084", "408434", "408451", "408456", "408569", "408666", "4087", "408716", "408723", "408992", "409002", "409003", "409005", 
    "409067", "409074", "409076", "409090", "409092", "409098", "409111", "409126", "409129", "409130", "409144", "409159", 
    "409163", "409165", "409167", "409173", "409174", "409180", "409186", "409202", "409209", "409210", "409270", "409303", 
    "409318", "409319", "409322", "409323", "409907", "410489", "410505", "410626", "410627", "410634", "410636", "410641", 
    "410645", "411", "411268", "411741", "412", "4123", "412722", "412980", "4144", "41553", "416782", "416851", "416955", 
    "417911", "417917", "418103", "419391", "419400", "419401", "419410", "419411", "419413", "419416", "419427", "419447", 
    "419458", "419535", "419737", "419793", "419804", "419860", "4199", "419915", "419924", "419964", "4200", "420015", "420038", 
    "420078", "4201", "420101", "420137", "420139", "4202", "420246", "420301", "420304", "420315", "420419", "420454", "420475", 
    "420558", "420572", "420601", "420619", "420722", "420748", "420898", "421001", "421098", "421103", "421105", "421137", 
    "421155", "421168", "421169", "421191", "421202", "421229", "421230", "421244", "421261", "421289", "421300", "421328", 
    "421393", "421418", "421430", "421472", "421665", "421666", "421684", "421695", "421716", "421718", "421783", "421850", 
    "421853", "421877", "421977", "421992", "422014", "422025", "422081", "422109", "422116", "422132", "422139", "422141", 
    "422146", "422191", "422199", "422204", "422224", "422236", "422297", "422416", "422424", "422472", "422473", "422486", 
    "422539", "422557", "422571", "422572", "422575", "422616", "422624", "422638", "422643", "422662", "422693", "422698", 
    "422711", "422727", "422744", "422816", "422844", "422853", "422854", "422857", "422859", "422941", "422967", "423027", 
    "423037", "423071", "423084", "423113", "423177", "423214", "423273", "423329", "423331", "423354", "423371", "423375", 
    "423451", "423453", "423464", "423478", "423479", "423582", "423627", "423651", "423749", "423751", "423762", "423778", 
    "423795", "423815", "423828", "423846", "423963", "423998", "424006", "424046", "424049", "424050", "424052", "424167", 
    "424200", "424214", "424223", "424225", "424243", "424253", "424336", "424443", "424453", "424607", "424673", "424679", 
    "424680", "424685", "424729", "424799", "424800", "424802", "424807", "424953", "425096", "425101", "425102", "425147", 
    "425179", "425749", "425752", "427442", "427488", "427489", "427492", "427494", "427496", "427512", "427676", "429201", 
    "430800", "430801", "433", "433173", "4333", "433465", "433476", "433568", "433572", "433632", "433638", "433653", "433658", 
    "433659", "433660", "434168", "434176", "434181", "434248", "434264", "434272", "434284", "434313", "434314", "434326", 
    "434327", "434329", "434355", "434360", "434439", "434440", "434538", "434582", "434601", "434641", "434645", "434724", 
    "434736", "434794", "434910", "434918", "434951", "434997", "434999", "435", "435020", "435021", "435111", "435140", "435170", 
    "435175", "435181", "435200", "435241", "435243", "435299", "435302", "435311", "435347", "435360", "435441", "435445", 
    "435496", "435565", "435574", "435580", "435588", "435591", "435609", "435617", "435618", "435644", "435665", "435666", 
    "435668", "435693", "435715", "435719", "436179", "436182", "436190", "436245", "436315", "436322", "436333", "43635", "437", 
    "438170", "4391", "4403", "4434", "4436", "4450", "4452", "448387", "448393", "4484", "448426", "448431", "448432", "448435", 
    "448462", "449", "4497", "449998", "450216", "4504", "4511", "4514", "45755", "459212", "459479", "4595", "4598", "459888", 
    "46071", "461", "461111", "461120", "461122", "461149", "4612", "4614", "4618", "4620", "463", "463886", "463902", "463910", 
    "463917", "464090", "464112", "464779", "464855", "465141", "4661", "466164", "4663", "466474", "466511", "466512", "466523", 
    "466548", "466566", "466598", "466607", "466685", "466732", "466765", "466775", "4671", "467511", "467733", "467736", "467739", 
    "467752", "467767", "467768", "4681", "469264", "469272", "469275", "469277", "469284", "469286", "469289", "469291", "470082", 
    "470441", "470999", "471196", "471208", "472487", "472538", "474", "475918", "476027", "476629", "476630", "476681", "476822", 
    "476837", "476869", "476890", "4769", "476922", "477243", "477267", "477282", "477360", "4774", "477408", "4778", "477915", 
    "477922", "478653", "478666", "478721", "478739", "478745", "478782", "479125", "479260", "479272", "479278", "479290", 
    "479397", "480024", "480207", "480329", "481", "481029", "482756", "483490", "483553", "483604", "483635", "483640", "483667", 
    "483736", "483749", "483754", "483760", "483787", "483799", "483809", "483828", "483830", "483876", "483949", "484015", 
    "484058", "484086", "484120", "484121", "484158", "4842", "484266", "484273", "484274", "484301", "484314", "484337", "484346", 
    "484350", "484403", "484408", "484432", "484433", "484505", "484513", "484516", "484517", "484645", "484694", "484757", 
    "484829", "4849", "484999", "485107", "485820", "485983", "486158", "486521", "486757", "486767", "486768", "486771", 
    "486772", "486773", "486774", "486775", "486904", "487043", "488", "488010", "488182", "488198", "488372", "491", "4913", 
    "4939", "4960", "50094", "5029", "5088", "5139", "5145", "5168", "5178", "5185", "5199", "5201", "5202", "5203", "5210", 
    "5226", "5232", "5260", "52603", "531", "5326", "5329", "5361", "5374", "5395", "5419", "5507", "5533", "5535", "55905", "5597", 
    "5598", "5609", "5647", "5654", "56750", "5710", "5714", "5762", "5809", "5813", "5840", "5861", "5884", "5898", "59101", "5926", 
    "5932", "5953", "5966", "5974", "6001", "6034", "6036", "60979", "6100", "6128", "6148", "615", "6150", "6151", "6168", "6268", 
    "6302", "6335", "6347", "6350", "6356", "6368", "6389", "6405", "6406", "64275", "6468", "6519", "67369", "6771", "6777", "6787", 
    "6799", "68042", "6821", "6833", "6837", "6838", "6845", "6849", "6855", "6881", "68886", "6896", "69133", "6915", "6916", "7002", 
    "7025", "7035", "7039", "7047", "7066", "7067", "70743", "708", "7096", "7098", "7101", "7120", "7197", "7207", "7208", "7243", 
    "7245", "7310", "7329", "7340", "7344", "7366", "7384", "7397", "7400", "7415", "7418", "7425", "7433", "744", "74480", "74482", 
    "7490", "7497", "7502", "7504", "7510", "7517", "7518", "7530", "7543", "7567", "7568", "7576", "7585", "7590", "7595", "7610", 
    "7668", "7669", "7673", "7695", "7702", "7705", "7708", "775", "7750", "7857", "787", "7945", "797", "8027", "81698", "82896", 
    "8324", "8408", "8418", "85237", "854", "8625", "8689", "8693", "87120", "8737", "8752", "876", "8761", "8774", "8777", "8791", 
    "8830", "8835", "8838", "8839", "8840", "8843", "8847", "88669", "8877", "8931", "8935", "8981", "8988", "8997", "9004", "9008", 
    "9017", "9025", "9047", "90615", "9069", "9077", "9078", "9087", "9088", "9089", "9100", "9101", "9103", "9114", "9115", "9134", 
    "9135", "9136", "9147", "9151", "9163", "917", "9195", "9208", "9218", "9220", "92257", "9226", "9258", "938", "947", "94970", 
    "95765", "963", "9790", "99017", "372341", "244131", "5164", "354304")

OUTLATTERS = (
    "ak", "al", "aldinum", "andana", "andandi", "andanna", "andir", "andið", "bergum", "brögum", "bura", "buran", "buranna", "burum", 
    "buruna", "burunnar", "burunni", "burunum", "burur", "bururnar", "bygginu", "báðum", "bæg", "dramanna", "efnana", "efum", "eigan", 
    "eikanna", "ein", "ekki", "eldra", "eldri", "ester", "eys", "fangin", "fimmta", "fimmti", "fiss", "fissins", "fitið", "fjórða", 
    "fjórði", "fleinum", "formað", "formerum", "formununum", "forum", "framað", "frá", "funar", "fundin", "fól", "gaf", "gegnum", 
    "gerra", "gers", "geru", "gerum", "gini", "ginir", "ginum", "gleð", "gripu", "gröm", "grúf", "hallan", "hanni", "hefi", "hemur", 
    "hina", "hitni", "hitum", "hjó", "inn", "iði", "keppi", "kinnana", "kosni", "kvað", "kvel", "kúru", "lamið", "langana", "las", 
    "leikin", "leikins", "lettu", "lettum", "linni", "listanir", "litana", "litananna", "litin", "litins", "liðu", "lystu", "lúra", 
    "lúrið", "mana", "mangið", "marin", "mótana", "naum", "nefjana", "nera", "nánast", "níu", "níðins", "of", "orðana", "rann", 
    "rant", "rants", "rauði", "reiðan", "renn", "ruðust", "ryfir", "rym", "rynni", "ræki", "rækið", "rómanir", "róum", "rúnar", 
    "sef", "set", "sjóna", "sjötta", "sjötti", "sjöunda", "sjöundi", "skráum", "skýrs", "sleit", "slest", "slægð", "sprest", "staðin", 
    "stendur", "stunin", "sætan", "sí", "síðastliðnum", "te", "tingana", "tíðna", "tönnur", "ungan", "van", "vaningum", "vast", 
    "vegana", "vegu", "verra", "verður", "við", "viðana", "voru", "ækist", "æsti", "úr", "þriðja", "þriðji", "þáttana", "þáttununum")

CONSONANTS = "bdðfghjklmnprstvxzþ"
UPPERS = "AÁBDÐEÉFGHIÍJKLMNOÓPRSTUÚVXYÝZÞÆÖ"
BADS_LO = ("ddur", "ftur", "fður", "gdur", "gður", "ktur", "gtur", "ltur", "ptur", "ldur", "ndur", "rtur", 
    "stur", "rður", "ttur", "áður", "æður", "éður")
class Fixer():
    def __init__(self):
        self.former_parts = set()
        self.latter_parts = set()

    def main(self):
        # y[0] = nefnimynd
        # y[1] = ID-númer
        # y[2] = orðflokkur
        # y[3] = yfirflokkur
        # y[4] = orðmynd
        # y[5] = BÍN-mark
        # Það sem sleppi alls staðar:
        # X  FORBIDDEN_FORMS
        # X  FORBIDDEN_CLASSES
        # X  margorða myndir (hvor annar o.fl.)

        print("Sieving")
        self.sieve_parts()  # Bætir við gildum myndum úr tilraun.csv
        print("Adding other forms")
        self.other_forms()  # Bætir öðrum myndum við
        print("Printing")
        self.print_parts()  # Skrifar gildar myndir út í skjöl
        print("Done!")

    def former(self, y):
        """ Orð sem geta staðið sem fyrri hluti í samsetningu """    
        # Nafnorð: ef.et og ft. og nf.et. 
        # Stofn.
            #kk -- taka -ur eða -i
            #kvk: nota þf. ef endar á samhljóði, annars nf. án -a. Ef -i, hluti af stofni.
            #hk: ef enda á samhljóði er það stofn. ef enda á -a, taka það. ef -i og þf. eins, hluti stofns.
        # Bandstafsmyndir
        # Lýsingarorð: stofn.
        # Sagnorð: stofn og stofn+i
        # Valin atviksorð
        # Sleppa sérnöfnum
        
        if y[3] in FORBIDDEN_CATEGORIES or "ü" in y[4] :
            return
        # Nafnorð
        if y[2] in ["kk", "kvk", "hk"] and not "gr" in y[5]: # Fann nafnorð, mark er í y[5]
            if "EF" in y[5]: 
                self.former_parts.add(y[4])
                #print("1:\t{}".format(y[4]))
            if y[5] in FORBIDDEN_CATEGORIES:
                return
            # Stofnmyndir
            if "kvk" in y[2] and "ÞFET" in y[5]:            # Stofn kvenkynsorða
                if y[0].endswith("un") or y[0].endswith("an") or y[0].endswith("ing") or y[0].endswith("ung"): # Ath. truflar 'baun', 'laun'...
                    return
                if self.ends_in_consonant(y[0]):
                    if "ö" in y[0][-3:]:                    # Orð eins og tönn, sök, dvöl, höfn... samsetningar nota 'a' í staðinn
                        subbed = y[0][:y[0].rfind('ö')] + "a" + y[0][y[0].rfind('ö')+1]
                        self.former_parts.add(subbed)
                    else:
                        self.former_parts.add(y[4])             # Orð sem enda á samhljóða, eins og urð, ... Stofninn er nefnimyndin.
                elif y[4].endswith("i"):
                    #self.former_parts.add(y[4])             # Orð eins og heiði, keppni, beiðni, ... -i er hluti af stofninum. Er eins og ef.et., engin ástæða til að bæta við!
                    self.former_parts.add(y[4]+"s")         # Stór hluti þessara orða leyfir bandstaf, sbr. hæfnismat, keppnisskap, ...
                #elif y[0].endswith("a"):
                    #if not y[0].endswith("ja"):
                        #self.former_parts.add(y[0][:-1])    # Orð eins og slanga, dúkka, ... Stofninn er án sérhljóðans. Virðast ekki notuð í samsetningum!
                    #else:                   
                        #pass                                # Orð eins og langnefja, ... Stofninn er ekki notaður sem fyrri hluti.
                else:
                    self.former_parts.add(y[0])             # Orð eins og skrá, þrá, ró, trú, ... Stofninn er nefnimyndin.
            elif "hk" in y[2] and "NFET" in y[5]:                              # Stofn hvorugkynsorða
                if y[0].endswith("land"):
                    return
                self.former_parts.add(y[4])                 # Orð eins og hús, rán, haf; firma, nammi, vé, sjampó, ... stofninn er nefnimyndin
            elif "kk" in y[2] and "ÞFET" in y[5]:
                if y[0].endswith("ingur") or y[0].endswith("ungur") or y[0].endswith("aður") or y[0].endswith("uður") or y[0].endswith("angur"):
                    return
                if y[0].endswith("ur"):
                    self.former_parts.add(y[4])             # Orð eins og hestur, fögnuður, maður, vegur, ... stofninn er þolfallsmyndin.
                elif y[0].endswith("i"):
                    #self.former_parts.add(y[0][:-1])        # Orð eins og gróði, fjöldi, kappi, ... stofninn er án sérhljóðans. Virðast ekki notuð í samsetningum!
                    pass
                elif "ö" in y[0][-5:]:                    # Orð eins og vörður, völlur, köstur, ... samsetningar nota 'a' í staðinn
                    subbed = y[0][:y[0].rfind('ö')] + "a" + y[0][y[0].rfind('ö')+1]
                    self.former_parts.add(subbed)

                else:
                    self.former_parts.add(y[4])             # Orð eins og þistill, bróðir, skór, steinn, jökull, aftann, karl, víðir, herra, ... stofn er þolfallsmyndin.

        # Lýsingarorð        
        elif y[2] in ["lo"]:
            if y[0].endswith("andi") or y[0].endswith("legur") or y[0].endswith("aður") or y[0].endswith("inn") or y[0].endswith("kvæmur") \
                or y[0].endswith("samur") or y[0].endswith("gengur") or y[0].endswith("mennur") or y[0].endswith("rænn") or y[0].endswith("nægur") \
                or y[0].endswith("lægur") or y[0].endswith("látur") or y[0].endswith("drægur") or y[0][-4:] in BADS_LO:
                return
            if "FSB-KVK-NFET" in y[5]:
                if y[0].endswith("ur"):                
                    if y[2].endswith("ur"):                 # Stofninn inniheldur -ur: fagur, napur, dapur, ... Stofninn er nf.et.kk.
                        self.former_parts.add(y[0])
                        #print("3A:\t{}".format(y[0]))
                    else:                                   # Orð sem enda á -ur í kk. en ekki kvk. ... Stofninn er nf.et.kk. -ur.
                        self.former_parts.add(y[0][:-2])    
                        #print("3B:\t{}".format(y[0][:-2]))
                elif y[0].endswith("all"):                  # Orð eins og gamall, einsamall, ... Stofninn er nf.et.kk. -l.
                    self.former_parts.add(y[0][:-1])
                else:                                       # Orð eins og grænn, laus, alger, grár, vansvefta, ... Stofninn er nf.et.kvk.
                    if "ö" in y[0][-3:]:                    # Orð eins og jöfn, sönn, gjörn, ... samsetningar nota 'a' í staðinn
                        subbed = y[0][:y[0].rfind('ö')] + "a" + y[0][y[0].rfind('ö')+1]
                        self.former_parts.add(subbed)
                    else:
                        self.former_parts.add(y[4])
                        #print("3C:\t{}".format(y[4]))
                        #print("\t3C:\t{}".format(y))
            else:
                return
        # Sagnorð
        elif y[2] in ["so"]:
            pass            # Sleppi sagnasamsetningum í bili. Hef ekki rekið mig á að það sé að hjálpa.
            # Búin að skoða niðurstöður eftir að sleppti því, þær eru mun skárri. Held mig við að sleppa sagnasamsetningum.
            #if "MM" in y[5] or not "NH" in y[5]:
                #print(y[4])
            #    return
            #if y[0].endswith("a"):                          # Orð eins og halda, ætla
            #    self.former_parts.add(y[0][:-1])
            #    self.former_parts.add(y[0][:-1]+"i")
            #elif y[0].endswith("u"):                        # Orð eins og munu, skulu
            #    pass
            #else:
            #    self.former_parts.add(y[0])                 # Orð eins og sjá, slá, fá
            #    self.former_parts.add(y[0]+"i")

        # Atviksorð
        elif y[2] in ["ao"]:
            pass
        return

    def latter(self, y):
        """ Orð sem geta staðið sem síðasti hluti í samsetningu """
        # Allar orðmyndir opinna orðflokka; no, lo, so, ao. Búið að útiloka hin áður en hingað er komið.
        # Viðskeyti? Sleppi eins og er.
        # Ath. að neðst í skjali eru alls konar ao sem ganga ekki sem seinni hluti; agnir, setningaratviksorð og annað. Taka út handvirkt eftir á.
        if y[2] == "ao" and y[3] == "ob":
            return
        if y[1] in FORBIDDEN_IDS or y[4] in OUTLATTERS or "GM-BH-ST" in y[5] or "MM-SAGNB" in y[5] or "ü" in y[4] :
            return
        self.latter_parts.add(y[4])

    def sieve_parts(self):
        print("ord.csv ...")
        with open('ord.csv', 'r') as tilraun:
            while True:
                x = tilraun.readline()
                y = x.split(";")
                if not y[0]:
                    break
                if y[2] in FORBIDDEN_CLASSES or " " in y[0]:
                    continue
                else:
                    self.former(y)
                    if y[2] in OPEN_CLASSES:
                        self.latter(y)
        print("ord.auka.csv ...")
        with open('ord.auka.csv', 'r') as auka:
            while True:
                x = auka.readline()
                y = x.split(";")
                if not y[0]:
                    break
                if len(y) < 2 or y[2] in FORBIDDEN_CLASSES or " " in y[0]:
                    continue
                else:
                    self.former(y)
                    if y[2] in OPEN_CLASSES:
                        self.latter(y)
        print("ord.add.csv ...")
        with open('ord.add.csv', 'r') as add:
            while True:
                x = add.readline()
                y = x.split(";")
                if not y[0]:
                    break
                if len(y) < 2 or y[2] in FORBIDDEN_CLASSES or " " in y[0]:
                    continue
                else:
                    self.former(y)
                    if y[2] in OPEN_CLASSES:
                        self.latter(y)
        print("systematic_additions ...")
        with open('systematic_additions.csv', 'r') as kerfis:
            while True:
                x = kerfis.readline()
                y = x.split(";")
                if not y[0]:
                    break
                if len(y) < 2 or y[2] in FORBIDDEN_CLASSES or " " in y[0]:
                    continue
                else:
                    self.former(y)
                    if y[2] in OPEN_CLASSES:
                        self.latter(y)

    def other_forms(self):
        formers_to_add = (
            "af", "afar", "aftan", "aftur", "al", "all", "alls", "alpa", "alt", "alvöru", "alþjóða", "and", "annars", "augn", "auk", "auka", "aust", "austan", 
            "austanfjalls", "austansuðaustan", "austanvert", "austnorðan", "austsuðaustur", "austur", "austursuðaustur", "auð", "að", "aðal", 
            "bak", "bland", "blindra", "blökku", "brott", "bráða", "burt", "dánar", "dóta", "efra", "efri", "eftir", "ei", "ein", "einka", "eins", "ekta", 
            "eldra", "eldri", "ellefu", "endur", "erki", "fagur", "fatlaðra", "fer", "fimm", "fimmtán", "fimmtíu", "firna", "fjar", "fjarska", 
            "fjær", "fjór", "fjórtán", "fjöl", "fjörutíu", "fletti", "flökku", "for", "foráttu", "fram", "framan", "frum", "frá", "full", "fullorðins", 
            "fyrir", "fyrr", "fyrra", "fyrri", "fyrst", "fátækra", "gegn", "gegnum", "ger", "gjör", "grjóta", "gær", "hand", "handan", "harla", 
            "heilsárs", "heim", "heima", "heiman", "hingað", "hjarð", "hjá", "hland", "hnjá", "hundrað", "hundruð", "hundruða", "hálf", "hægri", "hér", 
            "héðan", "inn", "innan", "innbyrðis", "inni", "innra", "innri", "innvortis", "jafn", "já", "kamel", "katt", "kné", "kráar", "kringum", "krist", 
            "krists", "kven", "land", "langa", "langsum", "lausa", "míní", "líkams", "lítt", "mandarín", "mann", "marg", "masters", "mega", "megin", "meir", "með", 
            "meðal", "milli", "milljarð", "milljarða", "milljón", "milljóna", "mis", "miðdegis", "moskító", "míkró", "mót", "nanó", "nauða", 
            "nei", "neðan", "neðra", "neðri", "niðri", "niður", "norð", "norðan", "norðaustan", "norðaustur", "norður", "norðvestan", "norðvestur", 
            "nyrðra", "nær", "næst", "næstum", "ní", "nítján", "níu", "níutíu", "nóró", "nú", "ný", "of", "ofan", "ofsa", "ofur", "parma", "pastel", 
            "prumpu", "pólí", "pólý", "regin", "reða", "réttsýnis", "rök", "sam", "saman", "samgöngu", "sautján", "sebra", "seinna", "seinni", 
            "semí", "sex", "sextán", "sextíu", "sjálfs", "sjö", "sjötíu", "sjúkra", "ská", "slembi", "smur", "smá", "snemm", "spari", "stað", "staffa", "stóra", 
            "sundur", "sunnan", "suðaustan", "suðaustanlands", "suðaustur", "suður", "suðvestur", "svaka", "svo", "sára", "séffer", "sér", "sí", 
            "síð", "síðdegis", "sósíal", "súnní", "tengi", "til", "tor", "trjá", "tuttugu", "tví", "tvítug", "tvö", "tí", "títt", "tíu", "tólf", 
            "um", "umfram", "undan", "undir", "undra", "undur", "upp", "uppi", "utan", "van", "vara", "vegna", "vel", "vestan", "vestsuðvestur", 
            "vestur", "vinstri", "visa", "vita", "við", "voða", "vond", "vöðlu", "yfir", "yngra", "yngri", "á", "áfram", "án", "árdegis", "átján", "átt", 
            "átta", "áttatíu", "áður", "æ", "æva", "æði", "æðsta", "æðsti", "í", "íransk", "ítalsk", "ó", "ógeðis", "óvenju", "óða", "öfga", "öku", 
            "ör", "últra", "úr", "út", "útbyrðis", "úti", "þar", "þaðan", "þrettán", "þrjátíu", "þrumu", "þrusu", "þrí", "þvers", "þversum", "því", 
            "þá", "þérna", "þétt", "þúsund", "þúsunda"
            )
        for each in formers_to_add:
            self.former_parts.add(each)
        outformer = ("böð", "búi", "fló", "áa", "gass")
        self.former_parts = [ w for w in self.former_parts if w not in FORBIDDEN_FORMS and w not in outformer]
        self.latter_parts = [ w for w in self.latter_parts if w not in FORBIDDEN_FORMS]

    def print_parts(self):
        with open('formers.txt','w+') as formers:
            for item in self.former_parts:
                    formers.write("{}\n".format(item))
            formers.close()

        with open('last.txt', 'w+') as latters:
            for item in self.latter_parts:
                latters.write("{}\n".format(item))
            latters.close()
        return

    def ends_in_consonant(self, word):
        return word[-1] in CONSONANTS

    def is_uppercase(self, word):
        return word[0] in UPPERS

if __name__ == "__main__":
    start = Fixer()
    start.main()

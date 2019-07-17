.. _nonterminals:

Nonterminals
============

This section lists the nonterminals that can occur within simplified
sentence trees, i.e. instances of the :py:class:`SimpleTree` class.
The nonterminal name of a tree node can be read from the
:py:attr:`SimpleTree.tag` property.

Sentences and paragraphs
------------------------

*Setningar, málsgreinar og efnisgreinar*

+--------------+----------------------------------------------------------+
| S0           | Root of tree                                             |
+--------------+----------------------------------------------------------+
| S-MAIN       | Main clause (aðalsetning)                                |
+--------------+----------------------------------------------------------+
| S-HEADING    | Sentence-heading (fyrirsögn)                             |
+------------+------------------------------------------------------------+
| S-PREFIX     | Prefix clause (*Með öðrum orðum:* Páll sá kött)          |
+--------------+----------------------------------------------------------+
| S-QUE        | Question clause (spurnarsetning)                         |
|              | („*Hvaða stjaka viltu*?“)                                |
+--------------+----------------------------------------------------------+
| CP-THT       | Complement clause (skýringarsetning)                     |
|              | (Páll veit *að kötturinn kemur heim*)                    |
+--------------+----------------------------------------------------------+
| CP-QUE       | Question subclause (spurnaraukasetning)                  |
|              | (Páll spurði *hvaða stjaka hún vildi*)                   |
+--------------+----------------------------------------------------------+
| CP-REL       | Relative clause (tilvísunarsetning)                      |
|              | (Páll, *sem kom inn*, klappaði kettinum)                 |
+--------------+----------------------------------------------------------+
| CP-ADV-TEMP  | Adverbial temporal phrase (tíðarsetning)                 |
|              | (Páll fór út *á meðan kötturinn mjálmaði*)               |
+--------------+----------------------------------------------------------+
| CP-ADV-PURP  | Adverbial purpose phrase (tilgangssetning)               |
|              | (Fuglinn flaug *til þess að ná sér í mat*)               |
+--------------+----------------------------------------------------------+
| CP-ADV-ACK   | Adverbial acknowledgement phrase (viðurkenningarsetning) |
|              | (Páll fór út, *þó að hann væri þreyttur*)                |
+--------------+----------------------------------------------------------+
| CP-ADV-CONS  | Adverbial consequence phrase (afleiðingarsetning)        |
|              | (Páll fór út, *þannig að hann er þreyttur*)              |
+--------------+----------------------------------------------------------+
| CP-ADV-CAUSE | Adverbial causal phrase (orsakarsetning)                 |
|              | (Páll fór út, *þar sem hann er þreyttur*)                |
+--------------+----------------------------------------------------------+
| CP-ADV-COND  | Adverbial conditional phrase (skilyrðissetning)          |
|              | (Páll færi út, *ef hann gæti*)                           |
+--------------+----------------------------------------------------------+
| CP-ADV-CMP   | Adverbial comparative phrase (samanburðarsetning)        |
+--------------+----------------------------------------------------------+
| CP-QUOTE     | Direct quote (bein tilvitnun)                            |
|              | („*Þetta er fínt*,“ sagði Páll)                          |
+--------------+----------------------------------------------------------+


Inflectional phrases
--------------------

*Beygingarliðir*

+------------+---------------------------------------------------+
| IP         | Inflectional phrase (beygingarliður)              |
+------------+---------------------------------------------------+
| IP-INF     | Infinitival inflectional phrase                   |
+------------+---------------------------------------------------+


Noun phrases
------------

*Nafnliðir*

+------------+---------------------------------------------------+
| NP         | Noun phrase                                       |
+------------+---------------------------------------------------+
| NP-SUBJ    | Noun phrase - subject (*Páll* sá sólina)          |
+------------+---------------------------------------------------+
| NP-OBJ     | Noun phrase - direct object (Páll sá *sólina*)    |
+------------+---------------------------------------------------+
| NP-IOBJ    | Noun phrase - indirect object                     |
|            | (Páll sýndi *barninu* bókina)                     |
+------------+---------------------------------------------------+
| NP-PRD     | Noun phrase - predicate (Páll er *formaður*)      |
+------------+---------------------------------------------------+
| NP-ADP     | Noun phrase - adjectival object (líkur *Páli*)    |
+------------+---------------------------------------------------+
| NP-POSS    | Noun phrase - possessive (köttur *Páls*)          |
+------------+---------------------------------------------------+
| NP-ADDR    | Noun phrase - address (*Fiskislóð 31*)            |
+------------+---------------------------------------------------+
| NP-TITLE   | Noun phrase - title (Páll Jónsson *ritari*)       |
+------------+---------------------------------------------------+
| NP-COMPANY | Noun phrase - company (*Samherji hf.*)            |
+------------+---------------------------------------------------+
| NP-MEASURE | Noun phrase - quantity                            |
+------------+---------------------------------------------------+
| NP-AGE     | Noun phrase - age                                 |
+------------+---------------------------------------------------+


Adjective phrases
-----------------

*Lýsingarliðir*

+------------+---------------------------------------------------+
| ADJP       | Adjective phrase (Páll er *góður og gegn* maður)  |
+------------+---------------------------------------------------+

Verb phrases
------------

*Sagnliðir*

+------------+---------------------------------------------------+
| VP         | Verb phrase                                       |
+------------+---------------------------------------------------+
| VP-AUX     | Auxiliary verb phrase (hjálparsögn)               |
|            | (Páll *hefur* klappað kettinum)                   |
+------------+---------------------------------------------------+

Prepositional phrases
---------------------

*Forsetningarliðir*

+------------+---------------------------------------------------+
| PP         | Prepositional phrase                              |
+------------+---------------------------------------------------+

Adverbial phrases
-----------------

*Atviksliðir*

+--------------------+-------------------------------------------+
| ADVP               | Adverbial phrase                          |
+--------------------+-------------------------------------------+
| ADVP-DIR           | Directional adverbial phrase              |
+--------------------+-------------------------------------------+
| ADVP-DATE-ABS      | Absolute date phrase                      |
+--------------------+-------------------------------------------+
| ADVP-DATE-REL      | Relative date phrase                      |
+--------------------+-------------------------------------------+
| ADVP-TIMESTAMP-ABS | Absolute timestamp                        |
+--------------------+-------------------------------------------+
| ADVP-TIMESTAMP-REL | Relative timestamp                        |
+--------------------+-------------------------------------------+
| ADVP-TMP-SET       | Temporal frequency phrase                 |
+--------------------+-------------------------------------------+
| ADVP-DUR-ABS       | Absolute duration                         |
+--------------------+-------------------------------------------+
| ADVP-DUR-REL       | Relative duration                         |
+--------------------+-------------------------------------------+
| ADVP-DUR-TIME      | Time period phrase                        |
+--------------------+-------------------------------------------+


Other phrases
-------------

*Aðrir liðir*

+--------+---------------------------------------------------+
| P      | Preposition                                       |
+--------+---------------------------------------------------+
| TO     | Infinitive particle                               |
+--------+---------------------------------------------------+
| C      | Conjunction                                       |
+--------+---------------------------------------------------+

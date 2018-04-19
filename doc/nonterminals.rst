.. _nonterminals:

Nonterminals
============

This section lists the nonterminals that can occur within simplified sentence trees,
i.e. instances of the :py:class:`SimpleTree` class. The nonterminal name of a tree
node can be read from the :py:attr:`SimpleTree.tag` property.

Sentences and paragraphs
------------------------

*Setningar, málsgreinar og efnisgreinar*

+------------+---------------------------------------------------+
| P          | Paragraph/head of tree                            |
+------------+---------------------------------------------------+
| S          | Sentence                                          |
+------------+---------------------------------------------------+
| S-MAIN     | Sentence-main                                     |
+------------+---------------------------------------------------+
| S-REF      | Sentence-referential (*sem Páll sá í dag*)        |
+------------+---------------------------------------------------+
| S-COND     | Sentence-condition (ef *Páll vildi*)              |
+------------+---------------------------------------------------+
| S-CONS     | Sentence-consequence (þá *færi hann heim*)        |
+------------+---------------------------------------------------+
| S-EXPLAIN  | Sentence-explanation                              |
|            | (Páll, *sem kom inn*, klappaði kettinum)          |
+------------+---------------------------------------------------+
| S-QUOTE    | Sentence-quote (*sagði Jón*)                      |
+------------+---------------------------------------------------+
| S-PREFIX   | Sentence-prefix (*Með öðrum orðum:* Páll sá kött) |
+------------+---------------------------------------------------+
| S-THT      | Sentence-complement (skýring)                     |
+------------+---------------------------------------------------+
| S-QUE      | Sentence-question (*hvaða*...)                    |
+------------+---------------------------------------------------+
| S-ADV      | Sentence-adverbial (atvikssetning)                |
+------------+---------------------------------------------------+
| S-ADV-TEMP | Sentence-adverbial-temporal                       |
|            | (Páll fór út *á meðan kötturinn mjálmaði*)        |
+------------+---------------------------------------------------+
| S-ADV-PURP | Sentence-adverbial-purpose                        |
|            | (Fuglinn flaug *til þess að ná sér í mat*)        |
+------------+---------------------------------------------------+
| S-ADV-ACK  | Sentence-adverbial-acknowledgement                |
|            | (Páll fór út, *þó að hann sé þreyttur*)           |
+------------+---------------------------------------------------+
| S-ADV-COND | Sentence-adverbial-condition                      |
|            | (Páll færi út, *ef hann gæti*)                    |
+------------+---------------------------------------------------+
| S-ADV-CONS | Sentence-adverbial-consequence                    |
|            | (Páll fór út, *þannig að hann er þreyttur*)       |
+------------+---------------------------------------------------+
| S-ADV-CAUSE| Sentence-adverbial-cause                          |
|            | (Páll fór út, *þar sem hann er þreyttur*)         |
+------------+---------------------------------------------------+

Inflected phrases
-----------------

*Beygingarliðir*

+------------+---------------------------------------------------+
| IP         | Inflected phrase (beygingarliður)                 |
+------------+---------------------------------------------------+

Noun phrases
------------

*Nafnliðir*

+------------+---------------------------------------------------+
| NP         | Noun phrase                                       |
+------------+---------------------------------------------------+
| NP-SUBJ    | Noun phrase-subject (*Páll* sá sólina)            |
+------------+---------------------------------------------------+
| NP-OBJ     | Noun phrase-direct object (Páll sá *sólina*)      |
+------------+---------------------------------------------------+
| NP-IOBJ    | Noun phrase-indirect object                       |
|            | (Páll sýndi *barninu* bókina)                     |
+------------+---------------------------------------------------+
| NP-PRD     | Noun phrase-predicate (Páll er *formaður*)        |
+------------+---------------------------------------------------+
| NP-POSS    | Noun phrase-possessive (köttur *Páls*)            |
+------------+---------------------------------------------------+
| NP-DAT     | Noun phrase-dative (Kona *tengd samtökunum* kom)  |
+------------+---------------------------------------------------+
| NP-ADDR    | Noun phrase-address (*Fiskislóð 31*)              |
+------------+---------------------------------------------------+
| NP-TITLE   | Noun phrase-title (Páll Jónsson *ritari*)         |
+------------+---------------------------------------------------+

Adjective phrases
-----------------

*Lýsingarliðir*

+------------+---------------------------------------------------+
| ADJP       | Adjective phrase (Páll er *góður*)                |
+------------+---------------------------------------------------+

Verb phrases
------------

*Sagnliðir*

+------------+---------------------------------------------------+
| VP         | Verb phrase                                       |
+------------+---------------------------------------------------+
| VP-SEQ     | Sequence of verb phrases                          |
|            | (Páll *gekk út og sótti skófluna*)                |
+------------+---------------------------------------------------+
| VP-PP      | Verb phrase-present participle                    |
|            | (lýsingarháttur nútíðar, Páll fór *gangandi*)     |
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

+------------+---------------------------------------------------+
| ADVP       | Adverbial phrase                                  |
+------------+---------------------------------------------------+
| ADVP-DATE  | Adverbial phrase-date/time                        |
+------------+---------------------------------------------------+



from proteus import config, Model
import csv
import locale
import string
import getopt
import sys
import unicodedata as ud
import sys

filename = '/tmp/script/enfants_cedille.csv'
delimiter = ','

col = [
    'Nom',
    u'Prénom',
    'Type',
    'Enfant']

f = open(filename,
         'rt', encoding='utf-8')

lines = csv.reader(f,
                   delimiter=delimiter)

config = config.set_trytond(database='cedille')

Party = Model.get('party.party')

cpt_line = 0
for l in lines:
    cpt_line += 1

    if cpt_line <= 1:
        continue
    else:
        pass
        # print cpt_line

    line = dict(zip(col, l))

    # print(line)

    if line['Nom'] and line[u'Prénom'] :
       

        party = Party(
        firstname=line[u'Prénom'],
        lastname=line['Nom'],
        party_type=line['Type'],
        is_child=True,
        )
        party.save()

f.close()

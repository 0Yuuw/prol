from proteus import config, Model
import csv
import locale
import string
import getopt
import sys
import unicodedata as ud
import sys

filename = '/tmp/script/contacts-sape_mdc.csv'
delimiter = ';'

col = [
    'Secteur',
    'Nom',
    'Réf',
    'Rue',
    'No',
    'NPA',
    'Lieu',
    'Tél',
    'Mail',
]

f = open(filename,
         'rt', encoding='utf-8')

lines = csv.reader(f,
                   delimiter=delimiter)

config = config.set_trytond(database='mdc')

Party = Model.get('party.party')
Contact_mech = Model.get('party.contact_mechanism')
Country = Model.get('country.country')
PartyType = Model.get('pl_cust_plbase.partytype')

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

    party = Party( 
        lastname=line['Nom'],
        notes='{}\n{}'.format(line['Secteur'],line['Réf']),
        party_type='o',
        is_person_moral=True,
        )
    party.save()

    party.addresses[0].addr_street = line[u'Rue']
    party.addresses[0].addr_street_num = line[u'No']
    party.addresses[0].postal_code = line[u'NPA']
    party.addresses[0].city = line[u'Lieu']

    

    party.save()

    for c in [
            (u'Tél', 'phone', u'Tél'),
            ('Mail', 'email', u'Mail'),
            ]:

        if line[c[0]]:
            try:
                cont = Contact_mech(party=party,
                                    type=c[1],
                                    name=line[u'Nom du contact'] or c[2],
                                    other_value=line[c[0]]
                                    )

                cont.save()
            except:
                cont = Contact_mech(party=party,
                                    type='other',
                                    name=c[2],
                                    other_value=line[c[0]]
                                    )

                cont.save()

f.close()

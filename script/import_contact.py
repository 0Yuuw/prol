from proteus import config, Model
import csv
import locale
import string
import getopt
import sys
import unicodedata as ud
import sys

filename = '/tmp/script/contacts-oe.csv'
delimiter = ';'

col = [
    'Nom',
    u'Prénom',
    u'Civilité',
    'Rue',
    u'Complément',
    'NPA',
    'Ville',
    'Pays',
    'Nom du contact',
    'Courriel',
    'Phone',
    'Mobile',
    'Type',]

civ_corresp = {'M.': 'mr',
               'Monsieur': 'mr',
               'Me': 'me',
               'Famille': '',
               'Prof': 'prof',
               'Prof.': 'prof',
               'Mme': 'mrs',
               'Madame': 'mrs',
               'Monsieur et Madame': 'mr&mrs',
               'Dr': 'dr',
               'Docteur': 'dr',
               '': ''
               }

# PARTY_TITLE = [
#     ('', ''),
#     ('mr', 'Mr'),
#     ('mr&mrs', 'Mr & Mrs'),
#     ('mrs', 'Mrs'),
#     ('me', 'Me'),
#     ('dr', 'Dr'),
#     #('prof', 'Prof'),
# ]


type_corresp = {'C': 'c',
                'F': 'f',
                'A': 'o'}

f = open(filename,
         'rt', encoding='utf-8')

lines = csv.reader(f,
                   delimiter=delimiter)

config = config.set_trytond(database='prolibre')

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

    if line['Nom'] and line[u'Prénom'] :
       

        party = Party(
        firstname=line[u'Prénom'],
        lastname=line['Nom'],
        party_type=type_corresp[line['Type']],
        party_title=[line[u'Civilité']] and civ_corresp[line[u'Civilité']] or '',
        is_person_moral=False,
        )
        party.save()
    else : 
       
        party = Party(
        
        lastname=line['Nom'],
        party_type=type_corresp[line['Type']],
        is_person_moral=True,
        )
        party.save()

    party.addresses[0].contact_name = line[u'Nom du contact']
    party.addresses[0].addr_street = line[u'Rue']
    party.addresses[0].addr_compl = line[u'Complément']
    party.addresses[0].postal_code = line[u'NPA']
    party.addresses[0].city = line[u'Ville']

    if line[u'Pays']:
        count = Country.find([('name', '=', line[u'Pays'])])

        if count:
            party.addresses[0].country = count[0]
        else:
            print(u'Pas trouvé le pays : {}'.format(line[u'Pays']))

    party.save()

    for c in [
            (u'Phone', 'phone', u'Tél'),
            ('Courriel', 'email', u'Mail'),
            ('Mobile', 'mobile', 'Natel')]:

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

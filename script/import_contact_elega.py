from proteus import config, Model
import csv
import locale
import string
import getopt
import sys
import unicodedata as ud
import sys
import re

filename = '/tmp/script/contact_elega.csv'
delimiter = ';'

col = [
    'CODE',
    'Devise',
    'Société',
    'Nom',
    'Prénom',
    'C/F',
    'Réf',
    'Complément',
    'Rue',
    'No',
    'Complément2',
    'NPA',
    'Lieu',
    'Pays',
    'E-Mail',
    'Nom Tél1',
    'Tél1',
    'Nom Tél2',
    'Tél2',
    'Nom Tél3',
    'Tél3',
    'Remarques',
   ]

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

config = config.set_trytond(database='elega')

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

    print(line)

    if False and line['Nom'] and line[u'Prénom'] :
        party = Party(
        firstname=line[u'Prénom'],
        lastname=line['Nom'],
        party_type=type_corresp[line['C/F']],
        party_title=[line[u'Civilité']] and civ_corresp[line[u'Civilité']] or '',
        is_person_moral=False,
        )
        party.save()
    else : 
        party = Party(
        lastname=line['Société'] and line['Société'].strip() or line['CODE'].strip(),
        description=line['CODE'].strip(),
        party_type=type_corresp[line['C/F']],
        is_person_moral=True,
        nickname=line['Réf'].strip(),
        notes=line['Remarques'].strip()
        )
        party.save()

    party.addresses[0].contact_name = line['Nom'].strip()
    party.addresses[0].contact_firstname = line['Prénom'].strip()
    
    party.addresses[0].addr_compl = line[u'Complément'].strip()
    party.addresses[0].addr_street = line[u'Rue'].strip()
    party.addresses[0].addr_street_num = line[u'No'].strip()

    party.addresses[0].addr_compl2 = line[u'Complément2'].strip()
    party.addresses[0].postal_code = line[u'NPA'].strip()
    party.addresses[0].city = line[u'Lieu'].strip()

    if line[u'Pays']:
        count = Country.find([('name', 'ilike', line[u'Pays'].strip())])

        if count:
            party.addresses[0].country = count[0]
        else:
            print(u'Pas trouvé le pays : {}'.format(line[u'Pays']))
    else : 
        count = Country.find([('code', '=', 'CH')])
        if count:
            party.addresses[0].country = count[0]
        else:
            print(u'Pas trouvé le pays : {}'.format('CH'))

    party.save()

    for c in [
            (u'Tél1', 'phone', u'Tél1'),
            (u'Tél2', 'phone', u'Tél2'),
            (u'Tél3', 'phone', u'Tél3')]:

        if line[c[0]].strip():
            try:
                cont = Contact_mech(party=party,
                                    type=c[1],
                                    name=line['Nom ' + c[0]] or c[2],
                                    other_value=re.sub(r'\D', '', line[c[0]])
                                    )

                cont.save()
            except:
                cont = Contact_mech(party=party,
                                    type='other',
                                    name=c[2],
                                    other_value=re.sub(r'\D', '', line[c[0]])
                                    )

                cont.save()

    for c in [(u'E-Mail', 'email', u'E-Mail'),]:

        if line[c[0]].strip():
            try:
                cont = Contact_mech(party=party,
                                    type=c[1],
                                    name=c[2],
                                    value=line[c[0]].strip()
                                    )

                cont.save()
            except:
                cont = Contact_mech(party=party,
                                    type='other',
                                    name=c[2],
                                    other_value=line[c[0]].strip()
                                    )

                cont.save()


f.close()

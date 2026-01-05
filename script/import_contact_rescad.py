from proteus import config, Model
import csv
import locale
import string
import getopt
import sys
import unicodedata as ud
import sys
import re

filename = '/tmp/script/rescad/accounts.csv'
delimiter = ','

filename2 = '/tmp/script/rescad/accounts_cstm.csv'
delimiter = ','

filename3 = '/tmp/script/rescad/notes.csv'
delimiter = ','

filename4 = '/tmp/script/rescad/tasks.csv'
delimiter = ','


col = [
    'id',
    'name',
    'date_entered',
    'date_modified',
    'modified_user_id',
    'created_by',
    'description',
    'deleted',
    'assigned_user_id',
    'account_type',
    'industry',
    'annual_revenue',
    'phone_fax',
    'billing_address_street',
    'billing_address_city',
    'billing_address_state',
    'billing_address_postalcode',
    'billing_address_country',
    'rating',
    'phone_office',
    'phone_alternate',
    'website',
    'ownership',
    'employees',
    'ticker_symbol',
    'shipping_address_street',
    'shipping_address_city',
    'shipping_address_state',
    'shipping_address_postalcode',
    'shipping_address_country',
    'parent_id',
    'sic_code',
    'campaign_id',
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

country_corresp = {

    'Switzerland' : 'CH',
    'United Kingdom' : 'GB',
    'USA' : 'US',
    'Lebanon' : 'LB',
    'Netherlands' : 'NL',
    'Fürstentum Liechtenstein' : 'LI',
    'Spain' : 'ES',
    'FL' : 'LI',
    'Marshall Islands' : 'MH',
    'Venezuela' : 'VE',
}

type_corresp = {'Customer': 'c',
                'Prospect': 'p',
                'Other': 'o'}

f = open(filename,
         'rt', encoding='utf-8')

lines = csv.reader(f,
                   delimiter=delimiter)

f2 = open(filename2,
         'rt', encoding='utf-8')

lines2 = csv.reader(f2,
                   delimiter=delimiter)

f3 = open(filename3,
         'rt', encoding='utf-8')

lines3 = csv.reader(f3,
                   delimiter=delimiter)

f4 = open(filename4,
         'rt', encoding='utf-8')

lines4 = csv.reader(f4,
                   delimiter=delimiter)

config = config.set_trytond(database='rescad')

Party = Model.get('party.party')
Logs = Model.get('pl_cust_rescad.logs')
Tasks = Model.get('pl_cust_rescad.tasks')

Contact_mech = Model.get('party.contact_mechanism')
Country = Model.get('country.country')
PartyType = Model.get('pl_cust_plbase.partytype')

cpt_line = 0
for l in [] : #lines:
    cpt_line += 1

    if cpt_line <= 1:
        continue
    else:
        pass
        # print cpt_line

    line = dict(zip(col, l))

    #print(line)
    
    party = Party(
        lastname=line['name'],
        code=line['id'].strip(),
        party_type=line['account_type'].strip() and type_corresp[line['account_type'].strip()] or 'o',
        #nickname=line['Réf'].strip(),
        notes=line['description'].strip(),
        description=line['industry'].strip())
    party.save()
    
    party.addresses[0].addr_street = line[u'billing_address_street'].strip().replace('\n', '')
    party.addresses[0].postal_code = line['billing_address_postalcode'].strip().replace('\n', '')
    party.addresses[0].city = line['billing_address_city'].strip().replace('\n', '')

    if line[u'billing_address_country']:
        count = Country.find([('name', 'ilike', line[u'billing_address_country'].strip().replace('\n', ''))])
        if not count :
            count = Country.find([('code', 'ilike', line[u'billing_address_country'].strip().replace('\n', ''))])
        
        if not count : 
            count = Country.find([('code', 'ilike', country_corresp[line[u'billing_address_country'].strip().replace('\n', '')])])

        if count:
            party.addresses[0].country = count[0]
        else:
            print(u'Pas trouvé le pays : {}'.format(line[u'billing_address_country']))
    else : 
        count = Country.find([('code', '=', 'CH')])
        if count:
            party.addresses[0].country = count[0]
        else:
            print(u'Pas trouvé le pays : {}'.format('CH'))

    party.save()
    
    #     'phone_fax',
    #         'phone_office',
    # 'phone_alternate',
    # 'website',
    
    for c in [
            (u'phone_fax', 'phone', u'Tél1'),
            (u'phone_office', 'phone', u'Tél2'),
            (u'phone_alternate', 'phone', u'Tél3')]:

        if line[c[0]].strip():
            try:
                cont = Contact_mech(party=party,
                                    type=c[1],
                                    name=c[2],
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

    # for c in [(u'E-Mail', 'email', u'E-Mail'),]:

    #     if line[c[0]].strip():
    #         try:
    #             cont = Contact_mech(party=party,
    #                                 type=c[1],
    #                                 name=c[2],
    #                                 value=line[c[0]].strip()
    #                                 )

    #             cont.save()
    #         except:
    #             cont = Contact_mech(party=party,
    #                                 type='other',
    #                                 name=c[2],
    #                                 other_value=line[c[0]].strip()
    #                                 )

    #             cont.save()


col2 = [
    "id_c",
    "acc_type_business_c",
    "investment_profile_c",
    "alternativeinvestments_c",
    "managementfees_c",
    "comments_c"
   ]

inv_corresp = {
    'Fixed Income' :'fix',
    'Revenue Oriented' :'rev',
    'Balanced' :'bal',
    'Growth' :'grow',
    'Capital Gain' :'cap',
}

cpt_line = 0
for l in [] : #lines2:
    cpt_line += 1

    if cpt_line <= 1:
        continue
    else:
        pass
        # print cpt_line

    line = dict(zip(col2, l))

    party = Party.find([("code", "=", line["id_c"])])

    if not party :
        print('Erreur avec le code {}'.format())
        continue
    else :
        party = party[0]
    
    party.investment_profile = inv_corresp[line["investment_profile_c"]]
    party.alternativeinvestments = line["alternativeinvestments_c"]
    party.managementfees = line["managementfees_c"]
    party.comments = line["comments_c"]

    party.save()



col3 = [
    "id",
    "date_entered",
    "date_modified",
    "modified_user_id",
    "created_by",
    "name",
    "filename",
    "file_mime_type",
    "parent_type",
    "parent_id",
    "contact_id",
    "portal_flag",
    "embed_flag",
    "description",
    "deleted"
   ]

cpt_line = 0
for l in [] : #lines3:
    cpt_line += 1

    if cpt_line <= 1:
        continue
    else:
        pass
        # print cpt_line

    line = dict(zip(col3, l))

    if line['parent_type'] != 'Accounts': 
        continue 

    party = Party.find([("code", "=", line["parent_id"])])
    if not party :
        print('Erreur avec le code {}'.format(line["parent_id"]))
        continue
    else :
        party = party[0]

    logs = Logs(
        date=line['date_entered'].split(' ')[0],
        subject=line['name'].strip(),
        party=party.id,
        description=line['description'].strip())
    logs.save()

col4 = [
    "id",
    "name",
    "date_entered",
    "date_modified",
    "modified_user_id",
    "created_by",
    "description",
    "deleted",
    "assigned_user_id",
    "status",
    "date_due_flag",
    "date_due",
    "date_start_flag",
    "date_start",
    "parent_type",
    "parent_id",
    "contact_id",
    "priority"
]

cpt_line = 0
for l in lines4:
    cpt_line += 1

    if cpt_line <= 1:
        continue
    else:
        pass
        # print cpt_line

    line = dict(zip(col4, l))
    print(line)
    print(line['parent_type'])

    if line['parent_type'] != 'Accounts': 
        continue 

    party = Party.find([("code", "=", line["parent_id"])])
    if not party :
        print('Erreur avec le code {}'.format(line["parent_id"]))
        continue
    else :
        party = party[0]

    tasks = Tasks(
        date=line['date_due'] and line['date_due'].split(' ')[0] or None,
        party=party.id,
        description=line['description'].strip())
    tasks.save()

f4.close()
f3.close()
f2.close()
f.close()

from proteus import config, Model
import csv
import locale
import string
import getopt
import sys
import unicodedata as ud
import sys
from decimal import Decimal
from datetime import datetime, timedelta

config = config.set_trytond(database='prolibre_prod')
delimiter = ';'

file_user = '/tmp/script/utilisateur.csv'
file_compte = '/tmp/script/compte.csv'
file_type_compte = '/tmp/script/type_de_compte.csv'
file_tax = '/tmp/script/taxe.csv'
file_product = '/tmp/script/produit.csv'
file_product_compte = '/tmp/script/produit_cat.csv'
file_journal = '/tmp/script/journal.csv'

f_user = open(file_user,
              'rt', encoding='utf-8')

f_type = open(file_type_compte,
              'rt', encoding='utf-8')

f = open(file_compte,
         'rt', encoding='utf-8')

f_tax = open(file_tax,
             'rt', encoding='utf-8')

f_prod = open(file_product,
              'rt', encoding='utf-8')

f_cat = open(file_product_compte,
             'rt', encoding='utf-8')

f_journal = open(file_journal,
                 'rt', encoding='utf-8')

lines_user = csv.reader(f_user,
                        delimiter=delimiter)

lines_type = csv.reader(f_type,
                        delimiter=delimiter)

lines = csv.reader(f,
                   delimiter=delimiter)

lines_tax = csv.reader(f_tax,
                       delimiter=delimiter)

lines_prod = csv.reader(f_prod,
                        delimiter=delimiter)

lines_prod_cat = csv.reader(f_cat,
                            delimiter=delimiter)

lines_journal = csv.reader(f_journal,
                           delimiter=delimiter)

USER = Model.get('res.user')
PARTY = Model.get('party.party')
EMPLOY = Model.get('company.employee')
ACCOUNT = Model.get('account.account')
ACCOUNT_TYPE = Model.get('account.account.type')
JOURNAL = Model.get('account.journal')
SEQ = Model.get('ir.sequence')
TAX = Model.get('account.tax')
PRODUCT = Model.get('product.template')
UOM = Model.get('product.uom')
CAT = Model.get('product.category')

col_journal = ['Nom',
               'Code',
               'Type',
               'Sequence',
               ]

cpt_line = 0
for l in lines_journal:
    cpt_line += 1

    if cpt_line <= 1:
        continue
    else:
        pass
        # print cpt_line

    line = dict(zip(col_journal, l))
    # print(line)
    if not JOURNAL.find([('name', '=', line['Nom'])]):
        seq, = SEQ.find([('name', '=', line['Sequence'])])

        j = JOURNAL(name=line[u'Nom'],
                    code=line[u'Code'],
                    type=line[u'Type'],
                    sequence=seq
                    )
        j.save()


col_user = ['Nom',
            'Login',
            'MDP',
            ]

cpt_line = 0
for l in lines_user:
    cpt_line += 1

    if cpt_line <= 1:
        continue
    else:
        pass
        # print cpt_line

    line = dict(zip(col_user, l))

    if not USER.find([('name', '=', line[u'Nom'])]):

        u = USER(name=line[u'Nom'],
                 login=line[u'Login'],
                 password=line[u'MDP'],
                 )

        u.save()

    else:
        print('Deja present -- {}'.format(line[u'Nom']))

col_type = ['Nom',
            'Client',
            'Stock',
            'Fournisseur',
            'Produit',
            'Charge',
            'Actif',
            'Relevé',
            ]

cpt_line = 0
for l in lines_type:
    cpt_line += 1

    if cpt_line <= 1:
        continue
    else:
        pass
        # print cpt_line

    line = dict(zip(col_type, l))
    if not ACCOUNT_TYPE.find([('name', '=', line[u'Nom'])]):
        tc = ACCOUNT_TYPE(name=line[u'Nom'],
                          company=1,
                          statement=line['Relevé'],
                          revenue=line['Produit'] == 'x' and True or False,
                          payable=line['Fournisseur'] == 'x' and True or False,
                          receivable=line['Client'] == 'x' and True or False,
                          assets=line['Actif'] == 'x' and True or False,
                          stock=line['Stock'] == 'x' and True or False,
                          expense=line['Charge'] == 'x' and True or False,
                          )
        tc.save()
    else:
        print('Deja present -- {}'.format(line[u'Nom']))

col = ['Nom',
       'Parent',
       'Code',
       'Type',
       'reconcile',
       'tiers',
       ]

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

    if line.get('Parent'):
        p = ACCOUNT.find([('name', '=', line['Parent'])])
    else:
        p = None

    if line.get('Type'):
        t = ACCOUNT_TYPE.find([('name', '=', line['Type'])])
    else:
        t = None

    if not ACCOUNT.find([('code', '=', line['Code'])]):
        ac = ACCOUNT(name=line[u'Nom'],
                     code=line['Code'],
                     company=1,
                     parent=p and p[0] or p,
                     type=t and t[0] or t,
                     reconcile=line['reconcile'] == 'x' and True or False,
                     party_required=line['tiers'] == 'x' and True or False,
                     )
        ac.save()
    else:
        print('Deja present -- {}'.format(line['Code']))

col_tax = ['Nom',
           'Description',
           'Type',
           'Taux',
           'Compte de facture',
           'Compte de note de crédit',
           ]

cpt_line = 0
for l in lines_tax:
    cpt_line += 1

    if cpt_line <= 1:
        continue
    else:
        pass
        # print cpt_line

    line = dict(zip(col_tax, l))
    print(line)
    if not TAX.find([('name', '=', line[u'Nom'])]):
        cf, = ACCOUNT.find([('code', '=', line['Compte de facture'])])
        cnc, = ACCOUNT.find([('code', '=', line['Compte de note de crédit'])])

        print('*************')
        print(cf)
        print(cnc)
        print('*************')
        t = TAX(name=line[u'Nom'],
                description=line[u'Description'],
                type=line[u'Type'],
                rate=Decimal(line[u'Taux']),
                invoice_account=cf or None,
                credit_note_account=cnc or None,
                )

        t.save()

    else:
        print('Deja present -- {}'.format(line[u'Nom']))

col_cat = ['Nom',
           'Compte de produits',
           'Compte de charge',
           'TVA',
           ]

cpt_line = 0
for l in lines_prod_cat:
    cpt_line += 1

    if cpt_line <= 1:
        continue
    else:
        pass
        # print cpt_line

    line = dict(zip(col_cat, l))
    print(line)
    if not CAT.find([('name', '=', line[u'Nom'])]):
        tva = False
        if line[u'TVA']:
            tva, = TAX.find([('name', '=', line[u'TVA'])])

        if line['Compte de produits']:
            acc, = ACCOUNT.find([('code', '=', line['Compte de produits'])])

            c = CAT(name=line[u'Nom'],
                    accounting=True,
                    account_revenue=acc,
                    )
        else:
            acc, = ACCOUNT.find([('code', '=', line['Compte de charge'])])

            c = CAT(name=line[u'Nom'],
                    accounting=True,
                    account_expense=acc,
                    )

        c.save()

        if tva:
            c.customer_taxes.append(tva)
            c.save()

    else:
        print('Deja present -- {}'.format(line[u'Nom']))


print('////////////////////////////')
col_prod = ['A',
            'Code',
            'Nom',
            'Type',
            'UDM',
            'Prix',
            'Categorie',
            ]
cpt_line = 0
for l in lines_prod:
    cpt_line += 1

    if cpt_line <= 1:
        continue
    else:
        pass
        print(cpt_line)

    line = dict(zip(col_prod, l))
    print(line)
    if not PRODUCT.find([('name', '=', line[u'Nom'])]):
        udm, = UOM.find(['name', '=', line[u'UDM']])
        cat, = CAT.find([('name', '=', line[u'Categorie'])])
        p = PRODUCT(name=line[u'Nom'],
                    code=line[u'Code'],
                    #type=line[u'Type'],
                    list_price=Decimal(line[u'Prix']),
                    default_uom=udm,
                    account_category=cat
                    )

        p.save()
    else:
        print('Deja present -- {}'.format(line[u'Nom']))


f.close()
f_type.close()
f_prod.close()
f_cat.close()
f_tax.close()
f_user.close()
f_journal.close()

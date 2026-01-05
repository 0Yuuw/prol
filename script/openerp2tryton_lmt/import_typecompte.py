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

config = config.set_trytond(database='elega')
delimiter = ';'

file_type_compte = '/tmp/script/openerp2tryton/type_de_compte.csv'


f_type = open(file_type_compte,
              'rt', encoding='utf-8')


lines_type = csv.reader(f_type,
                        delimiter=delimiter)

ACCOUNT_TYPE = Model.get('account.account.type')

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


f_type.close()
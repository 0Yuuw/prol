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


file_compte = '/tmp/script/elega-plancomptable-250523-final.csv'

f = open(file_compte,
         'rt', encoding='utf-8')

lines = csv.reader(f,
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


f.close()

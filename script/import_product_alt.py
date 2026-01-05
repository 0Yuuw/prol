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

config = config.set_trytond(database='alternative')
delimiter = '|'

file_product = '/tmp/script/Alt-listeproduits-240705.csv'


f_prod = open(file_product,
              'rt', encoding='utf-8')

lines_prod = csv.reader(f_prod,
                        delimiter=delimiter)

PRODUCT = Model.get('product.template')
VAR = Model.get('product.product')

UOM = Model.get('product.uom')

col_prod = ['OE',
            'Référence',
            'Produit',
            'Description',
            'Commentaire',
            'UdM',
            'Prix public'
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
    if not PRODUCT.find([('code', '=', line[u'Référence'])]):
        udm, = UOM.find(['name', '=', 'Heure'])
        p = PRODUCT(name=line[u'Description'],
                    code=line[u'Référence'],
                    #type=line[u'Type'],
                    list_price=Decimal(line[u'Prix public']),
                    #description=line[u'Commentaire'],
                    default_uom=udm,
                    account_category=11,
                    )

        p.save()

        v, = VAR.find([('code', '=', line[u'Référence'])])
        v.description = line[u'Commentaire']
        v.save()

    else:
        print('Deja present -- {}'.format(line[u'Référence']))



f_prod.close()

from proteus import config, Model, Wizard
import csv
import locale
import string
import getopt
import sys
import unicodedata as ud
import sys
from decimal import Decimal
from datetime import datetime, timedelta
import time

config = config.set_trytond(database='revuelta')
delimiter = ';'

file_inv = '/tmp/script/ConventionCollective-journal-2023.csv'

f_inv = open(file_inv,
             'rt', encoding='utf-8')

lines_inv = csv.reader(f_inv,
                       delimiter=delimiter)
PARTYS = Model.get('party.party')
ACCOUNT = Model.get('account.account')
MOVE = Model.get('account.move')
JOURNAL = Model.get('account.journal')
PERIOD = Model.get('account.period')

col_inv = [
    'No',
    'Date',
    'Débit',
    'Crédit',
    'Libellé',
    'Montant',
]


cpt_line = 0
for l in lines_inv:
    cpt_line += 1

    if cpt_line <= 1:
        continue
    else:
        pass
        # print cpt_line

    line = dict(zip(col_inv, l))

    
    print(line)

    acc_cred, = ACCOUNT.find([('code', '=', line['Crédit'])])
    acc_deb, = ACCOUNT.find([('code', '=', line['Débit'])])
    journal_cash, = JOURNAL.find([('code', '=', 'OD'),])
   
    move = MOVE()
    move.description = '{}'.format(line['Libellé'])
    move.period, = PERIOD.find([('start_date','<=', datetime.strptime(
                          line['Date'], "%d.%m.%Y")), ('end_date','>=', datetime.strptime(
                          line['Date'], "%d.%m.%Y"))])
    move.journal = journal_cash
    move.date = datetime.strptime(
                          line['Date'], "%d.%m.%Y")
    mline = move.lines.new()
    mline.description = '{}'.format(line['Libellé'])
    mline.account = acc_cred
    mline.credit = Decimal(line['Montant'])
    mline.party = PARTYS(1)
    mline = move.lines.new()
    mline.description = '{}'.format(line['Libellé'])
    mline.account = acc_deb
    mline.debit = Decimal(line['Montant'])
    move.save()
    move.click('post')
    print(move.id)
    print('OK')
 
f_inv.close()

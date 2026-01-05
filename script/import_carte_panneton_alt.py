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

config = config.set_trytond(database="alternative")
delimiter = "|"

file_product = "/tmp/script/Partenaires-240830.csv"


f_prod = open(file_product, "rt", encoding="utf-8")

lines_prod = csv.reader(f_prod, delimiter=delimiter)

ADDRESS = Model.get("party.address")

col_prod = [
    "Partenaire",
    "Prénom",
    "Nom",
    "C-Voeux",
    "Panettone",
    "Fonction",
    "Compl. adr.",
    "Rue",
    "Numéro",
    "Compl. adr. (suite)",
    "Code postal",
    "Ville",
    "Pays",
    "ID",
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
    if line["ID"] and ADDRESS.find([("id", "=", int(line["ID"].replace('\u202f','')))]):
        addr, = ADDRESS.find([("id", "=", int(line["ID"].replace('\u202f','')))])
        
        addr.carte = line["C-Voeux"] == '1'
        addr.panettone = line["Panettone"] == '1'
        addr.save()

    else:
        print(line)

f_prod.close()

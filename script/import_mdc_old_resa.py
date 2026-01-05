from proteus import config, Model
import csv
import locale
import string
import getopt
import sys
import unicodedata as ud
import sys

filename = "/tmp/script/resa_pros_Tryton2024.csv"
delimiter = ";"

col = [
    "Jour",
    "Nom de l'institution",
    "Provenance",
    "Type d'institution",
    "Personne de contact",
    "E-mail",
    "Téléphone",
    "Enfants",
    "Adultes",
    "Âge",
    "Activité",
    "Période",
    "Sieste",
    "Pique Nique",
    "Commentaire",
]

f = open(filename, "rt", encoding="utf-8")

lines = csv.reader(f, delimiter=delimiter)

config = config.set_trytond(database="mdc")

BOOKS = Model.get("pl_cust_mdc.booking_inst")
DAYS = Model.get("pl_cust_mdc.day_inst")

corresp_age = {
    '' : '0-2',
    '0 à 2' : '0-2',
    '0 à 4' : '3-4',
    '3 à 4' : '3-4',
    '4 à 6' : '5-6',
    '5 à 6' : '5-6',
    '7 à 8' : '7-8',
}
corresp_inst_type = {
    'IPE Canton' :"ipe", 
    'IPE canton' :"ipe",     
    'IPE VDG' :"ipe", 
    'Autre' : "priv", 
    "DIP Ecoles publiques" : "dip", 
    "Association" : "priv", 
    "Crèche privée" : "priv", 
    "Ecole privée" : "priv", 
    "Ecoles et foyers spécialisées" : "dip", 
    "Jardin d'enfants" : "ipe", 
}   
corresp_mad = {
    "matin" : "m",
    "après-midi" : "a",
    "journée" : "d",
    "Journée" : "d",
}

INST_TYPE = [
        ("IPE Ville de Genève/Canton de Genève", "IPE Ville de Genève/Canton de Genève"),
        ("Collectivité publique hors Ville de Genève", "Collectivité publique hors Ville de Genève"),
        ("E&C (Ecole & Culture) – DIP", "E&C (Ecole & Culture) – DIP"),
        ("Collectivité publique / Association / Fondation", "Collectivité publique / Association / Fondation"),
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

    day = DAYS.find([("name", "=", '{} 2024'.format(line["Jour"].replace('01','1').replace('02','2').replace('03','3').replace('04','4').replace('05','5').replace('06','6').replace('07','7').replace('08','8').replace('09','9')))])
    #print(day)

    if day: 
        if 1 :
            book = BOOKS(
                booking_date='2024-01-01',
                inst_name = line["Nom de l'institution"],
                inst_prov = line["Provenance"],
                inst_type = corresp_inst_type[line["Type d'institution"]],    
                inst_rep = line["Personne de contact"],   
                inst_email = line["E-mail"],
                inst_tel = line["Téléphone"],
                nb_child = line["Enfants"] and int(line["Enfants"]) or 0,
                child_year = corresp_age[line["Âge"]],
                nb_adult = line["Adultes"] and int(line["Adultes"]) or 0,
                inst_activity = line["Activité"],
                inst_comment = line["Commentaire"],
                mad = corresp_mad[line["Période"].strip()],
                sieste = line["Sieste"] == 'x',
                piqueNique = line["Pique Nique"] == 'x',
                state = 'valid',
                day = day[0]
            )
            book.save()
        else : 
            print(line)
        
    else :
        print('{} 2024'.format(line["Jour"]))


f.close()

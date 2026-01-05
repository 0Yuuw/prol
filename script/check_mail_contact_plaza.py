from proteus import config, Model
import csv
import locale
import string
import getopt
import sys
import unicodedata as ud

import re
import dns.resolver
import time 

config = config.set_trytond(database='plaza')

# Vérifie le format de l'adresse email
def is_valid_syntax(email):
    regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return re.match(regex, email) is not None

# Vérifie si le domaine a un serveur mail (enregistrements MX)
def check_dns_mx(email):
    try:
        domain = email.split('@')[1]
        records = dns.resolver.resolve(domain, 'MX')
        mx_records = [str(r.exchange).rstrip('.') for r in records]
        return True
    except Exception:
        return False

Party = Model.get('party.party')
Contact_mech = Model.get('party.contact_mechanism')

all_part = Party.find([('check_import', '=', True)])
to_remove = []

tot = (len(all_part))


for p in all_part:

    valid_mail = False 
    for cm in p.contact_mechanisms:
        if is_valid_syntax(cm.value):
            valid_mail = True
            #print(cm.value)
            break

        if not is_valid_syntax(cm.value) and '@' in cm.value :
            print('{} erreur de syntaxe :{}'.format(tot,cm.value))

    if not valid_mail : 
        to_remove.append(p.id)
    tot -= 1
    
print(len(to_remove))
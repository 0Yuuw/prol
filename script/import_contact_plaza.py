from proteus import config, Model
import csv
import locale
import string
import getopt
import sys
import unicodedata as ud
import sys

filename = '/tmp/script/plaza.csv'
delimiter = ';'

col = [
    'CK_Membre',
    'C_Genre1',
    'C_Parrainage',
    'Membre_AHAED',
    'Membre_CILECT',
    'Donateur_sponsor',
    'C_Partenaire',
    'C_VIP',
    'C_Politesse',
    'C_Politesse2',
    'C_Prenom1',
    'C_Nom1',
    'C_Societe',
    'C_Langue_Envoi',
    'C_Langue',
    'C_Notes',
    'C_Tel_Mobile',
    'C_Skype',
    'C_Tel_Prive',
    'C_Tel_pro',
    'C_Email_Prive',
    'C_Retour_Mail_Prive',
    'C_Email_pro',
    'C_Retour_Mail_Pro',
    'C_Retour_Adresse_Prive',
    'C_CO_Prive',
    'C_RueNum_Prive',
    'C_CP_Prive',
    'C_CodePostal_Prive',
    'C_Ville_Prive',
    'C_Canton_Prive',
    'C_Pays_Prive',
    'C_Retour_Adresse_Pro',
    'CRM_Depart_pro',
    'C_CO_Pro',
    'C_RueNum_Pro',
    'C_CP_Pro',
    'C_CodePostal_Pro',
    'C_Ville_Pro',
    'C_Canton_Pro',
    'C_Pays_Pro',
    'Compte_Type',
    'Compte_Type_de',
    'Compte_Sou_Type_de',
    'MédiaFréquence',
    'MédiaRayonnement',
    'MédiaSecteur',
    'C_Alumni',
    'C_Annee_Diplome',
    'C_Intervenants',
    'C_IntérêtTous',
    'C_Archi_Interieur',
    'C_Comm_Visuelle',
    'C_Design_Mode',
    'C_Design_Bijou',
    'C_Arts_Visuels',
    'C_Cinema',
    'C_Media_Design',
    'C_IRAD',
    'C_Design_Horloger',
    'C_Espaces_com',
    'C_Bande_Dessinée',
    'C_VIP_Defile',
    'C_GUEST_Defile',
    'C_USBCinéma',
    'C_Diplomes',
    'FonctionLiéeAdressePro',
    'Créateur',
    'Enseignant',
    'Élu_mandat',
    'Journaliste',
    'Autre',
    'Autre2'
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


type_corresp = {'C': 'c',
                'F': 'f',
                'A': 'o'}

f = open(filename,
         'rt', encoding='utf-8')

lines = csv.reader(f,
                   delimiter=delimiter)

config = config.set_trytond(database='plaza')

Party = Model.get('party.party')
Address = Model.get('party.address')
Contact_mech = Model.get('party.contact_mechanism')
Country = Model.get('country.country')
Subdivision = Model.get('country.subdivision')
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

    print(cpt_line)

    if line['C_Genre1'].lower() == 'contact' and line['C_Nom1']:
        party = Party(
            firstname=line[u'C_Prenom1'].strip().replace('\n', ' '),
            lastname=line['C_Nom1'].strip().replace('\n', ' '),
            organisation=line['C_Societe'].strip().replace('\n', ' '),
            party_type='-',
            party_title=[line[u'C_Politesse2']
                         ] and civ_corresp[line[u'C_Politesse2']] or '',
            is_person_moral=False,
        )
        party.save()
    elif line['C_Societe']:
        party = Party(
            lastname=line['C_Societe'].strip().replace('\n', ' '),
            party_type='-',
            is_person_moral=True,
        )
        party.save()
    else:
        print('La je sais pas quoi faire avec lui : {}'.format(
            line['CK_Membre']))

    party.vip = line[u'C_VIP'] == 'oui'
    party.part = line[u'C_Partenaire'] == 'oui'
    party.lang = line[u'C_Langue'] == 'Anglais' and 1 or 11
    party.save()

    if line[u'C_CodePostal_Prive'] and not line[u'C_CodePostal_Pro']:
        party.addresses[0].addr_street = line[u'C_RueNum_Prive'].strip().replace(
            '\n', ' ').replace('\x0b', ' ')
        party.addresses[0].addr_compl = line[u'C_CO_Prive'].strip().replace(
            '\n', ' ').replace('\x0b', ' ')
        party.addresses[0].addr_compl2 = line[u'C_CP_Prive'].strip().replace(
            '\n', ' ').replace('\x0b', ' ')
        party.addresses[0].postal_code = line[u'C_CodePostal_Prive'].strip().replace(
            '\n', ' ').replace('\x0b', ' ')
        party.addresses[0].city = line[u'C_Ville_Prive'].strip().replace(
            '\n', ' ').replace('\x0b', ' ')
        party.save()

        if line[u'C_Pays_Prive']:
            count = Country.find([('name', '=', line[u'C_Pays_Prive'])])

            if count:
                party.addresses[0].country = count[0]
            else:
                party.addresses[0].type = party.addresses[0].type and ' {}'.format(
                    line[u'C_Pays_Prive']) or '{}'.format(line[u'C_Pays_Prive'])
                print(u'Pas trouvé le pays : {}'.format(line[u'C_Pays_Prive']))
        party.save()
        try:
            if line[u'C_Canton_Prive'] and count:
                cant = Subdivision.find(
                    [('country', '=', count[0]), ('name', '=', line[u'C_Canton_Prive'])])

                if not cant:
                    cant = Subdivision.find(
                        [('country', '=', count[0]), ('name', '=', line[u'C_Canton_Prive'].replace(' ', '-'))])

                if cant:
                    party.addresses[0].subdivision = cant[0]
                else:
                    cant = Subdivision.find(
                        [('country', '=', count[0]), ('code', '=', 'CH-{}'.format(line[u'C_Canton_Prive']))])
                    if cant:
                        party.addresses[0].subdivision = cant[0]
                    else:
                        party.addresses[0].type = party.addresses[0].type and ' {}'.format(
                            line[u'C_Canton_Prive']) or '{}'.format(line[u'C_Canton_Prive'])
                        print(u'Pas trouvé le canton : {}'.format(
                            line[u'C_Canton_Prive']))

            party.save()
        except:
            party.addresses[0].subdivision = None
            party.addresses[0].type = party.addresses[0].type and ' {}'.format(
                line[u'C_Canton_Prive']) or '{}'.format(line[u'C_Canton_Prive'])
            party.save()

    elif not line[u'C_CodePostal_Prive'] and line[u'C_CodePostal_Pro']:
        party.addresses[0].addr_street = line[u'C_RueNum_Pro'].strip().replace(
            '\n', ' ').replace('\x0b', ' ')
        party.addresses[0].addr_compl = line[u'C_CO_Pro'].strip().replace(
            '\n', ' ').replace('\x0b', ' ')
        party.addresses[0].addr_compl2 = line[u'C_CP_Pro'].strip().replace(
            '\n', ' ').replace('\x0b', ' ')
        party.addresses[0].postal_code = line[u'C_CodePostal_Pro'].strip().replace(
            '\n', ' ').replace('\x0b', ' ')
        party.addresses[0].city = line[u'C_Ville_Pro'].strip().replace(
            '\n', ' ').replace('\x0b', ' ')
        party.addresses[0].pro = True
        party.save()

        if line[u'C_Pays_Pro']:
            count = Country.find([('name', '=', line[u'C_Pays_Pro'])])

            if count:
                party.addresses[0].country = count[0]
            else:
                party.addresses[0].type = party.addresses[0].type and ' {}'.format(
                    line[u'C_Pays_Pro']) or '{}'.format(line[u'C_Pays_Pro'])
                print(u'Pas trouvé le pays : {}'.format(line[u'C_Pays_Pro']))
        party.save()
        try:
            if line[u'C_Canton_Pro'] and count:
                cant = Subdivision.find(
                    [('country', '=', count[0]), ('name', '=', line[u'C_Canton_Pro'])])

                if not cant:
                    cant = Subdivision.find(
                        [('country', '=', count[0]), ('name', '=', line[u'C_Canton_Pro'].replace(' ', '-'))])

                if cant:
                    party.addresses[0].subdivision = cant[0]
                else:
                    cant = Subdivision.find(
                        [('country', '=', count[0]), ('code', '=', 'CH-{}'.format(line[u'C_Canton_Pro']))])
                    if cant:
                        party.addresses[0].subdivision = cant[0]
                    else:
                        party.addresses[0].type = party.addresses[0].type and ' {}'.format(
                            line[u'C_Canton_Pro']) or '{}'.format(line[u'C_Canton_Pro'])
                        print(u'Pas trouvé le canton : {}'.format(
                            line[u'C_Canton_Pro']))

            party.save()
        except:
            party.addresses[0].subdivision = None
            party.addresses[0].type = party.addresses[0].type and ' {}'.format(
                line[u'C_Canton_Pro']) or '{}'.format(line[u'C_Canton_Pro'])
            party.save()

    elif line[u'C_CodePostal_Prive'] and line[u'C_CodePostal_Pro']:

        #print('Deux adresse {}!!!'.format(party.name))
        new_addr = Address(party=party)
        new_addr.save()

        party.addresses[0].addr_street = line[u'C_RueNum_Prive'].strip().replace(
            '\n', ' ').replace('\x0b', ' ')
        party.addresses[0].addr_compl = line[u'C_CO_Prive'].strip().replace(
            '\n', ' ').replace('\x0b', ' ')
        party.addresses[0].addr_compl2 = line[u'C_CP_Prive'].strip().replace(
            '\n', ' ').replace('\x0b', ' ')
        party.addresses[0].postal_code = line[u'C_CodePostal_Prive'].strip().replace(
            '\n', ' ').replace('\x0b', ' ')
        party.addresses[0].city = line[u'C_Ville_Prive'].strip().replace(
            '\n', ' ').replace('\x0b', ' ')
        party.save()

        if line[u'C_Pays_Prive']:
            count = Country.find([('name', '=', line[u'C_Pays_Prive'])])

            if count:
                party.addresses[0].country = count[0]
            else:
                party.addresses[0].type = party.addresses[0].type and ' {}'.format(
                    line[u'C_Pays_Prive']) or '{}'.format(line[u'C_Pays_Prive'])
                print(u'Pas trouvé le pays : {}'.format(line[u'C_Pays_Prive']))
        party.save()
        try:
            if line[u'C_Canton_Prive'] and count:
                cant = Subdivision.find(
                    [('country', '=', count[0]), ('name', '=', line[u'C_Canton_Prive'])])

                if not cant:
                    cant = Subdivision.find(
                        [('country', '=', count[0]), ('name', '=', line[u'C_Canton_Prive'].replace(' ', '-'))])

                if cant:
                    party.addresses[0].subdivision = cant[0]
                else:
                    cant = Subdivision.find(
                        [('country', '=', count[0]), ('code', '=', 'CH-{}'.format(line[u'C_Canton_Prive']))])
                    if cant:
                        party.addresses[0].subdivision = cant[0]
                    else:
                        party.addresses[0].type = party.addresses[0].type and ' {}'.format(
                            line[u'C_Canton_Prive']) or '{}'.format(line[u'C_Canton_Prive'])
                        print(u'Pas trouvé le canton : {}'.format(
                            line[u'C_Canton_Prive']))

            party.save()
        except:
            party.addresses[0].subdivision = None
            party.addresses[0].type = party.addresses[0].type and ' {}'.format(
                line[u'C_Canton_Prive']) or '{}'.format(line[u'C_Canton_Prive'])
            party.save()

        party.addresses[1].addr_street = line[u'C_RueNum_Pro'].strip().replace(
            '\n', ' ').replace('\x0b', ' ')
        party.addresses[1].addr_compl = line[u'C_CO_Pro'].strip().replace(
            '\n', ' ').replace('\x0b', ' ')
        party.addresses[1].addr_compl2 = line[u'C_CP_Pro'].strip().replace(
            '\n', ' ').replace('\x0b', ' ')
        party.addresses[1].postal_code = line[u'C_CodePostal_Pro'].strip().replace(
            '\n', ' ').replace('\x0b', ' ')
        party.addresses[1].city = line[u'C_Ville_Pro'].strip().replace(
            '\n', ' ').replace('\x0b', ' ')
        party.addresses[1].pro = True
        party.save()

        if line[u'C_Pays_Pro']:
            count = Country.find([('name', '=', line[u'C_Pays_Pro'])])

            if count:
                party.addresses[1].country = count[0]
            else:
                party.addresses[1].type = party.addresses[1].type and ' {}'.format(
                    line[u'C_Pays_Pro']) or '{}'.format(line[u'C_Pays_Pro'])
                print(u'Pas trouvé le pays : {}'.format(line[u'C_Pays_Pro']))
        party.save()
        try:
            if line[u'C_Canton_Pro'] and count:
                cant = Subdivision.find(
                    [('country', '=', count[0]), ('name', '=', line[u'C_Canton_Pro'])])

                if not cant:
                    cant = Subdivision.find(
                        [('country', '=', count[0]), ('name', '=', line[u'C_Canton_Pro'].replace(' ', '-'))])

                if cant:
                    party.addresses[1].subdivision = cant[0]
                else:
                    cant = Subdivision.find(
                        [('country', '=', count[0]), ('code', '=', 'CH-{}'.format(line[u'C_Canton_Pro']))])
                    if cant:
                        party.addresses[1].subdivision = cant[0]
                    else:
                        party.addresses[1].type = party.addresses[0].type and ' {}'.format(
                            line[u'C_Canton_Pro']) or '{}'.format(line[u'C_Canton_Pro'])
                        print(u'Pas trouvé le canton : {}'.format(
                            line[u'C_Canton_Pro']))
        except:
            party.addresses[0].subdivision = None
            party.addresses[0].type = party.addresses[0].type and ' {}'.format(
                line[u'C_Canton_Pro']) or '{}'.format(line[u'C_Canton_Pro'])
            party.save()

        party.save()

    for c in [
        ('C_Tel_Mobile', 'mobile', 'Tél Mobile'),
        ('C_Skype', 'skype', 'Skype'),
        ('C_Tel_Prive', 'phone', 'Tél privé'),
        ('C_Tel_pro', 'phone', 'Tél pro'),
        ('C_Email_Prive', 'email', 'E-Mail privé'),
        ('C_Email_pro', 'email', 'E-Mail'),
        ]:

        if line[c[0]]:
            try:
                cont = Contact_mech(party=party,
                                    type=c[1],
                                    name=c[2],
                                    other_value=line[c[0]].replace('\n', ' ').replace('\x0b', ' ')
                                    )

                cont.save()
            except:
                cont = Contact_mech(party=party,
                                    type='other',
                                    name=c[2],
                                    other_value=line[c[0]].replace('\n', ' ').replace('\x0b', ' ')
                                    )

                cont.save()


            
    notes = ''
    t_tmp = ' / '.join(chaine for chaine in [
        line['Compte_Type'],
        line['Compte_Type_de'],
        line['Compte_Sou_Type_de']] if chaine) or ''
    notes += t_tmp and 'Type : {}\n'.format(t_tmp) or ''
    f_tmp = ' / '.join(chaine for chaine in [
        line['FonctionLiéeAdressePro'],
        line['Créateur'],
        line['Enseignant'],
        line['Élu_mandat'],
        line['Journaliste'],
        line['Autre'],
        line['Autre2']] if chaine)
    notes += f_tmp and 'Fonction : {}\n'.format(f_tmp) or ''
   
    d_tmp = ' / '.join(val for chaine,val in [
        (line['C_Intervenants'],'Intervenants'),
        (line['C_IntérêtTous'],'IntérêtTous'),
        (line['C_Archi_Interieur'],'Archi_Interieur'),
        (line['C_Comm_Visuelle'],'Comm_Visuelle'),
        (line['C_Design_Mode'],'Design_Mode'),
        (line['C_Design_Bijou'],'Design_Bijou'),
        (line['C_Arts_Visuels'],'Arts_Visuels'),
        (line['C_Cinema'],'Cinema'),
        (line['C_Media_Design'],'Media_Design'),
        (line['C_IRAD'],'IRAD'),
        (line['C_Design_Horloger'],'Design_Horloger'),
        (line['C_Espaces_com'],'Espaces_com'),
        (line['C_Bande_Dessinée'],'Bande_Dessinée'),
        (line['C_VIP_Defile'],'VIP_Defile'),
        (line['C_GUEST_Defile'],'GUEST_Defile'),
        (line['C_USBCinéma'],'USBCinéma'),
        (line['C_Diplomes'],'Diplomes'),
        ] if chaine == 'oui')

    notes += d_tmp and '\nDisciplines : {}\n\n'.format(d_tmp) or ''

    a_tmp = '/'.join(chaine for chaine in [
        line['C_Alumni'],
        line['C_Annee_Diplome']] if chaine) or ''
    notes += a_tmp and 'Alumni : {}\n'.format(a_tmp) or ''
        
    notes += line['CK_Membre'] and 'Numéro : {}\n'.format(line['CK_Membre']) or ''
    notes += line['C_Parrainage'] and 'Parrainage : {}\n'.format(line['C_Parrainage']) or ''
    notes += line['Membre_AHAED'] and '{}\n'.format(line['Membre_AHAED']) or ''
    notes += line['Membre_CILECT']=='oui' and 'Membre_CILECT\n' or ''
    notes += line['Donateur_sponsor']=='oui' and 'Donateur-Sponsor\n' or ''
    notes += line['C_Notes'] and 'Notes : {}\n'.format(line['C_Notes']) or ''
    notes += line['CRM_Depart_pro'] and 'CRM origine : {}\n'.format(line['CRM_Depart_pro']) or ''

    party.notes = notes 
    party.save()

f.close()

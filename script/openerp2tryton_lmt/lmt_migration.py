#!/usr/bin/env python
import json
import datetime
import csv
import sys
import os
import base64
import re

from argparse import ArgumentParser
from collections import defaultdict
from decimal import Decimal
from itertools import chain

import psycopg2
import psycopg2.extras
from psycopg2 import sql

import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberFormat

from stdnum import get_cc_module, ean

from sql import Table, Null
from sql.aggregate import Sum
from sql.conditionals import Coalesce

from proteus import config, Model, Wizard
from proteus.pyson import PYSONDecoder

correspstate = {
    'production' : 'open',
    'refused' : 'denied',
    'draft' : 'devis',
    'closed' :'close',
}


def main(oe_database, tryton_database, to_do):
    config.set_trytond(tryton_database)

    conn = psycopg2.connect(host='postgres', dbname=oe_database, user='tryton', password='xoequee7ooYaing')
    cur = conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)
    conn2 = psycopg2.connect(host='postgres', dbname=tryton_database, user='tryton', password='xoequee7ooYaing')
    cur2 = conn2.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)
    print("On commence....", file=sys.stderr)
    print(to_do, file=sys.stderr)

    #if True : 
    #    return None 

    if to_do[0] == 'cat':
        print("Migrate Categories", file=sys.stderr)
        migrate_cat(cur)
 
    if to_do[0] == 'party':
        print("Migrate party", file=sys.stderr)
        migrate_party(cur)

    if to_do[0] == 'appels':
        print("Migrate Appels", file=sys.stderr)
        migrate_appels(cur)

    if to_do[0] == 'dons':
        print("Migrate Dons", file=sys.stderr)
        migrate_dons(cur)

    if to_do[0] == 'appelant':
        print("Migrate Appelant", file=sys.stderr)
        migrate_appelant(cur)
        
    cur.close()
    conn.close()

id2party = {}
identifier_types = []

corresp_title = {
    3 : 'mrs',
    6 : 'mr',
    7 : 'mr&mrs',
    10 : 'dr',
    13 : 'mrss',
    14 : 'me',
    16 : 'dr&mrs',
    17 : 'pr',
    18 : 'me&mrs',
    20 : 'mss',
    23 : 'p',
    32 : 'pp',
    36 : 'dp',
    39 : 'c',
    40 : 'cc',
    41 : 'dd',
    42 : 'ba',
    43 : 's',
    44 : 'mrm', 
    45 : 'mrsm', 
    47 : 'mr', 
    48 : 'mss&mrss', 
    49 : 'mrs&mr',
    50 : 'mrs',
    51 : 'mr',
    52 : 'mr',
    53 : 'mr',
    54 : 'mr',
    55 : 'mr',
    56 : 'mr',
    57 : 'drs',
    58 : 'd',
}

def migrate_cat(cur):
    Party = Model.get('party.party')
    Category = Model.get('party.category')
    default_category = get_default(Category)

    CatRel = Model.get('party.party-party.category')
    default_catrel = get_default(CatRel)

    id2category = {}
    category2parent = {}
    category = Table('res_partner_category')
    cat_rel = Table('res_partner_category_rel')
    cur.execute(*category.select())
    for oe_category in cur:
        category = Category(_default=False)
        set_default(category, default_category)
        category.name = oe_category.name.split('/')[-1]
        id2category[oe_category.id] = category
        if oe_category.parent_id:
            category2parent[category] = oe_category.parent_id
    Category.save(list(id2category.values()))

    for category, parent_id in category2parent.items():
        category.parent = id2category[parent_id]
        category.save()

    
    newcatrel2id = {}
    cat_rel = Table('res_partner_category_rel')
    cur.execute(*cat_rel.select())
    for val,oe_cat_rel in enumerate(cur):
        if Party.find([('code', '=', '{}'.format(oe_cat_rel.partner_id)), ('active', 'in', [True, False])]):
            part = Party.find([('code', '=', '{}'.format(oe_cat_rel.partner_id)),('active', 'in', [True, False])])[0]
            part.categories.append(id2category[oe_cat_rel.category_id])
            part.save()
        else: 
            print(oe_cat_rel.partner_id)

def migrate_party(cur):
    Party = Model.get('party.party')
    Address = Model.get('party.address')
    ContactMechanism = Model.get('party.contact_mechanism')
    Lang = Model.get('ir.lang')
    Country = Model.get('country.country')
    Configuration = Model.get('party.configuration')
    
    default_party = get_default(Party)
    partner = Table('res_partner')
    query = partner.select(getattr(partner, '*'))
    cur.execute(*query)
    for partner in cur:
        if Party.find([('code', '=', '{}'.format(partner.id))]):
            id2party[partner.id] = Party.find([('code', '=', '{}'.format(partner.id))])[0]
            continue

        party = Party(_default=False)
        set_default(party, default_party)
        
        party.lastname = partner.lastname and partner.lastname.strip() or ''
        party.firstname = partner.firstname and partner.firstname.strip() or ''
        
        party.party_title = partner.title and corresp_title[partner.title] or ''
        party.active = partner.active
        party.is_person_moral = not partner.physical and True or False
        party.notes = partner.comment
        party.description = partner.ref
        party.party_type = (partner.customer and 'don') or partner.ptype or 'o' #partner.supplier and 'f' or partner.customer and 'c' or 'o' 
        party.is_writer = partner.ptype == 13 
        party.code = '{}'.format(partner.id)
        
        if partner.website:
            website = party.contact_mechanisms.new(type='website')
            website.value = partner.website
        del party.addresses[:]
        id2party[partner.id] = party

        
    contact_mechanisms = set()
    default_address = get_default(Address)
    default_contact_mechanism = get_default(ContactMechanism)
    address = Table('res_partner_address')
    # contact = Table('res_partner_contact')
    # job = Table('res_partner_job')

    
    country = Table('res_country')
    query = (country
             .select(
                 country.id, country.code,
                 where=country.code != Null))
    cur.execute(*query)
    country_codes = {c.id : c.code for c in cur}
    countries = Country.find([])
    code2country = {c.code: c for c in countries}

    address_do = []
        
    where = ~(address.id.in_(address_do)) if address_do else None

    query = address.select(
                getattr(address, '*'),
                where=where
                )
         
    cur.execute(*query)
    for j in cur:
        if not j.partner_id :
            continue
        #print(j)
        party = id2party[j.partner_id]

        street = j.street and j.street.replace('\n','') or ''
        try : 
            street_num, street = separer_adresse_evidente(street)
        except : 
            street_num = ''
            street = j.street and j.street.replace('\n','') or ''

        #print(job, file=sys.stderr)
        new_address =  Address(_default=False)
        set_default(new_address, default_address)

        nom_complet = j.name and j.name.strip() or ''
        # On sépare les mots
        mots = nom_complet.split()

        # Le nom de famille est celui qui est en majuscules
        prenom = " ".join([m for m in mots if not m.isupper()])
        nom = " ".join([m for m in mots if m.isupper()])

        new_address.contact_firstname = prenom
        new_address.contact_name = nom
        new_address.contact_title = j.title and corresp_title[j.title] or ''
        new_address.contact_phone = j.phone
        new_address.contact_phone2 = j.mobile
        new_address.contact_mail = j.email 
        new_address.contact_function = j.function and j.function.strip() or ''
        new_address.addr_street = street
        new_address.addr_street_num = street_num
        new_address.addr_compl2 = j.street2
        new_address.postal_code = j.zip
        new_address.city = j.city
        new_address.country = j.country_id and code2country[country_codes[j.country_id]] or None
        party.addresses.append(new_address)

    Party.save(list(id2party.values()))



# _columns = {
#         'name'       : name
#         'date'       : fields.datetime(u'Date'),
#         'date_only'  : call_date
#         'hour_only'  : call_time
#         'ecoutant'   : call_writer
#         'duree'      : call_length
#         ************'nocturne'   : fields.boolean(u'Nocturne'),
#         ************'ferie'      : fields.boolean(u'Férié'),
#         'type_appel' : call_type
#         'type_spec'  : call_special
#         'type_appelant' : call_user_type
#         'appelant'   : fields.many2one('lmt.appelant', u'Appelant'),
#         'notes'      : fields.text(u"Profil"),
#         'sexe'       : call_user_gender
#         'age'        : call_user_age
#         ************'raison'     : fields.selection(raison, u"Raison de l'appel"),
#         'contenu'    : contenu
#         'contenu2'    : contenu_2
#         'contenu3'    : contenu_3
#         'contenu_compl' : call_complement
#         'orientation' : call_orientation
#         'contenu_all' : fields.function(_get_contenu, type="text", string='Contenu'),
#         'resume'     : call_resume
#         'resume_light' : fields.function(_get_resume, type="text", string='Résumé'),
#         'aide'       : fields.selection(aide, u"Aide apportée"),
#         'comm'       : call_action
#         'int_ext_umus'   : interv_umus
#         'int_ext_police' : interv_police
#         'int_ext_med'    : interv_medecins
#         'int_ext_autre'  : interv_autres
#         'viol_dom_prov'  : fields.selection(type_dom_prov, u"Provenance de l'appel"),
#         'viol_dom_role'  : fields.selection(type_dom_role, u"Rôle"),
#         'viol_dom_rela'  : fields.selection(type_dom_rel, u"Relation"),
#         'viol_dom_type'  : fields.selection(type_dom_type, u"Type"),
        
#         'sos_jeu_prov'  : fields.selection(type_sos_prov, u"Provenance de l'appel"),
#         'sos_jeu_prob'  : fields.selection(type_sos_prob, u"Problème"),
#         'sos_jeu_role'  : fields.selection(type_sos_role, u"Rôle"),
#         'sos_jeu_type'  : fields.selection(type_sos_type, u"Type"),

#         'vih_prov'  : fields.selection(type_vih_prov, u"Provenance de l'appel"),
#         'vih_motif'  : fields.selection(type_vih_motif, u"Motif"),
                    
#         'lavi_type'     : fields.selection(tmp, u"Type"),
#     }

corresp_pseudo = {
    "Adele":6357,
    "Agata":6351,
    "Agathe":5923,
    "Agnes":6197,
    "Agnès":1,
    "Aïda":5004,
    "Aide par mail Lausanne":1,
    "Alain":6197,
    "Alice":6133,
    "Andrea":6277,
    "Anita":6348,
    "Anja":6528,
    "Anne":6437,
    "Anne-Lise":6254,
    "Anouna":5005,
    "Ariane":6256,
    "Aude":6033,
    "Bea":5006,
    "Béatrice":1,
    "Bénédicte":1,
    "Bernadette":5007,
    "Boaz":5008,
    "Brigitte":1,
    "Brigitte":1,
    "Brigitte T":6438,
    "Bruce":6139,
    "Camille":6279,
    "Carole":6280,
    "Caroline":5009,
    "Caroline B":1,
    "Cecile":5010,
    "Cécile M":6132,
    "Chantal":6135,
    "Chantal":1,
    "Charlotte":1,
    "Chloé":1,
    "Chris":5011,
    "Christian":5059,
    "Christine":6128,
    "Cindy":1,
    "Claire":1,
    "Colette":5013,
    "Corinne":6147,
    "Cristina":6143,
    "Daniel":6063,
    "Danielle":6434,
    "Dany":6352,
    "Dominica":1,
    "Elisa":1,
    "Elisabeth":5014,
    "Elo":1,
    "Elvire":5015,
    "Emma":5016,
    "Emma P":6436,
    "Erika":5060,
    "Finola":6355,
    "Florence":1,
    "Florence":1,
    "Francine":6282,
    "Francine J":6358,
    "Francois":6258,
    "Françoise":5065,
    "Frederik":6283,
    "Frédérique":1,
    "Guylaine":5020,
    "Gwendoline":5021,
    "Haniya":6350,
    "Hanna":1,
    "Hanna":1,
    "Hans":6435,
    "Helena":6259,
    "Helene":5062,
    "Héloïse":6354,
    "Henriette":5939,
    "Ildiko":6138,
    "Iris":5023,
    "Ivana":1,
    "Jacqueline":1,
    "Jacqueline":1,
    "Jacqueline H.":6198,
    "Jacques":1,
    "Jean":1,
    "Jean-Marie":1,
    "Joel":6284,
    "Johann":1,
    "Jordan":1,
    "Juan":6349,
    "Julien":1,
    "Juliette":1,
    "Justine":1,
    "Katia":5071,
    "Katy":5028,
    "Lana":6051,
    "Laure":5066,
    "Laurence":5029,
    "Laurent":6201,
    "Laurie":1,
    "Lea":5030,
    "Lisa":5031,
    "Lise":6290,
    "Lise V":6356,
    "Louis":5032,
    "Lucie":1,
    "Lucienne":5033,
    "Maël":1,
    "Manon":1,
    "Manon":6527,
    "Maria":6291,
    "Marianne":5036,
    "Marianne F.":5864,
    "Marie":5937,
    "Marie-Christine":5037,
    "Marie-Claire":6137,
    "Marina":1,
    "Marina":1,
    "Marinette":6292,
    "Martine":6035,
    "Maud":5039,
    "May":6200,
    "Maya":5040,
    "Mélanie":5072,
    "Melody":5041,
    "Michel":6136,
    "Michele":5042,
    "Milena":1,
    "Miriam":6023,
    "Mohamed":6523,
    "Monique":6255,
    "Morgan":6146,
    "Mouna":5043,
    "Nadia de Preux":1,
    "Nathalie":6131,
    "Nathaly":6142,
    "Nicky":1,
    "Nicole":1,
    "Nicole B":6440,
    "Nicoline":5045,
    "Nikoleka":5924,
    "Nina":5046,
    "Olivier":6286,
    "Pascal":6361,
    "Patricia":6439,
    "Philippe":5047,
    "Pierre":6134,
    "Rachel":"6070 / 5048",
    "Raphaëlle":5061,
    "Raymond":6141,
    "Robert":5049,
    "Roger":1,
    "Romane":1,
    "Sally":1,
    "Sally":1,
    "Salomon":5008,
    "Samia":6181,
    "Sandra":5050,
    "Sandrine":6199,
    "Sébastien":6140,
    "Shpresa":1,
    "Silvana":6353,
    "Susan":1,
    "Sylvie":6144,
    "Tamara":1,
    "Tanya":6145,
    "Therese":1,
    "Thérèse":1,
    "Thibault":1,
    "Toune":6294,
    "Urs":6433,
    "Valerie":1,
    "Valérie C":1,
    "Valérie R":6287,
    "Vanessa":1,
    "Vania L":1,
    "Veronique":6524,
    "Virginie":6525,
    "Viviane":6022,
    "Yousra":1,
    "Yvan":5053,
    "Yves":1,
    "Zoé":5938,
    }


def migrate_appels(cur):
    Calls = Model.get('pl_cust_tel.calls')
    Party = Model.get('party.party')
    RegCalls = Model.get('pl_cust_tel.regularcalls')

    default_call = get_default(Calls)

    appels = Table('lmt_appels')
    ecoutant = Table('lmt_ecoutant')
    appelant = Table('lmt_appelant')
    query = (appels.join(ecoutant,condition=ecoutant.id == appels.ecoutant).select(
            appels.name,
            appels.date_only,
            appels.hour_only,
            appels.type_appel,
            appels.ecoutant, 
            ecoutant.name.as_('pseudo'),
            appels.duree,
            appels.type_spec,
            appels.sexe,
            appels.age,
            appels.appelant,
            appels.notes,
            #appelant.id.as_('appid'),
            #appelant.notes.as_('appnotes'),
            appels.type_appelant,
            appels.contenu,
            appels.contenu2,
            appels.contenu3,
            appels.contenu_compl,
            appels.orientation,
            appels.resume,
            appels.comm,
            appels.int_ext_umus,
            appels.int_ext_police,
            appels.int_ext_med,
            appels.int_ext_autre,
            appels.viol_dom_prov,
            appels.viol_dom_role,
            appels.viol_dom_rela,
            appels.viol_dom_type,
            appels.sos_jeu_prov,
            appels.sos_jeu_prob,
            appels.sos_jeu_role,
            appels.sos_jeu_type,
            appels.vih_prov,
            appels.vih_motif,
    where=appels.date_only > '2021-12-31'))
    cur.execute(*query)
    nb_do = 0
    for app in cur:
        if Calls.find([('name', '=', '{}'.format(app.name))]):
            id2party[app.name] = Calls.find([('name', '=', '{}'.format(app.name))])[0]
            continue
        
        if app.date_only < '2022-01-01' :
            continue
        
        #if nb_do > 2000:
        #    break
        #print(app.pseudo)
        call = Calls(_default=False)
        set_default(call, default_call)
        

        call.call_date = app.date_only
        call.call_time = app.hour_only
        call.name = app.name 
        call.call_type = app.type_appel

        writer = Party.find([('description', '=', '{}'.format(corresp_pseudo[app.pseudo])),('active', 'in', [True, False])])
        if writer : 
            writer = writer[0].id
            #print('{} {}'.format(app.pseudo,writer))
        else :
            writer = 1
        
        rc = None 
        rc = RegCalls.find([('oe_id', '=', app.appelant),('active', 'in', [True, False])])
        if rc :
            rc = rc[0].id
        else :
            rc = None 

        #.join(partner,condition=partner.id == oe_dons.partner
        # )
        call.call_pseudo = app.pseudo
        call.call_writer = writer
        call.call_length = app.duree
        if app.type_appel == 'tel_spec': 
            call.call_special = app.type_spec or 'silence'

        call.call_regular= rc
        call.call_regular_notes = app.notes
        call.call_user_gender = app.sexe
        call.call_user_age = app.age
        call.call_user_type = app.type_appelant
        if app.type_appel != 'tel_spec':
            call.contenu = app.contenu or 'solitude'

        if app.contenu == 'sos':

            corresp_origin = {
                'ge' : 'ge',
                'vd' : 'vd',
                'ne' : 'ne',
                'vs': 'vs',
                'fr' : 'fr',
                'ju': 'ju',
                'f' : 'france',
                'autre': 'prov_autre',
                'nr': 'nr'
            }

            corresp_prob = {
                'tech' : 'tech',
                'rens' : 'rens_dep',
                'aide' : 'aide' ,
                'autre' : 'prob_autre',
            }

            corresp_role = {
                'jh' : 'j',
                'jf' : 'j',
                'ph' : 'p',
                'pf' : 'p',
                'pro' : 'pro',
                'autre' : 'role_autre',
            }

            corresp_type = {
                'jvid' : 'autre',  
                'jint' : 'autre', 
                'mas' : 'mas',  
                'table' : 'table',   
                'pocker' : 'pocker',  
                'pmu' : 'pmu',  
                'lotel' : 'lotel',
                'bourse' : 'bourse',  
                'par' : 'par',  
                'lot' : 'lot',  
            }

            call.call_origin_sos = corresp_origin[app.sos_jeu_prov]
            call.call_problem_sos = corresp_prob[app.sos_jeu_prob]
            call.call_role_sos = corresp_role[app.sos_jeu_role]
            call.call_type_sos = corresp_type[app.sos_jeu_type]
        elif app.contenu == 'vih':
            call.call_origin_vih = app.vih_prov
            call.call_motif_vih = app.vih_motif
        elif app.contenu == 'vd':
            call.call_origin_vd = app.viol_dom_prov
            call.call_role_vd = app.viol_dom_role
            call.call_rel_vd = app.viol_dom_rela
            call.call_type_vd = app.viol_dom_type
        else :
            call.contenu_2 = app.contenu2
            call.contenu_3 = app.contenu3
        
        call.call_complement = app.contenu_compl
        call.call_orientation = app.orientation
        call.call_resume = app.resume
        call.call_action = app.comm
        call.interv_umus = app.int_ext_umus
        call.interv_police = app.int_ext_police
        call.interv_medecins = app.int_ext_med
        call.interv_autres = app.int_ext_autre

        id2party[app.name] = call
        nb_do += 1
        print(nb_do)
        #if nb_do > 5000:
        #    break

    Calls.save(list(id2party.values()))


# _columns = {
#         'name'     : name
#         'dtype'    : type
#         'amount'   : amount
#         'date'     : date
#         'year'     : fields.function(_year_get_fnc, type="char", string=_('Year'), size=10, readonly=True, store=True),
#         'partner'  : donator
#         'remark'   : notes
#         'historic' : fields.boolean(_(u'Historic Data')),
#         'att_sent' : attestation_sent
#         'modif'    : fields.char(_(u'Last Change'), size=100, readonly=True),
#         'no_att'   : no_att
#         'account_bk'   : fields.many2one('account.account', _(u'Liquidity Account')),
#         'account_dons' : fields.many2one('account.account', _(u'Product Account')),
#         'journal_id'   : fields.many2one('account.journal', _(u'Journal')),
#         'state': fields.selection([
#             ('draft',_('Draft')),
#             ('valid',_('Valid')),
#             ],_('State'), select=True, readonly=True,),

#         }                                
    

def migrate_dons(cur):
    Dons = Model.get('pl_cust_dons.dons')
    Party = Model.get('party.party')
    DT = Model.get('pl_cust_dons.type_dons')

    default_don = get_default(Dons)

    partner = Table('res_partner')
    oe_dons = Table('pl_dons')
    query = (oe_dons.join(partner,condition=partner.id == oe_dons.partner
         )).select(
                oe_dons.name,
                oe_dons.date,
                oe_dons.amount,
                oe_dons.remark,
                oe_dons.complement,
                oe_dons.att_sent,
                oe_dons.no_att,
                oe_dons.dtype,
                partner.ref,
         )
    cur.execute(*query)
    nb_do = 0
    for don in cur:
        if Dons.find([('name', '=', '{}'.format(don.name))]):
            id2party[don.name] = Dons.find([('name', '=', '{}'.format(don.name))])[0]
            print(don.name)

        new_don = Dons(_default=False)
        set_default(new_don, default_don)
        donator = Party.find([('description', '=', '{}'.format(don.ref)),('active', 'in', [True, False])])
        if donator : 
            donator = donator[0].id
        else :
            print(don.name)
            donator = 1

        new_don.name = don.name
        new_don.date = don.date
        print(don.dtype)
        new_don.type = DT.find([('code', '=', '{}'.format(don.dtype))])[0].id
        new_don.donator = donator
        new_don.amount = don.amount
        
        new_don.notes = don.remark

        new_don.complement = don.complement
        new_don.attestation_sent = don.att_sent
        new_don.no_att  = don.no_att
        
        id2party[don.name] = new_don
        nb_do += 1
        #if nb_do > 500:
        #    break  

    Dons.save(list(id2party.values()))

def migrate_appelant(cur):

    RegulCall = Model.get('pl_cust_tel.regularcalls')
    default_regcall = get_default(RegulCall)
    
    appelant = Table('lmt_appelant')

    query = appelant.select(getattr(appelant, '*'))
    cur.execute(*query)
    for ap in cur:

        new_regcall = RegulCall(_default=False)
        set_default(new_regcall, default_regcall)
        
        new_regcall.name = ap.name
        new_regcall.oe_id = ap.id
        new_regcall.sexe = ap.sexe
        new_regcall.age = ap.age
        new_regcall.notes = ap.notes
        new_regcall.active = ap.active
        id2party[ap.id] = new_regcall

    RegulCall.save(list(id2party.values()))
   

def get_default(Model):
    return Model.default_get(Model._fields.keys(), False,
        Model._config.context)

def set_default(record, values):
    record._default_set(values)

def separer_adresse_evidente(adresse):
    # On vérifie uniquement le format clair : <nombre>,<espace>...
    match = re.match(r"^\s*(\d+\s*[A-Z]?)\s*,\s*(.+)$", adresse, flags=re.IGNORECASE)
    if match:
        numero = match.group(1)
        rue = match.group(2)
        return numero, rue

    # Cas 2 : numéro clair à la fin
    match = re.match(r"(.+?)\s*,?\s*(\d+\s*[A-Z]?)\s*$", adresse, flags=re.IGNORECASE)
    if match:
        rue = match.group(1).strip()
        numero = match.group(2).replace(" ", "").upper()
        return numero, rue

    
    return '', adresse.strip()

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-td', '--to_do', dest='to_do', nargs='+',
        default=[], metavar='TO Do', help='To Do')
    parser.add_argument('-oe', dest='oe_database', required=True)
    parser.add_argument('-d', '--database', dest='tryton_database',
        required=True)

    args = parser.parse_args()

    main(args.oe_database, args.tryton_database, args.to_do)

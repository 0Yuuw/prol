#!/usr/bin/env python
import json
import datetime
import csv
import sys
import os
import base64

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
    if to_do[0] == 'party':
        print("Migrate party", file=sys.stderr)
        migrate_party(cur)

    if to_do[0] == 'folder':
        print("Migrate Folder", file=sys.stderr)
        migrate_folder(cur)

    if to_do[0] == 'devis':
        print("Migrate Devis", file=sys.stderr)
        migrate_folder_line(cur)

    if to_do[0] == 'pj' :
        print("Migrate PJ", file=sys.stderr)
        migrate_pj(cur)

    if to_do[0] == 'account' :
        print("Migrate account", file=sys.stderr)
        migrate_account(cur)

    if to_do[0] == 'tax' :
        print("Migrate tax", file=sys.stderr)
        migrate_tax(cur)

    if to_do[0] == 'period' :
        print("Migrate period", file=sys.stderr)
        migrate_period(cur)

    if to_do[0] == 'journal' :
        print("Migrate journal", file=sys.stderr)
        migrate_journal(cur)

    if to_do[0] == 'move' :
        print("Migrate move", file=sys.stderr)
        migrate_move(cur)

    if to_do[0] == 'line' :
        print("Migrate line", file=sys.stderr)
        migrate_move_line(cur)

    if to_do[0] == 'fiscalyear' :
        print("Migrate fiscalyear", file=sys.stderr)
        create_fiscalyear()

    if to_do[0] == 'invoice' :
        print("Migrate Invoice", file=sys.stderr)
        migrate_invoice(cur)

    if to_do[0] == 'invline' :
        print("Migrate Invoice Line", file=sys.stderr)
        migrate_invoice_line(cur)

    if to_do[0] == 'inv2move' :
        print("Migrate Invoice 2 move", file=sys.stderr)
        migrate_invoice_move(cur, cur2, conn2)
    

    if to_do[0] == 'invlinetax' :
        print("Migrate Invoice Line Tax", file=sys.stderr)
        migrate_invoice_line_tax(cur)

    if to_do[0] == 'invupdatetax' : 
        print("Update Invoice Tax", file=sys.stderr)
        update_invoice_tax()

    if to_do[0] == 'reconcil' : 
        print("Create reconciliation", file=sys.stderr)
        migrate_reconciliation(cur)
    
    if to_do[0] == 'move2reconcil' : 
        print("Create move to reconciliation ", file=sys.stderr)
        migrate_reconcil_line(cur,cur2,conn2)
        
    cur.close()
    conn.close()

id2party = {}
identifier_types = []

corresp_title = {
    1 : '',
    2 : '',
    6 : 'mr',
    7 : 'mrs', 
    8 : 'mrs', 
    9 : 'mrs', 
    10 : 'mr', 
    11 : 'mr&mrs',
    12 : 'mrs',
    13 : 'me',
    14 : 'dr',
    15 : 'mr&mrs',
    19 : 'mr&mrs',
    16 : 'mr',
    18 : 'mrs',
}

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
        party.lastname = partner.name.strip()
        party.active = partner.active
        party.is_person_moral = True
        party.notes = partner.comment
        party.description = partner.ref
        party.party_type = partner.supplier and 'f' or partner.customer and 'c' or 'o' 
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
    contact = Table('res_partner_contact')
    job = Table('res_partner_job')

    
    country = Table('res_country')
    query = (country
            .select(
                country.id, country.code,
                where=country.code != Null))
    cur.execute(*query)
    country_codes = {c.id : c.code for c in cur}
    countries = Country.find([])
    code2country = {c.code: c for c in countries}

        #     query = (company
    #         .join(address, condition=company.partner_id == address.partner_id)
    #         .join(country, condition=address.country_id == country.id)
    #         .select(
    #             country.code,
    #             where=country.code != Null))
    #     cur.execute(*query)

    
    query = (address.join(job,
         condition=job.address_id == address.id
         ).join(contact,
         condition=job.contact_id == contact.id
         ).select(
            address.id.as_('addr_id'),
            address.partner_id,
            address.street, 
            address.street2, 
            address.compl, 
            address.city, 
            address.zip, 
            address.phone.as_('addr_phone'), 
            address.email.as_('addr_mail'), 
            address.country_id,
            contact.title, 
            contact.first_name, 
            contact.name, 
            contact.email.as_('mail1'),
            job.email.as_('mail2'),
            contact.mobile.as_('phone1'), 
            job.phone.as_('phone2'), 
            job.function))
         
    cur.execute(*query)
    address_do = []
    for j in cur:
        if not j.partner_id :
            continue
        
        address_do.append(j.addr_id)    
        party = id2party[j.partner_id]
        street = j.street and j.street.replace('\n','') or ''
        street_num = ''
        if street and street.split(' ')[-1].isdigit():
            street = ' '.join(j.street.split(' ')[:-1])
            street_num = j.street.split(' ')[-1]
       
        #print(job, file=sys.stderr)
        new_address =  Address(_default=False)
        set_default(new_address, default_address)
        new_address.addr_street = street
        new_address.addr_street_num = street_num
        new_address.contact_name = j.name
        new_address.contact_firstname = j.first_name
        new_address.contact_title = j.title and corresp_title[j.title] or ''
        new_address.contact_function = j.function and j.function.replace('\n','') or ''
        new_address.contact_phone = j.phone1
        new_address.contact_phone2 = j.phone2
        new_address.contact_mail = j.mail1 or j.mail2
        new_address.addr_compl = j.compl
        new_address.addr_compl2 = j.street2
        new_address.postal_code = j.zip
        new_address.city = j.city
        new_address.country = j.country_id and code2country[country_codes[j.country_id]] or None
        party.addresses.append(new_address)
        
    query = (address.select(
                getattr(address, '*'),
                where= not address.id in address_do))
             
    cur.execute(*query)
    for j in cur:
        if not j.partner_id :
            continue
        #print(j)
        party = id2party[j.partner_id]

        street = j.street and j.street.replace('\n','') or ''
        street_num = ''
        if street and street.split(' ')[-1].isdigit():
            street = ' '.join(j.street.split(' ')[:-1])
            street_num = j.street.split(' ')[-1]

        #print(job, file=sys.stderr)
        new_address =  Address(_default=False)
        set_default(new_address, default_address)
        new_address.addr_street = street
        new_address.addr_street_num = street_num
        #new_address.contact_title = a faire
        new_address.addr_compl = j.compl
        new_address.addr_compl2 = j.street2
        new_address.postal_code = j.zip
        new_address.city = j.city
        new_address.country = j.country_id and code2country[country_codes[j.country_id]] or None
        party.addresses.append(new_address)

    Party.save(list(id2party.values()))


def migrate_folder(cur):
    Party = Model.get('party.party')
    Folder = Model.get('pl_cust_plfolders.folders')
    
    partys = Party.find([])
    code2partys = {c.code: c for c in partys}
    print(code2partys)
    default_Folder = get_default(Folder)

    contact = Table('res_partner_contact')
    query = contact.select(contact.id , contact.name, contact.first_name)
    cur.execute(*query)
    contactid2name = {c.id : '{} {}'.format(c.first_name, c.name) for c in cur}


    contract = Table('eagle_contract')
    query = contract.select(getattr(contract, '*'))
    cur.execute(*query)
    for c in cur:
        folder = Folder(_default=False)
        set_default(folder, default_Folder)
        folder.folder_type = 'o'
        folder.name = c.name
        folder.state = correspstate[c.state]
        folder.notes = c.my_notes
        folder.date_start = c.date_start
        folder.date_end = c.date_end
        folder.description = c.concern
        folder.party_id = code2partys['{}'.format(c.customer_id)]
        folder.contact_name = c.contact_id and contactid2name[c.contact_id] or ''

        #print(c.name)
        folder.save()

def migrate_folder_line(cur):
    Folder = Model.get('pl_cust_plfolders.folders')
    Tax = Model.get('account.tax')
    Prod = Model.get('product.product')
    DevisLine = Model.get('pl_cust_devis.devisline')
    default_DevisLine = get_default(DevisLine)

    tax = Table('eagle_contrat_line_tax')
    query = tax.select(tax.cnt_line_id , tax.tax_id)
    cur.execute(*query)
    tax2tax = {c.cnt_line_id : c.tax_id for c in cur}

    #Tax
    print('Tax')
    id2tax = {c.oeid: c.id for c in Tax.find([])}
    #oetax = Table('account_tax')   
    #query = oetax.select(oetax.id , oetax.name)
    #cur.execute(*query)
    #oetax2name = {c.id : c.name for c in cur}   
    ###


    folders = Folder.find([])
    num2folders = {c.name: c for c in folders}
    #print(num2folders)
    contract = Table('eagle_contract')
    contractline = Table('eagle_contract_position')
    query = contractline.join(contract,
            condition=contractline.contract_id == contract.id).select(getattr(contractline, '*'),contract.name.as_('cont_name'))
    cur.execute(*query)
    n = 0
    for c in cur:
        n += 1
        print(n)
        devis = DevisLine(_default=False)
        set_default(devis, default_DevisLine)
        devis.product = Prod(1)
        devis.folder_id = num2folders[c.cont_name]
        if tax2tax.get(c.id,None):
            devis.product_tva = id2tax['{}'.format(tax2tax[c.id])]
        
        devis.sequence=c.sequence
        devis.name = c.description and c.description.replace('\r','').replace('\n','') or ''
        devis.comment = c.notes and c.notes.replace('\r','').replace('\n','') or ''
        devis.product_price = c.list_price
        devis.quantity = c.qty
        devis.force_invoice = c.state == 'done'

        devis.save()
    
def migrate_pj(cur):
    Party = Model.get('party.party')
    Folder = Model.get('pl_cust_plfolders.folders')
    
    PJs = Model.get('ir.attachment')
    default_pj = get_default(PJs)

    folders = Folder.find([])
    num2folders = {c.name: c for c in folders}

    contract = Table('eagle_contract')
    query = contract.select(contract.id , contract.name)
    cur.execute(*query)
    contractid2name = {c.id : c.name for c in cur}

    attachement = Table('ir_attachment')
    query = attachement.select(getattr(attachement, '*'), where=attachement.res_model == 'eagle.contract')
    cur.execute(*query)
    for c in cur:
        try:
            num2folders['{}'.format('{}'.format(contractid2name[c.res_id]))]
        except:
            continue

        pj = PJs(_default=False)
        set_default(pj, default_pj)
        if isinstance(c.datas, memoryview):
            binary_data = base64.decodebytes(c.datas.tobytes())
        else:
            binary_data = base64.decodebytes(c.datas.encode('utf-8'))  # ou un autre encodage approprié

        print(f"Type des données après conversion: {type(binary_data)}")
        if not isinstance(binary_data, (bytes, bytearray)):
            raise ValueError("Les données récupérées ne sont pas en format binaire attendu")
        pj.data = binary_data
        pj.name = c.datas_fname
        #pj.resource = code2partys['{}'.format(c.res_id)]
        pj.resource = num2folders['{}'.format('{}'.format(contractid2name[c.res_id]))]
        print(c.name)
        pj.save()

    partys = Party.find([])
    code2partys = {c.code: c for c in partys}
    #print(code2partys)

    query = attachement.select(getattr(attachement, '*'), where=attachement.res_model == 'res.partner')
    cur.execute(*query)
    for c in cur:
        try:
            code2partys['{}'.format(c.res_id)]
        except:
            continue

        pj = PJs(_default=False)
        set_default(pj, default_pj)
        if isinstance(c.datas, memoryview):
            binary_data = base64.decodebytes(c.datas.tobytes())
        else:
            binary_data = base64.decodebytes(c.datas.encode('utf-8'))  # ou un autre encodage approprié

        print(f"Type des données après conversion: {type(binary_data)}")
        if not isinstance(binary_data, (bytes, bytearray)):
            raise ValueError("Les données récupérées ne sont pas en format binaire attendu")
        pj.data = binary_data
        pj.name = c.datas_fname
        pj.resource = code2partys['{}'.format(c.res_id)]
        print(c.name)
        pj.save()

    Invoice = Model.get('account.invoice')
    #Invoice
    print('invoice')
    id2invoice = {c.oeid : c for c in Invoice.find([])}
    ######

    query = attachement.select(getattr(attachement, '*'), where=attachement.res_model == 'account.invoice')
    cur.execute(*query)
    for c in cur:
        try:
            id2invoice['{}'.format(c.res_id)]
        except:
            print(c.res_id)
            continue

        pj = PJs(_default=False)
        set_default(pj, default_pj)
        if isinstance(c.datas, memoryview):
            binary_data = base64.decodebytes(c.datas.tobytes())
        else:
            binary_data = base64.decodebytes(c.datas.encode('utf-8'))  # ou un autre encodage approprié

        print(f"Type des données après conversion: {type(binary_data)}")
        if not isinstance(binary_data, (bytes, bytearray)):
            raise ValueError("Les données récupérées ne sont pas en format binaire attendu")
        pj.data = binary_data
        pj.name = c.datas_fname
        pj.resource = id2invoice['{}'.format(c.res_id)]
        print(c.name)
        pj.save()


def migrate_account(cur):
    Account = Model.get('account.account')
    default_a = get_default(Account)

    oeaccount = Table('account_account')
    query = oeaccount.select(getattr(oeaccount, '*'))
    cur.execute(*query)
    for c in cur:
        a = Account(_default=False)
        set_default(a, default_a)
        a.code = c.code
        a.name = c.name
        a.save()
    
    all_account = Account.find([])
    code2account = {c.code: c.id for c in all_account}
       
    query = oeaccount.select(oeaccount.id , oeaccount.code)
    cur.execute(*query)
    oeaccount2code = {c.id : c.code for c in cur}   

    query = oeaccount.select(getattr(oeaccount, '*'))
    cur.execute(*query)
    for c in cur:
        if c.parent_id :
            a = Account(code2account[c.code])
            a.parent = code2account[oeaccount2code[c.parent_id]]
            a.save()

def create_fiscalyear():
    FiscalYear = Model.get('account.fiscalyear')
    Sequence = Model.get('ir.sequence')
    SequenceStrict = Model.get('ir.sequence.strict')
    SequenceType = Model.get('ir.sequence.type')

    for year in range(2011,2025):

        new_fiscalyear = FiscalYear()
        new_fiscalyear.name = '{}'.format(year)
        new_fiscalyear.start_date = '{}-01-01'.format(year)
        new_fiscalyear.end_date = '{}-12-31'.format(year)
        sequence = Sequence(name='{}'.format(year))
        sequence.sequence_type, = SequenceType.find([
            ('name', '=', "Account Move"),
            ])
        # TODO set number
        sequence.save()
        new_fiscalyear.post_move_sequence = sequence

        invoice_sequence, = new_fiscalyear.invoice_sequences
        for name, field in [
                ('Customer Invoice', 'out_invoice_sequence'),
                ('Supplier Invoice', 'in_invoice_sequence'),
                ('Customer Credit Note', 'out_credit_note_sequence'),
                ('Supplier Credit Note', 'in_credit_note_sequence'),
                ]:
            sequence = SequenceStrict(name='%s %s' % (name, '{}'.format(year)))
            sequence.sequence_type, = SequenceType.find([
                    ('name', '=', "Invoice"),
                    ])
            # TODO set number
            sequence.save()
            setattr(invoice_sequence, field, sequence)
        new_fiscalyear.save()

def migrate_period(cur):
    Period = Model.get('account.period')
    default_p = get_default(Period)
    FiscalYear = Model.get('account.fiscalyear')

    fiscalyear = Table('account_fiscalyear')
    query = fiscalyear.select(fiscalyear.id , fiscalyear.name)
    cur.execute(*query)
    oefiscalyear2name = {c.id : c.name for c in cur}   

    all_fiscalyear = FiscalYear.find([])
    name2fiscalyear = {c.name: c.id for c in all_fiscalyear}

    oeperiod = Table('account_period')
    query = oeperiod.select(getattr(oeperiod, '*'))
    cur.execute(*query)
    for c in cur: 
        p = Period(_default=False)
        set_default(p, default_p)
        p.name = c.name
        p.start_date = c.date_start
        p.end_date = c.date_stop
        p.fiscalyear = name2fiscalyear[oefiscalyear2name[c.fiscalyear_id]]
        p.save()
    

def migrate_journal(cur):
    Journal = Model.get('account.journal')
    default_j = get_default(Journal)

    oejournal = Table('account_journal')
    query = oejournal.select(getattr(oejournal, '*'))
    cur.execute(*query)
    for c in cur: 
        j = Journal(_default=False)
        set_default(j, default_j)
        j.name = c.name
        j.code = c.code
        j.type = c.type
        try :
            j.save()
        except :
            j.type = 'general'
            j.save()

def migrate_tax(cur):
    Tax = Model.get('account.tax')
    Account = Model.get('account.account')
    default_t = get_default(Tax)

    #Account
    print('account')
    code2account = {c.code: c.id for c in Account.find([])}
    oeaccount = Table('account_account')   
    query = oeaccount.select(oeaccount.id , oeaccount.code)
    cur.execute(*query)
    oeaccount2code = {c.id : c.code for c in cur}   
    ###

    oetax = Table('account_tax')
    query = oetax.select(getattr(oetax, '*'))
    cur.execute(*query)
    for c in cur: 
        t = Tax(_default=False)
        set_default(t, default_t)
        print(c.name)
        t.name = c.name
        t.rate = c.amount
        t.description = '{} (oeid:{})'.format(c.name,c.id)
        t.oeid = '{}'.format(c.id)
        t.invoice_account = code2account['0']
        t.credit_note_account = code2account['0']
        t.save()

def migrate_reconciliation(cur): 
    Reconciliation = Model.get('account.move.reconciliation')
    default_r = get_default(Reconciliation)

    nb = 0
    reconcil = Table('account_move_reconcile')
    query = reconcil.select(getattr(reconcil, '*'))
    cur.execute(*query)
    for c in cur: 
        nb += 1
        r = Reconciliation(_default=False)
        set_default(r, default_r)
        r.oeid = '{}'.format(c.id)
        r.number = c.name
        r.date = c.create_date.date()
        r.save()
    
def migrate_reconcil_line(cur,cur2,conn2):
    Line =  Model.get('account.move.line')
    Reconciliation = Model.get('account.move.reconciliation')

    #Move 
    print('reconciliation')
    id2reconcil = {c.oeid : c.id for c in Reconciliation.find([])}

    oemoveline = Table('account_move_line')
    query = oemoveline.select(getattr(oemoveline, '*'))
    cur.execute(*query)
    nb=0
    for c in cur: 
        nb+=1
        print(nb)
        if c.reconcile_id :
            l = Line.find([('oeid', '=', '{}'.format(c.id))])[0]    

            # Requête SQL pour mettre à jour le salaire
            update_query = sql.SQL("""
            UPDATE account_move_line
            SET reconciliation = %s
            WHERE id = %s
            """)

            # Exécuter la requête
            cur2.execute(update_query, (int(id2reconcil['{}'.format(c.reconcile_id)]), l.id))

            # Valider la transaction
            conn2.commit()

def migrate_invoice_move(cur,cur2,conn2):
    Invoice = Model.get('account.invoice')
    Move = Model.get('account.move')

    #Move 
    print('move')
    id2move = {c.oeid : c.id for c in Move.find([])}

    oeinvoice = Table('account_invoice')
    query = oeinvoice.select(getattr(oeinvoice, '*'))
    cur.execute(*query)
    nb=0
    for c in cur: 
        nb += 1
        i = Invoice.find([('oeid', '=', '{}'.format(c.id))])[0]    


        if c.move_id and not i.move:
            print('{} {} {}'.format(nb,id2move['{}'.format(c.move_id)], i))

            # Requête SQL pour mettre à jour le salaire
            update_query = sql.SQL("""
            UPDATE account_invoice
            SET move = %s
            WHERE id = %s
            """)

            # Exécuter la requête
            cur2.execute(update_query, (int(id2move['{}'.format(c.move_id)]), i.id))

            # Valider la transaction
            conn2.commit()
            try : 
                i.click('post')
                #i.state='paid'
                #i.move = id2move['{}'.format(c.move_id)]
            except: 
                print('bheuuu move or id :{} inv tryton id:{}'.format(c.move_id, i.id))
        elif c.move_id and i.state != 'paid': 
            try : 
                i.click('post')
            except:
                pass
            
        i.save()

def migrate_move(cur):
    Move = Model.get('account.move')
    Journal = Model.get('account.journal')
    Period = Model.get('account.period')
    default_m = get_default(Move)


    oejournal = Table('account_journal')
    query = oejournal.select(oejournal.id , oejournal.code)
    cur.execute(*query)
    oejournal2code = {c.id : c.code for c in cur}   

    code2journal = {c.code : c.id for c in Journal.find([])}

    oeperiod = Table('account_period')
    query = oeperiod.select(oeperiod.id , oeperiod.name)
    cur.execute(*query)
    oeperiod2code = {c.id : c.name for c in cur}   

    code2period = {c.name : c.id for c in Period.find([])}

    oemove = Table('account_move')
    query = oemove.select(getattr(oemove, '*'))
    cur.execute(*query)
    nb=0
    for c in cur: 
        nb+=1
        print(nb)
        m = Move(_default=False)
        set_default(m, default_m)
        m.oenumber = c.name
        m.oeid = '{}'.format(c.id)
        m.date = c.date
        m.journal = code2journal[oejournal2code[c.journal_id]]
        m.description = c.ref
        m.period = code2period[oeperiod2code[c.period_id]]
        m.save()

def migrate_move_line(cur):
    Line =  Model.get('account.move.line')
    default_l = get_default(Line)

    Account = Model.get('account.account')
    Move = Model.get('account.move')
    Journal = Model.get('account.journal')
    Period = Model.get('account.period')
    Party = Model.get('party.party')

    #Move 
    print('move')
    #oemove = Table('account_move')
    #query = oemove.select(oemove.id , oemove.name)
    #cur.execute(*query)
    #oemove2name = {c.id : c.name for c in cur}   

    name2move = {c.oeid : c.id for c in Move.find([])}

    #Party 
    print('party')
    id2party = {c.code: c for c in Party.find([])}
    ###

    #Journal
    print('journal')
    oejournal = Table('account_journal')
    query = oejournal.select(oejournal.id , oejournal.code)
    cur.execute(*query)
    oejournal2code = {c.id : c.code for c in cur}   

    code2journal = {c.code : c.id for c in Journal.find([])}
    ######

    #Period
    print('period')
    oeperiod = Table('account_period')
    query = oeperiod.select(oeperiod.id , oeperiod.name)
    cur.execute(*query)
    oeperiod2code = {c.id : c.name for c in cur}   

    code2period = {c.name : c.id for c in Period.find([])}
    ####

    #Account
    print('account')
    code2account = {c.code: c.id for c in Account.find([])}
    oeaccount = Table('account_account')   
    query = oeaccount.select(oeaccount.id , oeaccount.code)
    cur.execute(*query)
    oeaccount2code = {c.id : c.code for c in cur}   
    ###

    oemoveline = Table('account_move_line')
    query = oemoveline.select(getattr(oemoveline, '*'))
    cur.execute(*query)
    nb=0
    for c in cur: 
        nb+=1
        #print(nb)
        if Line.find([('oeid', '=', '{}'.format(c.id))]):
            continue
        l = Line(_default=False)
        set_default(l, default_l)
        l.oeid = '{}'.format(c.id)
        l.debit = "{:.2f}".format(c.debit)
        l.credit = "{:.2f}".format(c.credit)
        l.move = name2move['{}'.format(c.move_id)]
        if c.partner_id :
            l.party = id2party['{}'.format(c.partner_id)]
        l.account = code2account[oeaccount2code[c.account_id]]
        l.date = c.date
        l.journal = code2journal[oejournal2code[c.journal_id]]
        l.description = c.name.replace('\r', '').replace('\n', '')
        l.period = code2period[oeperiod2code[c.period_id]]
        print('1---- {} {} ----'.format(nb, c.id))
        try :
            l.save()
        except:
            print('2---- {} ----'.format(c.id))
            l.description += ' (date OE {})'.format(c.date)
            l.date = Move(name2move['{}'.format(c.move_id)]).date
            l.period = Move(name2move['{}'.format(c.move_id)]).period
            l.save()

def migrate_invoice(cur):
    Invoice =  Model.get('account.invoice')
    default_i = get_default(Invoice)

    Folder = Model.get('pl_cust_plfolders.folders')
    Account = Model.get('account.account')
    #Move = Model.get('account.move')
    Journal = Model.get('account.journal')
    Period = Model.get('account.period')
    Party = Model.get('party.party')

    #Party 
    print('party')
    id2party = {c.code: c for c in Party.find([])}
    ###

    #Journal
    print('journal')
    oejournal = Table('account_journal')
    query = oejournal.select(oejournal.id , oejournal.code)
    cur.execute(*query)
    oejournal2code = {c.id : c.code for c in cur}   

    code2journal = {c.code : c.id for c in Journal.find([])}
    ######

    #Account
    print('account')
    code2account = {c.code: c.id for c in Account.find([])}
    oeaccount = Table('account_account')   
    query = oeaccount.select(oeaccount.id , oeaccount.code)
    cur.execute(*query)
    oeaccount2code = {c.id : c.code for c in cur}   
    ###

    #Folder
    folders = Folder.find([])
    num2folders = {c.name: c for c in folders}
    
    contract = Table('eagle_contract')
    query = contract.select(contract.id , contract.name)
    cur.execute(*query)
    oecontract2name = {c.id : c.name for c in cur} 
    ###

    oeinvoice = Table('account_invoice')
    query = oeinvoice.select(getattr(oeinvoice, '*'))
    cur.execute(*query)
    nb=0
    for c in cur: 
        nb+=1
        print(nb)
        i = Invoice(_default=False)
        set_default(i, default_i)
        i.oeid = '{}'.format(c.id)
        i.number = c.number
        i.reference = c.number
        #print(c.type)
        if c.account_id in (40,183):
            i.type = 'in'
            i.journal = code2journal[oejournal2code[22]]
        else:
            i.type = 'out'
            i.journal = code2journal[oejournal2code[21]]

        #print('in_' in c.type and 'in' or 'out')
        i.party = id2party['{}'.format(c.partner_id)]
        if c.contract_id:
            i.folder_id = num2folders[oecontract2name[c.contract_id]]
        i.account = code2account[oeaccount2code[c.account_id]]
        i.invoice_date = c.date_invoice
        i.date_due = c.date_due
        i.comment = c.comment
        i.description = c.name
        i.save()

def migrate_invoice_line(cur):
    InvLine =  Model.get('account.invoice.line')
    default_il = get_default(InvLine)

    Invoice = Model.get('account.invoice')
    Account = Model.get('account.account')
    #Move = Model.get('account.move')
    Journal = Model.get('account.journal')
    Period = Model.get('account.period')
    Party = Model.get('party.party')

    #Party 
    print('party')
    id2party = {c.code: c for c in Party.find([])}
    ###

    #Invoice
    print('invoice')
    id2invoice = {c.oeid : c.id for c in Invoice.find([])}
    ######

    #Account
    print('account')
    code2account = {c.code: c.id for c in Account.find([])}
    oeaccount = Table('account_account')   
    query = oeaccount.select(oeaccount.id , oeaccount.code)
    cur.execute(*query)
    oeaccount2code = {c.id : c.code for c in cur}   
    ###

    oeinvoiceline = Table('account_invoice_line')
    query = oeinvoiceline.select(getattr(oeinvoiceline, '*'))
    cur.execute(*query)
    nb=0
    for c in cur: 
        nb+=1
        print(nb)
        il = InvLine(_default=False)
        set_default(il, default_il)
        il.oeid = '{}'.format(c.id)
        il.note = c.note
        il.description = c.name
        il.account = code2account[oeaccount2code[c.account_id]]
        il.invoice = id2invoice['{}'.format(c.invoice_id)]
        il.unit_price = c.price_unit
        il.quantity = c.quantity
        il.save()
    

def migrate_invoice_line_tax(cur):
    InvLine =  Model.get('account.invoice.line')
    Invoice = Model.get('account.invoice')
    Tax =  Model.get('account.tax')

    #Invoice
    #print('invoice')
    #id2invoice = {c.oeid : c.id for c in Invoice.find([])}
    ######

    #Tax
    print('Tax')
    id2tax = {c.oeid: c.id for c in Tax.find([])}
    ###

    #InvoiceLine
    print('invoice_line')
    id2invline = {c.oeid : c.id for c in InvLine.find([])}
    ######

    oeinvoicelinetax = Table('account_invoice_line_tax')
    query = oeinvoicelinetax.select(getattr(oeinvoicelinetax, '*'))
    cur.execute(*query)
    nb=0
    for c in cur: 
        nb+=1
       
        il=InvLine(id2invline['{}'.format(c.invoice_line_id)])
        t=Tax(id2tax['{}'.format(c.tax_id)])
        print(nb)
        il.taxes.append(t)
        il.save()
        
        il.invoice.save()
        #print('{} update tax'.format(nb))
        #Invoice.update_taxes(InvLine(id2invline['{}'.format(c.invoice_line_id)]).invoice)
    
def update_invoice_tax():
    Invoice = Model.get('account.invoice')
    all_inv = Invoice.find([])
    nb = 0
    tot = len(all_inv)

    for i in all_inv:
        nb+=1
        if i.taxes:
            for t in i.taxes:
                t.delete()
        
        i.click('draft')
        #i.click('validate_invoice')
        #i.click('draft')
        print('{} / {}'.format(nb,tot))
        
        
def get_default(Model):
    return Model.default_get(Model._fields.keys(), False,
        Model._config.context)

def set_default(record, values):
    record._default_set(values)

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-td', '--to_do', dest='to_do', nargs='+',
        default='account', metavar='TO Do', help='To Do')
    parser.add_argument('-oe', dest='oe_database', required=True)
    parser.add_argument('-d', '--database', dest='tryton_database',
        required=True)

    args = parser.parse_args()

    main(args.oe_database, args.tryton_database, args.to_do)

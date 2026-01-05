#!/usr/bin/env python
import json
import datetime
import csv
import sys

from argparse import ArgumentParser
from collections import defaultdict
from decimal import Decimal
from itertools import chain

import psycopg2
import psycopg2.extras

import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberFormat

from stdnum import get_cc_module, ean

from sql import Table, Null
from sql.aggregate import Sum
from sql.conditionals import Coalesce

from proteus import config, Model, Wizard
from proteus.pyson import PYSONDecoder


def main(oe_database, tryton_database, modules, languages, load):
    config.set_trytond(tryton_database)
    to_activate, activated = activate_modules(modules)

    conn = psycopg2.connect(host='postgres', dbname='altoe', user='tryton', password='xoequee7ooYaing')
    cur = conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)

    if 'account_invoice' in activated:
        print("Migrate payment terms", file=sys.stderr)
        migrate_payment_term(activated, cur)

    if 'party' in activated:
        print("Migrate parties", file=sys.stderr)
        migrate_party(activated, cur)

    if 'company' in activated:
        print("Migrate company", file=sys.stderr)
        migrate_company(activated, cur)

    if 'account_fr' in activated:
        print("Create French chart of account", file=sys.stderr)
        create_chart_of_account('Plan comptable (French)', '4111', '4011')

    if load.get('account') and 'account' in activated:
        print("Load accounts", file=sys.stderr)
        load_csv(Model.get('account.account'), load['account'])

    if 'company' in activated:
        print("Migrate employess", file=sys.stderr)
        migrate_employee(activated, cur)

    if 'product' in activated:
        if load.get('uom'):
            print("Load unit of measure", file=sys.stderr)
            load_csv(Model.get('product.uom'), load['uom'])
        print("Migrate products", file=sys.stderr)
        migrate_product(activated, cur)
        if 'purchase' in modules:
            print("Migrate product suppliers", file=sys.stderr)
            migrate_product_supplier(activated, cur)

    if 'stock' in activated:
        print("Migrate stock locations", file=sys.stderr)
        migrate_stock(activated, cur)
        if (load.get('product_cost_warehouse')
                and 'product_cost_warehouse' in activated):
            print("Load product cost price per warehouse", file=sys.stderr)
            migrate_product_cost_warehouse(load['product_cost_warehouse'])
        print("Migrate stock levels", file=sys.stderr)
        migrate_stock_levels(activated, cur)

    if 'sale' in activated:
        print("Migrate sales", file=sys.stderr)
        migrate_sale(activated, cur)

    if 'sale_opportunity' in activated:
        print("Migrate sale opportunities", file=sys.stderr)
        migrate_opportunity(activated, cur)

    if 'purchase' in activated:
        print("Migrate purchases", file=sys.stderr)
        migrate_purchase(activated, cur)

    if 'account_invoice' in activated:
        print("Migrate invoices", file=sys.stderr)
        migrate_invoice(activated, cur)

    if 'account' in activated:
        print("Migrate fiscal years", file=sys.stderr)
        migrate_fiscalyear(activated, cur)
        print("Migrate account balances", file=sys.stderr)
        migrate_account_balance(activated, cur)

    cur.close()
    conn.close()

    print("Setup languages", file=sys.stderr)
    setup_languages(languages)


def get_default(Model):
    return Model.default_get(Model._fields.keys(), False,
        Model._config.context)


def set_default(record, values):
    record._default_set(values)


def load_csv(Model, filename):
    with open(filename, 'r') as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader)
        for data in reader:
            Model.import_data(header, [data], Model._config.context)


def activate_modules(modules):
    Module = Model.get('ir.module')
    modules = Module.find([
            ('name', 'in', modules),
            ('state', '!=', 'activated'),
            ])
    [m.click('activate') for m in modules]
    modules = [m.name for m in Module.find([('state', '=', 'to activate')])]
    Wizard('ir.module.activate_upgrade').execute('upgrade')

    ConfigWizardItem = Model.get('ir.module.config_wizard.item')
    items = ConfigWizardItem.find([('state', '!=', 'done')])
    for item in items:
        item.state = 'done'
    ConfigWizardItem.save(items)

    activated_modules = [m.name
        for m in Module.find([('state', '=', 'activated')])]
    return modules, activated_modules


def setup_languages(languages):
    Lang = Model.get('ir.lang')
    Module = Model.get('ir.module')

    languages = Lang.find([
            ('code', 'in', languages),
            ])
    for lang in languages:
        lang.translatable = True
    Lang.save(languages)

    Module.click(Module.find([('state', '=', 'activated')]), 'upgrade')
    Wizard('ir.module.activate_upgrade').execute('upgrade')


id2party = {}
identifier_types = []


def migrate_party(modules, cur):
    Party = Model.get('party.party')
    Address = Model.get('party.address')
    ContactMechanism = Model.get('party.contact_mechanism')
    Lang = Model.get('ir.lang')
    Country = Model.get('country.country')
    Note = Model.get('ir.note')
    if 'party_relationship' in modules:
        RelationType = Model.get('party.relation.type')
        parent_of = RelationType(name='Parent Of')
        parent_of.save()
    else:
        parent_of = None
    if 'account_invoice' in modules:
        PaymentTerm = Model.get('account.invoice.payment_term')
    else:
        PaymentTerm = None
    country_codes = []
    if 'company' in modules:
        company = Table('res_company')
        address = Table('res_partner_address')
        country = Table('res_country')
        query = (company
            .join(address, condition=company.partner_id == address.partner_id)
            .join(country, condition=address.country_id == country.id)
            .select(
                country.code,
                where=country.code != Null))
        cur.execute(*query)
        country_codes.extend((c for c, in cur))
    Configuration = Model.get('party.configuration')

    langs = Lang.find([])
    code2lang = {l.code: l for l in langs}

    countries = Country.find([])
    code2country = {c.code: c for c in countries}

    if PaymentTerm:
        payment_terms = PaymentTerm.find([])
        name2payment_term = {p.name: p for p in payment_terms}
        payment_term = Table('account_payment_term')
        cur.execute(*payment_term.select(payment_term.id, payment_term.name))
        payment_term2name = {p.id: p.name for p in cur}

    notes = []
    default_party = get_default(Party)
    parents = {}
    partner = Table('res_partner')
    query = partner.select(getattr(partner, '*'))
    cur.execute(*query)
    for partner in cur:
        party = Party(_default=False)
        set_default(party, default_party)
        party.name = partner.name.strip()
        #party.code = partner.ref or '+%s' % partner.id
        party.active = partner.active
        if partner.lang:
            party.lang = code2lang.get(
                partner.lang, code2lang.get(partner.lang.split('_')[0]))
        if isinstance(partner.title, str) and partner.title.strip():
            party.name += ' ' + partner.title.strip()
        if partner.vat:
            identifier = party.identifiers.new()
            identifier.code = partner.vat
            for type in identifier_types:
                if type and '_' in type:
                    module = get_cc_module(*type.split('_', 1))
                    if module and module.is_valid(identifier.code):
                        identifier.type = type
                        break
            else:
                identifier.type = None
        if partner.website:
            website = party.contact_mechanisms.new(type='website')
            website.value = partner.website
        if partner.parent_id:
            parents[partner.id] = partner.parent_id
        del party.addresses[:]
        id2party[partner.id] = party

        if partner.comment:
            notes.append(Note(resource=party, message=partner.comment))

    contact_mechanisms = set()
    default_address = get_default(Address)
    default_contact_mechanism = get_default(ContactMechanism)
    address = Table('res_partner_address')
    country = Table('res_country')
    query = address.join(country, 'LEFT',
        condition=address.country_id == country.id
        ).select(getattr(address, '*'), country.code.as_('country_code'),
            where=address.partner_id != Null)
    cur.execute(*query)
    for address in cur:
        party = id2party[address.partner_id]
        if address.street or address.street2 or address.city or address.zip:
            new_address = Address(_default=False)
            set_default(new_address, default_address)
            new_address.street = '\n'.join(
                filter(None, [address.street, address.street2]))
            new_address.city = address.city
            new_address.postal_code = address.zip
            new_address.country = code2country.get(address.country_code)
            if address.type == 'default':
                new_address.sequence = 1
                if 'account_invoice' in modules:
                    new_address.invoice = True
                if 'stock' in modules:
                    new_address.delivery = True
            elif address.type == 'invoice' and 'account_invoice' in modules:
                new_address.invoice = True
                new_address.sequence = 2
            elif address.type == 'delivery' and 'stock' in modules:
                new_address.delivery = True
                new_address.sequence = 2
            else:
                new_address.sequence = 3
                if address.type == 'onetime':
                    new_address.active = False
            party.addresses.append(new_address)

        for type in ['fax', 'phone', 'mobile', 'email']:
            if getattr(address, type):
                contact = ContactMechanism(_default=False)
                set_default(contact, default_contact_mechanism)
                contact.type = type
                value = getattr(address, type)
                if type in {'phone', 'mobile', 'fax'}:
                    for country_code in chain([
                                a.country.code for a in party.addresses
                                if a.country], country_codes, [None]):
                        try:
                            value = phonenumbers.parse(value, country_code)
                        except NumberParseException:
                            continue
                        if not phonenumbers.is_valid_number(value):
                            contact.type = 'other'
                        value = phonenumbers.format_number(
                            value, PhoneNumberFormat.INTERNATIONAL)
                        break
                    else:
                        contact.type = 'other'
                contact.value = value
                if (party, value) in contact_mechanisms:
                    continue
                contact_mechanisms.add((party, value))
                if address.name:
                    contact.name = address.name.strip()
                if address.type == 'default':
                    if 'account_invoice' in modules:
                        contact.invoice = True
                    if 'stock' in modules:
                        contact.delivery = True
                elif (address.type == 'invoice'
                        and 'account_invoice' in modules):
                    contact.invoice = True
                elif address.type == 'delivery' and 'stock' in modules:
                    contact.delivery = True
                for field in ['email', 'website', 'skype', 'sip',
                        'other_value']:
                    # Clean function field to speed up
                    contact._values.pop(field)
                party.contact_mechanisms.append(contact)

    if False and PaymentTerm:
        property_ = Table('ir_property')
        query = property_.select(
            where=property_.name.like('account.payment.term,%')
            & property_.res_id.like('res.partner,%')
            & property_.name.in_([
                    'property_payment_term',
                    'property_supplier_payment_term']))
        cur.execute(*query)
        for prop in cur:
            if not prop.res_id:
                # TODO
                continue
            party = id2party.get(int(prop.res_id.split(',', 1)[1]))
            if not party:
                continue
            term_name = payment_term2name[int(prop.value.split(',', 1)[1])]
            term = name2payment_term[term_name]
            if prop.name == 'property_payment_term':
                party.customer_payment_term = term
            else:
                party.supplier_payment_term = term

    # TODO fiscal position

    Party.save(list(id2party.values()))

    if parent_of:
        to_save = []
        for partner_id, parent_id in parents.items():
            party = id2party[partner_id]
            parent = id2party[partner_id]
            parent.relations.new(to=party, type=parent_of)
            to_save.append(parent)
        Party.save(to_save)

    Note.save(notes)

    # Reset the sequence
    configuration = Configuration(1)
    codes = [p.code for p in Party.find([])]
    configuration.party_sequence.number_next = max(map(int, codes)) + 1
    configuration.party_sequence.save()


id2payment_terms = {}


def migrate_payment_term(modules, cur):
    PaymentTerm = Model.get('account.invoice.payment_term')
    PaymentTermLine = Model.get('account.invoice.payment_term.line')

    payment_term = Table('account_payment_term')
    payment_term_line = Table('account_payment_term_line')

    lines = defaultdict(list)
    query = payment_term_line.select(order_by=payment_term_line.sequence.asc)
    cur.execute(*query)
    for line in cur:
        lines[line.payment_id].append(line)

    default_term = get_default(PaymentTerm)
    default_term_line = get_default(PaymentTermLine)
    default_term_line.pop('relativedeltas', None)
    types = {
        'procent': 'percent',
        'balance': 'remainder',
        'fixed': 'fixed',
        }
    query = payment_term.select()
    cur.execute(*query)
    for term in cur:
        payment_term = PaymentTerm(_default=False)
        set_default(payment_term, default_term)
        payment_term.name = term.name
        payment_term.active = term.active
        payment_term.description = term.note

        for line in lines.get(term.id, []):
            payment_line = PaymentTermLine(_default=False)
            set_default(payment_line, default_term_line)
            payment_line.sequence = line.sequence
            payment_line.type = types[line.value]
            if payment_line.type == 'percent':
                payment_line.percentage = (
                    Decimal(str(line.value_amount)) / Decimal(100))
            elif payment_line.type == 'fixed':
                payment_line.amount = Decimal(str(line.value_amount))
                # TODO currency
            relativedelta = payment_line.relativedeltas.new()
            relativedelta.days = line.days
            if line.days2 > 0:
                relativedelta.day = line.days2
            elif line.days2 < 0:
                relativedelta.day = 31 + line.days2 + 1
            payment_term.lines.append(payment_line)
        if payment_term.lines:
            last_line = payment_term.lines[-1]
            last_line.type = 'remainder'
        else:
            payment_term.lines.new(type='remainder')
        id2payment_terms[term.id] = payment_term
    PaymentTerm.save(list(id2payment_terms.values()))


def migrate_company(modules, cur):
    Currency = Model.get('currency.currency')
    User = Model.get('res.user')

    company = Table('res_company')
    currency = Table('res_currency')
    query = company.join(currency,
        condition=company.currency_id == currency.id
        ).select(getattr(company, '*'), currency.name.as_('currency_code'))
    cur.execute(*query)
    oe_company, = cur.fetchall()  # XXX limit to one company

    company_config = Wizard('company.company.config')
    company_config.execute('company')
    company = company_config.form
    company.party = id2party[oe_company.partner_id]
    company.currency, = Currency.find([
            ('code', '=', oe_company.currency_code),
            ])
    company_config.execute('add')

    current_config = config.get_config()
    current_config.set_context(
        context=User.get_preferences(True, current_config.context))


user2employee = defaultdict()


def migrate_employee(modules, cur):
    Party = Model.get('party.party')
    Employee = Model.get('company.employee')
    Company = Model.get('company.company')

    company, = Company.find([])

    for login, name in user2employee.items():
        party = Party(name=name)
        employee = Employee(party=party, company=company)
        user2employee[login] = employee

    default_party = Party(name='Migration')
    default_employee = Employee(party=default_party, company=company)
    Party.save([e.party for e in user2employee.values()] + [default_party])
    Employee.save(list(user2employee.values()) + [default_employee])
    user2employee.default_factory = lambda: default_employee


def create_chart_of_account(template, receivable, payable):
    AccountTemplate = Model.get('account.account.template')
    Company = Model.get('company.company')
    Account = Model.get('account.account')

    create_chart = Wizard('account.create_chart')
    create_chart.execute('account')
    create_chart.form.account_template, = AccountTemplate.find([
            ('parent', '=', None),
            ('name', '=', template),
            ])
    create_chart.form.company, = Company.find([])
    create_chart.execute('create_account')
    create_chart.form.account_receivable, = Account.find([
            ('code', '=', receivable),
            ])
    create_chart.form.account_payable, = Account.find([
            ('code', '=', payable),
            ])
    create_chart.execute('create_properties')


uom_names = {}
tax_names = {}
tax_deductible_rates = {}
template2template = {}
product2product = {}


def migrate_product(modules, cur):
    Category = Model.get('product.category')
    Product = Model.get('product.product')
    Template = Model.get('product.template')
    Uom = Model.get('product.uom')

    default_category = get_default(Category)
    id2category = {}
    category2parent = {}
    category = Table('product_category')
    cur.execute(*category.select())
    for oe_category in cur:
        category = Category(_default=False)
        set_default(category, default_category)
        category.name = oe_category.name
        id2category[oe_category.id] = category
        if oe_category.parent_id:
            category2parent[category] = oe_category.parent_id
    Category.save(list(id2category.values()))

    #for category, parent_id in category2parent.items():
    #    category.parent = id2category[parent_id]
    #Category.save(category2parent.keys())

    product = Table('product_product')
    template = Table('product_template')
    uom = Table('product_uom')

    cost_methods = {
        'standard': 'fixed',
        'average': 'average',
        }

    name2uom = {u.name: u for u in Uom.find([])}
    cur.execute(*uom.select())
    print(cur)
    uom2uom = {u.id: name2uom[uom_names.get(u.name, u.name)] for u in cur}

    if 'account_product' in modules:
        Tax = Model.get('account.tax')

        taxes = {tax.name: tax for tax in Tax.find([
                    ('parent', '=', None),
                    ])}

        product_taxes = Table('product_taxes_rel')
        account_tax = Table('account_tax')

        customer_taxes = defaultdict(list)
        query = product_taxes.join(account_tax,
            condition=product_taxes.tax_id == account_tax.id
            ).select(product_taxes.prod_id, account_tax.name)
        cur.execute(*query)
        #for tax in cur:
        #    customer_taxes[tax.prod_id].append(
        #        taxes[tax_names.get(tax.name, tax.name)])

        product_supplier_taxes = Table('product_supplier_taxes_rel')
        supplier_taxes = defaultdict(list)
        supplier_taxes_deductible_rates = {}
        query = product_supplier_taxes.join(account_tax,
            condition=product_supplier_taxes.tax_id == account_tax.id
            ).select(product_supplier_taxes.prod_id, account_tax.name)
        cur.execute(*query)
        # for tax in cur:
        #     supplier_taxes[tax.prod_id].append(
        #         taxes[tax_names.get(tax.name, tax.name)])
        #     if tax.name in tax_deductible_rates:
        #         supplier_taxes_deductible_rates[tax.prod_id] = (
        #             tax_deductible_rates[tax.name])

    default_template = get_default(Template)
    categories_accounting = {}
    query = product.join(template,
        condition=product.product_tmpl_id == template.id
        ).select(getattr(product, '*'),
            template.uos_id,
            template.list_price,
            template.standard_price,
            template.purchase_ok,
            template.uom_id,
            template.sale_ok,
            template.name,
            template.uom_po_id,
            template.type,
            template.volume,
            template.weight,
            template.description,
            template.description_purchase,
            template.description_sale,
            template.cost_method,
            template.categ_id,
            )
    cur.execute(*query)
    for oe_product in cur:
        if template2template.get(oe_product.product_tmpl_id):
            continue
        template = Template(_default=False)
        set_default(template, default_template)
        template.name = oe_product.name

        if oe_product.type == 'product':
            template.type = 'goods'
        elif oe_product.type == 'service':
            template.type = 'service'
        elif oe_product.type == 'consu':
            template.type = 'goods'
            template.consumable = True

        if template.type != 'service' and 'product_measurements' in modules:
            if oe_product.volume:
                template.volume = oe_product.volume
                if round(template.volume, 2) != template.volume:
                    template.volume = round(template.volume * 1000, 2)
                    template.volume_uom = name2uom['Liter']
                else:
                    template.volume_uom = name2uom['Cubic meter']
            if oe_product.weight:
                template.weight = oe_product.weight
                if round(template.weight, 2) != template.weight:
                    template.weight = round(template.weight * 1000, 2)
                    template.weight_uom = name2uom['Gram']
                else:
                    template.weight_uom = name2uom['Kilogram']

        if oe_product.categ_id:
            template.category = id2category[oe_product.categ_id]
        template.list_price = Decimal(str(oe_product.list_price or 0))
        template.cost_price = Decimal(str(oe_product.standard_price or 0))
        template.cost_price_method = cost_methods[oe_product.cost_method]
        template.default_uom = uom2uom[oe_product.uom_id]
        if 'sale' in modules:
            if oe_product.uos_id:
                template.sale_uom = uom2uom[oe_product.uos_id]
                if ('sale_secondary_unit' in modules
                        and template.default_uom.category
                        != template.sale_uom.category):
                    template.sale_secondary_uom = template.sale_uom
                    template.sale_secondary_uom_factor = round(
                        1 / oe_product.uos_coeff, 12)
                    template.sale_uom = template.default_uom
            template.salable = oe_product.sale_ok
        if 'purchase' in modules:
            if oe_product.uom_po_id:
                template.purchase_uom = uom2uom[oe_product.uom_po_id]
            template.purchasable = oe_product.purchase_ok

        if 'account_product' in modules:
            cust_taxes = tuple(sorted((
                        t.id
                        for t in customer_taxes[oe_product.product_tmpl_id])))
            supp_taxes = tuple(sorted((
                        t.id
                        for t in supplier_taxes[oe_product.product_tmpl_id])))
            supp_deductible_rate = (
                supplier_taxes_deductible_rates.get(
                    oe_product.product_tmpl_id, 1))
            if cust_taxes or supp_taxes:
                key = (cust_taxes, supp_taxes, supp_deductible_rate)
                if key not in categories_accounting:
                    category_accounting = Category(
                        name="Tax (%s)" % (len(categories_accounting) + 1),
                        accounting=True,
                        customer_taxes=[Tax(t) for t in cust_taxes],
                        supplier_taxes=[Tax(t) for t in supp_taxes],
                        supplier_taxes_deductible_rate=Decimal(
                            supp_deductible_rate))
                    category_accounting.save()
                    categories_accounting[key] = category_accounting
                template.account_category = categories_accounting[key]
        del template.products[:]
        template2template[oe_product.product_tmpl_id] = template
    Template.save(list(template2template.values()))

    default_product = get_default(Product)
    products = []
    cur.execute(*query)
    for oe_product in cur:
        product = Product(_default=False)
        set_default(product, default_product)
        product.suffix_code = oe_product.default_code
        product.description = '\n'.join(filter(None,
                [oe_product.description, oe_product.description_purchase,
                    oe_product.description_sale]))
        product.active = oe_product.active
        product.template = template2template[oe_product.product_tmpl_id]
        if oe_product.ean13:
            identifier = product.identifiers.new()
            identifier.code = oe_product.ean13
            if ean.is_valid(identifier.code):
                identifier.type = 'ean'
        products.append(product)
        product2product[oe_product.id] = product
    Product.save(products)


def migrate_product_supplier(modules, cur):
    ProductSupplier = Model.get('purchase.product_supplier')
    product_supplierinfo = Table('product_supplierinfo')

    product_suppliers = []
    cur.execute(*product_supplierinfo.select(
            getattr(product_supplierinfo, '*')))
    for supplierinfo in cur:
        if supplierinfo.product_id not in template2template:
            continue
        product_supplier = ProductSupplier()
        product_supplier.template = template2template[supplierinfo.product_id]
        product_supplier.party = id2party[supplierinfo.name]
        product_supplier.name = (
            supplierinfo.product_name.strip()
            if supplierinfo.product_name else None)
        product_supplier.code = (
            supplierinfo.product_code.strip()
            if supplierinfo.product_code else None)
        product_supplier.lead_time = datetime.timedelta(
            days=supplierinfo.delay)
        product_supplier.sequence = supplierinfo.sequence
        product_suppliers.append(product_supplier)
    ProductSupplier.save(product_suppliers)


location2location = {}
warehouse2warehouse = {}


def migrate_stock(modules, cur):
    Location = Model.get('stock.location')
    location = Table('stock_location')
    warehouse = Table('stock_warehouse')

    Location.write(Location.find(
            [('type', 'in', ['warehouse', 'view', 'storage'])]), {
            'active': False,
            }, Location._config.context)

    usage2type = {
        'view': 'view',
        'internal': 'storage',
        }
    query = location.select(
        getattr(location, '*'),
        where=location.usage.in_(['view', 'internal']))
    cur.execute(*query)
    for oe_location in cur:
        location = Location()
        location.name = oe_location.name.strip()
        location.type = usage2type[oe_location.usage]
        location2location[oe_location.id] = location
    Location.save(list(location2location.values()))

    cur.execute(*query)
    for oe_location in cur:
        location = location2location[oe_location.id]
        if oe_location.location_id:
            location.parent = location2location.get(oe_location.location_id)
    Location.save(list(location2location.values()))

    query = warehouse.select(getattr(warehouse, '*'))
    cur.execute(*query)
    for oe_warehouse in cur:
        warehouse = Location(type='warehouse')
        warehouse.name = oe_warehouse.name.strip()
        location = location2location[oe_warehouse.lot_stock_id]
        location.parent = None
        location.save()
        warehouse.input_location = location
        warehouse.storage_location = location
        warehouse.output_location = location
        warehouse.save()
        location.parent = warehouse
        location.save()
        warehouse2warehouse[oe_warehouse.id] = warehouse

    while True:
        locations = Location.find([
                ('type', '=', 'view'),
                ('childs', '=', None),
                ])
        if not locations:
            break
        Location.delete(locations)


warehouse2products = {}


def migrate_product_cost_warehouse(filename):
    Product = Model.get('product.product')
    ProductConfiguration = Model.get('product.configuration')
    Location = Model.get('stock.location')

    configuration = ProductConfiguration(1)
    configuration.cost_price_warehouse = True
    configuration.save()
    pconfig = config.get_config()

    decoder = PYSONDecoder()
    cost_price_digits = decoder.decode(
        Product._fields['cost_price']['digits'])[1]

    warehouses = Location.find([('type', '=', 'warehouse')])
    for warehouse in warehouses:
        with pconfig.set_context(warehouse=warehouse.id):
            products = Product.find([])
            id2product = {p.id: p for p in products}
            warehouse2products[warehouse.id] = id2product
            with open(filename, 'r') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    if (warehouse2warehouse[int(row['warehouse_id'])].id
                            != warehouse.id):
                        continue
                    try:
                        product = product2product[int(row['product_id'])]
                    except KeyError:
                        print(
                            "Ignoring product_id: %s" % row['product_id'],
                            file=sys.stderr)
                        continue
                    product = id2product[product.id]
                    product.cost_price = round(
                        Decimal(row['cost_price']), cost_price_digits)
            Product.save(products)


def migrate_stock_levels(modules, cur):
    Location = Model.get('stock.location')
    Move = Model.get('stock.move')
    move = Table('stock_move')

    supplier_location, = Location.find([('type', '=', 'supplier')], limit=1)
    moves = []
    query = move.select(
        move.location_dest_id.as_('location'),
        move.product_id.as_('product'),
        Sum(move.product_qty).as_('quantity'),
        where=move.state == 'done',
        group_by=[move.location_dest_id, move.product_id])
    query |= move.select(
        move.location_id.as_('location'),
        move.product_id.as_('product'),
        (-Sum(move.product_qty)).as_('quantity'),
        where=move.state == 'done',
        group_by=[move.location_id, move.product_id])
    query = query.select(
        query.location,
        query.product,
        Sum(query.quantity).as_('quantity'),
        group_by=[query.location, query.product])
    cur.execute(*query)
    for oe_location, oe_product, quantity in cur:
        if oe_location not in location2location:
            continue
        if oe_product not in product2product:
            continue
        move = Move()
        move.product = product2product[oe_product]
        move.quantity = round(quantity, move.uom.digits)
        if move.quantity <= 0:
            continue
        move.from_location = supplier_location
        move.to_location = location2location[oe_location]
        if 'product_cost_warehouse' in modules and move.to_location.warehouse:
            id2product = warehouse2products[move.to_location.warehouse.id]
            move.unit_price = id2product[move.product.id].cost_price
        else:
            move.unit_price = move.product.cost_price
        moves.append(move)
    Move.save(moves)
    pconfig = config.get_config()
    user = pconfig.user
    pconfig.user = 0
    Move.click(moves, 'do')
    pconfig.user = user


sale2sale = {}
unknown_term = None


def migrate_sale(modules, cur):
    Sale = Model.get('sale.sale')
    SaleLine = Model.get('sale.line')
    Uom = Model.get('product.uom')
    PaymentTerm = Model.get('account.invoice.payment_term')

    global unknown_term
    unknown_term = PaymentTerm(name='Unknown', active=False)
    unknown_term.lines.new(type='remainder')
    unknown_term.save()

    default_sale = get_default(Sale)
    sale_order = Table('sale_order')
    query = sale_order.select(where=sale_order.state != 'cancel')
    cur.execute(*query)
    for order in cur:
        sale = Sale(_default=False)
        set_default(sale, default_sale)
        sale.invoice_method = 'manual'
        sale.shipment_method = 'manual'
        sale.reference = order.name
        sale.party = id2party[order.partner_id]
        sale.description = order.client_order_ref
        sale.sale_date = order.date_order
        if order.payment_term:
            sale.payment_term = id2payment_terms[order.payment_term]
        else:
            sale.payment_term = unknown_term
        # TODO currency
        sale.comment = order.note
        if order.state == 'draft':
            sale.state = 'draft'
        else:
            sale.state = 'done'
        if not sale.invoice_address or not sale.shipment_address:
            new_address = sale.party.addresses.new()
            new_address.save()
            if not sale.invoice_address:
                sale.invoice_address = new_address
            if not sale.shipment_address:
                sale.shipment_address = new_address
        sale2sale[order.id] = sale

    name2uom = {u.name: u for u in Uom.find([])}

    default_line = get_default(SaleLine)
    sale_line = Table('sale_order_line')
    uom = Table('product_uom')
    query = sale_line.join(sale_order,
        condition=sale_line.order_id == sale_order.id
        ).join(uom, 'LEFT',
            condition=sale_line.product_uom == uom.id
            ).select(getattr(sale_line, '*'), uom.name.as_('uom_name'),
                where=sale_order.state != 'cancel')
    cur.execute(*query)
    for order_line in cur:
        sale = sale2sale[order_line.order_id]
        line = SaleLine(_default=False)
        set_default(line, default_line)
        sale.lines.append(line)
        line.sequence = order_line.sequence
        line.product = product2product.get(order_line.product_id)
        if order_line.uom_name:
            line.unit = name2uom[uom_names.get(
                    order_line.uom_name, order_line.uom_name)]
        line.quantity = order_line.product_uom_qty
        line.unit_price = (Decimal(str(order_line.price_unit))
            * (1 - Decimal(str(order_line.discount)) / 100))
        line.description = order_line.name
        line.note = order_line.notes
        if sale.state == 'done':
            del line.taxes[:]

    # TODO add taxes on lines

    Sale.save(list(sale2sale.values()))


lead_section = []
opportunity_section = []
lost_stage = []


def migrate_opportunity(modules, cur):
    Opportunity = Model.get('sale.opportunity')
    Company = Model.get('company.company')
    Party = Model.get('party.party')
    Configuration = Model.get('sale.configuration')

    company, = Company.find([])

    # Create missing parties first because of on_change_party
    default_party = get_default(Party)
    parties = {}
    case = Table('crm_case')
    cur.execute(*case.select())
    for case in cur:
        if case.partner_id:
            parties[case.id] = id2party[case.partner_id]
        elif case.partner_name or case.email_from:
            party = Party(_default=False)
            set_default(party, default_party)
            party.name = case.partner_name or case.email_from
            if case.email_from:
                party.contact_mechanisms.new(type='email',
                    value=case.email_from, comment=case.partner_name2)
            if case.partner_mobile:
                party.contact_mechanisms.new(type='mobile',
                    value=case.partner_mobile)
            if case.partner_phone:
                party.contact_mechanisms.new(type='phone',
                    value=case.partner_phone)
            del party.addresses[:]
            parties[case.id] = party
    Party.save(list(parties.values()))

    sale = Table('sale_order')
    cur.execute(*sale.select(sale.id, sale.payment_term,
            where=sale.payment_term != Null))
    sale2term = {s.id: id2payment_terms[s.payment_term] for s in cur}

    def get_payment_term(ref):
        target, sale_id = ref.split(',')
        assert target == 'sale.order'
        sale_id = int(sale_id)
        return sale2term.get(sale_id, unknown_term)

    default_states = {
        'draft': 'lead',
        'open': 'opportunity',
        'pending': 'lead',
        'done': 'converted',
        'cancel': 'cancelled',
        }
    lead_states = {
        'draft': 'lead',
        'open': 'lead',
        'pending': 'lead',
        'done': 'converted',
        'cancel': 'cancelled',
        }
    opportunity_states = {
        'draft': 'opportunity',
        'open': 'opportunity',
        'pending': 'opportunity',
        'done': 'converted',
        'cancel': 'lost',
        }

    default_opportunity = get_default(Opportunity)
    opportunities = []
    max_id = 0
    case = Table('crm_case')
    user = Table('res_users')
    cur.execute(*case.join(user,
            condition=case.user_id == user.id
            ).select(getattr(case, '*'), user.login.as_('user_login')))
    for case in cur:
        opportunity = Opportunity(_default=False)
        set_default(opportunity, default_opportunity)
        opportunity.party = parties.get(case.id)
        opportunity.start_date = case.date or case.create_date
        opportunity.description = case.name
        opportunity.reference = str(case.id)
        max_id = max(max_id, case.id)
        # TODO currency
        opportunity.amount = Decimal(str(case.planned_revenue))
        opportunity.probability = max(min(int(case.probability), 100), 0)
        if case.section_id in lead_section:
            state = lead_states[case.state]
        elif case.section_id in opportunity_section:
            state = opportunity_states[case.state]
        else:
            state = default_states[case.state]
        if case.ref:
            state = 'converted'
        if state == 'converted':
            if not case.ref:
                if case.stage_id in lost_stage:
                    state = 'lost'
                else:
                    state = 'cancelled'
            else:
                opportunity.payment_term = get_payment_term(case.ref)
                if case.ref.startswith('sale.order,'):
                    _, sale_id = case.ref.split(',')
                    opportunity.sale = sale2sale.get(int(sale_id))
        if (case.stage_id in lost_stage
                and state not in ['converted', 'cancelled']):
            state = 'lost'
        if state == 'opportunity' and not opportunity.party:
            state = 'lead'
        opportunity.state = state
        opportunity.comment = case.note
        opportunity.employee = user2employee[case.user_login]
        opportunities.append(opportunity)
    Opportunity.save(opportunities)

    # Reset the sequence
    configuration = Configuration(1)
    configuration.sale_opportunity_sequence.number_next = max_id + 1
    configuration.sale_opportunity_sequence.save()


purchase2purchase = {}


def migrate_purchase(modules, cur):
    Purchase = Model.get('purchase.purchase')
    PurchaseLine = Model.get('purchase.line')
    Uom = Model.get('product.uom')
    PaymentTerm = Model.get('account.invoice.payment_term')

    unknown_term = PaymentTerm(name='Unknown', active=False)
    unknown_term.lines.new(type='remainder')
    unknown_term.save()

    default_purchase = get_default(Purchase)
    purchase_order = Table('purchase_order')
    query = purchase_order.select(
        where=~purchase_order.state.in_(['draft', 'cancel']))
    cur.execute(*query)
    for order in cur:
        purchase = Purchase(_default=False)
        set_default(purchase, default_purchase)
        purchase.invoice_method = 'manual'
        purchase.reference = order.name
        purchase.supplier_reference = order.partner_ref
        purchase.party = id2party[order.partner_id]
        purchase.purchase_date = order.date_order
        purchase.payment_term = unknown_term
        # TODO currency
        purchase.comment = order.notes
        purchase.state = 'done'
        if not purchase.invoice_address:
            new_address = purchase.party.addresses.new()
            new_address.save()
            purchase.invoice_address = new_address
        purchase2purchase[order.id] = purchase

    name2uom = {u.name: u for u in Uom.find([])}

    default_line = get_default(PurchaseLine)
    purchase_line = Table('purchase_order_line')
    uom = Table('product_uom')
    query = purchase_line.join(purchase_order,
        condition=purchase_line.order_id == purchase_order.id
        ).join(uom, 'LEFT',
            condition=purchase_line.product_uom == uom.id
            ).select(getattr(purchase_line, '*'), uom.name.as_('uom_name'),
                where=~purchase_order.state.in_(['draft', 'cancel']))
    cur.execute(*query)
    for order_line in cur:
        purchase = purchase2purchase[order_line.order_id]
        line = PurchaseLine(_default=False)
        set_default(line, default_line)
        purchase.lines.append(line)
        line.product = product2product.get(order_line.product_id)
        if order_line.uom_name:
            line.unit = name2uom[uom_names.get(
                    order_line.uom_name, order_line.uom_name)]
        line.quantity = order_line.product_qty
        line.unit_price = Decimal(str(order_line.price_unit))
        line.description = order_line.name
        line.note = order_line.notes
        del line.taxes[:]

    # TODO add taxes on lines

    Purchase.save(list(purchase2purchase.values()))


invoice2invoice = {}
journal_names = {}
account_codes = {}


def get_account(code, code2account):
    account = None
    code = account_codes.get(code, code)
    for i in range(len(code) + 1):
        for strip in [account_codes.get(code[:i] + '*'), code[:i]]:
            if strip in code2account:
                account = code2account[strip]
    assert account, code
    return account


def migrate_invoice(modules, cur):
    Invoice = Model.get('account.invoice')
    InvoiceLine = Model.get('account.invoice.line')
    InvoiceTax = Model.get('account.invoice.tax')
    Uom = Model.get('product.uom')
    PaymentTerm = Model.get('account.invoice.payment_term')
    Journal = Model.get('account.journal')
    Account = Model.get('account.account')

    unknown_term = PaymentTerm(name='Unknown', active=False)
    unknown_term.lines.new(type='remainder')
    unknown_term.save()

    code2journal = {j.code: j for j in Journal.find([])}
    code2account = {a.code: a for a in Account.find([
                ('kind', '!=', 'view'),
                ])}

    types = {
        'in_invoice': 'in_invoice',
        'in_refund': 'in_credit_note',
        'out_invoice': 'out_invoice',
        'out_refund': 'out_credit_note',
        }

    default_invoice = get_default(Invoice)
    invoice_order = Table('account_invoice')
    journal = Table('account_journal')
    account = Table('account_account')
    query = invoice_order.join(journal,
        condition=invoice_order.journal_id == journal.id
        ).join(account,
            condition=invoice_order.account_id == account.id
        ).select(getattr(invoice_order, '*'),
            journal.code.as_('journal_code'),
            account.code.as_('account_code'),
            where=invoice_order.state.in_(['open', 'paid']))
    cur.execute(*query)
    for order in cur:
        invoice = Invoice(_default=False)
        set_default(invoice, default_invoice)
        invoice.type = types[order.type]
        invoice.number = order.number
        invoice.reference = order.reference
        invoice.description = order.name
        invoice.invoice_date = order.date_invoice
        invoice.party = id2party[order.partner_id]
        # TODO currency
        try:
            invoice.journal = code2journal[
                journal_names.get(order.journal_code, order.journal_code)]
        except KeyError:
            pass  # Let the default one
        invoice.account = get_account(order.account_code, code2account)
        if order.payment_term:
            invoice.payment_term = id2payment_terms[order.payment_term]
        else:
            invoice.payment_term = unknown_term
        invoice.comment = order.comment
        if not invoice.invoice_address:
            new_address = invoice.party.addresses.new()
            new_address.save()
            invoice.invoice_address = new_address
        invoice2invoice[order.id] = invoice

    name2uom = {u.name: u for u in Uom.find([])}

    default_line = get_default(InvoiceLine)
    invoice_line = Table('account_invoice_line')
    uom = Table('product_uom')
    query = invoice_line.join(invoice_order,
        condition=invoice_line.invoice_id == invoice_order.id
        ).join(uom, 'LEFT',
            condition=invoice_line.uos_id == uom.id
            ).join(account,
                condition=invoice_line.account_id == account.id
                ).select(getattr(invoice_line, '*'),
                    uom.name.as_('uom_name'),
                    account.code.as_('account_code'),
                    where=invoice_order.state.in_(['open', 'paid']))
    cur.execute(*query)
    for invoice_line in cur:
        invoice = invoice2invoice[invoice_line.invoice_id]
        line = InvoiceLine(_default=False)
        set_default(line, default_line)
        invoice.lines.append(line)
        line.product = product2product.get(invoice_line.product_id)
        line.quantity = invoice_line.quantity
        if invoice_line.uom_name:
            line.unit = name2uom[uom_names.get(
                    invoice_line.uom_name, invoice_line.uom_name)]
        line.account = get_account(invoice_line.account_code, code2account)
        if invoice.type in ['out_invoice', 'out_credit_note']:
            if line.account.kind != 'revenue':
                line.account.kind = 'revenue'
                line.account.save()
        elif invoice.type in ['in_invoice', 'in_credit_note']:
            if line.account.kind != 'expense':
                line.account.kind = 'expense'
                line.account.save()
        line.unit_price = (Decimal(str(invoice_line.price_unit))
            * (1 - Decimal(str(invoice_line.discount)) / 100))
        line.description = invoice_line.name
        if invoice_line.note:
            line.description += '\n' + invoice_line.note
        while line.taxes:
            line.taxes.pop()

    default_tax = get_default(InvoiceTax)
    tax = Table('account_invoice_tax')
    query = tax.join(invoice_order,
        condition=tax.invoice_id == invoice_order.id
        ).join(account,
            condition=tax.account_id == account.id
            ).select(getattr(tax, '*'),
                account.code.as_('account_code'),
                where=invoice_order.state.in_(['open', 'paid']))
    cur.execute(*query)
    for otax in cur:
        invoice = invoice2invoice[otax.invoice_id]
        tax = InvoiceTax(_default=False)
        set_default(tax, default_tax)
        invoice.taxes.append(tax)
        tax.description = otax.name
        tax.sequence = otax.sequence
        tax.account = get_account(otax.account_code, code2account)
        tax.base = otax.base_amount
        tax.amount = otax.amount
        tax.manual = True
        # TODO code and tax

    Invoice.save(list(invoice2invoice.values()))
    for invoice in invoice2invoice.values():
        invoice.state = 'paid'
    Invoice.save(list(invoice2invoice.values()))


def migrate_fiscalyear(modules, cur):
    FiscalYear = Model.get('account.fiscalyear')
    Sequence = Model.get('ir.sequence')
    SequenceStrict = Model.get('ir.sequence.strict')
    SequenceType = Model.get('ir.sequence.type')

    fiscalyear = Table('account_fiscalyear')

    query = fiscalyear.select(
        order_by=fiscalyear.date_start.desc,
        limit=1)
    cur.execute(*query)
    fiscalyear, = cur.fetchall()

    new_fiscalyear = FiscalYear()
    new_fiscalyear.name = fiscalyear.name
    new_fiscalyear.start_date = fiscalyear.date_start
    new_fiscalyear.end_date = fiscalyear.date_stop
    sequence = Sequence(name=fiscalyear.name)
    sequence.sequence_type, = SequenceType.find([
            ('name', '=', "Account Move"),
            ])
    # TODO set number
    sequence.save()
    new_fiscalyear.post_move_sequence = sequence

    if 'account_invoice' in modules:
        invoice_sequence, = new_fiscalyear.invoice_sequences
        for name, field in [
                ('Customer Invoice', 'out_invoice_sequence'),
                ('Supplier Invoice', 'in_invoice_sequence'),
                ('Customer Credit Note', 'out_credit_note_sequence'),
                ('Supplier Credit Note', 'in_credit_note_sequence'),
                ]:
            sequence = SequenceStrict(name='%s %s' % (name, fiscalyear.name))
            sequence.sequence_type, = SequenceType.find([
                    ('name', '=', "Invoice"),
                    ])
            # TODO set number
            sequence.save()
            setattr(invoice_sequence, field, sequence)
    new_fiscalyear.save()


def migrate_account_balance(modules, cur):
    Move = Model.get('account.move')
    Line = Model.get('account.move.line')
    Account = Model.get('account.account')
    FiscalYear = Model.get('account.fiscalyear')
    Period = Model.get('account.period')
    Journal = Model.get('account.journal')
    Sequence = Model.get('ir.sequence')

    fiscalyear, = FiscalYear.find([])

    today = datetime.date.today()
    period = Period(name='Migration',
        start_date=today, end_date=today,
        fiscalyear=fiscalyear, type='adjustment')
    period.save()

    code2account = {a.code: a for a in Account.find([
                ('type', '!=', None),
                ('closed', '!=', True),
                ])}

    journal = Journal(name='Migration', type='situation')
    journal.sequence, = Sequence.find(
        [('sequence_type.name', '=', "Account Journal")])
    journal.save()

    move = Move()
    move.date = today
    move.period = period
    move.journal = journal
    move.save()

    line = Table('account_move_line')
    account = Table('account_account')
    account_move = Table('account_move')
    period = Table('account_period')
    fiscalyear = Table('account_fiscalyear')
    query = line.join(account,
        condition=line.account_id == account.id
        ).join(account_move,
            condition=line.move_id == account_move.id
            ).join(period,
                condition=account_move.period_id == period.id
                ).join(fiscalyear,
                    condition=period.fiscalyear_id == fiscalyear.id
                    )
    query = query.select(
        Sum(Coalesce(line.debit, 0) - Coalesce(line.credit, 0)).as_('balance'),
        account.code, line.partner_id,
        where=line.state == 'valid',
        group_by=[account.id, account.code, line.partner_id])
    cur.execute(*query)
    vlist = []
    for line in cur:
        values = {
            'move': move.id,
            }
        if line.balance > 0:
            values['debit'] = line.balance
        elif line.balance < 0:
            values['credit'] = -line.balance
        else:
            continue
        account = get_account(line.code, code2account)
        values['account'] = account.id
        if account.party_required:
            assert line.partner_id, line.code
            values['party'] = id2party[line.partner_id].id
        vlist.append(values)
        if len(vlist) > 1000:
            Line.create(vlist, Line._config.context)
            vlist.clear()
    if vlist:
        Line.create(vlist, Line._config.context)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-m', '--module', dest='modules', nargs='+',
        default=[], metavar='MODULE', help='module to migrate')
    parser.add_argument('-l', '--language', dest='languages', nargs='+',
        default=[], metavar='LANGUAGE', help='language to activate')
    parser.add_argument('-oe', dest='oe_database', required=True)
    parser.add_argument('-d', '--database', dest='tryton_database',
        required=True)
    parser.add_argument('--identifier', dest='identifiers', nargs='+',
        default=['eu_vat'], metavar='TYPE',
        help="identifiers type to try for VAT")
    parser.add_argument('--uom', dest='uom',
        help='JSON file for UOM migration')
    parser.add_argument('--load_uom', dest='load_uom',
        help='CSV file of UOM to load')
    parser.add_argument('--tax', dest='tax',
        help='JSON file for Tax migration')
    parser.add_argument('--tax-deductible-rate', dest='tax_deductible_rate',
        help='JSON file for Tax deductible rate migration')
    parser.add_argument('--journal', dest='journal',
        help='JSON file for Journal migration')
    parser.add_argument('--account', dest='account',
        help='JSON file for Account migration')
    parser.add_argument('--load_account', dest='load_account',
        help='CSV file of Account to load')
    parser.add_argument('--load-product-cost-warehouse',
        dest='load_product_cost_warehouse',
        help="CSV file of product, warehouse, cost_price")
    parser.add_argument('--user-employee', dest='user_employee',
        help='JSON file for User / Employee mapping')
    parser.add_argument('--lost_stage', dest='lost_stage',
        help='JSON file with lost stage ids')
    parser.add_argument('--lead_section', dest='lead_section',
        help='JSON file with lead section ids')
    parser.add_argument('--opportunity_section', dest='opportunity_section',
        help='JSON file with opportunity section ids')

    args = parser.parse_args()

    if args.identifiers:
        identifier_types.extend(args.identifiers)

    if args.uom:
        uom_names.update(json.load(open(args.uom)))

    if args.tax:
        tax_names.update(json.load(open(args.tax)))

    if args.tax_deductible_rate:
        tax_deductible_rates.update(json.load(open(args.tax_deductible_rate)))

    if args.journal:
        journal_names.update(json.load(open(args.journal)))

    if args.account:
        account_codes.update(json.load(open(args.account)))

    if args.user_employee:
        user2employee.update(json.load(open(args.user_employee)))

    if args.lost_stage:
        lost_stage.extend(json.load(open(args.lost_stage)))

    if args.lead_section:
        lead_section.extend(json.load(open(args.lead_section)))

    if args.opportunity_section:
        opportunity_section.extend(json.load(open(args.opportunity_section)))

    main(args.oe_database, args.tryton_database, args.modules, args.languages,
        {
            'uom': args.load_uom,
            'account': args.load_account,
            'product_cost_warehouse': args.load_product_cost_warehouse,
            })

# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from string import Template
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.model import ModelView, ModelSQL, DeactivableMixin, sequence_ordered
from trytond.pyson import Bool, Eval
from trytond.transaction import Transaction
import re

__all__ = ['PLBaseParty', 'PLBasePartyType', 'PLBasePartyLang', 'PLBaseAddress', 'PLBasePartyTitle']

PARTY_TITLE = [
    ('', ''),
    ('mr', 'Mr'),
    ('mr&mrs', 'Mr & Mrs'),
    ('mrs', 'Mrs'),
    ('me', 'Me'),
    ('dr', 'Dr'),
    #('prof', 'Prof'),
]


def normalize_iban(iban):
    if not iban:
        return ''
    return re.sub(r'\s+', '', iban).upper()


def format_iban(iban):
    """
    Format IBAN as: XXXX XXXX XXXX XXXX XXXX X
    """
    iban = normalize_iban(iban)
    return ' '.join(iban[i:i+4] for i in range(0, len(iban), 4))

class PLBasePartyLang(ModelSQL, ModelView):
    'En français par défaut'
    __name__ = 'party.party_lang'

    #@staticmethod
    #def default_lang():
    #    return 11

class PLBasePartyType(ModelSQL, ModelView, DeactivableMixin):
    'Party_type'
    __name__ = 'pl_cust_plbase.partytype'

    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code', required=True, translate=False)

class PLBasePartyTitle(ModelSQL, ModelView):
    'Party_Title'
    __name__ = 'pl_cust_plbase.partytitle'

    name = fields.Char('Name', required=True, translate=True)
    addr = fields.Char('addr', required=True, translate=True)
    sal = fields.Char('sal', required=True, translate=True)
    code = fields.Char('Code', required=True, translate=False)

class PLBaseParty(ModelSQL, ModelView):
    'PLBase Party'
    __name__ = 'party.party'

    #party_type = fields.Selection(PARTY_TYPE, 'Type'
    # 
    # )
    nickname = fields.Char('Nickname')
    description = fields.Char('Description')
    party_type = fields.Selection('get_party_type', 'Type', sort=True)
    party_title = fields.Selection('get_party_title', 'Title',
                                   states={
                                       'invisible': Eval('is_person_moral', False),
                                   },
                                   depends=['is_person_moral'])

    party_title_string = party_title.translated('party_title')

    birthdate = fields.Date('Birthdate',
                            states={
                                'invisible': Eval('is_person_moral', False),
                            },
                            depends=['is_person_moral'])
    notes = fields.Text('Comment')
    
    firstname = fields.Char('Firstname',
                            states={
                                'invisible': Eval('is_person_moral', False),
                            },
                            depends=['is_person_moral'])

    lastname = fields.Char('Lastname', required=True)
    prof = fields.Char('Profession',
                       states={
                           'invisible': Eval('is_person_moral', False),
                       },
                       depends=['is_person_moral'])
    organisation = fields.Char('Organisation',
                               states={
                                   'invisible': Eval('is_person_moral', False),
                               },
                               depends=['is_person_moral'])
    is_person_moral = fields.Boolean('Person Moral ?')
    
    iban = fields.Char('IBAN')
    default_category_account_expense = fields.Many2One(
            'account.account', 'Default Account Expense')
    default_category_account_revenue = fields.Many2One(
            'account.account', 'Default Account Revenue')

    default_tax_expense = fields.Many2One(
        'account.tax', "Tax Expense", ondelete='RESTRICT')
    default_tax_revenue = fields.Many2One(
        'account.tax', "Tax Revenue", ondelete='RESTRICT')
    
    iban_formatted = fields.Function(
        fields.Char("IBAN", readonly=True),
        'get_iban_formatted'
    )

    def get_iban_formatted(self, name):
        return format_iban(self.iban)

    @fields.depends('iban')
    def on_change_iban(self):
        if self.iban:
            self.iban = normalize_iban(self.iban)

    @classmethod
    def get_party_type(cls):
        PARTYTYPE = Pool().get('pl_cust_plbase.partytype')
        all_type = PARTYTYPE.search([])
        return [('', '')] + [(ft.code, ft.name) for ft in all_type]

    @staticmethod
    def default_party_type():
        return ''

    
    @classmethod
    def get_party_title(cls):
        PARTYTITLE = Pool().get('pl_cust_plbase.partytitle')
        all_title = PARTYTITLE.search([])
        return [('','')] + [(ft.code, ft.name) for ft in all_title]

    @staticmethod
    def default_party_title():
        return ''

    def get_full_name(self, name):
        return '{}{}{}'.format(self.party_title and '{} '.format(self.party_title_string) or '', self.firstname and '{} '.format(self.firstname) or '', self.lastname or '') 

    def get_rec_name(self, name):
        if self.lastname and self.firstname :
            return '{} {}'.format(self.firstname,self.lastname)
        else :
            return '{}'.format(self.lastname)

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
                ('lastname',) + tuple(clause[1:]),
                ('firstname',) + tuple(clause[1:]),
                ('nickname',) + tuple(clause[1:]),
                ('addresses.contact_name',) + tuple(clause[1:]),
                ]

    @fields.depends('firstname', 'lastname')
    def on_change_is_person_moral(self):
        if self.firstname:
            self.firstname = ''

    @classmethod
    def create(cls, vlist):
        vlist = [x.copy() for x in vlist]
        for values in vlist:
            #if not values.get('code'):
            #    values['code'] = cls._new_code()
            values.setdefault('addresses', None)
            if values.get('firstname') or values.get('lastname'):
                values['name'] = '{} {}'.format(values.get(
                    'lastname', ''), values.get('firstname', ''))
        return super().create(vlist)

    @classmethod
    def write(cls, *args):
        super().write(*args)

        to_write = []

        actions = iter(args)
        for partys, values in zip(actions, actions):

            for party in partys:
                if 'firstname' in values.keys() or 'lastname' in values.keys():
                    fn = party.firstname
                    ln = party.lastname

                    if 'firstname' in values.keys():
                        fn = values.get('firstname')

                    if 'lastname' in values.keys():
                        ln = values.get('lastname')

                    to_write.extend(([party], {
                        'name': '{}{}'.format(ln or '', fn and ' {}'.format(fn) or '')}))

        if to_write:
            cls.write(*to_write)


class PLBaseAddress(sequence_ordered(), ModelSQL, ModelView):
    'PLBase Address'
    __name__ = 'party.address'

    type = fields.Char('Address Type')

    panettone = fields.Boolean('Panettone')
    carte = fields.Boolean('Carte de voeux')

    addr_street = fields.Char('Address Street')
    addr_street_num = fields.Char('Address Num')
    contact_name = fields.Char('Contact Name')
    contact_firstname = fields.Char('Contact FirstName')
    contact_title = fields.Selection('get_party_title', 'Title')
    contact_function = fields.Char('Contact Function')
    contact_phone = fields.Char('Contact Phone')
    contact_phone2 = fields.Char('Contact Phone 2')
    contact_mail = fields.Char('Contact Mail')
    addr_compl = fields.Char('Address Compl')
    addr_compl2 = fields.Char('Address Compl2')
    format_ = fields.Text("Format", required=True,
                          help="Available variables (also in upper case):\n"
                          "- ${party_name}\n"
                          "- ${name}\n"
                          "- ${attn}\n"
                          "- ${contact_firstname}\n"
                          "- ${contact_name}\n"
                          "- ${compl}\n"
                          "- ${num_street}\n"
                          "- ${street}\n"
                          "- ${compl2}\n"
                          "- ${zip}\n"
                          "- ${city}\n"
                          "- ${subdivision}\n"
                          "- ${subdivision_code}\n"
                          "- ${country}\n"
                          "- ${country_code}")

        
    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order = [
            ('contact_name', 'ASC'),
        ]

    @classmethod
    def default_format_(cls):
        return """${party_name}
${compl}
${street} ${num_street}
${compl2}
${postal_code} ${city}
${country}
${contact}"""

    @classmethod
    def get_party_title(cls):
        PARTYTITLE = Pool().get('pl_cust_plbase.partytitle')
        all_title = PARTYTITLE.search([])
        return [('','')] + [(ft.code, ft.name) for ft in all_title]

    def get_full_address(self, name):
        pool = Pool()
        AddressFormat = pool.get('party.address.format')
        full_address = Template(self.default_format_()).substitute(
            **self._get_address_substitutions())
        return '\n'.join(
            filter(None, (x.strip() for x in full_address.splitlines())))

    def myparty_full_name(self):
        name = '-'
        #if self.party_name:
        #    name = self.party_name
        print('******************')
        print(self.party)
        if self.party and not self.party.is_person_moral:
            name = '{}{}{}'.format(self.party.party_title and '{}\n'.format(self.party.party_title_string) or '', self.party.firstname and '{} '.format(self.party.firstname) or '', self.party.lastname or '') 

            #name = """{} {} {}
            #""".format(self.party.title and self.party.party_title_string.title(),
            #           self.party.firstname and self.party.firstname.title(),
            #           self.party.lastname and self.party.lastname.title())
        else :
            name = self.party.name

        return name

    def mycontact_full_name(self):
        txt = ''
        #if self.party_name:
        #    name = self.party_name
        print('******************')
        print(self.party)
        title = ''
        if self.contact_title :
            PARTYTITLE = Pool().get('pl_cust_plbase.partytitle')
            title = PARTYTITLE(PARTYTITLE.search(['code', '=', self.contact_title])[0])
        if self.contact_name :
            t = title and title.addr and '{} '.format(title.addr) or ''
            txt = "A l'att de {}{}{}".format(t, self.contact_firstname and '{} '.format(self.contact_firstname) or '', self.contact_name or '')

        return txt
    
    def _get_address_substitutions(self):
        context = Transaction().context
        subdivision_code = ''
        if getattr(self, 'subdivision', None):
            subdivision_code = self.subdivision.code or ''
            if '-' in subdivision_code:
                subdivision_code = subdivision_code.split('-', 1)[1]
        substitutions = {
            'party_name': self.myparty_full_name(),
            'attn': '',
            'name': getattr(self, 'name', None) or '',
            'contact' : self.mycontact_full_name(),
            'contact_firstname': getattr(self, 'contact_firstname', None) and '{} '.format(getattr(self, 'contact_firstname', None)) or '',
            'contact_name': getattr(self, 'contact_name', None) or '',
            'compl': getattr(self, 'addr_compl', None) or '',
            'street': getattr(self, 'addr_street', None) or '',
            'num_street': getattr(self, 'addr_street_num', None) or '',
            'compl2': getattr(self, 'addr_compl2', None) or '',
            'postal_code': getattr(self, 'postal_code', None) or '',
            'city': getattr(self, 'city', None) or '',
            'subdivision': (self.subdivision.name
                            if getattr(self, 'subdivision', None) else ''),
            'subdivision_code': subdivision_code,
            'country': (self.country.name
                        if getattr(self, 'country', None) and self.country.code != 'CH' else ''),
            'country_code': (self.country.code or ''
                             if getattr(self, 'country', None) else ''),
        }
        if context.get('address_from_country') == getattr(self, 'country', ''):
            substitutions['country'] = ''
        if context.get('address_attention_party', False):
            substitutions['attn'] = (
                context['address_attention_party'].full_name)
        for key, value in list(substitutions.items()):
            substitutions[key.upper()] = value.upper()
        return substitutions


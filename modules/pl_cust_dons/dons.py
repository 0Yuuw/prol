from trytond.model import ModelSQL, ModelView, fields, DeactivableMixin
from trytond.pool import Pool, PoolMeta
from trytond.exceptions import UserError
from trytond.pyson import Eval



__all__ = ['Dons', 'TypeDonateur', 'TypeDons', 'Party']


class Dons(ModelSQL, ModelView):
    'Dons'
    __name__ = 'pl_cust_dons.dons'

    name = fields.Char("N°")
    date = fields.Date('Date', required=True)
    type = fields.Many2One('pl_cust_dons.type_dons', 'Type of donation', required=True)
    donator = fields.Many2One('party.party', 'Donator', required=True)
    amount = fields.Numeric('Amount (CHF)', required=True)
    formatted_amount = fields.Function(
        fields.Char("Amount (formatted)"),
        'get_formatted_amount'
    )
    notes = fields.Text('Notes')

    complement = fields.Char('Complement')
    attestation_sent = fields.Boolean('Attestation sent')
    no_att = fields.Boolean('No attestation')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order = [
            ("date", "DESC"),
        ]
        
    @staticmethod
    def default_attestation_sent():
        return False

    def get_formatted_amount(self, name):
        def format_chf(amount):
            return f"{amount:,.2f}".replace(",", "'")
        return format_chf(self.amount) if self.amount is not None else "0.00"



class TypeDonateur(ModelSQL, ModelView):
    'Type Donateur'
    __name__ = 'pl_cust_dons.type_donateur'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    contacts = fields.One2Many('party.party', 'type_donateur', 'Contacts')


class TypeDons(ModelSQL, ModelView, DeactivableMixin):
    'Type Dons'
    __name__ = 'pl_cust_dons.type_dons'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    dons = fields.One2Many('pl_cust_dons.dons', 'type', 'Dons')

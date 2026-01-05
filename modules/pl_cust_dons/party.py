from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import PoolMeta
from datetime import date

__all__ = ['Party']

class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    type_donateur = fields.Many2One('pl_cust_dons.type_donateur', 'Donator type')
    is_donnateur = fields.Boolean('Donateur')
    dons = fields.One2Many('pl_cust_dons.dons', 'donator', '')
    total_donations_year = fields.Function(
        fields.Numeric('Total donations this year'), 'on_change_with_total_donations_year'
    )

    @fields.depends('dons')
    def on_change_with_total_donations_year(self, name=None):
        current_year = date.today().year
        return sum(1 for don in self.dons if don.date and don.date.year == current_year)

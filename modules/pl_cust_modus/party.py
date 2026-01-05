from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import PoolMeta
from datetime import date

__all__ = ['ModusParty']

class ModusParty(metaclass=PoolMeta):
    __name__ = 'party.party'

    pivprof = fields.Selection([('', ''),('priv','Privé'),('np','Non-profit')], 'Privé/Non-profit')
    contevents = fields.Boolean('Contacts events')

    @staticmethod
    def default_pivprof():
        return ''
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import PoolMeta
from datetime import date

__all__ = ['Party']

class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    def get_rec_name(self, name) :
        return '{}{}'.format(self.nickname and '{}/'.format(self.nickname),self.name)

  
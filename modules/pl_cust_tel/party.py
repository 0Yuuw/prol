from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Not, Bool

__all__ = ['Party']

class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    party = fields.Many2One('party.party', 'Contact')
    calls = fields.One2Many('pl_cust_tel.calls', 'call_writer', "Appels")
    is_writer = fields.Boolean('Ecoutant')
    engagement_date = fields.Date('Date de début')
    pseudo = fields.Char('Pseudo')
    comments = fields.Text('Commentaires')

    @classmethod
    def _default_is_writer(cls):
        return False

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
                ('pseudo',) + tuple(clause[1:]),
                ('addresses.contact_name',) + tuple(clause[1:]),
                ]
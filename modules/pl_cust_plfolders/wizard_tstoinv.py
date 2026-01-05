from trytond.wizard import Wizard, StateView, StateTransition, StateAction, Button
from trytond.model import ModelView, fields
from trytond.pool import Pool
from trytond.transaction import Transaction
from datetime import datetime
from trytond.pyson import Eval, PYSONEncoder
from decimal import Decimal

from trytond.model.exceptions import ValidationError


class FolderFactError(ValidationError):
    pass


__all__ = ['TStoInv',
           'TStoInvStart'
           ]


def format_date2(date):
    y, m, d = str(date).split('-')
    return '{}.{}.{}'.format(d, m, y)


class TStoInvStart(ModelView):
    "TStoInvStart"
    __name__ = 'pl_cust_plfolders.tstoinv_start'

    folder_id = fields.Many2One(
        'pl_cust_plfolders.folders', 'Folder', required=True, readonly=True)
    
    inv_id = fields.Many2One('account.invoice','Facture', required=False)
    
    folder_ts_tot = fields.Function(fields.Char('Folder TS tot'),
                                    'on_change_with_folder_ts_tot')

    timesheet_ids = fields.One2Many(
        'pl_cust_plfolders.foldersheet', None, 'Timesheet')

    @staticmethod
    def default_folder_id():
        if Transaction().context.get('active_model', '') == 'pl_cust_plfolders.folders':
            return Transaction().context.get('active_id', '')
        return None

    @staticmethod
    def default_timesheet_ids():
        pool = Pool()
        foldersheet_obj = pool.get('pl_cust_plfolders.foldersheet')
        if Transaction().context.get('active_model', '') == 'pl_cust_plfolders.folders':
            res = []
            for i in foldersheet_obj.search([
                ('folder_id', '=', Transaction().context.get('active_id', '')),
                    ('invoice_id', '=', None),  ('archived', '=', False)]):

                res.append(i.id)
            return res
        return None

    @fields.depends('timesheet_ids')
    def on_change_with_folder_ts_tot(self, name=None):

        tot_ts = 0

        if self.timesheet_ids:
            for t in self.timesheet_ids:

                if t.activity and t.duration and t.duration.total_seconds():
                    tot_ts += t.duration.total_seconds()*(int(t.pct)/100)

        hours, remainder = divmod(tot_ts, 3600)
        minutes, seconds = divmod(remainder, 60)
        if int(hours) and int(minutes):
            return '{0}h {1}min'.format(int(hours), int(minutes))
        elif int(hours):
            return '{}h'.format(int(hours))
        elif int(minutes):
            return '{}min'.format(int(minutes))
        else:
            return '-'



class TStoInv(Wizard):
    "TStoInv"
    __name__ = "pl_cust_plfolders.tstoinv"

    ids_list = []
    new_inv = None

    start = StateView('pl_cust_plfolders.tstoinv_start',
                      'pl_cust_plfolders.wizard_tstoinv_view_form', [
                          Button('Annuler', 'end', 'tryton-cancel'),
                          Button('Lier à la facture', 'tstoinv',
                                 'tryton-ok', default=True),
                      ])

    tstoinv = StateTransition()

    def transition_tstoinv(self):

        pool = Pool()
        Date_ = Pool().get('ir.date')
        ts_obj = pool.get('pl_cust_plfolders.foldersheet')
        ts_obj.write([ts for ts in self.start.timesheet_ids], {'invoice_id': self.start.inv_id.id})

        return 'end'

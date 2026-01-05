# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import DeactivableMixin, ModelView, ModelSQL, Workflow, fields
from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If, Bool
from trytond import backend
# from .party import EMPLOYEE_TYPE
from trytond.pyson import Date
from datetime import datetime, timedelta

from trytond.model.exceptions import ValidationError


class EmployeValidationError(ValidationError):
    pass


class UnableToDelete(ValidationError):
    pass


def format_seconds(s):
    hours, remainder = divmod(s, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours and minutes:
        return '{}h {:02}m'.format(int(hours), int(minutes))
    elif hours and not minutes:
        return '{}h'.format(int(hours))
    elif not hours and minutes:
        return '{}m'.format(int(minutes))
    else:
        return '-'


__all__ = ['Folders', 'FolderSheet', 'SheetAct',
           'SheetTask', 'FoldSequence', 'FoldInvoice', 'FoldEmployee', 'FoldEmployeeType']

STATES = {
    'readonly': ~Eval('active'),
}
DEPENDS = ['active']


class FoldEmployeeType(ModelSQL, ModelView):
    'Employee_type'
    __name__ = 'pl_cust_plfolders.employeetype'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True, translate=False)


class FoldEmployee(ModelSQL, ModelView, DeactivableMixin):
    __name__ = 'company.employee'

    #employee_type = fields.Selection(EMPLOYEE_TYPE, 'Type')
    employee_type = fields.Selection('get_employee_type', "Type")
    employee_type_string = employee_type.translated('employee_type')
    code = fields.Char('code')

    @classmethod
    def get_employee_type(cls):
        FOLDERTYPE = Pool().get('pl_cust_plfolders.employeetype')
        all_type = FOLDERTYPE.search([])
        return [(ft.code, ft.name) for ft in all_type]


class SheetAct(ModelSQL, ModelView):
    'Folder timesheet activity'
    __name__ = 'pl_cust_plfolders.sheetact'

    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code', size=2, translate=False)
    tasks = fields.One2Many(
        'pl_cust_plfolders.sheettasks', 'activity', 'Tasks')


class SheetTask(ModelSQL, ModelView, DeactivableMixin):
    'Folder timesheet tasks'
    __name__ = 'pl_cust_plfolders.sheettasks'

    name = fields.Char('Name', required=True, translate=True)
    activity = fields.Many2One(
        'pl_cust_plfolders.sheetact', 'Activity', required=True)
    duration = fields.TimeDelta('Duration', 'company_work_time')

    @staticmethod
    def default_duration():
        return timedelta(0)


class FolderSheet(ModelSQL, ModelView):
    'Folder timesheet'
    __name__ = 'pl_cust_plfolders.foldersheet'

    name = fields.Char('Description', states={'readonly': Bool(
        Eval('invoiced')), }, depends=['invoiced'])

    activity = fields.Many2One('pl_cust_plfolders.sheetact', 'Activity', required=True, states={
                               'readonly': Bool(Eval('invoiced')), }, depends=['invoiced'])
    task = fields.Many2One('pl_cust_plfolders.sheettasks', 'Task', states={
                           'readonly': Bool(Eval('invoiced')), }, depends=['invoiced'], required=True)
    date = fields.Date('Date', help="Date", required=True, states={
                       'readonly': Bool(Eval('invoiced')), }, depends=['invoiced'])

    folder_id = fields.Many2One(
        'pl_cust_plfolders.folders', 'Folder', required=True)

    duration = fields.TimeDelta('Duration', required=True, states={
                                'readonly': Bool(Eval('invoiced')), }, depends=['invoiced'])

    hour_price = fields.Float('Price per hour', states={
                              'readonly': Bool(Eval('invoiced')), }, depends=['invoiced'])

    price = fields.Function(fields.Float('Price'), 'on_change_with_price')

    folder_type = fields.Function(fields.Char(
        'Folder Type'), 'on_change_with_folder_type')

    resp_id = fields.Many2One('company.employee', 'Employee', required=True, states={
                              'readonly': Bool(Eval('invoiced')), }, depends=['invoiced'])

    resp_type = fields.Function(fields.Selection(
        'get_employee_type', 'Employee Type'), 'on_change_with_resp_type')
    invoiced = fields.Function(fields.Boolean(
        'Invoiced'), 'on_change_with_invoiced', searcher='search_invoiced')
    invoice_id = fields.Many2One('account.invoice', 'Invoice')

    pct = fields.Selection([('0', '0%'),
                            ('50', '50%'),
                            ('100', '100%'),
                            ('150', '150%'),
                            ('200', '200%'), ], 'PCT', sort=False, required=True)

    archived = fields.Boolean('Archived')

    @classmethod
    def __setup__(cls):
        super(FolderSheet, cls).__setup__()
        cls._order = [
            ('date', 'DESC'),
            ('id', 'DESC'),
        ]

    @classmethod
    def delete(cls, foldersheets):
        for ts in foldersheets:
            if ts.invoiced:
                raise UnableToDelete(
                    "Impossible de supprimer un timesheet facturé")

        super().delete(foldersheets)

    @classmethod
    def get_employee_type(cls):
        FOLDERTYPE = Pool().get('pl_cust_plfolders.employeetype')
        all_type = FOLDERTYPE.search([])
        return [(ft.code, ft.name) for ft in all_type]

    @staticmethod
    def default_resp_id():
        return Transaction().context.get('employee')

    @staticmethod
    def default_pct():
        return '100'

    @staticmethod
    def default_date():
        Date_ = Pool().get('ir.date')
        return Transaction().context.get('date') or Date_.today()

    @fields.depends('resp_id', 'folder_id', 'task', 'hour_price')
    def on_change_resp_id(self):
        if not self.folder_id:
            return

        corresp = {
            'T1': self.folder_id.folder_price1,
            'T2': self.folder_id.folder_price2,
            'T3': self.folder_id.folder_price3,
            'T4': self.folder_id.folder_price4,
            'T5': self.folder_id.folder_price5,
        }

        if self.resp_id:
            if corresp.get(self.resp_id.employee_type, None) :
                self.hour_price = corresp[self.resp_id.employee_type]

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
                ('folder_id',) + tuple(clause[1:]),
                ]

    @fields.depends('task', 'name', 'duration')
    def on_change_task(self):
        if not self.task:
            self.activity = None
        else:
            self.activity = self.task.activity
            if not self.name:
                self.name = self.task.name
            if not self.duration and not self.task.duration == timedelta(0):
                self.duration = self.task.duration

    @fields.depends('resp_id', 'folder_id', 'task', 'duration', 'name')
    def on_change_with_hour_price(self, name=None):
        if not self.folder_id:
            return 0.0

        corresp = {
            'T1': self.folder_id.folder_price1,
            'T2': self.folder_id.folder_price2,
            'T3': self.folder_id.folder_price3,
            'T4': self.folder_id.folder_price4,
            'T5': self.folder_id.folder_price5,
        }

        if self.resp_id:
            if corresp.get(self.resp_id.employee_type, None) :
                return corresp[self.resp_id.employee_type]

    @fields.depends('invoice_id', 'archived')
    def on_change_with_invoiced(self, name=None):
        if self.invoice_id or self.archived:
            return True

        return False

    @classmethod
    def search_invoiced(cls, name, clause):
        bool_op = 'AND'
        return [bool_op,
                ('invoice_id', clause[1], None),
                ('archived',) + tuple(clause[1:]),
                ]

    @fields.depends('duration', 'hour_price', 'task', 'pct', 'folder_id')
    def on_change_with_price(self, name=None):
        if not self.folder_id:
            return

        LANG = Pool().get('ir.lang')
        lang_fr = LANG(LANG.search([('code', '=', 'fr')])[0])

        if self.duration and self.hour_price and self.folder_id.currency and self.pct:
            return ((self.duration.total_seconds()/3600.0) * self.hour_price)*(int(self.pct)/100)
        else:
            return 0

    @fields.depends('resp_id')
    def on_change_with_resp_type(self, name=None):
        if self.resp_id:
            return (self.resp_id.employee_type)

    @fields.depends('folder_id')
    def on_change_with_folder_type(self, name=None):
        if self.folder_id:
            return self.folder_id.folder_type


class FoldInvoice(ModelSQL, ModelView):
    __name__ = 'account.invoice'
    folder_id = fields.Many2One('pl_cust_plfolders.folders', 'Folders')
    timesheet_ids = fields.One2Many(
        'pl_cust_plfolders.foldersheet', 'invoice_id', 'Timesheet')

    @classmethod
    def __setup__(cls):

        super().__setup__()
        cls._check_modify_exclude.add('folder_id')

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()

        default.setdefault('folder_id', None)
        default.setdefault('timesheet_ids', None)
        
        new_lines = []
        for line in lines:
            new_line, = super().copy([line], default)
            new_lines.append(new_line)
        return new_lines


class Folders(DeactivableMixin, Workflow, ModelSQL, ModelView):
    'Folders'
    __name__ = 'pl_cust_plfolders.folders'
    name = fields.Char('Number', required=False, readonly=False)
    timesheet_ids_not_inv = fields.One2Many(
        'pl_cust_plfolders.foldersheet', 'folder_id', 'Timesheet')
    timesheet_ids = fields.One2Many(
        'pl_cust_plfolders.foldersheet', 'folder_id', 'Timesheet')
    invoice_ids = fields.One2Many('account.invoice', 'folder_id', 'Invoices')
    in_invoice_ids = fields.One2Many(
        'account.invoice', 'folder_id', 'In Invoices')

    date_start = fields.Date('Date start', help="Date start")
    date_end = fields.Date('Date end', help="Date end")
    party_id = fields.Many2One('party.party', 'Party', required=True)
    fact_to = fields.Many2One('party.party', 'Invoice To')
    description = fields.Char('Description', required=True)
    notes = fields.Text('Comment')
    internal_notes = fields.Text('Internal Notes')
    internal_com = fields.Char('Internal Com')

    folder_type = fields.Selection('get_folder_type', "Folder Type")
    folder_type_string = folder_type.translated('folder_type')

    folder_forf_amount = fields.Integer('Folder Forfait amount')
    folder_charges = fields.Float('Folder Charges(%)')
    folder_tax_bool = fields.Boolean('Folder Tax')

    folder_price1 = fields.Integer('T1')
    folder_price2 = fields.Integer('T2')
    folder_price3 = fields.Integer('T3')
    folder_price4 = fields.Integer('T4')
    folder_price5 = fields.Integer('T5')

    currency = fields.Many2One('currency.currency', 'Currency', required=False)

    newfolder_tot_ts_withoutpct = fields.TimeDelta(
        'Tot TS without pct', 'company_work_time', readonly=False)
    newfolder_tot_ts = fields.TimeDelta(
        'Tot TS', 'company_work_time', readonly=False)
    newfolder_tot_fact_ts = fields.TimeDelta(
        'Tot TS fact', 'company_work_time', readonly=False)
    newfolder_tot_notfact_ts = fields.TimeDelta(
        'Tot TS not fact', 'company_work_time', readonly=False)
    newfolder_expected = fields.TimeDelta(
        'Tot TS expected', 'company_work_time')

    newfolder_expected_txt = fields.Char('Tot TS expected')
    newfolder_tot_ts_withoutpct_txt = fields.Char('Tot TS without pct')
    newfolder_tot_ts_txt = fields.Char('Tot TS')
    newfolder_tot_fact_ts_txt = fields.Char('Tot TS fact')
    newfolder_tot_notfact_ts_txt = fields.Char('Tot TS not fact')

    check_ts = fields.Function(fields.Char(
        'Check TS'), 'on_change_with_check_ts')

    as_attachment = fields.Function(fields.Boolean('pj'), 'get_as_attachement')
    delai = fields.Char('Delai')
    resp = fields.Many2One('company.employee', 'Resp',)
    
    @classmethod
    def get_as_attachement(cls, invoices, name):
        pool = Pool()
        ATTACH = pool.get('ir.attachment')

        res = {i.id: False for i in invoices}
        for inv in invoices : 
            if ATTACH.search([('resource', '=', inv)]) :
                res[inv.id] = True
        return res

    @fields.depends('newfolder_expected', 'newfolder_tot_ts')
    def on_change_with_check_ts(self, name=None):
        if not self.newfolder_expected:
            return ''
        else:
            if not self.newfolder_tot_ts:
                return 'success'
            elif self.newfolder_expected > self.newfolder_tot_ts:
                return 'success'
            else:
                return 'danger'

    @fields.depends('folder_type')
    def on_change_folder_type(self):
        if self.folder_type:
            FOLDERTYPE = Pool().get('pl_cust_plfolders.foldertype')
            ft = FOLDERTYPE.search([('code', '=', self.folder_type)])
            if ft : 
                ft = ft[0]
                self.folder_price1 = ft.folder_price1
                self.folder_price2 = ft.folder_price2
                self.folder_price3 = ft.folder_price3
                self.folder_price4 = ft.folder_price4
                self.folder_price5 = ft.folder_price5

    @classmethod
    def __setup__(cls):
        super().__setup__()

        cls.timesheet_ids_not_inv.filter = [('invoiced', '=', False)]

        cls.invoice_ids.filter = [('type', '=', 'out')]
        cls.in_invoice_ids.filter = [('type', '=', 'in')]

        cls._order = [
            ('name', 'DESC'),
        ]

        cls._buttons.update({
            'make_invoice': {},
            'ts_to_inv': {},
            'update_prices': {},
            'update_infos': {},
            'print_letter': {},
            'periodic_ts': {},
        })

    @classmethod
    @ModelView.button_action('pl_cust_plfolders.act_wizard_new_tstoinv')
    def ts_to_inv(cls, folders):
        pass

    @classmethod
    @ModelView.button_action('pl_cust_plfolders.act_wizard_createinv')
    def make_invoice(cls, folders):
        pass

    @classmethod
    @ModelView.button_action('pl_cust_plfolders.act_wizard_periodicts')
    def periodic_ts(cls, folders):
        pass

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            #('/tree', 'visual', If(Eval('newfolder_expected', 0) > 0, If(Eval('newfolder_tot_ts') >= Eval('newfolder_expected'),'danger', If(Eval('newfolder_expected'), 'success','')), '')),
            ('/tree', 'visual', Eval('check_ts', '')),
        ]

    @staticmethod
    def default_name():
        return ''

    @staticmethod
    def default_folder_price1():
        return 0

    @staticmethod
    def default_folder_price2():
        return 0

    @staticmethod
    def default_folder_price3():
        return 0

    @staticmethod
    def default_folder_price4():
        return 0

    @staticmethod
    def default_folder_price5():
        return 0

    @staticmethod
    def default_folder_tax_bool():
        return True

    @staticmethod
    def default_folder_charges():
        return 0

    @staticmethod
    def default_folder_type():
        FOLDERTYPE = Pool().get('pl_cust_plfolders.foldertype')
        all_type = FOLDERTYPE.search([])
        return all_type and all_type[0].code or ''

    #def default_folder_type():
    #    return 'o'

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')
        if Transaction().context.get('company'):
            company = Company(Transaction().context['company'])
            return company.currency.id

    @staticmethod
    def default_date_start():
        Date_ = Pool().get('ir.date')
        return Transaction().context.get('date') or Date_.today()

    @classmethod
    def get_folder_type(cls):
        FOLDERTYPE = Pool().get('pl_cust_plfolders.foldertype')
        all_type = FOLDERTYPE.search([])
        return [(ft.code, ft.name) for ft in all_type]

    @classmethod
    def _new_name(cls, **pattern):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Configuration = pool.get('pl_cust_plfolders.configuration')
        config = Configuration(1)
        sequence = config.get_multivalue('folders_sequence', **pattern)
        if sequence:
            return sequence.get()

    def get_rec_name(self, name):
        return "{}{}{}".format(self.party_id and self.party_id.name or '?',
                               self.description and '-'+self.description or '',
                               self.name and '-'+self.name or '')

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
                ('name',) + tuple(clause[1:]),
                ('party_id',) + tuple(clause[1:]),
                ('description',) + tuple(clause[1:]),
                ]

    # mise à jour des infos via un bouton
    @classmethod
    @ModelView.button
    def update_infos(cls, folders):
        for f in folders:

            # Calcul des divers totaux pour le TS
            tmp_totts_nopct, tmp_totts, tmp_tot_fact_ts, tmp_tot_notfact_ts = 0, 0, 0, 0

            for t in f.timesheet_ids:

                if t.task and t.duration and t.duration.total_seconds():
                    tmp_totts_nopct += t.duration.total_seconds()
                if t.task and t.duration and t.duration.total_seconds():
                    tmp_totts += t.duration.total_seconds()*(int(t.pct)/100)
                if t.invoiced and t.task and t.duration and t.duration.total_seconds():
                    tmp_tot_fact_ts += t.duration.total_seconds()*(int(t.pct)/100)
                if not t.invoiced and t.task and t.duration and t.duration.total_seconds():
                    tmp_tot_notfact_ts += t.duration.total_seconds()*(int(t.pct)/100)

            # Totaux sur les heures
            f.newfolder_tot_ts_withoutpct = timedelta(seconds=tmp_totts_nopct)
            f.newfolder_tot_ts = timedelta(seconds=tmp_totts)
            f.newfolder_tot_fact_ts = timedelta(seconds=tmp_tot_fact_ts)
            f.newfolder_tot_notfact_ts = timedelta(seconds=tmp_tot_notfact_ts)

            f.newfolder_expected_txt = f.newfolder_expected and format_seconds(
                f.newfolder_expected.total_seconds()) or '-'
            f.newfolder_tot_ts_withoutpct_txt = format_seconds(tmp_totts_nopct)
            f.newfolder_tot_ts_txt = format_seconds(tmp_totts)
            f.newfolder_tot_fact_ts_txt = format_seconds(tmp_tot_fact_ts)
            f.newfolder_tot_notfact_ts_txt = format_seconds(tmp_tot_notfact_ts)

            f.save()
        return True
    #####################

    @classmethod
    @ModelView.button
    def update_prices(cls, folders):
        corresp = {
            'T1': folders[0].folder_price1,
            'T2': folders[0].folder_price2,
            'T3': folders[0].folder_price3,
            'T4': folders[0].folder_price4,
            'T5': folders[0].folder_price5,
        }

        for ts_line in folders[0].timesheet_ids:

            # if ts_line.invoiced:
            #    continue

            if ts_line.resp_id:
                if corresp.get(ts_line.resp_id.employee_type, None) :
                    ts_line.hour_price = corresp[ts_line.resp_id.employee_type]

                    print(corresp[ts_line.resp_id.employee_type])
            ts_line.save()

    @classmethod
    def copy(cls, folders, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()

        default.setdefault('name', None)
        default.setdefault('invoice_ids', None)
        default.setdefault('in_invoice_ids', None)
        default.setdefault('timesheet_ids', None)
        default.setdefault('date_start', None)
        default.setdefault('date_end', None)

        new_folders = []
        for fold in folders:
            if not default.get('description', False):
                default['description'] = '(COPIE) {}'.format(fold.description)
            new_folder, = super(Folders, cls).copy([fold], default)
            new_folders.append(new_folder)
        return new_folders

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Employee = pool.get('company.employee')
        vlist = [x.copy() for x in vlist]
        employ = ''

        for values in vlist:
            if not values.get('name'):
                values['name'] = cls._new_name()

        return super().create(vlist)

    @classmethod
    def write(cls, *args):
        super().write(*args)
        actions = iter(args)
        for folders, values in zip(actions, actions):
            cls.update_prices(folders)
            

class FoldSequence(DeactivableMixin, ModelSQL, ModelView):
    "Sequence"
    __name__ = 'ir.sequence'

    @classmethod
    def _get_substitutions(cls, date):
        '''
        Returns a dictionary with the keys and values of the substitutions
        available to format the sequence
        '''
        pool = Pool()
        Date = pool.get('ir.date')
        if not date:
            date = Date.today()
        return {
            'year': date.strftime('%Y'),
            'plyear': date.strftime('%y'),
            'month': date.strftime('%m'),
            'day': date.strftime('%d'),
        }

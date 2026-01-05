# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import DeactivableMixin, ModelView, ModelSQL, Workflow, fields
from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If
from trytond import backend
from trytond.pyson import Date
from datetime import datetime, timedelta, time
import pytz

from trytond.model.exceptions import ValidationError

class DateValidationError(ValidationError):
    pass

class EmployeValidationError(ValidationError):
    pass

def _date_limite(date):
    #d_limite = date - timedelta(days=1)
    #while d_limite.weekday() >= 5:  # Si la date est un samedi ou un dimanche
    #    d_limite -= timedelta(days=1)
    #return d_limite
    return date

def secTohms(nb_sec):
    q, s = divmod(nb_sec, 60)
    h, m = divmod(q, 60)
    return h, m, s


__all__ = ['TTTimetables', 'TTDays', 'TTDaysType', 'TTHours',
           'TTOvertimeValidate', 'TTWeeklyDetail', 'TTWeeklyDetailHours']

STATES = {
    'readonly': ~Eval('active'),
}
DEPENDS = ['active']

HOUR_TYPE = [
    ('in', 'In'),
    ('out', 'Out'),
]

DAYS = [('mon', 'Lundi'),
        ('tue', 'Mardi'),
        ('wed', 'Mercredi'),
        ('thu', 'Jeudi'),
        ('fri', 'Vendredi'),
        ('sat', 'Samedi'),
        ('sun', 'Dimanche'),
        ]


class TTWeeklyDetailHours(ModelSQL, ModelView):
    'Time Traking Hours'
    __name__ = 'pl_cust_timetracking.ttweeklydetailhours'

    employ_hour = fields.Time('Employee Hour')
    type_hour = fields.Selection(HOUR_TYPE, 'Type')
    weekly_detail_id = fields.Many2One(
        'pl_cust_timetracking.ttweeklydetail', 'WeeklyDetail', ondelete='CASCADE')


class TTWeeklyDetail(ModelSQL, ModelView):
    'Time Tracking Weekly Detail'
    __name__ = 'pl_cust_timetracking.ttweeklydetail'

    timetable_id = fields.Many2One(
        'pl_cust_timetracking.tttimetables', 'TimeTable', ondelete='CASCADE')
    day = fields.Selection(DAYS, 'Day')
    hours_ids = fields.One2Many(
        'pl_cust_timetracking.ttweeklydetailhours', 'weekly_detail_id', 'Hours List')

    tot_hours = fields.Function(fields.Time('To hours', format='%H:%M'),
                                'on_change_with_tot_hours')

    @fields.depends('hours_ids')
    def on_change_with_tot_hours(self, name=None):

        if len(self.hours_ids) % 2:
            return None
        elif self.hours_ids:
            t_tot = 0

            for i in range(0, len(self.hours_ids)-1, 2):
                h1 = self.hours_ids[i]
                h2 = self.hours_ids[i+1]
                if not h1 or not h2:
                    return None
                elif not h1.type_hour or not h2.type_hour or not h1.type_hour == 'in' or not h2.type_hour == 'out':
                    return None
                elif not h2.employ_hour or not h1.employ_hour or not h2.employ_hour > h1.employ_hour:
                    return None

                t_tot += ((h2.employ_hour.hour*60 + h2.employ_hour.minute) -
                          (h1.employ_hour.hour*60 + h1.employ_hour.minute)) * 60
            tmp_h, tmp_m, tmp_s = secTohms(t_tot)
            return time(tmp_h, tmp_m, tmp_s)

        return None


class TTTimetables(ModelSQL, ModelView):
    'Time Traking Work Timetables'
    __name__ = 'pl_cust_timetracking.tttimetables'

    date_start = fields.Date('Start Date', required=True)
    date_end = fields.Date('End Date')
    employee_id = fields.Many2One(
        'company.employee', 'Employee', required=True)
    tx_activity = fields.Integer('Tx activity (%)')
    weekly_duration = fields.Integer('Weekly Duration')
    weekly_detail = fields.One2Many(
        'pl_cust_timetracking.ttweeklydetail', 'timetable_id', 'Weekly Detail')
    weekly_duration_auto = fields.Function(fields.Float('Weekly Duration Auto'),
                                           'on_change_with_weekly_duration_auto')

    monday = fields.Boolean('Monday')
    tuesday = fields.Boolean('Tuesday')
    wednesday = fields.Boolean('Wednesday')
    thursday = fields.Boolean('Thursday')
    friday = fields.Boolean('Friday')
    saturday = fields.Boolean('Saturday')
    sunday = fields.Boolean('Sunday')

    @staticmethod
    def default_tx_activity():
        return 100

    @staticmethod
    def default_employee_id():
        return Transaction().context.get('employee')

    @staticmethod
    def default_date_start():
        Date_ = Pool().get('ir.date')
        return Transaction().context.get('date') or Date_.today()

    @fields.depends('weekly_detail', 'weekly_duration')
    def on_change_with_weekly_duration_auto(self, name=None):
        if self.weekly_duration:
            return self.weekly_duration
        elif self.weekly_detail:
            htot = 0
            for d in self.weekly_detail:
                if d.tot_hours:
                    htot += d.tot_hours.hour + d.tot_hours.minute/60.0

            return htot

        return 0

class TTDaysType(ModelSQL, ModelView):
    'Time Traking Days Type'
    __name__ = 'pl_cust_timetracking.ttdaystype'

    name = fields.Char('Name', required=True)
    code = fields.Char('code', required=True)

class TTDays(ModelSQL, ModelView):
    'Time Traking Days'
    __name__ = 'pl_cust_timetracking.ttdays'

    date = fields.Date('Date', required=True)
    employee_id = fields.Many2One(
        'company.employee', 'Employee', required=True)
    hours_ids = fields.One2Many(
        'pl_cust_timetracking.tthours', 'day_id', 'Hours List', search_order=[('')])
    not_valid = fields.Function(fields.Boolean('Day not valid'),
                                'on_change_with_not_valid')
    tot_hours = fields.Function(fields.Time('To hours', format='%H:%M'),
                                'on_change_with_tot_hours')

    day_type = fields.Selection('get_day_type', "Type")
    day_type_string = day_type.translated('day_type')

    @classmethod
    def get_day_type(cls):
        DAYTYPE = Pool().get('pl_cust_timetracking.ttdaystype')
        all_type = DAYTYPE.search([])
        return [(ft.code, ft.name) for ft in all_type]

    @staticmethod
    def default_employee_id():
        return Transaction().context.get('employee')

    @staticmethod
    def default_day_type():
        return 'std'

    @staticmethod
    def default_date():
        Date_ = Pool().get('ir.date')
        return Transaction().context.get('date') or Date_.today()

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('date', 'DESC NULLS FIRST'))
        cls.hours_ids.search_order = [('employ_hour', 'ASC')]

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('/tree', 'visual', If(Eval('not_valid'), 'danger', If(Eval('day_type','') != 'std', 'warning', ''))),
        ]

    @fields.depends('hours_ids')
    def on_change_with_not_valid(self, name=None):

        if len(self.hours_ids) % 2:
            return True
        elif self.hours_ids:
            t_next = 'in'
            for h in self.hours_ids:
                if not h.type_hour == t_next:
                    return True

                t_next = t_next == 'in' and 'out' or 'in'

        return False

    @fields.depends('hours_ids')
    def on_change_with_tot_hours(self, name=None):

        if len(self.hours_ids) % 2:
            return None
        elif self.hours_ids:
            t_tot = 0

            for i in range(0, len(self.hours_ids)-1, 2):
                h1 = self.hours_ids[i]
                h2 = self.hours_ids[i+1]
                if not h1 or not h2:
                    return None
                elif not h1.type_hour or not h2.type_hour or not h1.type_hour == 'in' or not h2.type_hour == 'out':
                    return None
                elif not h2.employ_hour or not h1.employ_hour or not h2.employ_hour > h1.employ_hour:
                    return None

                t_tot += ((h2.employ_hour.hour*60 + h2.employ_hour.minute) -
                          (h1.employ_hour.hour*60 + h1.employ_hour.minute)) * 60
            tmp_h, tmp_m, tmp_s = secTohms(t_tot)
            return time(tmp_h, tmp_m, tmp_s)

        return None

    @classmethod
    def write(cls, *args):

        pool = Pool()
        Date_ = pool.get('ir.date')
        today_ = Date_.today()
        User = pool.get('res.user')
        Group = pool.get('res.group')
        user = User(Transaction().user)
        ModelData = pool.get('ir.model.data')
        admingroup = Group(ModelData.get_id('pl_cust_timetracking',
                    'group_timetracking_admin'))
        is_admin = admingroup in user.groups
        EMPLOYEE = Pool().get('company.employee')
        employ = EMPLOYEE(Transaction().context.get('employee'))
        print('on passe par ici')
        actions = iter(args)
        for tdays, values in zip(actions, actions):
            for d in tdays :
                if not is_admin and 'date' in values.keys():
                    if values.get('date') and values.get('date') < _date_limite(today_):
                        raise DateValidationError(
                        "Vous ne pouvez pas entrer du timesheet pour cette date (Maximum 24h)")
                elif not is_admin:
                    if d.date < _date_limite(today_):
                        raise DateValidationError(
                            "Vous ne pouvez pas modifier du timesheet pour cette date (Maximum 24h)")
                    
        super().write(*args)

class TTHours(ModelSQL, ModelView):
    'Time Traking Hours'
    __name__ = 'pl_cust_timetracking.tthours'

    sys_date = fields.Date('System Date', readonly=True)
    sys_hour = fields.Time('System Hour', readonly=True)
    sys_user = fields.Many2One('res.user', 'System User', readonly=True)
    employ_hour = fields.Time('Employee Hour')
    type_hour = fields.Selection(HOUR_TYPE, 'Type')
    day_id = fields.Many2One(
        'pl_cust_timetracking.ttdays', 'Day', ondelete='CASCADE')
    employee_id = fields.Many2One(
        'company.employee', 'Employee', required=True)

    @staticmethod
    def default_employee_id():
        return Transaction().context.get('employee')

    @staticmethod
    def default_sys_user():
        return Transaction().user

    @staticmethod
    def default_sys_date():
        Date_ = Pool().get('ir.date')
        return Date_.today()

    @staticmethod
    def default_sys_hour():
        return datetime.now(tz=pytz.timezone("Europe/Paris")).time()

    @staticmethod
    def default_employ_hour():
        return datetime.now(tz=pytz.timezone("Europe/Paris")).time()

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('employ_hour', 'ASC'))

class TTOvertimeValidate(ModelSQL, ModelView):
    'Time Traking Overtime Validate'
    __name__ = 'pl_cust_timetracking.ttovertimevalidate'

    employee_id = fields.Many2One(
        'company.employee', 'Employee', required=True)
    date = fields.Date('Date', required=True)
    nb_hours = fields.Integer('Nb Hours', required=True)

    @staticmethod
    def default_employee_id():
        return Transaction().context.get('employee')

from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.model import ModelView, fields
from trytond.pool import Pool
from trytond.transaction import Transaction
from datetime import datetime, date

from trytond.pyson import Eval
from decimal import Decimal
import codecs
import os
import csv
import pytz

from .timetracking import HOUR_TYPE
from trytond.model.exceptions import ValidationError


class TTWizardError(ValidationError):
    pass


__all__ = ['TTWizard', 'TTWizardStart', ]


class TTWizardStart(ModelView):
    "TTWizardStart"
    __name__ = 'pl_cust_timetracking.ttwizard_start'

    employee_id = fields.Many2One('company.employee', 'Employee', states={'readonly': ~Eval('is_admin', False)}, depends=['is_admin'])
    type_hour = fields.Selection(HOUR_TYPE, 'Type', required=True)
    date = fields.Date('Date', states={'readonly': ~Eval('is_admin', False)}, depends=['is_admin'])
    time = fields.Time('Hours', format='%H:%M')
    is_admin = fields.Boolean('is_admin')

    @staticmethod
    def default_is_admin():
        pool = Pool()
        User = pool.get('res.user')
        Group = pool.get('res.group')
        user = User(Transaction().user)
        ModelData = pool.get('ir.model.data')
        admingroup = Group(ModelData.get_id('pl_cust_timetracking',
                    'group_timetracking_admin'))
        return admingroup in user.groups
        
    @staticmethod
    def default_employee_id():
        return Transaction().context.get('employee')

    @staticmethod
    def default_date():
        Date_ = Pool().get('ir.date')
        return Transaction().context.get('date') or Date_.today()

    @staticmethod
    def default_time():
        return datetime.now(tz=pytz.timezone("Europe/Paris")).time()

    @staticmethod
    def default_type_hour():
        Date_ = Pool().get('ir.date')  
        DAYS = Pool().get('pl_cust_timetracking.ttdays')
        day_search = DAYS.search(
            [('date', '=', Date_.today()), ('employee_id', '=', Transaction().context.get('employee'))])

        if day_search:
            day = DAYS(day_search[0])
            return day.hours_ids and day.hours_ids[-1].type_hour == 'in' and 'out' or 'in'
        else:
            return 'in'



class TTWizard(Wizard):
    "TTWizard"
    __name__ = "pl_cust_timetracking.ttwizard"

    start = StateView('pl_cust_timetracking.ttwizard_start',
                      'pl_cust_timetracking.ttwizard_start_view_form', [
                          Button('Cancel', 'end', 'tryton-cancel'),
                          Button('Validate', 'validate_tt',
                                 'tryton-ok', default=True),
                      ])

    validate_tt = StateTransition()

    def transition_validate_tt(self):

        pool = Pool()
        DAYS = pool.get('pl_cust_timetracking.ttdays')
        HOURS = pool.get('pl_cust_timetracking.tthours')

        day_search = DAYS.search(
            [('date', '=', self.start.date), ('employee_id', '=', self.start.employee_id)])

        if day_search:
            day = DAYS(day_search[0])
        else:
            day, = DAYS.create([{'date': self.start.date,
                                'employee_id': self.start.employee_id}])

        h = HOURS.create([{'employ_hour': self.start.time,
                           'type_hour': self.start.type_hour,
                           'day_id': day,
                           'employee_id': self.start.employee_id}])

        return 'end'

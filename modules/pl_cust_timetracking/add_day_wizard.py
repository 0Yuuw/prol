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


class TTAddDayWizardError(ValidationError):
    pass


__all__ = ['TTAddDayWizard', 'TTAddDayWizardStart', ]


class TTAddDayWizardStart(ModelView):
    "TTAddDayWizardStart"
    __name__ = 'pl_cust_timetracking.ttadddaywizard_start'

    employee_id = fields.Many2One(
        'company.employee', 'Employee', required=True)
    date = fields.Date('Date', required=True)


class TTAddDayWizard(Wizard):
    "TTWizard"
    __name__ = "pl_cust_timetracking.ttadddaywizard"

    start = StateView('pl_cust_timetracking.ttadddaywizard_start',
                      'pl_cust_timetracking.ttadddaywizard_start_view_form', [
                          Button('Cancel', 'end', 'tryton-cancel'),
                          Button('Add day', 'validate_newday',
                                 'tryton-ok', default=True),
                      ])

    validate_newday = StateTransition()

    def transition_validate_newday(self):

        pool = Pool()
        DAYS = pool.get('pl_cust_timetracking.ttdays')
        HOURS = pool.get('pl_cust_timetracking.tthours')
        TIMETABLES = pool.get('pl_cust_timetracking.tttimetables')

        day_search = DAYS.search(
            [('date', '=', self.start.date), ('employee_id', '=', self.start.employee_id)])

        if day_search:
            day = DAYS(day_search[0])
            return 'end'
        else:
            day, = DAYS.create([{'date': self.start.date,
                                 'employee_id': self.start.employee_id}])

        ttables = TIMETABLES.search(['AND',
                                     [('employee_id', '=', self.start.employee_id)],
                                     [('date_start', '<=', self.start.date)],
                                     ['OR', [('date_end', '>=', self.start.date)],
                                      [('date_end', '=', None)]]])
        if ttables:
            ttables = TIMETABLES(ttables[0])
            for d in ttables.weekly_detail:
                if d.day == self.start.date.strftime('%a').lower():
                    for hour in d.hours_ids:
                        h = HOURS.create([{'employ_hour': hour.employ_hour,
                                           'type_hour': hour.type_hour,
                                           'day_id': day,
                                           'employee_id': self.start.employee_id}])
                    break
            else:
                for hour in [('08:30:00', 'in'), ('12:30:00', 'out'), ('13:30:00', 'in'), ('17:30:00', 'out')]:
                    h = HOURS.create([{'employ_hour': hour[0],
                                       'type_hour': hour[1],
                                       'day_id': day,
                                       'employee_id': self.start.employee_id}])
        else:
            for hour in [('08:00:00', 'in'), ('12:00:00', 'out'), ('13:00:00', 'in'), ('17:00:00', 'out')]:
                h = HOURS.create([{'employ_hour': hour[0],
                                   'type_hour': hour[1],
                                   'day_id': day,
                                   'employee_id': self.start.employee_id}])

        return 'end'

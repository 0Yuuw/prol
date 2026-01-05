# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# -*- coding: UTF-8 -*-
from decimal import Decimal
from trytond.wizard import Wizard, StateView, StateTransition, Button

from trytond.model import DeactivableMixin, ModelView, ModelSQL, Workflow, fields
from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If, Bool
from trytond import backend
# from .party import EMPLOYEE_TYPE
from trytond.pyson import Date
from datetime import datetime, timedelta, date
from trytond.exceptions import UserWarning
import pytz
from trytond.model.exceptions import ValidationError


class EmployeValidationError(ValidationError):
    pass


class UnableToDelete(ValidationError):
    pass


class Error(ValidationError):
    pass


__all__ = ['Calendar', 'GenerateCalendar', 'GenerateCalendarStart', 'GenerateDayOff', 'GenerateDayOffStart', ]

STATES = {
    'readonly': ~Eval('active'),
}
DEPENDS = ['active']

DAY_TYPE = [
    ('s', 'Standard'),
    ('h', 'Holiday'),
    ('o', 'DayOff'),
]

class DayOFF(ModelSQL, ModelView):
    'DayOFF'
    __name__ = 'pl_cust_feefolders.dayoff'

    date = fields.Date('Date', readonly=False)
    day_type = fields.Selection(DAY_TYPE, 'Type', required=True)
    day_type_string = day_type.translated('day_type')

    @classmethod
    def copy(cls, folders, default=None):
        raise UnableToDelete(
            "Impossible de dupliquer une semaine...merci de contacter ProLibre")

class Calendar(ModelSQL, ModelView):
    'Calendar'
    __name__ = 'pl_cust_reportactivity.calendar'

    name = fields.Char('Name', readonly=True)
    year = fields.Integer('Year', readonly=True)

    date = fields.Date('Date', help="Date", readonly=True)

    calendar_type = fields.Selection(DAY_TYPE, 'Type', required=True)
    calendar_type_type_string = calendar_type.translated('calendar_type')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order = [
            ('date', 'DESC'),
        ]

    @staticmethod
    def default_calendar_type():
        return 's'

    # @classmethod
    # def view_attributes(cls):
    #     return super().view_attributes() + [
    #         ('/tree', 'visual', If(Eval('thpe_week'), 'success', (If(Eval('nb_day_open') != 5, 'danger', '')))),
    #     ]

    @classmethod
    def create(cls, vlist):
        vlist = [x.copy() for x in vlist]

        # for values in vlist:
        #     if not values.get('name'):
        #         values['name'] = '{}-{}'.format(
        #             values.get('week_number'), values.get('year'))

        return super().create(vlist)

    @classmethod
    def delete(cls, employs):
        raise UnableToDelete(
            "Impossible de supprimer une semaine...merci de contacter ProLibre")
    
    @classmethod
    def copy(cls, folders, default=None):
        raise UnableToDelete(
            "Impossible de dupliquer une semaine...merci de contacter ProLibre")


class GenerateCalendarStart(ModelView):
    "Generate Calendar Start"
    __name__ = 'pl_cust_reportactivity.generate_calendar_start'

    year = fields.Integer('Year to generate')

class GenerateCalendar(Wizard):
    "Generate Calendar"
    __name__ = 'pl_cust_reportactivity.generate_calendar'

    start = StateView('pl_cust_reportactivity.generate_calendar_start',
                      'pl_cust_reportactivity.generate_calendar_start_view_form', [
                          Button('Cancel', 'end', 'tryton-cancel'),
                          Button('Generate', 'generate',
                                 'tryton-ok', default=True),
                      ])
    generate = StateTransition()

    def transition_generate(self):
        pool = Pool()
        obj_CALENDAR = pool.get('pl_cust_reportactivity.calendar')

        if obj_CALENDAR.search(['year', '=', self.start.year]):
            return 'end'

        annee = self.start.year
        
        jours_sans_weekend = []
        # Parcourir tous les jours de l'année
        for mois in range(1, 13):  # de janvier (1) à décembre (12)
            for jour in range(1, 32):  # maximum 31 jours dans un mois
                try:
                    date_tmp = date(annee, mois, jour)
                    
                    # Si ce n'est ni samedi (5) ni dimanche (6)
                    if date_tmp.weekday() < 5:
                        jours_sans_weekend.append({'date' : date_tmp, 'year' : annee, 'name': str(date_tmp)})
                        
                except ValueError:
                    # Ignore les jours invalides (par exemple le 31 février)
                    continue
        
        obj_CALENDAR.create(jours_sans_weekend)

        return 'end'


class GenerateDayOffStart(ModelView):
    "Generate DayOff Start"
    __name__ = 'pl_cust_feefolders.generate_dayoff_start'

    date_start = fields.Date('Date Start', required=True)
    date_end = fields.Date('Date End', help="Date", required=True)
    day_type = fields.Selection(DAY_TYPE, 'Type', required=True)

    @fields.depends('date_start', 'date_end')
    def on_change_date_start(self):
        if not self.date_end:
            self.date_end = self.date_start


class GenerateDayOff(Wizard):
    "Generate DayOff"
    __name__ = 'pl_cust_feefolders.generate_dayoff'

    start = StateView('pl_cust_feefolders.generate_dayoff_start',
                      'pl_cust_feefolders.generate_dayoff_start_view_form', [
                          Button('Cancel', 'end', 'tryton-cancel'),
                          Button('Generate', 'generate',
                                 'tryton-ok', default=True),
                      ])
    generate = StateTransition()

    def transition_generate(self):
        pool = Pool()
        obj_DAYOFF = pool.get('pl_cust_feefolders.dayoff')
        obj_WEEKS = pool.get('pl_cust_feefolders.weeks')

        start_date = self.start.date_start
        end_date = self.start.date_end

        year_to_do = []
        weeks = []
        if not obj_WEEKS.search(['year', '=', start_date.year]):
            year_to_do.append(start_date.year)

        if start_date.year != end_date.year and not obj_WEEKS.search(['year', '=', end_date.year]):
            year_to_do.append(end_date.year)

        for ytd in year_to_do:
            for week in range(0, 54):
                date_year, week_number, day_of_week = datetime.strptime(
                    f'{ytd}-W{week}-1', "%Y-W%U-%w").isocalendar()
                if date_year == ytd:
                    start = datetime.strptime(
                        f'{date_year} {week_number} 1', "%G %V %u")
                    end = start + timedelta(days=4)
                    if {'date_start': start, 'date_end': end,
                            'week_number': week_number, 'year': date_year} not in weeks:
                        weeks.append({'date_start': start, 'date_end': end,
                                      'week_number': week_number, 'year': date_year})

        obj_WEEKS.create(weeks)

        d = start_date
        while d <= end_date:
            if d.weekday() < 5:
                if not obj_DAYOFF.search(['date', '=', d]):
                    obj_DAYOFF.create(
                        [{'date': d, 'day_type': self.start.day_type}])
            d += timedelta(days=1)

        return 'end'

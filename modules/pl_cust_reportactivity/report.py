# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.model import ModelView, ModelSQL
from trytond.report import Report
from trytond.rpc import RPC
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateTransition, StateView, StateAction, \
    StateReport, Button
from datetime import datetime, timedelta

from decimal import *
import re

__all__ = ['ReportActivity']

import qrcode
import qrcode.image.svg
from barcode import Code39
from barcode.writer import ImageWriter

from PIL import Image
from trytond.model.exceptions import ValidationError

class RapportValidationError(ValidationError):
    pass

__all__ = ['AtivityReportStart', 'AtivityReport', 'PrintActivityReport']

def my_format_date(date):
    if not date:
        return '-'

    corresp = {
        1: 'janvier',
        2: 'février',
        3: 'mars',
        4: 'avril',
        5: 'mai',
        6: 'juin',
        7: 'juillet',
        8: 'août',
        9: 'septembre',
        10: 'octobre',
        11: 'novembre',
        12: 'décembre',
    }

    return '{} {} {}'.format(date.strftime("%-d"),
                             corresp[date.month],
                             date.strftime("%Y"),
                             )


def format_date2(date):
    if date :
        y, m, d = str(date).split('-')
        return '{}.{}.{}'.format(d, m, y)
    else :
        return '-'

class AtivityReportStart(ModelView):
    'Start activity report'
    __name__ = 'pl_cust_reportactivity.activityreport_start'
    from_date = fields.Date('From Date', required=True)
    to_date = fields.Date('To Date', required=False)
    employee_id = fields.Many2One(
        'company.employee', 'Employee', required=True)

    @staticmethod
    def default_employee_id():
        return Transaction().context.get('employee')

    @staticmethod
    def default_from_date():
        aujourdhui = datetime.now()
        lundi = aujourdhui - timedelta(days=aujourdhui.weekday())
        return lundi.date()

    @staticmethod
    def default_to_date():
        aujourdhui = datetime.now()
        lundi = aujourdhui - timedelta(days=aujourdhui.weekday())
        vendredi = lundi + timedelta(days=4)
        return vendredi.date()
    
class AtivityReport(Wizard):
    'Activity Report'
    __name__ = 'pl_cust_reportactivity.activitytreport'
    start = StateView('pl_cust_reportactivity.activityreport_start',
                      'pl_cust_reportactivity.activityreport_start_view_form', [
                          Button('Cancel', 'end', 'tryton-cancel'),
                          Button('Print', 'print_',
                                 'tryton-print', default=True),
                      ])
    print_ = StateReport('pl_cust_reportactivity.printactivityreport')

    def do_print_(self, action):
        Date_ = Pool().get('ir.date')

        data = {
            'employee_id': self.start.employee_id.id,
            'from_date': self.start.from_date,
            'to_date': self.start.to_date or Date_.today(),
        }
        return action, data

class PrintActivityReport(Report):
    __name__ = 'pl_cust_reportactivity.printactivityreport'

    @classmethod
    def execute(cls, ids, data):
        # Pour donner le nom au fichier
        res = super().execute(ids, data)
        # convert the res to a list because it is a tuple and we need to modify it
        aux = list(res)
        aux[-1] = 'rapport_activity'
        return tuple(aux)

    @classmethod
    def _get_records(cls, ids, model, data):

        FolderSheet = Pool().get('pl_cust_plfolders.foldersheet')

        clause = [
            ('resp_id', '=', data['employee_id']),
            ('date', '>=', data['from_date']),
            ('date', '<=', data['to_date']),
        ]

        return FolderSheet.search(clause,
                                  order=[('date', 'asc')])

    @classmethod
    def get_context(cls, records, headers, data):
        report_context = super().get_context(records, headers, data)

        Employee = Pool().get('company.employee')
        employ = Employee(data['employee_id'])
        TimeTables = Pool().get('pl_cust_timetracking.tttimetables')
        TTDays = Pool().get('pl_cust_timetracking.ttdays')
        Calendar = Pool().get('pl_cust_reportactivity.calendar')
        tt_id = TimeTables.search([('employee_id', '=', employ)])
        
        wd_corresp = {
                'mon':1,
                'tue':2,
                'wed':3,
                'thu':4,
                'fri':5,
                'sat':6,
                'sun':7,
            }   
        employ_theo_tot = {
                    1:0,
                    2:0,
                    3:0,
                    4:0,
                    5:0,
                    6:0,
                    7:0,
                }

        if tt_id:
            tt = TimeTables.browse(tt_id)[0]
        
            if tt:
                for wd in tt.weekly_detail:
                    employ_theo_tot[wd_corresp[wd.day]] = wd.tot_hours.hour + wd.tot_hours.minute/60.0

        clause = [
            ('employee_id', '=', data['employee_id']),
            ('date', '>=', data['from_date']),
            ('date', '<=', data['to_date']),
        ]

        all_ett = TTDays.search(clause,
                               order=[('date', 'asc')])

        list_month = []
        list_week = []
        tab_res = {}

        dict_month = {1: 'Janvier',
                      2: 'Février',
                      3: 'Mars',
                      4: 'Avril',
                      5: 'Mai',
                      6: 'Juin',
                      7: 'Juillet',
                      8: 'Août',
                      9: 'Septembre',
                      10: 'Octobre',
                      11: 'Novembre',
                      12: 'Décembre'
                      }

        dict_day = {1: 'Lun',
                    2: 'Mar',
                    3: 'Mer',
                    4: 'Jeu',
                    5: 'Ven',
                    6: 'Sam',
                    7: 'Dim',
                    }

        dict_ts = {}
        for ts in records:
            if not ts.date in dict_ts:
                dict_ts[ts.date] = []
            dict_ts[ts.date].append(ts)

        ett_date_list = [(d.date, d) for d in all_ett]
        dict_ett = dict(ett_date_list)

        tot_period_ett = 0
        tot_period_ts = 0

        date_check = data['from_date']
        fold = None

        while date_check <= data['to_date']:
            

            if date_check.isocalendar()[2] in (6, 7): 
                date_check += timedelta(1)
                continue

            month = '{} {}'.format(
                dict_month[date_check.month], date_check.year)
            week = 'Semaine {}'.format(date_check.isocalendar()[1])
            day = '{} {}'.format(dict_day[date_check.isocalendar()[
                                 2]], date_check.strftime('%d.%m.%Y'))

            if not month in list_month:
                tab_res[month] = {'tot_hours_month_ett': 0,
                                  'tot_hours_month_ts': 0,
                                  'tot_hours_month_theo': 0,
                                  'week_list': []}
                list_month.append(month)

            if not week in tab_res[month]['week_list']:
                tab_res[month][week] = {'day_list': [], 'tot_hours_week_theo': 0, 'tot_hours_week_ett': 0, 'tot_hours_week_ts': 0}
                tab_res[month]['week_list'].append(week)

            tab_res[month][week]['day_list'].append(day)

            tab_res[month][week][day] = {'tot_hours_day_ett': 0,
                                         'tot_hours_day_ts': 0,
                                         'tot_ett_theo' : employ_theo_tot[date_check.isocalendar()[2]],
                                         'tot_ett_reel' : 0,
                                         'hours_list': [],
                                         'hours_list_txt': '',
                                         'color': 0,
                                         'not_valid': False}

            tab_res[month]['tot_hours_month_theo'] += employ_theo_tot[date_check.isocalendar()[2]]
            tab_res[month][week]['tot_hours_week_theo'] += employ_theo_tot[date_check.isocalendar()[2]]
            
            if date_check in dict_ett:
                #Calculs pour l'ETT
                d = dict_ett[date_check]
                if not d.not_valid and d.tot_hours: 
                    hours_in_minutes_ett = d.tot_hours.hour + d.tot_hours.minute/60.0
                    tab_res[month]['tot_hours_month_ett'] += hours_in_minutes_ett
                    tab_res[month][week]['tot_hours_week_ett'] += hours_in_minutes_ett
                    tab_res[month][week][day]['tot_hours_day_ett'] += hours_in_minutes_ett
                    tot_period_ett += hours_in_minutes_ett
                    tab_res[month][week][day]['color'] = 0
                else: 
                    if d.not_valid :
                        tab_res[month][week][day]['color'] = 2
                        tab_res[month][week][day]['hours_list_txt'] = 'Erreur de pointage'
                    elif not d.day_type == 'std' and tab_res[month][week][day]['tot_ett_theo'] > 0:
                        tab_res[month][week][day]['color'] = 1
                        tab_res[month][week][day]['hours_list_txt'] = 'Maladie ou Vacances'
                        tab_res[month]['tot_hours_month_ett'] += employ_theo_tot[date_check.isocalendar()[2]]
                        tab_res[month][week]['tot_hours_week_ett'] += employ_theo_tot[date_check.isocalendar()[2]]
                        tab_res[month][week][day]['tot_hours_day_ett'] += employ_theo_tot[date_check.isocalendar()[2]]
                        tot_period_ett += employ_theo_tot[date_check.isocalendar()[2]]

            else :
                if tab_res[month][week][day]['tot_ett_theo'] > 0 : 
                    tab_res[month][week][day]['color'] = 4
                    tab_res[month][week][day]['hours_list_txt'] = "Pas de pointage"
                else :
                    tab_res[month][week][day]['color'] = 1
                    tab_res[month][week][day]['hours_list_txt'] = "Pas d'horaire"

            if date_check in dict_ts:
            
                #Calculs pour le TS
                tot_seconds_ts = 0
                for ts in dict_ts[date_check]:
                    tot_seconds_ts += ts.duration.total_seconds()

                hours_in_minutes_ts = tot_seconds_ts/3600
                # if hours_in_minutes_ts < 5.0:
                #     tab_res[month][week][day]['color'] = 2
                # elif hours_in_minutes_ts >= 8.0:
                #     tab_res[month][week][day]['color'] = 1
                # else:
                #     tab_res[month][week][day]['color'] = 0

                tab_res[month][week][day]['hours_list_txt'] = 'Nombre de TS : {}'.format(
                    len(dict_ts[date_check]))
                tab_res[month]['tot_hours_month_ts'] += hours_in_minutes_ts
                tab_res[month][week]['tot_hours_week_ts'] += hours_in_minutes_ts
                tab_res[month][week][day]['tot_hours_day_ts'] += hours_in_minutes_ts

                tot_period_ts += hours_in_minutes_ts
            else :
                    if tab_res[month][week][day]['color'] == 0 :
                        tab_res[month][week][day]['color'] = 4
                        tab_res[month][week][day]['hours_list_txt'] = tab_res[month][week][day]['hours_list_txt'] and tab_res[month][week][day]['hours_list_txt'] + ' | Pas de TS' or 'Pas de TS'


            cd = Calendar.search([('date' ,'=', date_check)])
            if cd and not cd[0].calendar_type == 's' :
                tab_res[month][week][day]['color'] = 1
                tab_res[month][week][day]['hours_list_txt'] = "Jour fermé"

            tab_res[month][week][day]['ratio'] = tab_res[month][week][day]['tot_hours_day_ett'] and tab_res[month][week][day]['tot_hours_day_ts'] / tab_res[month][week][day]['tot_hours_day_ett']*100
            date_check += timedelta(1)

        report_context['hours_tot_ts'] = tot_period_ts
        report_context['hours_tot_ett'] = tot_period_ett
        report_context['ratio'] = tot_period_ett and tot_period_ts / tot_period_ett*100
        report_context['list_month'] = list_month
        report_context['list_week'] = list_week
        report_context['tab_res'] = tab_res
        report_context['employee'] = employ
        report_context['from_date'] = data['from_date'].strftime("%d.%m.%Y")
        report_context['to_date'] = data['to_date'].strftime("%d.%m.%Y")

        return report_context

class ReportActivity(Report):
    __name__ = 'pl_cust_reportactivity.reportactivity'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__rpc__['execute'] = RPC(False)

    # @classmethod
    # def _execute(cls, records, header, data, action):
    #     pool = Pool()
    #     Invoice = pool.get('account.invoice')
    #     # Re-instantiate because records are TranslateModel
    #     inv = Invoice.browse(records)
    #     result = super()._execute(
    #         records, header, data, action)
    #     return result

    # @classmethod
    # def execute(cls, ids, data):
    #     pool = Pool()
    #     Invoice = pool.get('account.invoice')
    #     LANG = pool.get('ir.lang')
        
    #     with Transaction().set_context(
    #             language='fr',
    #             address_with_party=True):
    #         result = super().execute(ids, data)
    #         return result

    @classmethod
    def get_context(cls, records, headers, data):
        pool = Pool()
        Date = pool.get('ir.date')
        LANG = pool.get('ir.lang')

        context = super().get_context(records, headers, data)

        # print(context)
        context['folders'] = context['record']
        context['lang'] = LANG(LANG.search([('code', '=', 'fr')])[0])

        context['lines'] = []
        
        #context['mytoday'] = my_format_date(context['invoice'].invoice_date)
        context['mytoday_now'] = my_format_date(Date.today())

        return context

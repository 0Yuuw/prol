# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from datetime import timedelta
from trytond.model import ModelView, fields
from trytond.model.exceptions import AccessError
from trytond.wizard import Wizard, StateTransition, StateView, StateAction, \
    StateReport, Button
from trytond.report import Report
from trytond.transaction import Transaction
from trytond.pool import Pool
import sys
import locale


__all__ = ['FoldPrintReportStart', 'FoldPrintReport', 'FoldReport', 'FoldTSReport']


class FoldPrintReportStart(ModelView):
    'Print Fold Report'
    __name__ = 'pl_cust_plfolders.foldprintreport_start'
    from_date = fields.Date('From Date', required=True)
    to_date = fields.Date('To Date', required=False)
    employee_id = fields.Many2One(
        'company.employee', 'Employee', required=True)

    @staticmethod
    def default_employee_id():
        return Transaction().context.get('employee')


class FoldPrintReport(Wizard):
    'Print Fold Report'
    __name__ = 'pl_cust_plfolders.foldprintreport'
    start = StateView('pl_cust_plfolders.foldprintreport_start',
                      'pl_cust_plfolders.foldprintreport_start_view_form', [
                          Button('Cancel', 'end', 'tryton-cancel'),
                          Button('Print', 'print_',
                                 'tryton-print', default=True),
                      ])
    print_ = StateReport('pl_cust_plfolders.foldreport')

    def do_print_(self, action):
        Date_ = Pool().get('ir.date')

        data = {
            'employee_id': self.start.employee_id.id,
            'from_date': self.start.from_date,
            'to_date': self.start.to_date or Date_.today(),
        }
        return action, data


class FoldReport(Report):
    __name__ = 'pl_cust_plfolders.foldreport'

    @classmethod
    def execute(cls, ids, data):
        # Pour donner le nom au fichier
        res = super().execute(ids, data)
        # convert the res to a list because it is a tuple and we need to modify it
        aux = list(res)
        aux[-1] = 'Rapport_de_TS'
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

        # report_context['company'] = company
        # report_context['digits'] = company.currency.digits

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

        dict_record = {}

        for ts in records:
            if not ts.date in dict_record:
                dict_record[ts.date] = []
            dict_record[ts.date].append(ts)

        tot_period = 0
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
                tab_res[month] = {'tot_hours_month': 0,
                                  'week_list': []}
                list_month.append(month)

            if not week in tab_res[month]['week_list']:
                tab_res[month][week] = {'day_list': [], 'tot_hours_week': 0}
                tab_res[month]['week_list'].append(week)

            tab_res[month][week]['day_list'].append(day)
            if date_check in dict_record:
                tab_res[month][week][day] = {'tot_hours_day': 0,
                                             'hours_list': [],
                                             'hours_list_txt': '',
                                             'color': 0,
                                             'not_valid': False}
                tot_seconds = 0
                for ts in dict_record[date_check]:
                    tot_seconds += ts.duration.total_seconds()

                hours_in_minutes = tot_seconds/3600
                if hours_in_minutes < 5.0:
                    tab_res[month][week][day]['color'] = 2
                elif hours_in_minutes >= 8.0:
                    tab_res[month][week][day]['color'] = 1
                else:
                    tab_res[month][week][day]['color'] = 0

                tab_res[month][week][day]['hours_list_txt'] = 'Nombre de TS : {}'.format(
                    len(dict_record[date_check]))
                tab_res[month]['tot_hours_month'] += hours_in_minutes
                tab_res[month][week]['tot_hours_week'] += hours_in_minutes
                tab_res[month][week][day]['tot_hours_day'] += hours_in_minutes

                tot_period += hours_in_minutes

            else:

                tab_res[month][week][day] = {'tot_hours_day': 0,
                                             'hours_list': [],
                                             'color': 3,
                                             'hours_list_txt': 'AUCUN TS',
                                             'not_valid': True}

            date_check += timedelta(1)

        report_context['hours_tot'] = tot_period
        report_context['list_month'] = list_month
        report_context['list_week'] = list_week
        report_context['tab_res'] = tab_res
        report_context['employee'] = employ
        report_context['from_date'] = data['from_date'].strftime("%d.%m.%Y")
        report_context['to_date'] = data['to_date'].strftime("%d.%m.%Y")

        return report_context


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
    y, m, d = str(date).split('-')
    return '{}.{}.{}'.format(d, m, y[-2:])


def format_seconds(s):
    hours, remainder = divmod(s, 3600)
    minutes, seconds = divmod(remainder, 60)
    return hours, minutes, seconds

    minutes, seconds = divmod(remainder, 60)
    return hours, minutes, seconds

class FoldTSReport(Report):
    __name__ = 'pl_cust_plfolders.tsreport'

    @classmethod
    def execute(cls, ids, data):
        # Pour donner le nom au fichier
        res = super().execute(ids, data)
        # convert the res to a list because it is a tuple and we need to modify it
        aux = list(res)
        aux[-1] = 'Rapport_activites'
        return tuple(aux)

    @classmethod
    def get_context(cls, records, headers, data):
        pool = Pool()
        Date_ = pool.get('ir.date')
        LANG = pool.get('ir.lang')

        context = super().get_context(records, headers, data)
        context['folder'] = context['record']
        context['mytoday'] = my_format_date(Date_.today())
        context['mydate'] = format_date2(Date_.today())
        context['lang'] = LANG(LANG.search([('code', '=', 'fr')])[0])
        
        context['ts_tab']=[]
        tot_tmp = 0
        for ts in context['folder'].timesheet_ids[::-1] :
                     
            tmp_dur = round(ts.duration.seconds/3600,2)
            tmp_dur2 = round((ts.duration.seconds*int(ts.pct)/100)/3600,2)
            tot_tmp += ts.duration.seconds*int(ts.pct)/100
            
            context['ts_tab'].append((format_date2(ts.date),ts.name,'{:.2f}'.format(tmp_dur),ts.pct,'{:.2f}'.format(tmp_dur2),ts.resp_id.code))

        context['tot'] = '{:.2f}'.format(round(tot_tmp/3600,2))
    
        return context
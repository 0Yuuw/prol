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


__all__ = ['TTPrintReportStart', 'TTPrintReport', 'TTReport']


class TTPrintReportStart(ModelView):
    'Print TT Report'
    __name__ = 'pl_cust_timetracking.ttprintreport_start'
    from_date = fields.Date('From Date', required=True)
    to_date = fields.Date('To Date', required=True)
    employee_id = fields.Many2One(
        'company.employee', 'Employee', required=True)

    @staticmethod
    def default_employee_id():
        return Transaction().context.get('employee')


class TTPrintReport(Wizard):
    'Print TT Report'
    __name__ = 'pl_cust_timetracking.ttprintreport'
    start = StateView('pl_cust_timetracking.ttprintreport_start',
                      'pl_cust_timetracking.ttprintreport_start_view_form', [
                          Button('Cancel', 'end', 'tryton-cancel'),
                          Button('Print', 'print_',
                                 'tryton-print', default=True),
                      ])
    print_ = StateReport('pl_cust_timetracking.ttreport')

    def do_print_(self, action):
        data = {
            'employee_id': self.start.employee_id.id,
            'from_date': self.start.from_date,
            'to_date': self.start.to_date,
        }
        return action, data


class TTReport(Report):
    __name__ = 'pl_cust_timetracking.ttreport'

    @classmethod
    def _get_records(cls, ids, model, data):

        TTDays = Pool().get('pl_cust_timetracking.ttdays')

        clause = [
            ('employee_id', '=', data['employee_id']),
            ('date', '>=', data['from_date']),
            ('date', '<=', data['to_date']),
        ]

        return TTDays.search(clause,
                             order=[('date', 'asc')])

    @classmethod
    def get_context(cls, records, headers, data):
        report_context = super().get_context(records, headers, data)

        Employee = Pool().get('company.employee')
        TimeTables = Pool().get('pl_cust_timetracking.tttimetables')

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

        record_date_list = [(d.date, d) for d in records]
        dict_record = dict(record_date_list)
        tot_period = 0
        date_check = data['from_date']
        tt = None
        
        while date_check <= data['to_date']:
            overday = False
            tt_id = TimeTables.search([('employee_id', '=', employ)])
            if tt_id:
                tt = TimeTables.browse(tt_id)[0]
            if tt:
                if (date_check.isocalendar()[2] == 1 and not tt.monday) or \
                   (date_check.isocalendar()[2] == 2 and not tt.tuesday) or \
                   (date_check.isocalendar()[2] == 3 and not tt.wednesday) or \
                   (date_check.isocalendar()[2] == 4 and not tt.thursday) or \
                   (date_check.isocalendar()[2] == 5 and not tt.friday) or \
                   (date_check.isocalendar()[2] == 6 and not tt.saturday) or \
                   (date_check.isocalendar()[2] == 7 and not tt.sunday):

                    if date_check in dict_record:
                        overday = True
                    else:
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
                tab_res[month][week] = {'day_list': [],
                                        'tot_hours_week': 0}
                tab_res[month]['week_list'].append(week)

            tab_res[month][week]['day_list'].append(day)
            if date_check in dict_record:
                d = dict_record[date_check]
                if d.day_type == 'std':
                    tab_res[month][week][day] = {'tot_hours_day': 0,
                                                'hours_list': [],
                                                'hours_list_txt': d.not_valid and 'Jour NON valide' or '',
                                                'color': 3,
                                                'not_valid': d.not_valid}
                else: 
                    tab_res[month][week][day] = {'tot_hours_day': 0,
                                                 'hours_list': [],
                                                 'hours_list_txt': d.day_type_string + '  ',
                                                 'color': 4,
                                                 'not_valid': d.not_valid}

                if not d.not_valid and d.tot_hours: 
                    hours_in_minutes = d.tot_hours.hour + d.tot_hours.minute/60.0
                    tab_res[month]['tot_hours_month'] += hours_in_minutes
                    tab_res[month][week]['tot_hours_week'] += hours_in_minutes
                    tab_res[month][week][day]['tot_hours_day'] += hours_in_minutes
                    if d.day_type == 'std':
                        tab_res[month][week][day]['color'] = overday and 1 or 0
                    
                    tot_period += hours_in_minutes
                for h in d.hours_ids[:-1]:
                    if not d.not_valid:
                        if h.type_hour == 'in':
                            tab_res[month][week][day]['hours_list_txt'] += '{}'.format(
                                h.employ_hour.isoformat(timespec='minutes'))
                        else:
                            tab_res[month][week][day]['hours_list_txt'] += ' - {} | '.format(
                                h.employ_hour.isoformat(timespec='minutes'))
                    tab_res[month][week][day]['hours_list'].append(h)
                if d.hours_ids and not d.not_valid:
                    tab_res[month][week][day]['hours_list_txt'] += ' - {}'.format(
                        d.hours_ids[-1].employ_hour.isoformat(timespec='minutes'))
                
            else:
                tab_res[month][week][day] = {'tot_hours_day': 0,
                                             'hours_list': [],
                                             'color': 2,
                                             'hours_list_txt': 'AUCUN POINTAGE',
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

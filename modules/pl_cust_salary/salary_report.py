# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.model import ModelView, ModelSQL
from trytond.report import Report
from trytond.rpc import RPC
from trytond.pool import Pool
from trytond.transaction import Transaction
from datetime import datetime
from decimal import *
import re

__all__ = ['SalaryReport']

from trytond.model.exceptions import ValidationError


class RapportValidationError(ValidationError):
    pass


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
    if date:
        y, m, d = str(date).split('-')
        return '{}.{}.{}'.format(d, m, y)
    else:
        return '-'


class SalaryReport(Report):
    __name__ = 'pl_cust_salary.salary_report'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__rpc__['execute'] = RPC(False)

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
        CURRENCY = pool.get('currency.currency')

        context = super().get_context(records, headers, data)

        # print(context)
        context['salary'] = context['record']
        context['lang'] = LANG(LANG.search([('code', '=', 'fr')])[0])
        context['currency'] = CURRENCY(
            CURRENCY.search([('code', '=', 'CHF')])[0])

        context['gross_salary'] = '{}'.format(cls.format_currency(context['salary'].gross_salary,
                                                                  context['lang'],
                                                                  context['currency']))

        context['gs_and_prim'] = '{}'.format(cls.format_currency(context['salary'].gross_salary + context['salary'].prim + context['salary'].prim2 + context['salary'].prim3,
                                                                  context['lang'],
                                                                  context['currency']))
        
        context['net_salary'] = '{}'.format(cls.format_currency(context['salary'].net_salary,
                                                                  context['lang'],
                                                                  context['currency']))
        
        context['prim'] = '{}'.format(cls.format_currency(context['salary'].prim,
                                                                  context['lang'],
                                                                  context['currency']))
                                                                
        context['prim2'] = '{}'.format(cls.format_currency(context['salary'].prim2,
                                                                  context['lang'],
                                                                  context['currency']))

        context['prim3'] = '{}'.format(cls.format_currency(context['salary'].prim3,
                                                                  context['lang'],
                                                                  context['currency']))

        context['prim4_without_tax'] = '{}'.format(cls.format_currency(context['salary'].prim4_without_tax,
                                                                  context['lang'],
                                                                  context['currency']))

        context['car'] = '{}'.format(cls.format_currency(context['salary'].car_charge,
                                                                  context['lang'],
                                                                  context['currency']))

        context['alloc'] = '{}'.format(cls.format_currency(context['salary'].alloc_charge,
                                                                  context['lang'],
                                                                  context['currency']))
                                                            
        context['gs_and_car'] = '{}'.format(cls.format_currency(context['salary'].gross_salary + context['salary'].prim + context['salary'].prim2 + context['salary'].prim3 + context['salary'].car_charge,
                                                                  context['lang'],
                                                                  context['currency']))

        context['gs_and_car_and_alloc'] = '{}'.format(cls.format_currency(context['salary'].gross_salary + context['salary'].prim + context['salary'].prim2 + context['salary'].prim3 + context['salary'].car_charge + context['salary'].alloc_charge,
                                                                  context['lang'],
                                                                  context['currency']))                                                

        context['lines'] = []
        tot_lines = 0

        for sl in context['salary'].line_ids:
            if sl.amount_employee > 0:
                tot_lines += sl.amount_employee
                context['lines'].append([
                    sl.name,
                    '{:.3f}'.format(sl.tx_employee),
                    '{}'.format(cls.format_currency(sl.amount_employee*-1,
                                                    context['lang'],
                                                    context['currency'])),
                    context['gs_and_car']])

        if context['salary'].lpp_charge > 0:
            tot_lines += context['salary'].lpp_charge
            context['lines'].append([
                    context['salary'].lpp_charge_txt,
                    '',
                    '{}'.format(cls.format_currency(context['salary'].lpp_charge*-1,
                                                    context['lang'],
                                                    context['currency'])),
                    ''])

        if context['salary'].is_charge > 0:
            tot_lines += context['salary'].is_charge_amount
            context['lines'].append([
                    context['salary'].is_charge_txt,
                    '{:.3f}'.format(context['salary'].is_charge),
                    '{}'.format(cls.format_currency(context['salary'].is_charge_amount*-1,
                                                    context['lang'],
                                                    context['currency'])),
                    context['gs_and_car_and_alloc']])

        context['lines'].append([
                    'Total déductions sociales',
                    '',
                    '{}'.format(cls.format_currency(tot_lines*-1,
                                                    context['lang'],
                                                    context['currency'])),
                    ''])

        context['employ_addr']=context['salary'].resp_id.party.addresses[0]
        context['mytoday']=my_format_date(context['salary'].date)
        context['mytoday_now']=my_format_date(Date.today())

        return context

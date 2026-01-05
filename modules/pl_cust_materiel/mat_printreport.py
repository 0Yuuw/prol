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


__all__ = ['MatDayReport']

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

    corresp2 = {
        '0': 'Dimanche',
        '1': 'Lundi',
        '2': 'Mardi',
        '3': 'Mercredi',
        '4': 'Jeudi',
        '5': 'Vendredi',
        '6': 'Samedi',
    }

    return '{} {} {} {}'.format(corresp2[date.strftime("%w")],
                             date.strftime("%-d"),
                             corresp[date.month],
                             date.strftime("%Y"),
                             )

class MatDayReport(Report):
    __name__ = 'pl_cust_materiel.matdayreport'

    @classmethod
    def execute(cls, ids, data):
        pool = Pool()
        MATDAY = pool.get('pl_cust_materiel.matday')
        md = MATDAY(data['id'])

        # Pour donner le nom au fichier
        res = super().execute(ids, data)
        # convert the res to a list because it is a tuple and we need to modify it
        aux = list(res)
        aux[-1] = 'Resume_journalier_{}'.format(md.date)
        return tuple(aux)

    @classmethod
    def get_context(cls, records, headers, data):

        context = super().get_context(records, headers, data)
        context['matday'] = context['record']
        context['titre'] = my_format_date(context['matday'].date)

        return context

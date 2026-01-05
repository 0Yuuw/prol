from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.model import ModelView, fields
from trytond.pool import Pool
from trytond.transaction import Transaction
from datetime import datetime, date
import codecs
import os
import csv

from trytond.model.exceptions import ValidationError


class TSReportError(ValidationError):
    pass


__all__ = ['WizardService', 'WizardServiceStart']

class WizardServiceStart(ModelView):
    """ First window to choose the export year """
    __name__ = 'pl_cust_tel.wizard_service_start'
    
    call_writer = fields.Many2One(
        'party.party',
        "Écoutant",
        required=True,
        domain=[('is_writer', '=', True)]
    )

    #@staticmethod   
    #def default_call_writer():
    #    pool = Pool()
    #    CurrentWriter = pool.get('pl_cust_tel.currentwriter')
    #    return CurrentWriter(1).call_writer and CurrentWriter(1).call_writer.id or None 

class WizardService(Wizard):
    "Wizard Export"
    __name__ = "pl_cust_tel.wizard_service"

    start = StateView(
        'pl_cust_tel.wizard_service_start',
        'pl_cust_tel.wizard_service_view_form',
        [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Prise de service', 'change', 'tryton-ok', default=True),
        ]
    )

    change = StateTransition()

    def transition_change(self):
        """ Generates a CSV file containing call statistics """

        pool = Pool()
        CurrentWriter = pool.get('pl_cust_tel.currentwriter')

        cw = CurrentWriter(1)
        cw.call_writer = self.start.call_writer
        cw.save()

        return 'end'
        

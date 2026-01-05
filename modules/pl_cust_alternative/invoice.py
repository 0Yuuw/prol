# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import (
    ModelView, ModelSQL, MatchMixin, DeactivableMixin, fields,
    sequence_ordered, Workflow)
from trytond.modules.account_invoice.exceptions import InvoiceNumberError

from trytond.pool import PoolMeta
from trytond.report import Report
from trytond.rpc import RPC
from trytond.pyson import Eval, If, Less
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.i18n import gettext
from trytond.exceptions import UserError
from itertools import groupby
from trytond.model.exceptions import AccessError

__all__ = ['AltInvoice']


class AltInvoice(ModelSQL, ModelView):
    'Alt Invoice'
    __name__ = 'account.invoice'
    
    @classmethod
    def set_number(cls, invoices):
    
        super(AltInvoice,cls).set_number(invoices)
        
        for invoice in invoices :
          
            if '-' in invoice.number or invoice.type == 'in':
                continue 
                
            if invoice.folder_id :
                    invoice.number += '-{}'.format(invoice.folder_id.name)

        cls.save(invoices)
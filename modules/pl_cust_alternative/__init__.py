# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .fold_printreport import *
from .invoice import *

def register():
    
    Pool.register(
        AltInvoice,
        module='pl_cust_alternative', type_='model')

    Pool.register(
        AltFoldReport,
        module="pl_cust_alternative", type_="report")
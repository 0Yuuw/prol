# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .folder import *
from .wizard_createinv import *
from.devis_printreport import *

def register():
    Pool.register(
        Devis,
        DevisFolders,
        DevisCreateInvoiceStart,
        module='pl_cust_devis', type_='model')
    
    Pool.register(
       DevisCreateInvoice,
       module='pl_cust_devis', type_='wizard')
    
    Pool.register(
        DevisReport,
        module='pl_cust_devis', type_='report')
    
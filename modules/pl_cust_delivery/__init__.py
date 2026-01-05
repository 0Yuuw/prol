# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .folder import *
from .wizard_createdelivery import *
from .wizard_createinv import *
from .delivery_printreport import *

def register():
    Pool.register(
        Delivery,
        DevisDelivery,
        DevisDeliveryFolders,
        CreateDeliveryStart,
        DeliveryCreateInvoiceStart,
        DeliveryTMP,
        module='pl_cust_delivery', type_='model')
    
    Pool.register(
        CreateDelivery,
        DeliveryCreateInvoice,
        module='pl_cust_delivery', type_='wizard')
    
    Pool.register(
        DeliveryDevisReport,
        DeliveryReport,
        module='pl_cust_delivery', type_='report')
    
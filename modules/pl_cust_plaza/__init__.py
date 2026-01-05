# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .party import *
from .wizard_data_export import *


def register():
    Pool.register(
        PlazaParty,
        PlazaAddress,
        DataExportStart,
        DataExportRes,
        module='pl_cust_plaza', type_='model')

    Pool.register(
        DataExport, 
        module='pl_cust_plaza', type_='wizard')

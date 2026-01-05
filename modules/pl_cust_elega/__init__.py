# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
# from .party import *
from .folder import *
from .elega_printreport import *

def register():
    Pool.register(
        ElegaFolders,
        module='pl_cust_plfolders', type_='model')

    Pool.register(
        ElegaReport,
        module='pl_cust_elega', type_='report')
    
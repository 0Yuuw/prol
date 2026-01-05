# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .folder import *

def register():
    pass
    Pool.register(
        InstParty,
        InstSheet,
        InstFolders,
        module='pl_cust_institutions', type_='model')

    #Pool.register(
    #    PeriodicTSWizard,
    #    module='pl_cust_institutions', type_='wizard')
   
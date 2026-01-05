# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .party import *

__all__ = ['register']

def register():
    Pool.register(
        PLBaseParty, 
        PLBasePartyTitle,
        PLBasePartyType,
        PLBasePartyLang,
        PLBaseAddress,
        module='pl_cust_plbase', type_='model')
#    Pool.register(
#        #PLImportStatement,
#        module='pl_cust_account', type_='wizard')
    

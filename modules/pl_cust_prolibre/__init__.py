# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .wizard_importts import *
from .folder import *

def register():
    Pool.register(
        PLFolders,
        PLFolderSheet,
        ImportTSStart,
        module='pl_cust_prolibre', type_='model')

    
    Pool.register(
       ImportTS,
       module='pl_cust_prolibre', type_='wizard')



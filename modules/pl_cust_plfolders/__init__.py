# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .configuration import *
from .folders import *
from .wizard_tstoinv import *
from .fold_printreport import *
from .wizard_createinv import *
from .add_periodic_ts_wizard import *

__all__ = ['register']

def register():
    
    Pool.register(
        FoldersWizardInvoice,
        FoldEmployeeType,
        FoldEmployee,
        FoldersConfiguration, 
        FoldersConfigurationSequence,
        FolderType,
        Folders, 
        FolderSheet, 
        SheetAct,   
        SheetTask,
        FoldSequence,
        FoldInvoice,
        TStoInvStart,
        FoldPrintReportStart,
        CreateInvoiceStart,
        PeriodicTSWizardStart,
        module='pl_cust_plfolders', type_='model')

    Pool.register(
        #PLImportStatement,
        TStoInv,
        FoldPrintReport,
        CreateInvoice,
        PeriodicTSWizard,
        module='pl_cust_plfolders', type_='wizard')

    Pool.register(
        FoldReport,
        FoldTSReport,
        module='pl_cust_plfolders', type_='report')
    
     
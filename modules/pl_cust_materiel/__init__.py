# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .materiel import *
from .wizard_manifestation import *
from .wizard_reparation import *
from .wizard_checkstock import *    
from .wizard_changestock import *    
from .wizard_changemanifestation import *
from .wiz_gen_days import *
from .mat_printreport import *
from. party import *

def register():
    
    Pool.register(
        Party,
        MatDayList,
        MatDay,
        Atelier,
        LieuManif,
        Logs,
        Materiel,
        Location,
        Manifestation,
        LocationTMP,
        LocationTMP2,
        AddManifStart,
        AddManifStep2,
        AddManifStep3,
        ChangeManifStart,
        ChangeManifStep2,
        ChangeManifStep3, 
        CheckStockStart,
        CheckStockStep2,
        ChangeStockStart,
        ChangeStockStep2,
        AddRepaStart,
        AddRepaStep2,
        ReturnRepaStart,
        GenerateDaysStart,
        module='pl_cust_materiel', type_='model')

    Pool.register(
        AddManif, 
        ChangeManif,
        CheckStock,
        ChangeStock,
        AddRepa,
        ReturnRepa,
        GenerateDays,
        module='pl_cust_materiel', type_='wizard')

    Pool.register(
        MatDayReport,
        module='pl_cust_materiel', type_='report')


# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .configuration import *
from .projects import *

__all__ = ['register']

def register():
    
    Pool.register(
        Category,
        ProjectLogs,
        ProjectTask,
        ProjectSheet,
        ProjectCategory,
        ProjectStage,
        ProjectsType,
        ProjectsAxe,
        ProjectParty,
        Party,
        ProjectPartyAddr,
        PartyAddr,
        Projects,
        module='pl_cust_plprojects', type_='model')

#     Pool.register(
#         ,
#         module='pl_cust_plprojects', type_='wizard')

#     Pool.register(
#         ,
#         module='pl_cust_plprojects', type_='report')
    
     
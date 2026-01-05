# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .foldersfollow import *

__all__ = ['register']

def register():
    
    Pool.register(
        FoldersFollowType,
        FoldersFollowWho,
        FoldersFollow, 
        FolldersFollowTasks, 
        Tasks,   
        module='pl_cust_foldersfollow', type_='model')

    # Pool.register(
    #     module='pl_cust_foldersfollow', type_='wizard')

    # Pool.register(
    #     module='pl_cust_foldersfollow', type_='report')
    
     
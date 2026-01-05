# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .calls import *
from . import party
from .wizard_export import *
from .wizard_service import *

def register():
    Pool.register(
        CallsConfiguration,
        CurrentWriter,
        RegularCalls,
        Calls,
        party.Party,
        WizardStart,
        WizardResult,
        WizardServiceStart,
        module='pl_cust_tel', type_='model')

    Pool.register(WizardExport,
                  WizardService,
                module='pl_cust_tel', type_='wizard')

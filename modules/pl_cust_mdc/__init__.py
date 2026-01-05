# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .mdc_conf import *
from .mdc_pub import *
from .mdc_inst import *
from .wizard_createinv import *
from .wiz_gen_days import *
from . import user
from . import routes

__all__ = ["register", "routes"]


def register():
    Pool.register(
        BookingWizardInvoice,
        MDCConfiguration,
        CreateInvoiceStart,
        GenerateDaysPubStart,
        GenerateDaysInstStart,
        BookingConfigurationSequence,
        MDCDayPub,
        MDCDayInst,
        MDCBookingPub,
        MDCGiftVoucher,
        MDCBookingInst,
        user.UserApplication,
        module="pl_cust_mdc",
        type_="model",
    )

    Pool.register(
        CreateInvoice,
        GenerateDaysPub,
        GenerateDaysInst,
        module="pl_cust_mdc",
        type_="wizard",
    )

    Pool.register(MDCReportPub, MDCReportVoucher, module="pl_cust_mdc", type_="report")

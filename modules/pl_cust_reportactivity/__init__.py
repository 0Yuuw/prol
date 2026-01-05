# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .report import *
from .calendar import *

def register():

    Pool.register(
        Calendar,
        GenerateCalendarStart,
        AtivityReportStart,
        module='pl_cust_reportactivity', type_='model')

    Pool.register(
        GenerateCalendar,
        AtivityReport,
        module='pl_cust_reportactivity', type_='wizard')

    Pool.register(
        PrintActivityReport,
        module="pl_cust_reportactivity", type_="report")
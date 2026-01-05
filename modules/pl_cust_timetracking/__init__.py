# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .timetracking import *
from .ttwizard import *
from .ttprintreport import *
from .add_day_wizard import *
from .hlwizard import *

def register():
    Pool.register(
        HLWizardStart,
        TTWeeklyDetail,
        TTWeeklyDetailHours,
        TTTimetables,
        TTDays,
        TTDaysType,
        TTHours,
        TTOvertimeValidate,
        TTWizardStart,
        TTPrintReportStart,
        TTAddDayWizardStart,
        module='pl_cust_timetracking', type_='model')

    Pool.register(#HLWizard,
                  TTWizard,
                  TTAddDayWizard,
                  TTPrintReport,
                  module='pl_cust_timetracking', type_='wizard')

    Pool.register(
        TTReport,
        module='pl_cust_timetracking', type_='report')

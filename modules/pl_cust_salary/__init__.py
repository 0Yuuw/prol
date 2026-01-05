# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .salary import *
from .salary_report import *

def register():
    Pool.register(
        SalEmployee,
        SalaryCat,
        SalaryConfSocialCharge,
        SocialCharges,
        SalaryContract,
        SalarySalaryLine, 
        SalarySalary,
        module='pl_cust_salary', type_='model')

    Pool.register(
        SalaryReport,
        module='pl_cust_salary', type_='report')
    
    Pool.register(
       CreateSalary,
       module='pl_cust_salary', type_='wizard')



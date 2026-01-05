# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import (
    ModelSQL,
    DeactivableMixin,
    Workflow,
    ModelView,
    fields,
    sequence_ordered,
)
from trytond.pyson import Eval, Bool
from datetime import datetime, timedelta
from trytond.pool import PoolMeta, Pool
from trytond.report import Report
from trytond.rpc import RPC
from trytond.transaction import Transaction
from decimal import *
from trytond.model.exceptions import ValidationError

__all__ = ["InstParty", "InstFolders", "InstSheet"]

def _date_limite(date):
    d_limite = date - timedelta(days=1)
    while d_limite.weekday() >= 5:  # Si la date est un samedi ou un dimanche
        d_limite -= timedelta(days=1)
    return d_limite

class DateValidationError(ValidationError):
    pass

class UnableToDelete(ValidationError):
    pass

class InstParty(ModelView):
    __name__ = 'party.party'

    is_child = fields.Boolean('Child')
    is_employee = fields.Boolean('Employee')

class InstFolders(ModelView):
    "Folders"
    __name__ = "pl_cust_plfolders.folders"

    resp_id = fields.Many2One('company.employee', 'Employee')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        # Récupération du domaine existant et ajout d'une nouvelle condition
        cls.party_id.domain = [('is_employee', '=', True)]

    @fields.depends('party_id')
    def on_change_with_resp_id(self, name=None):
        pool = Pool()
        Employee = pool.get('company.employee')
        if self.party_id:      
           emp =  Employee.search(['party','=', self.party_id])
           return emp and emp[0] or None 
    
class InstSheet(ModelView):
    "Sheet"
    __name__ = "pl_cust_plfolders.foldersheet"

    child_id = fields.Many2One('party.party', 'Child', domain=[('is_child', '=', True)])

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        vlist = [x.copy() for x in vlist]
        Date_ = pool.get('ir.date')
        today_ = Date_.today()
        User = pool.get('res.user')
        Group = pool.get('res.group')
        user = User(Transaction().user)
        ModelData = pool.get('ir.model.data')
        admingroup = Group(ModelData.get_id('pl_cust_plfolders',
                    'group_folder_admin'))
        is_admin = admingroup in user.groups

        for values in vlist:
            if not is_admin :
                if (values.get('date') and values.get('date') > Date_.today()):
                    raise DateValidationError(
                        "Vous ne pouvez pas entrer du timesheet pour une date dans le futur")
                elif values.get('date') and values.get('date') < _date_limite(today_):
                    raise DateValidationError(
                        "Vous ne pouvez pas entrer du timesheet pour cette date (Maximum 24h)")

        return super().create(vlist)

    @classmethod
    def write(cls, *args):

        pool = Pool()
        Date_ = pool.get('ir.date')
        today_ = Date_.today()
        User = pool.get('res.user')
        Group = pool.get('res.group')
        user = User(Transaction().user)
        ModelData = pool.get('ir.model.data')
        admingroup = Group(ModelData.get_id('pl_cust_plfolders',
                    'group_folder_admin'))
        is_admin = admingroup in user.groups
        EMPLOYEE = Pool().get('company.employee')
        employ = EMPLOYEE(Transaction().context.get('employee'))

        actions = iter(args)
        for foldersheets, values in zip(actions, actions):
            for ts in foldersheets:
                print(values.keys())
                
                
                if not is_admin and 'date' in values.keys():
                    if (values.get('date') and values.get('date') > Date_.today()):
                        raise DateValidationError(
                            "Vous ne pouvez pas entrer du timesheet pour une date dans le futur")
                    elif values.get('date') and values.get('date') < _date_limite(today_):
                        raise DateValidationError(
                            "Vous ne pouvez pas entrer du timesheet pour cette date (Maximum 24h)")

                elif not is_admin:
                    if ts.date < _date_limite(today_):
                        raise DateValidationError(
                            "Vous ne pouvez pas modifier du timesheet pour cette date (Maximum 24h)")
                    
        super().write(*args)



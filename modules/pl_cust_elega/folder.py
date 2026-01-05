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

__all__ = ["ElegaFolders"]

class ElegaFolders(ModelView):
    "Folders"
    __name__ = "pl_cust_plfolders.folders"

    
    @classmethod
    def create(cls, vlist):
        vlist = [x.copy() for x in vlist]
        employ = ''
        year_now = datetime.now().year
        year_short = datetime.now().strftime("%y") 
        for values in vlist:
            if not values.get('name'):
                values['name'] = cls._new_name()

            if values.get('name') : 
                values['name'] = values['name'].replace('D/{}'.format(year_now),'D/{}'.format(year_short))

        return super().create(vlist)




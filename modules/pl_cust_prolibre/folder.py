# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, DeactivableMixin, Workflow, ModelView, fields
from trytond.pyson import Eval
from datetime import datetime, timedelta
from trytond.pool import PoolMeta, Pool
from trytond.report import Report
from trytond.rpc import RPC
from trytond.transaction import Transaction
from decimal import *

__all__ = ['PLFolders', 'PLFolderSheet' ]


class PLFolderSheet(ModelSQL, ModelView):
    'PL Folder timesheet'
    __name__ = 'pl_cust_plfolders.foldersheet'

   
    @staticmethod
    def default_task():
        
        TASKS = Pool().get('pl_cust_plfolders.sheettasks')
        def_task = TASKS.search([('name', '=', 'Support')])
       
        return def_task and def_task[0].id or None
      
    @fields.depends('task', 'name', 'duration')
    def on_change_task(self):
        if not self.task:
            self.activity = None
        else:
            self.activity = self.task.activity
            if not self.duration and not self.task.duration == timedelta(0):
                self.duration = self.task.duration


class PLFolders(DeactivableMixin, Workflow, ModelSQL, ModelView):
    'Folders'
    __name__ = 'pl_cust_plfolders.folders'

    @classmethod
    def __setup__(cls):
        super().__setup__()

        cls._buttons.update({
            'importts': {
                'invisible': Eval('state') != 'open',
                'depends': ['state'],
            },
        })

    @classmethod
    @ModelView.button_action('pl_cust_prolibre.act_wizard_importts')
    def importts(cls, folders):
        pass

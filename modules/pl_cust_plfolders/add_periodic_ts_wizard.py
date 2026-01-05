from datetime import datetime, timedelta
from trytond.model import ModelView, fields
from trytond.pyson import If, Eval, Bool
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pool import Pool
from trytond.transaction import Transaction

__all__ = ['PeriodicTSWizard', 'PeriodicTSWizardStart', ]

class PeriodicTSWizardStart(ModelView):
    'PeriodicTSWizardStart'
    __name__ = 'pl_cust_plfolders.periodicts.start'

    folder_id = fields.Many2One(
        'pl_cust_plfolders.folders', 'Folder', required=True, states={
            "readonly": Bool(Eval("folder_id")),
        },
        depends=["folder_id"])
    employee = fields.Many2One('company.employee', 'Employee', states={
            "readonly": Bool(Eval("employee")),
        },
        depends=["employee"], required=True)    
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True)
    timesheet_ids = fields.One2Many(
        'pl_cust_plfolders.foldersheet', None, 'Timesheet', domain=[
        ('folder_id', '=', Eval('folder_id')),('resp_id','=',Eval('employee')), ('date','=',Eval('start_date')),], depends=['folder_id','employee','start_date'])

    day_of_week = fields.Selection([
        ('0', 'Monday'),
        ('1', 'Tuesday'),
        ('2', 'Wednesday'),
        ('3', 'Thursday'),
        ('4', 'Friday')
    ], 'Day of Week', required=True, sort=False)

    @staticmethod
    def default_folder_id():
        if Transaction().context.get('active_model', '') == 'pl_cust_plfolders.folders':
            return Transaction().context.get('active_id', '')
        return None

    @fields.depends('folder_id')
    def on_change_folder_id(self):
        if self.folder_id and hasattr(self.folder_id,'resp_id'):
            self.employee = self.folder_id.resp_id

class PeriodicTSWizard(Wizard):
    'PeriodicTSWizard'
    __name__ = 'pl_cust_plfolders.periodicts'

    start = StateView('pl_cust_plfolders.periodicts.start',
                      'pl_cust_plfolders.periodicts_start_view_form', [
                          Button('Cancel', 'end', 'tryton-cancel'),
                          Button('Ajouter', 'add_periodic_ts', 'tryton-ok', default=True),
                      ])

    add_periodic_ts = StateTransition()

    def transition_add_periodic_ts(self):
        pool = Pool()
        TimeSheet = pool.get('pl_cust_plfolders.foldersheet')

        
        employee = self.start.employee
        start_date = self.start.start_date
        end_date = self.start.end_date
        day_of_week = self.start.day_of_week

        current_date = start_date

        while current_date <= end_date:
            if current_date.weekday() not in [5, 6]:
                if current_date.weekday() == int(day_of_week):
                    for ts in self.start.timesheet_ids :
                        new_ts = TimeSheet.create([{
                            'name' : ts.name,
                            'activity' : ts.activity.id,
                            'task' : ts.task.id,
                            'date' : current_date,
                            'folder_id' : self.start.folder_id.id,
                            'duration' : ts.duration,
                            'resp_id' : self.start.employee.id,
                            }])
                        new_ts[0].save()

            current_date += timedelta(days=1)

        return 'end'

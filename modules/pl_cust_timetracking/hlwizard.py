from datetime import datetime, timedelta
from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pool import Pool
from trytond.transaction import Transaction

__all__ = ['HLWizard', 'HLWizardStart', ]

class HLWizardStart(ModelView):
    'Holiday Wizard Start'
    __name__ = 'pl_cust_timetracking.hlwizard_start'

    employee = fields.Many2One('company.employee', 'Employee', required=True)
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True)
    day_type = fields.Selection('get_day_type', "Type", required=True)
    day_of_week = fields.Selection([
        ('0', 'Monday'),
        ('1', 'Tuesday'),
        ('2', 'Wednesday'),
        ('3', 'Thursday'),
        ('4', 'Friday')
    ], 'Day of Week', sort=False)

    @classmethod
    def get_day_type(cls):
        DAYTYPE = Pool().get('pl_cust_timetracking.ttdaystype')
        all_type = DAYTYPE.search([])
        return [(ft.code, ft.name) for ft in all_type]

    @staticmethod
    def default_employee():
        return Transaction().context.get('employee')

class HLWizard(Wizard):
    'Holiday Wizard'
    __name__ = 'pl_cust_timetracking.hlwizard'

    start = StateView('pl_cust_timetracking.hlwizard_start',
                      'pl_cust_timetracking.hlwizard_start_view_form', [
                          Button('Cancel', 'end', 'tryton-cancel'),
                          Button('Update', 'update_day_type', 'tryton-ok', default=True),
                      ])
    update_day_type = StateTransition()

    def transition_update_day_type(self):
        pool = Pool()
        TTDays = pool.get('pl_cust_timetracking.ttdays')
        employee = self.start.employee
        start_date = self.start.start_date
        end_date = self.start.end_date
        day_type = self.start.day_type
        day_of_week = self.start.day_of_week

        current_date = start_date

        while current_date <= end_date:
            if current_date.weekday() not in [5, 6]:
                if day_of_week is None or current_date.weekday() == int(day_of_week):
                    ttdays = TTDays.search([
                        ('employee_id', '=', employee.id),
                        ('date', '=', current_date)
                    ])
                    if ttdays:
                        for ttday in ttdays:
                            ttday.day_type = day_type
                            ttday.save()
                    else:
                        TTDays.create([{
                            'employee_id': employee.id,
                            'date': current_date,
                            'day_type': day_type
                        }])
            current_date += timedelta(days=1)

        return 'end'

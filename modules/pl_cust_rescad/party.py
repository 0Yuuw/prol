from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import PoolMeta,Pool
from datetime import date

__all__ = ['RescadParty', 'RescadLogs', 'RescadTasks']

class RescadLogs(ModelSQL, ModelView):
    "Logs"
    __name__ = "pl_cust_rescad.logs"

    date = fields.Date("Date", required=True)
    subject = fields.Char("Sujet")
    description = fields.Text("Description")
    party = fields.Many2One('party.party', 'Party', required=True)
    #resp_id = fields.Many2One('company.employee', 'Employee', required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order = [
            ('date', 'DESC'),
            ("id", "DESC"),
        ]

    @staticmethod
    def default_date():
        Date = Pool().get('ir.date')
        return Date.today()
 
    # @staticmethod
    # def default_user():
    #     User = Pool().get('res.user')
    #     user = User(Transaction().user)
    #     return user.name


class RescadTasks(ModelSQL, ModelView):
    "Tasks"
    __name__ = "pl_cust_rescad.tasks"

    date = fields.Date("Date")
    description = fields.Text("Description")
    party = fields.Many2One('party.party', 'Party')
    resp_id = fields.Many2One('res.user', 'User')
    state = fields.Selection([('to_do','To do'),('done','Done'),('c','Canceled')], 'Annulé')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order = [
            ('date', 'DESC'),
            ("id", "DESC"),
        ]
    
    @staticmethod
    def default_state():
        return 'to_do'

    @staticmethod
    def default_date():
        Date = Pool().get('ir.date')
        return Date.today()
 
    # @staticmethod
    # def default_resp_id():
    #     User = Pool().get('res.user')
    #     user = User(Transaction().user)
    #     return user.name

class RescadParty(metaclass=PoolMeta):
    __name__ = 'party.party'

    investment_profile = fields.Selection([('',''), ('fix','Fixed Income'),('rev','Revenue Oriented'),('bal','Balanced'),('grow','Growth'),('cap','Capital Gain')], 'Investment profile')
    alternativeinvestments = fields.Char('Alternative investments')
    managementfees = fields.Char('Management fees')
    comments = fields.Char('Comments')
    logs = fields.One2Many("pl_cust_rescad.logs", "party", "Logs")
    tasks = fields.One2Many("pl_cust_rescad.tasks", "party", "Tasks")


    pro_activity = fields.Char('pro_activity')
    pro_is_employee = fields.Boolean('is_employee')
    pro_employee_employer = fields.Char('pro_employee_employer')
    pro_employee_industry = fields.Char('pro_employee_industry')
    pro_employee_position = fields.Char('pro_employee_position')  
    pro_employee_place = fields.Char('pro_employee_place')

    pro_is_selfemployed = fields.Boolean('is_selfemployed')
    pro_selfemployed_company = fields.Char('pro_selfemployed_company')
    pro_selfemployed_industry = fields.Char('pro_selfemployed_industry')
    pro_selfemployed_place = fields.Char('pro_selfemployed_place')
    pro_selfemployed_website = fields.Char('pro_selfemployed_website')

    pro_retired = fields.Boolean('is_retired')
    pro_previous_activities = fields.Char('pro_previous_activities')

    pro_is_other = fields.Boolean('is_orther')
    pro_other = fields.Char('other')

    pro_is_corporate_insider = fields.Boolean('is_corporate_insider')
    pro_corporate_insider_name = fields.Char('pro_corporate_insider_name')
    pro_corporate_insider_relation = fields.Char('pro_corporate_insider_relation')
    pro_corporate_insider_background = fields.Char('pro_corporate_insider_background')

# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import DeactivableMixin, ModelView, Unique, ModelSQL, Workflow, fields, sequence_ordered
from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If, Bool
from trytond import backend

# from .party import EMPLOYEE_TYPE
from trytond.pyson import Date
from datetime import datetime, timedelta

from trytond.model.exceptions import ValidationError

class BudgetError(ValidationError):
    pass

class UnableToDelete(ValidationError):
    pass


__all__ = ["Projects", "ProjectPartyAddr", "ProjectParty", "PartyAddr", "Party", "ProjectStage", "ProjectCategory", 'ProjectTask', 'ProjectSheet', 'ProjectLogs']

STATES = {
    "readonly": ~Eval("active"),
}
DEPENDS = ["active"]

class ProjectLogs(ModelSQL, ModelView):
    "Logs"
    __name__ = "pl_cust_plprojects.logs"

    date = fields.Date("Date", required=True)
    description = fields.Text("Description")
    project = fields.Many2One('pl_cust_plprojects.projects', 'Project', required=True)
    resp_id = fields.Many2One('company.employee', 'Employee', required=True)

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

    @staticmethod
    def default_logs_info():
        return 'other' 

    @staticmethod
    def default_user():
        User = Pool().get('res.user')
        user = User(Transaction().user)
        return user.name

class ProjectTask(ModelSQL, ModelView, DeactivableMixin):
    'Project timesheet tasks'
    __name__ = 'pl_cust_plprojects.tasks'

    name = fields.Char('Name', required=True)
    duration = fields.TimeDelta('Duration', 'company_work_time')

    @staticmethod
    def default_duration():
        return timedelta(0)

class ProjectSheet(ModelSQL, ModelView):
    'Folder timesheet'
    __name__ = 'pl_cust_plprojects.projectsheet'

    name = fields.Char('Description')

    task = fields.Many2One('pl_cust_plprojects.tasks', 'Task', required=True)

    date = fields.Date('Date', help="Date", required=True)

    project = fields.Many2One('pl_cust_plprojects.projects', 'Project', required=True)

    duration = fields.TimeDelta('Duration', required=True)

    resp_id = fields.Many2One('company.employee', 'Employee', required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order = [
            ('date', 'DESC'),
            ('id', 'DESC'),
        ]

    @staticmethod
    def default_resp_id():
        return Transaction().context.get('employee')

    @staticmethod
    def default_date():
        Date_ = Pool().get('ir.date')
        return Transaction().context.get('date') or Date_.today()

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
                ('project',) + tuple(clause[1:]),
                ]

    @fields.depends('task', 'name', 'duration')
    def on_change_task(self):
        if self.task:
            if not self.name:
                self.name = self.task.name
            if not self.duration and not self.task.duration == timedelta(0):
                self.duration = self.task.duration


class ProjectPartyAddr(ModelSQL, ModelView):
    "Project - Party Relation"
    __name__ = "pl_cust_plprojects.partyaddr.relation"

    project = fields.Many2One(
        "pl_cust_plprojects.projects", "Project", required=True, ondelete="RESTRICT"
    )
    is_pilote = fields.Boolean("Pilote")

    party_addr = fields.Many2One(
        "party.address", "PartyAddr", required=True, ondelete="RESTRICT", domain=[("party.party_type", "!=", 'empl')], depends=["party"])
    type_ = fields.Selection([('mandataire','Mandataire'),('sous-traitant', 'Sous-traitant'),('autre','Autre partenaire')],
                                 'Rôle partenaire', required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()  
        t = cls.__table__()
        cls._sql_constraints.append(
            ('unique_rel', Unique(t, t.project, t.party_addr),
                'Une seule relation possible'))

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('party_addr',) + tuple(clause[1:]),
            ]

class ProjectParty(ModelSQL, ModelView):
    "Project - Party Relation"
    __name__ = "pl_cust_plprojects.party.relation"

    project = fields.Many2One(
        "pl_cust_plprojects.projects", "Project", required=True, ondelete="RESTRICT"
    )
    employee = fields.Many2One(
        "party.party",
        "Employee",
        domain=[("party_type", "=", 'empl')],
        depends=["party_type"],
        required=True,
        ondelete="RESTRICT",
        
    )
    type_ = fields.Selection([('cp', 'Chef-e de projet'), ('p','Participant-e')],
                                 'Rôle employé-e', required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()  
        t = cls.__table__()
        cls._sql_constraints.append(
            ('unique_rel', Unique(t, t.project, t.employee),
                'Une seule relation possible'))

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('employee',) + tuple(clause[1:]),
            ]


class Party(ModelSQL, ModelView):
    __name__ = "party.party"

    #is_employ = fields.Boolean("Is Employee?")
    projects = fields.One2Many(
        "pl_cust_plprojects.party.relation", "employee", "Projects"
    )

class PartyAddr(ModelSQL, ModelView):
    __name__ = "party.address"

    projects = fields.One2Many(
        "pl_cust_plprojects.partyaddr.relation", "party_addr", "Projects"
    )

    def get_rec_name(self, name) :
        if self.contact_firstname and self.contact_name :
            cont_name = '{} {}'.format(self.contact_firstname,self.contact_name)
        else : 
            cont_name = '{}'.format(self.contact_firstname or self.contact_name)

        return '{}{}'.format(self.party.name, cont_name and '/ {}'.format(cont_name) or '',self.building_name)

class ProjectCategory(ModelSQL):
    "Project - Category"
    __name__ = "pl_cust_plprojects.category.relation"

    project = fields.Many2One(
        "pl_cust_plprojects.projects", "Project", required=True, ondelete="CASCADE"
    )
    category = fields.Many2One(
        "pl_cust_plprojects.category", "Category", required=True, ondelete="CASCADE"
    )

class ProjectStage(sequence_ordered(), ModelSQL, ModelView):
    "Project Stage"
    __name__ = "pl_cust_plprojects.stage"

    name = fields.Char("Name", required=True)
    is_done = fields.Boolean("Done?")
    calendar = fields.Boolean("Calendar?")

    stage_type = fields.Selection([('a', 'Rien'),('b','Mail à Gabriela'),('c', 'Mail à Isabel')],
                                 'type', required=True)

    delai = fields.Date("Delai")

    project = fields.Many2One(
        "pl_cust_plprojects.projects", "Project", required=True, ondelete="RESTRICT")

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('/tree', 'visual', If(Eval('is_done'), 'warning', '')),
        ]

class Projects(DeactivableMixin, Workflow, ModelSQL, ModelView):
    "projects"
    __name__ = "pl_cust_plprojects.projects"

    code = fields.Char("Code", required=True, readonly=False)
    name = fields.Char("Name", required=True, readonly=False)
    publicname = fields.Char("Public Name", required=False, readonly=False)
    contract_done = fields.Boolean("Contract done") 
    date_valid_cf = fields.Date("Date valid CF", help="Date valid CF")
    date_start = fields.Date("Date start", help="Date start")
    date_end = fields.Date("Date end", help="Date end")
    description = fields.Text("Description", required=True)
    notes = fields.Text("Comment")
    objectif = fields.Text("Objectif")
    amount_min = fields.Numeric('Budget minimum')
    amount_max = fields.Numeric('Budget maximum')

    project_type = fields.Selection("get_project_type", "Project Type")
    project_type_string = project_type.translated("project_type")

    project_axe = fields.Selection("get_project_axe", "Axe")
    project_axe_string = project_axe.translated("project_axe")

    as_attachment = fields.Function(fields.Boolean("pj"), "get_as_attachement")

    parties = fields.One2Many(
        "pl_cust_plprojects.partyaddr.relation", "project", "Parties")

    employees = fields.One2Many(
        "pl_cust_plprojects.party.relation", "project", "Employees")

    category = fields.Many2Many(
        "pl_cust_plprojects.category.relation", "project", "category", "Category", 
    )

    duree = fields.Selection([('3m', '< 3 month'),('3m6m','3 to 6 month'), ('6m12m','6 to 12 month'), ('12m24m','12 to 24 month'), ('24m','> 24 month')],
                                 'Duree', required=True)

    status = fields.Selection([('inspi', 'Inspi'),('inten','Itention'), ('disc','Discution'), ('eval','eval'), ('valid','valid'), ('in_progr','en Cours'),('finish','Termi'), ('cancel','Aband'), ('refus', 'Refused')],'Status', required=True)

    stages = fields.One2Many("pl_cust_plprojects.stage", "project", "Stages")
    sheets = fields.One2Many("pl_cust_plprojects.projectsheet", "project", "Timesheet")
    logs = fields.One2Many("pl_cust_plprojects.logs", "project", "Logs")


    name = fields.Char("Name", required=True)
    is_done = fields.Boolean("Done?")
    
    delai = fields.Date("Delai")

    @staticmethod
    def default_stages():
        return [
            {'name': 'Début du projet', 'stage_type': 'a'},
            {'name': 'Signature contrat', 'stage_type': 'a'},
            {'name': 'Livrable du WP1', 'stage_type': 'b'},
            {'name': 'Livrable du WP2', 'stage_type': 'b'},
            {'name': 'Fiche évaluation impact et décompte financier', 'stage_type': 'a'},
            {'name': 'Note de synthèse', 'stage_type': 'c'},
            {'name': 'Validé pour publication sur site', 'stage_type': 'c'},
            {'name': 'Fin du projet', 'stage_type': 'a'},
        ]

    @classmethod
    def validate(cls, projects):
        super().validate(projects)
        for project in projects:
            if project.amount_min and project.amount_max and project.amount_min > project.amount_max:
                raise BudgetError("Pour le budget, le montant minimum ne peut pas être supérieur au montant maximum.")

    @classmethod
    def get_as_attachement(cls, invoices, name):
        pool = Pool()
        ATTACH = pool.get("ir.attachment")

        res = {i.id: False for i in invoices}
        for inv in invoices:
            if ATTACH.search([("resource", "=", inv)]):
                res[inv.id] = True
        return res

    @classmethod
    def __setup__(cls):
        super().__setup__()

        cls._order = [
            ("name", "DESC"),
        ]

        cls._buttons.update({'open_form_tab': {},})

    #@classmethod
    #@ModelView.button_action('act_projects_form')
    #def open_form_tab(cls, projects):
    #    pass

    def open_form_tab(self):
        Action = Pool().get('ir.action.act_window')
        action = Action.get_action('act_projects_form')
        action['res_id'] = self.id
        action['names'] = self.id
        return action

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
                ('code',) + tuple(clause[1:]),
                ('name',) + tuple(clause[1:]),
                ('publicname',) + tuple(clause[1:]),
                ]

    @staticmethod
    def default_name():
        return ""

    def default_project_type():
        return "n"

    @staticmethod
    def default_date_start():
        Date_ = Pool().get("ir.date")
        return Transaction().context.get("date") or Date_.today()

    @classmethod
    def get_project_type(cls):
        PROJECTSTYPE = Pool().get("pl_cust_plprojects.projectstype")
        all_type = PROJECTSTYPE.search([])
        return [(ft.code, ft.name) for ft in all_type]

    @classmethod
    def get_project_axe(cls):
        PROJECTSAXE = Pool().get("pl_cust_plprojects.projectsaxe")
        all_axe = PROJECTSAXE.search([])
        return [(ft.code, ft.name) for ft in all_axe]

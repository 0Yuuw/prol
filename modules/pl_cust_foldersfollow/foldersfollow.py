# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import DeactivableMixin, ModelView, ModelSQL, Workflow, fields
from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If, Bool
from trytond import backend
# from .party import EMPLOYEE_TYPE
from trytond.pyson import Date
from datetime import datetime, timedelta

from trytond.model.exceptions import ValidationError


class EmployeValidationError(ValidationError):
    pass


class UnableToDelete(ValidationError):
    pass


def format_seconds(s):
    hours, remainder = divmod(s, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours and minutes:
        return '{}h {:02}m'.format(int(hours), int(minutes))
    elif hours and not minutes:
        return '{}h'.format(int(hours))
    elif not hours and minutes:
        return '{}m'.format(int(minutes))
    else:
        return '-'


__all__ = ['FoldersFollow', 'FolldersFollowTasks',
           'Tasks', 'FoldersFollowType', 'FoldersFollowWho']

STATES = {
    'readonly': ~Eval('active'),
}
DEPENDS = ['active']

class FoldersFollowType(ModelSQL, ModelView):
    'FoldersFollowType'
    __name__ = 'pl_cust_foldersfollow.foldersfollowtype'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True, translate=False)

class FoldersFollowWho(ModelSQL, ModelView):
    'FoldersFollowWho'
    __name__ = 'pl_cust_foldersfollow.foldersfollowwho'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True, translate=False)
    
class Tasks(ModelSQL, ModelView, DeactivableMixin):
    'Tasks'
    __name__ = 'pl_cust_foldersfollow.tasks'

    name = fields.Char('Name', required=True, translate=True)
    duration = fields.TimeDelta('Duration')

    @staticmethod
    def default_duration():
        return timedelta(0)

class FolldersFollowTasks(ModelSQL, ModelView):
    'FolldersFollowTasks'
    __name__ = 'pl_cust_foldersfollow.foldersfollowtasks'

    inout = fields.Selection([
        ('in','In'),
        ('out','Out'),
    ], "In/Out", required=True)
    inout_string = inout.translated("In/Out")

    name = fields.Char('Description')

    tasks = fields.Many2One('pl_cust_foldersfollow.tasks', 'Task', required=True)
    date = fields.Date('Date', help="Date", required=True)

    foldersfollow = fields.Many2One(
        'pl_cust_foldersfollow.foldersfollow', 'Folder', required=True)

    duration = fields.TimeDelta('Duration', required=True)

    resp_id = fields.Many2One('company.employee', 'Employee', required=True)

    @classmethod
    def __setup__(cls):
        super(FolldersFollowTasks, cls).__setup__()
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
                ('foldersfollow',) + tuple(clause[1:]),
                ]

class FoldersFollow(DeactivableMixin, Workflow, ModelSQL, ModelView):
    'FoldersFollow'
    __name__ = 'pl_cust_foldersfollow.foldersfollow'
    name = fields.Char('Number', required=False, readonly=False)
   
    followtasks = fields.One2Many(
        'pl_cust_foldersfollow.foldersfollowtasks', 'foldersfollow', 'Follow Tasks')
    
    date_start = fields.Date('Date start', help="Date start")
    date_end = fields.Date('Date end', help="Date end")
    party_id = fields.Many2One('party.party', 'Party')
    description = fields.Char('Description')
    notes = fields.Text('Comment')
    internal_notes = fields.Text('Internal Notes')

    folder_type = fields.Selection('get_folder_type', "Folder Type")
    folder_type_string = folder_type.translated('folder_type')

    who = fields.Selection([
        ('',''),
        ('1','Personne concernée'),
        ('2','Proche'),
        ('3','Professionnel-le-s'),
        ('4',"Pas d'info")] , "Qui")
    who_string = who.translated('qui')
    
    cat = fields.Selection([
        ('',''),
        ('1','Père'),
        ('2','Mère'),
        ('3','Oncle'),
        ('4','Cousine.x.s'),
        ('5','Grand père'),
        ('6','Beau-père'),
        ('7','Frère'),
        ('8','Plusieurs dans la famille'),
        ('9','Ami de famille'),
        ('10','Conjoint/partenaire'),
        ('11','Ex-conjoint/partenaire'),
        ('12','Ami'),
        ('13',"Ami d'ami"),
        ('14','Patron/Chef'),
        ('15','Collegue'),
        ('16','Camarade (école)'),
        ('17','Flirt'),
        ('18','Profess. Santé'),
        ('19','Police'),
        ('20','Profess. Autre'),
        ('21','Voisin'),
        ('22','Autre connu'),
        ('23','Inconnu'),
        ('24',"Pas d'info"),
        ('25','Client ts'),
        ('26','Connaissance'),
    ], "Cat")
    cat_string = cat.translated('Cat')

    jur = fields.Selection([
        ('',''),
        ('1','Aucune démarche'),
        ('2','Plainte (en cours)'),
        ('3','Médiation'),
        ('4','Plainte classée'),
        ('5','Condamnation'),
        ('6','Dénonciation à un organe de surveillance'),
        ('7','Démarche justice restaurative'),
        ('8',"Pas d'info"),
        ('9','Main courante'),
        ('10','Acquittement'),
    ], "Démarche juridique")
    jur_string = jur.translated('Démarche juridique')

    cop = fields.Selection([
        ('',''),
        ('1','Oui'),
        ('2','Non'),
        ('3',"Pas d'info"),
        ('4','Prescription'),
        ('5','Y réfléchit'),
    
    ], "Cat")
    cop_string = cop.translated('Cat')

    ecart_age = fields.Selection([
        ('',''),
        ('1','0-5 ans'),
        ('2','5-10 ans'),
        ('3',"10-20 ans"),
        ('4','> 20 ans'),
    ], "Ecart âge")
    ecart_age_string = ecart_age.translated('Ecart âge')

    age = fields.Selection([
        ('',''),
        ('1','16-25 ans'),
        ('2','26-39 ans'),
        ('3',"40-59 ans"),
        ('4','> 60 ans'),
    
    ], "Age")
    age_string = age.translated('Age')
        
    other_violence = fields.Selection([
        ('',''),
        ('1','Oui'),
        ('2','Non'),
    ], "Autres violences")
    other_violence_string = other_violence.translated('Autres violences')

    frequency = fields.Selection([
        ('',''),
        ('1','Unique'),
        ('2','Répété'),
    ], "Fréquence")
    frequency_string = frequency.translated('Fréquence')

    as_attachment = fields.Function(fields.Boolean('pj'), 'get_as_attachement')
    resp = fields.Many2One('company.employee', 'Resp',)
    
    @classmethod
    def get_as_attachement(cls, folders, name):
        pool = Pool()
        ATTACH = pool.get('ir.attachment')

        res = {i.id: False for i in folders}
        for inv in folders : 
            if ATTACH.search([('resource', '=', inv)]) :
                res[inv.id] = True
        return res

    @classmethod
    def __setup__(cls):
        super().__setup__()

        cls._order = [
            ('name', 'DESC'),
        ]

    @staticmethod
    def default_name():
        return ''

    @staticmethod
    def default_date_start():
        Date_ = Pool().get('ir.date')
        return Transaction().context.get('date') or Date_.today()
    
    @classmethod
    def get_folder_type(cls):
        FOLDERTYPE = Pool().get('pl_cust_foldersfollow.foldersfollowtype')
        all_type = FOLDERTYPE.search([])
        return [('','')] + [(ft.code, ft.name) for ft in all_type]

    @classmethod
    def get_who(cls):
        WHO = Pool().get('pl_cust_foldersfollow.foldersfollowwho')
        all_who = WHO.search([])
        return [('','')] + [(ft.code, ft.name) for ft in all_who]

    # @classmethod
    # def _new_name(cls, **pattern):
    #     pool = Pool()
    #     Sequence = pool.get('ir.sequence')
    #     Configuration = pool.get('pl_cust_foldersfollow.configuration')
    #     config = Configuration(1)
    #     sequence = config.get_multivalue('folders_sequence', **pattern)
    #     if sequence:
    #         return sequence.get()

    # def get_rec_name(self, name):
    #     return "{}{}{}".format(self.party_id and self.party_id.name or '?',
    #                            self.description and '-'+self.description or '',
    #                            self.name and '-'+self.name or '')

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
                ('name',) + tuple(clause[1:]),
                ('party_id',) + tuple(clause[1:]),
                ('description',) + tuple(clause[1:]),
                ]

    @classmethod
    def copy(cls, foldersfollow, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()

        default.setdefault('name', None)
        default.setdefault('timesheet_ids', None)
        default.setdefault('date_start', None)
        default.setdefault('date_end', None)

        new_folders = []
        for fold in foldersfollow:
            if not default.get('description', False):
                default['description'] = '(COPIE) {}'.format(fold.description)
            new_folder, = super(FoldersFollow, cls).copy([fold], default)
            new_folders.append(new_folder)
        return new_folders

    # @classmethod
    # def create(cls, vlist):
    #     pool = Pool()
    #     Employee = pool.get('company.employee')
    #     vlist = [x.copy() for x in vlist]
    #     employ = ''

    #     for values in vlist:
    #         if not values.get('name'):
    #             values['name'] = cls._new_name()

    #     return super().create(vlist)


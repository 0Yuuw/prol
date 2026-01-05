# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.model import ModelSingleton, ModelSQL, ModelView, MultiValueMixin, ValueMixin, fields
from trytond.pyson import Eval,Bool

__all__ = ['ProjectsType', 'ProjectsAxe', 'Category']

class ProjectsType(ModelSQL, ModelView):
    'Type'
    __name__ = 'pl_cust_plprojects.projectstype'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True, translate=False)

class ProjectsAxe(ModelSQL, ModelView):
    'Axe'
    __name__ = 'pl_cust_plprojects.projectsaxe'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True, translate=False)

class Category(ModelSQL, ModelView):
    "Category"
    __name__ = "pl_cust_plprojects.category"

    name = fields.Char("Name", required=True)

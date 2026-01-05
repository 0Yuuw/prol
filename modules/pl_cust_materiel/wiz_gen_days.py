# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# -*- coding: UTF-8 -*-
from decimal import Decimal
from trytond.wizard import Wizard, StateView, StateTransition, Button

from trytond.model import DeactivableMixin, ModelView, ModelSQL, Workflow, fields
from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If, Bool
from trytond import backend

# from .party import EMPLOYEE_TYPE
from trytond.pyson import Date
from datetime import datetime, timedelta
from trytond.exceptions import UserWarning
import pytz
from trytond.model.exceptions import ValidationError


class EmployeValidationError(ValidationError):
    pass


class UnableToDelete(ValidationError):
    pass


class Error(ValidationError):
    pass


__all__ = [
    "GenerateDays",
    "GenerateDaysStart",
]

class GenerateDaysStart(ModelView):
    "Generate Day Pub Start"
    __name__ = "pl_cust_materiel.generate_days_start"

    date_from = fields.Date("Date")
    date_to = fields.Date("Date")

class GenerateDays(Wizard):
    "Generate Days"
    __name__ = "pl_cust_materiel.generate_days"

    start = StateView(
        "pl_cust_materiel.generate_days_start",
        "pl_cust_materiel.generate_days_start_view_form",
        [
            Button("Cancel", "end", "tryton-cancel"),
            Button("Generate", "generate", "tryton-ok", default=True),
        ],
    )
    generate = StateTransition()

    def transition_generate(self):
        pool = Pool()
        obj_DAYS = pool.get("pl_cust_materiel.matday")

        d = self.start.date_from
        while d <= self.start.date_to:
            
            if not obj_DAYS.search([("date", "=", d)]):
                obj_DAYS.create(
                            [{"date": d}]
                            )
            d += timedelta(days=1)

        return "end"

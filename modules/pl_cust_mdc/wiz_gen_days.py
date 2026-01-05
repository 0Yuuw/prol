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
    "GenerateDaysPub",
    "GenerateDaysPubStart",
    "GenerateDaysInst",
    "GenerateDaysInstStart",
]


class GenerateDaysPubStart(ModelView):
    "Generate Day Pub Start"
    __name__ = "pl_cust_mdc.generate_dayspub_start"

    date_from = fields.Date("Date")
    date_to = fields.Date("Date")
    add_all_days = fields.Boolean("Add All Days")  


class GenerateDaysPub(Wizard):
    "Generate Days Pub"
    __name__ = "pl_cust_mdc.generate_dayspub"

    start = StateView(
        "pl_cust_mdc.generate_dayspub_start",
        "pl_cust_mdc.generate_dayspub_start_view_form",
        [
            Button("Cancel", "end", "tryton-cancel"),
            Button("Generate", "generate", "tryton-ok", default=True),
        ],
    )
    
    generate = StateTransition()

    def transition_generate(self):
        pool = Pool()
        obj_DAYS = pool.get("pl_cust_mdc.day_pub")
        Configuration = pool.get("pl_cust_mdc.configuration")
        config = Configuration(1)

        d = self.start.date_from
        while d <= self.start.date_to:
            if d.weekday() < 6:
                if self.start.add_all_days: 
                    if not obj_DAYS.search([("date", "=", d)]):
                        dtype = "p"
                        obj_DAYS.create(
                            [{"date": d, "dtype": dtype, "nb_max": config.nb_max}]
                        )
                else:
                    if d.weekday() in (2, 5):  
                        if not obj_DAYS.search([("date", "=", d)]):
                            dtype = "p"
                            obj_DAYS.create(
                                [{"date": d, "dtype": dtype, "nb_max": config.nb_max}]
                            )
            d += timedelta(days=1)

        return "end"


class GenerateDaysInstStart(ModelView):
    "Generate Day Inst Start"
    __name__ = "pl_cust_mdc.generate_daysinst_start"

    date_from = fields.Date("Date de début")
    date_to = fields.Date("Date de fin")
    close_days = fields.Boolean("Close Days")

    @classmethod
    def __setup__(cls):
        super(GenerateDaysInstStart, cls).__setup__()


class GenerateDaysInst(Wizard):
    "Generate Days Inst"
    __name__ = "pl_cust_mdc.generate_daysinst"

    start = StateView(
        "pl_cust_mdc.generate_daysinst_start",
        "pl_cust_mdc.generate_daysinst_start_view_form",
        [
            Button("Cancel", "end", "tryton-cancel"),
            Button("Generate", "generate", "tryton-ok", default=True),
        ],
    )
    generate = StateTransition()

    def transition_generate(self):
        pool = Pool()
        obj_DAYS = pool.get("pl_cust_mdc.day_inst")
        Configuration = pool.get("pl_cust_mdc.configuration")
        config = Configuration(1)

        d = self.start.date_from
        close_days_selected = self.start.close_days

        while d <= self.start.date_to:
            if d.weekday() not in [2, 5, 6]:
                existing_day = obj_DAYS.search([("date", "=", d)])
                
                if existing_day:
                    dtype = "c" if close_days_selected else "i"
                    obj_DAYS.write(existing_day, {"dtype": dtype})
                else:
                    dtype = "i"
                    obj_DAYS.create(
                        [
                            {
                                "date": d,
                                "dtype": dtype,
                                "nb_max": config.nb_max,
                                "nb_inst_max": config.nb_inst_max,
                            }
                        ]
                    )
            d += timedelta(days=1)

        return "end"
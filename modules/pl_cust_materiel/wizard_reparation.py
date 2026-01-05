from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.model import ModelView, fields
from trytond.pool import Pool
from trytond.transaction import Transaction
from datetime import datetime, date, timedelta, time
from trytond.pyson import Eval
from decimal import Decimal
import codecs
import os
import csv

from trytond.model.exceptions import ValidationError
from trytond.exceptions import UserWarning


class CheckWarning(UserWarning):
    pass


class NBError(ValidationError):
    pass


__all__ = ["AddRepa", "AddRepaStart", "AddRepaStep2", "ReturnRepa", "ReturnRepaStart"]


class AddRepaStart(ModelView):
    "AddRepaStart"
    __name__ = "pl_cust_materiel.addrepa_start"

    date_start = fields.Date("Date Start", required=True)
    date_end = fields.Date("Date End", required=True)

    materiel = fields.Many2One("pl_cust_materiel.materiel", "Materiel", required=True)
    qty = fields.Integer("Quantity", required=True)

    @fields.depends("date_start", "date_end")
    def on_change_date_start(self):
        if self.date_start and not self.date_end:
            # Ajout de 1 an à la date de début
            self.date_end = self.date_start.replace(year=self.date_start.year + 1)


class AddRepaStep2(ModelView):
    "AddRepaStep2"
    __name__ = "pl_cust_materiel.addrepa_step2"

    date_start = fields.Date("Date Start", readonly=True, required=True)
    date_end = fields.Date("Date End", readonly=True, required=True)
    materiel = fields.Many2One("pl_cust_materiel.materiel", "Materiel", required=True)
    qty = fields.Integer("Quantity")
    manifestations = fields.One2Many(
        "pl_cust_materiel.manifestation", None, "Manifestations"
    )
    localisation = fields.Many2One(
        "pl_cust_materiel.lieumanif", "Localisation", required=True
    )
    description = fields.Text("Description")
    party = fields.Many2One("party.party", "Party", required=True)
    datetime_start = fields.DateTime("DateTime Start", readonly=True)
    datetime_end = fields.DateTime("DateTime End", readonly=True)


class AddRepa(Wizard):
    "AddRepa"
    __name__ = "pl_cust_materiel.addrepa"

    start = StateView(
        "pl_cust_materiel.addrepa_start",
        "pl_cust_materiel.addrepa_start_view_form",
        [
            Button("Cancel", "end", "tryton-cancel"),
            Button("Check", "check", "tryton-ok", default=True),
        ],
    )

    step2 = StateView(
        "pl_cust_materiel.addrepa_step2",
        "pl_cust_materiel.addrepa_step2_view_form",
        [
            Button("Cancel", "end", "tryton-cancel"),
            Button("Add Reparation", "add_repa", "tryton-ok", default=True),
        ],
    )

    check = StateTransition()
    add_repa = StateTransition()

    def transition_check(self):
        return "step2"

    def transition_add_repa(self):
        pool = Pool()
        Manifs = pool.get("pl_cust_materiel.manifestation")
        Location = pool.get("pl_cust_materiel.location")
        Logs = pool.get("pl_cust_materiel.logs")

        logs_tmp = (
            self.step2.localisation and "{}\n\n".format(self.step2.localisation) or ""
        )
        logs_tmp += (
            self.step2.description and "{}\n\n".format(self.step2.description) or ""
        )
        logs_tmp += "{} {} en réparation\n".format(
            self.step2.qty,
            self.step2.materiel.name,
        )

        if self.step2.manifestations:
            raise NBError(
                "Il faut règler le problème des manifestations qui vont utiliser ce matériel!!!"
            )
        elif self.start.qty > self.start.materiel.qty:
            raise NBError(
                "Impossible, il y en a {} en stock et vous souhaitez en réparer {} !!!".format(
                    self.start.materiel.qty, self.start.qty
                )
            )

        new_manif = Manifs.create(
            [
                {
                    "name": "Réparation",
                    "localisation": self.step2.localisation,
                    "description": logs_tmp,
                    "date_start": self.step2.date_start,
                    "date_end": self.step2.date_end,
                    "party": self.step2.party.id,
                    "datetime_start": self.step2.datetime_start,
                    "datetime_end": self.step2.datetime_end,
                    "type": "repa",
                }
            ]
        )

        loc = Location.create(
            [
                {
                    "materiel": self.step2.materiel.id,
                    "qty": self.step2.qty,
                    "manifestation": new_manif[0].id,
                    "repa": True,
                }
            ]
        )

        log = Logs.create(
            [
                {
                    "logs_type": "repair",
                    "description": logs_tmp,
                    "manifestation": new_manif[0].id,
                    "materiel": self.step2.materiel.id,
                }
            ]
        )

        return "end"

    def default_step2(self, fields):
        def daterange(start, end):
            for n in range((end - start).days + 1):
                yield start + timedelta(n)

        pool = Pool()
        Materiels = pool.get("pl_cust_materiel.materiel")
        Manifs = pool.get("pl_cust_materiel.manifestation")

        crit1 = ("date_start", "<=", self.start.date_end)
        crit2 = ("date_end", ">=", self.start.date_start)

        all_manifs = Manifs.search(
            [
                crit1,
                crit2,
            ]
        )
        lines = []
        materiel = self.start.materiel

        daily_rented = {
            d: 0 for d in daterange(self.start.date_start, self.start.date_end)
        }

        for manif in all_manifs:
            overlap_start = max(self.start.date_start, manif.date_start)
            overlap_end = min(self.start.date_end, manif.date_end)
            for loc in manif.locations:
                if loc.materiel.id == materiel.id:
                    lines.append(manif.id)
                    for day in daterange(overlap_start, overlap_end):
                        daily_rented[day] += loc.qty

        peak = max(daily_rented.values(), default=0)

        if materiel.qty - peak - self.start.qty >= 0:
            lines = []

        return {
            "party": 1,
            "localisation": 1,
            "date_start": self.start.date_start,
            "date_end": self.start.date_end,
            "materiel": self.start.materiel.id,
            "qty": self.start.qty,
            "manifestations": lines,
            "datetime_start": datetime.combine(self.start.date_start, time(5, 59)),
            "datetime_end": datetime.combine(self.start.date_end, time(21, 59)),
        }


class ReturnRepaStart(ModelView):
    "ReturnRepaStart"
    __name__ = "pl_cust_materiel.returnrepa_start"

    location = fields.Many2One("pl_cust_materiel.location", "Location", required=True)
    qty = fields.Integer("Quantity", required=True)


class ReturnRepa(Wizard):
    "AddRepa"
    __name__ = "pl_cust_materiel.returnrepa"

    start = StateView(
        "pl_cust_materiel.returnrepa_start",
        "pl_cust_materiel.returnrepa_start_view_form",
        [
            Button("Cancel", "end", "tryton-cancel"),
            Button("Valider", "return_repa", "tryton-ok", default=True),
        ],
    )

    return_repa = StateTransition()

    def transition_return_repa(self):
        Manifs = Pool().get("pl_cust_materiel.manifestation")

        Date = Pool().get("ir.date")
        loc = self.start.location

        if self.start.qty == loc.qty:
            loc.repa_ok = True
            loc.manifestation.date_end = Date.today()
            loc.manifestation.datetime_end = datetime.combine(
                Date.today(), time(21, 59)
            )
            loc.manifestation.save()
            loc.save()
        elif self.start.qty == 0:
            return "end"
        elif 0 < self.start.qty < loc.qty:
            new_manif = Manifs.copy(
                [
                    loc.manifestation,
                ]
            )
            new_manif[0].locations[0].qty = loc.qty - self.start.qty
            new_manif[0].locations[0].save()

            loc.qty = self.start.qty
            loc.manifestation.date_end = Date.today()
            loc.manifestation.datetime_end = datetime.combine(
                Date.today(), time(21, 59)
            )
            loc.manifestation.save()
            loc.repa_ok = True
            loc.save()
        elif self.start.qty > loc.qty:
            raise NBError(
                "Vous ne pouvez pas en retourner plus que le nombre en réparation !!!"
            )
        elif self.start.qty < 0:
            raise NBError("Vous ne pouvez pas retourner un nombre négatif !!!")
        else:
            raise NBError("Contacter ProLibre il y a un bug ici!!!")

        
        return "end"

    def default_start(self, fields):

        pool = Pool()
        Locations = pool.get("pl_cust_materiel.location")

        if Transaction().context.get("active_model", "") == "pl_cust_materiel.location":
            loc = Locations(Transaction().context.get("active_id", ""))

        if loc:
            return {
                "location": loc.id,
                "qty": loc.qty,
            }
        else:
            return {}

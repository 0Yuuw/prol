# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from datetime import timedelta
from trytond.model import ModelView, fields
from trytond.model.exceptions import AccessError
from trytond.wizard import (
    Wizard,
    StateTransition,
    StateView,
    StateAction,
    StateReport,
    Button,
)
from decimal import Decimal

from trytond.report import Report
from trytond.transaction import Transaction
from trytond.pool import Pool
import sys
import locale
from trytond.model.exceptions import ValidationError

class RapportValidationError(ValidationError):
    pass

__all__ = ["ElegaReport"]


def my_format_date(date):
    if not date:
        return "-"

    corresp = {
        1: "janvier",
        2: "février",
        3: "mars",
        4: "avril",
        5: "mai",
        6: "juin",
        7: "juillet",
        8: "août",
        9: "septembre",
        10: "octobre",
        11: "novembre",
        12: "décembre",
    }

    return "{} {} {}".format(
        date.strftime("%-d"),
        corresp[date.month],
        date.strftime("%Y"),
    )


def format_date2(date):
    y, m, d = str(date).split("-")
    return "{}.{}.{}".format(d, m, y[-2:])


def format_seconds(s):
    hours, remainder = divmod(s, 3600)
    minutes, seconds = divmod(remainder, 60)
    return hours, minutes, seconds

    minutes, seconds = divmod(remainder, 60)
    return hours, minutes, seconds


class ElegaReport(Report):
    __name__ = "pl_cust_elega.elegareport"

    @classmethod
    def execute(cls, ids, data):
        pool = Pool()
        Folders = pool.get("pl_cust_plfolders.folders")

        # Pour donner le nom au fichier
        res = super().execute(ids, data)
        aux = list(res)

        # convert the res to a list because it is a tuple and we need to modify it
        if len(ids) == 1:
            (folder,) = Folders.browse(ids)
            aux[-1] = "Elega-{}".format(folder.name).replace('/','')
        else :
            aux[-1] = "Elega"

        return tuple(aux)

    @classmethod
    def get_context(cls, records, headers, data):
        pool = Pool()
        Date_ = pool.get("ir.date")
        LANG = pool.get("ir.lang")

        context = super().get_context(records, headers, data)
        context["folder"] = context["record"]

        if not context['folder'].contact_address: 
            context['addr'] = context['folder'].party_id.addresses[0]
        else :
            context['addr'] = context['folder'].contact_address
            #raise RapportValidationError('Il faut choisir une adresse pour pouvoir imprimer le devis')
    
        context["mytoday"] = my_format_date(Date_.today())
        context["mydate"] = format_date2(Date_.today())
        context["lang"] = LANG(LANG.search([("code", "=", "fr")])[0])

        context["tot"] = ""

        return context

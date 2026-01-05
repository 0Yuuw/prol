# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import requests
from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.report import Report
from trytond.model import (
    ModelView,
    ModelSQL,
    MultiValueMixin,
    ModelSingleton,
    ValueMixin,
    Unique,
    fields,
)
from trytond.pyson import Bool, Eval, If
from trytond.transaction import Transaction
from trytond.model.exceptions import ValidationError
from trytond.tools.qrcode import generate_png
from datetime import date
from datetime import datetime


class UnableToDelete(ValidationError):
    pass


__all__ = [
    "MDCDayPub",
    "MDCBookingPub",
    "MDCReportPub",
    "MDCGiftVoucher",
    "MDCReportVoucher",
]

MAD_choice_pub = [
    ("m", "Matin"),
    ("a", "Après-Midi"),
]

State = [
    ("draft", "Draft"),  # Brouillon
    ("payed", "Payed"),  # Payée
]

DAYPub_type = [("p", "Public"), ("h", "Holliday"), ("c", "Close")]

def my_format_date(date):
    if not date:
        return '-'

    corresp = {
        1: 'janvier',
        2: 'février',
        3: 'mars',
        4: 'avril',
        5: 'mai',
        6: 'juin',
        7: 'juillet',
        8: 'août',
        9: 'septembre',
        10: 'octobre',
        11: 'novembre',
        12: 'décembre',
    }

    corresp2 = {
        '0': 'dimanche',
        '1': 'lundi',
        '2': 'mardi',
        '3': 'mercredi',
        '4': 'jeudi',
        '5': 'vendredi',
        '6': 'samedi',
    }

    return '{} {} {} {}'.format(corresp2[date.strftime("%w")],
                             date.strftime("%-d"),
                             corresp[date.month],
                             date.strftime("%Y"),
                             )

def format_date2(date):
    if date:
        y, m, d = str(date).split("-")
        return "{}.{}.{}".format(d, m, y)
    else:
        return "-"


class MDCGiftVoucher(ModelSQL, ModelView):
    "MDC Gift Voucher"
    __name__ = "pl_cust_mdc.gift_voucher"

    lastname = fields.Char("Nom", readonly=True)
    firstname = fields.Char("Prénom")
    email = fields.Char("E-Mail")
    purchase_date = fields.Date(
        "Purchase Date", states={"readonly": Eval("state") != "draft"}
    )
    npa = fields.Char("NPA")
    nb_2 = fields.Integer("Quantity for 2 Entry")
    nb_4 = fields.Integer("Quantity for 4 Entry")
    nb_10 = fields.Integer("Quantity for 10 Entry")
    used = fields.Boolean("Is Used?")
    datatrans_id = fields.Char("Datatrans Id")
    refno = fields.Char("Datatrans Ref No")
    state = fields.Selection(State, "State")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order = [
            ("state", "DESC"),
        ]

    @staticmethod
    def default_purchase_date():
        return date.today()

    @classmethod
    def default_state(cls):
        return "draft"


class MDCBookingPub(ModelSQL, ModelView):
    "MDC Booking Pub"
    __name__ = "pl_cust_mdc.booking_pub"

    name = fields.Char("Booking", readonly=True)
    email = fields.Char("Email")
    npa = fields.Char("NPA")
    day = fields.Many2One("pl_cust_mdc.day_pub", "Day", required=True)
    nb_adult = fields.Integer("Number Adult")
    nb_02 = fields.Integer("Number 0-2")
    nb_34 = fields.Integer("Number 3-4")
    nb_56 = fields.Integer("Number 5-6")
    nb_78 = fields.Integer("Number 7-8")
    nb_gift = fields.Integer("Number Gift")
    nb_asso = fields.Integer("Number Asso")
    sp4 = fields.Boolean("Support 4")
    sp5 = fields.Boolean("Support 5")
    sp6 = fields.Boolean("Support 6")
    name_asso = fields.Char("Asso Name")
    mad = fields.Selection(MAD_choice_pub, "MAD choice")
    mad_string = mad.translated("mad")
    used = fields.Boolean("Used")
    party = fields.Many2One("party.party", "Party")
    datatrans_id = fields.Char("Datatrans Id")
    refno = fields.Char("Datatrans ref no")
    state = fields.Selection(State, "State")
    email_sent = fields.Boolean("Email sent")
    # support_ticket = fields.Boolean("Support Ticket")
    # gift_email_sent = fields.Boolean("Email sent")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order = [
            ("state", "DESC"),
        ]

    @classmethod
    def search_rec_name(cls, name, clause):
        _, operator, value = clause
        if operator.startswith("!") or operator.startswith("not "):
            bool_op = "AND"
        else:
            bool_op = "OR"
        return [
            bool_op,
            ("number", *clause[1:]),
            ("reference", *clause[1:]),
            ("party", *clause[1:]),
        ]

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            (
                "/tree",
                "visual",
                If(
                    Eval("state", "draft") == "draft",
                    "muted",
                    If(Eval("used"), "danger", "success"),
                ),
            ),
        ]
    @classmethod
    def default_email_sent(cls):
        return False
    
    # @classmethod
    # def default_gift_email_sent(cls):
    #     return False

    @classmethod
    def default_nb_adult(cls):
        return 0

    @classmethod
    def default_nb_02(cls):
        return 0

    @classmethod
    def default_nb_34(cls):
        return 0

    @classmethod
    def default_nb_56(cls):
        return 0

    @classmethod
    def default_nb_78(cls):
        return 0

    @classmethod
    def default_state(cls):
        return "draft"

    @classmethod
    def default_nb_gift(cls):
        return 0
    
    @classmethod
    def default_sp4(cls):
        return False

    @classmethod
    def default_sp5(cls):
        return False
    
    @classmethod
    def default_sp6(cls):
        return False

    @classmethod
    def _new_name(cls, **pattern):
        pool = Pool()
        Sequence = pool.get("ir.sequence")
        Configuration = pool.get("pl_cust_mdc.configuration")
        config = Configuration(1)
        sequence = config.get_multivalue("booking_sequence", **pattern)
        if sequence:
            return sequence.get()

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        vlist = [x.copy() for x in vlist]

        for values in vlist:
            if not values.get("name"):
                values["name"] = "{}".format(cls._new_name())

        return super().create(vlist)

    @classmethod
    def delete(cls, bookings):
        for b in bookings:
            if b.state == "payed":
                raise UnableToDelete("Impossible de supprimer une réservation payée")

        super().delete(bookings)
    
    # @classmethod
    # def default_support_ticket(cls):
    #     return False


class MDCDayPub(ModelSQL, ModelView):
    "MDC Day Pub"
    __name__ = "pl_cust_mdc.day_pub"
    _order_name = 'date'

    name = fields.Char("Day")
    date = fields.Date("Date")
    dtype = fields.Selection(DAYPub_type, "Day type")
    dtype_string = dtype.translated("dtype")

    nb_max = fields.Integer("Nb max")

    lim1 = fields.Function(fields.Integer("lim1"), "on_change_with_lim1")
    lim2 = fields.Function(fields.Integer("lim2"), "on_change_with_lim2")

    tot_morning = fields.Function(
        fields.Integer("Tot_morning"), "on_change_with_tot_morning"
    )
    tot_afternoon = fields.Function(
        fields.Integer("Tot_afternoon"), "on_change_with_tot_afternoon"
    )

    tot_live_morning = fields.Function(
        fields.Integer("Tot_live_morning"), "on_change_with_tot_live_morning"
    )
    tot_live_afternoon = fields.Function(
        fields.Integer("Tot_live_afternoon"), "on_change_with_tot_live_afternoon"
    )
    bookings_pub = fields.One2Many("pl_cust_mdc.booking_pub", "day", "Bookings")

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            (
                '/tree/field[@name="tot_morning"]',
                "visual",
                If(
                    Eval("tot_morning", 0) > Eval("lim2", 0),
                    "danger",
                    If(Eval("tot_morning", 0) > Eval("lim1", 0), "warning", "success"),
                ),
            ),
            (
                '/tree/field[@name="tot_afternoon"]',
                "visual",
                If(
                    Eval("tot_afternoon", 0) > Eval("lim2", 0),
                    "danger",
                    If(
                        Eval("tot_afternoon", 0) > Eval("lim1", 0), "warning", "success"
                    ),
                ),
            ),
        ]

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            (
                "date_uniq",
                Unique(t, t.date),
                "Attention !! Il y a déjà un jour avec cette date",
            ),
        ]
        cls._order.insert(0, ("date", "ASC"))

    @fields.depends("bookings_pub",)
    def on_change_with_tot_morning(self, name=None):
        tot = 0
        for book in self.bookings_pub:
            if book.state == "payed" and book.mad in ("md"):
                tot += (
                    book.nb_adult
                    + book.nb_02
                    + book.nb_34
                    + book.nb_56
                    + book.nb_78
                    + book.nb_gift
                    + book.nb_asso
                )
        return tot

    @fields.depends("bookings_pub",)
    def on_change_with_tot_afternoon(self, name=None):
        tot = 0
        for book in self.bookings_pub:
            if book.state == "payed" and book.mad in ("ad"):
                tot += (
                    book.nb_adult
                    + book.nb_02
                    + book.nb_34
                    + book.nb_56
                    + book.nb_78
                    + book.nb_gift
                    + book.nb_asso
                )
        return tot

    @fields.depends("bookings_pub",)
    def on_change_with_tot_live_morning(self, name=None):
        tot = 0
        for book in self.bookings_pub:
            if book.used and book.state == "payed" and book.mad in ("md"):
                tot += (
                    book.nb_adult
                    + book.nb_02
                    + book.nb_34
                    + book.nb_56
                    + book.nb_78
                    + book.nb_gift
                    + book.nb_asso
                )
        return tot

    @fields.depends("bookings_pub",)
    def on_change_with_tot_live_afternoon(self, name=None):
        tot = 0
        for book in self.bookings_pub:
            if book.used and book.state == "payed" and book.mad in ("ad"):
                tot += (
                    book.nb_adult
                    + book.nb_02
                    + book.nb_34
                    + book.nb_56
                    + book.nb_78
                    + book.nb_gift
                    + book.nb_asso
                )
        return tot

    @fields.depends(
        "nb_max",
    )
    def on_change_with_lim1(self, name=None):
        return self.nb_max * 0.7

    @fields.depends(
        "nb_max",
    )
    def on_change_with_lim2(self, name=None):
        return self.nb_max * 0.9

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        vlist = [x.copy() for x in vlist]

        for values in vlist:
            if not values.get("name") and values.get("date"):
                values["name"] = my_format_date(values.get("date"))

        return super().create(vlist)


class MDCReportPub(Report):
    __name__ = "pl_cust_mdc.mdc_reportpub"

    @classmethod
    def get_context(cls, records, headers, data):
        pool = Pool()
        Date = pool.get("ir.date")
        LANG = pool.get("ir.lang")
        Conf = pool.get("pl_cust_mdc.configuration")
        conf_val = Conf(1)

        context = super().get_context(records, headers, data)

        # print(context)
        context["booking"] = context["record"]
        context["lang"] = LANG(LANG.search([("code", "=", "fr")])[0])

        context["nb"] = (
            context["record"].nb_adult
            + context["record"].nb_34
            + context["record"].nb_56
            + context["record"].nb_78
        )
        context["nb_asso"] = context["record"].nb_asso
        context["nb_02"] = context["record"].nb_02
        context["nb_34"] = context["record"].nb_34
        context["nb_56"] = context["record"].nb_56
        context["nb_78"] = context["record"].nb_78
        context["nb_free"] = (
            context["record"].nb_gift
            + context["record"].nb_02
            + context["record"].nb_asso
        )
        context["urlrefno"] = "{}?refno={}".format(
            conf_val.checkticketUrl, context["booking"].refno
        )
        context["date"] = format_date2(context["record"].day.date)
        context["ma"] = context["record"].mad == "m" and "09h00" or "14h00"
        #
        #
        # http://192.168.3.45:4200/success?datatransTrxId=231113141906959855
        context["myimg"] = (
            generate_png(
                code="{}?refno={}".format(
                    conf_val.checkticketUrl, context["booking"].refno
                )
            ),
            "image/png",
        )

        return context


class MDCReportVoucher(Report):
    __name__ = "pl_cust_mdc.mdc_reportgift"

    @classmethod
    def get_context(cls, records, headers, data):
        pool = Pool()
        Date = pool.get("ir.date")
        LANG = pool.get("ir.lang")
        Conf = pool.get("pl_cust_mdc.configuration")
        conf_val = Conf(1)

        context = super().get_context(records, headers, data)

        booking = context["record"]

        if booking.state == "draft":
            raise Exception("Erreur, bons impayé !")

        context["booking"] = booking
        context["lang"] = LANG(LANG.search([("code", "=", "fr")])[0])

        context["nb_2"] = booking.nb_2
        context["nb_4"] = booking.nb_4
        context["nb_10"] = booking.nb_10
        context["urlrefno"] = booking.refno
        context["pdate"] = booking.purchase_date
        context["pdate"] = booking.purchase_date.strftime("%d.%m.%y")

        context["myimg2"] = (
            generate_png(
                code="{}?refno={}".format(
                    conf_val.checktgiftUrl, context["booking"].refno
                )
            ),
            "image/png",
        )

        return context

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
from trytond.pyson import Bool, Eval, If, Or
from trytond.transaction import Transaction
from trytond.model.exceptions import ValidationError
from trytond.tools.qrcode import generate_png

class UnableToDelete(ValidationError):
    pass

__all__ = ["MDCDayInst", "MDCBookingInst"]

CHILD_YEAR = [
    ("0-2", "0-2 Year"),
    ("3-4", "3-4 Year"),
    ("5-6", "5-6 Year"),
    ("7-8", "7-8 Year"),
]

MAD_choice_inst = [
    ("m", "Matin"),
    ("a", "Après-Midi"),
    ("d", "Journée"),
]

INST_TYPE = [
        ('ipe', "IPE Ville de Genève / Canton de Genève"),
        ('pub', "Collectivité publique hors Ville de Genève"),
        ('dip', "E&C (Ecole & Culture) – DIP"),
        ('priv', "Collectivité privée / Association / Fondation"),
    ]

State = [
    ("draft", "Draft"),  # Brouillon
    ("valid", "Validated"),  # Validée
    ("no", "No"),  # Pas possible
]

DAYInst_type = [("i", "Institution"), ("h", "Holliday"), ("c", "Close")]

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

class MDCBookingInst(ModelSQL, ModelView):
    "MDC BookingInst"
    __name__ = "pl_cust_mdc.booking_inst"
    
    name = fields.Char("Booking", readonly=True)
    inst_name = fields.Char("Inst Name")
    inst_prov = fields.Char("Inst Prov")
    inst_address = fields.Char("Inst Address")
    inst_zip = fields.Char("Inst Zip")
    inst_type = fields.Selection(INST_TYPE, "Inst Type")
    inst_rep = fields.Char("Inst Rép")
    inst_email = fields.Char("Inst Email Contact")
    inst_tel = fields.Char("Tel Contact")
    nb_child = fields.Integer("Number Child")
    child_year = fields.Selection(CHILD_YEAR, "Child Year")
    child_year_string = child_year.translated("child_year")
    nb_adult = fields.Integer("Number Adult")
    inst_activity = fields.Char("Activity")
    inst_comment = fields.Text("Comment")
    mad = fields.Selection(MAD_choice_inst, "MAD choice")
    mad_string = mad.translated("mad")

    tot_day = fields.Function(
        fields.Integer("Tot_Day"), "on_change_with_tot_day"
    )

    sieste = fields.Boolean("Sieste")
    piqueNique = fields.Boolean("Pique Nique")
    party = fields.Many2One("party.party", "Party")

    booking_date = fields.Date("Date de réservation")

    invoice = fields.Many2One("account.invoice", "Invoice")
    invoiced = fields.Function(fields.Boolean("Invoiced"), "on_change_with_invoiced")
    state = fields.Selection(State, "State")

    txt_for_mail = fields.Function(fields.Text("Resume"), "on_change_with_txt_for_mail")

    day = fields.Many2One("pl_cust_mdc.day_inst", "Day", required=True)

    @fields.depends("nb_child", "mad")
    def on_change_with_tot_day(self, name=None):
        
        if self.mad == "d" :
            return self.nb_child * 2
        else :
            return self.nb_child
        

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order = [
            ("state", "DESC"),
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
                    If(Eval("state", "draft") == "valid", "success", "danger"),
                ),
            ),
        ]

    @classmethod

    def default_booking_date(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today()

    @classmethod
    def default_nb_child(cls):
        return 0

    @classmethod
    def default_nb_adult(cls):
        return 0

    @classmethod
    def default_state(cls):
        return "draft"

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update(
            {
                "make_invoice": {
                    "invisible": Or(
                        ~(Eval("state") == "valid"), (Bool(Eval("invoice")))
                    ),
                },
                "make_valid": {
                    "invisible": ~(Eval("state") == "draft"),
                },
                "make_no": {
                    "invisible": ~(Eval("state") == "draft"),
                },
            }
        )

    @classmethod
    @ModelView.button_action("pl_cust_mdc.act_wizard_createinv")
    def make_invoice(cls, booking):
        pass

    @classmethod
    @ModelView.button
    def make_valid(cls, bookings):
        cls.write(
            bookings,
            {
                "state": "valid",
            },
        )
        return "reload"

    @classmethod
    @ModelView.button
    def make_no(cls, bookings):
        cls.write(
            bookings,
            {
                "state": "no",
            },
        )
        return "reload"

    @classmethod
    def delete(cls, bookings):
        #for b in bookings:
        #    #if b.state == "valid":
        raise UnableToDelete("Impossible de supprimer une réservation...Contacter ProLibre en cas de besoin")

        super().delete(bookings)

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

    @fields.depends("invoice")
    def on_change_with_invoiced(self, name=None):
        return False

    @fields.depends('inst_name','inst_prov','inst_rep','inst_email','nb_child','child_year','nb_adult','inst_activity','sieste','piqueNique','mad','day')
    def on_change_with_txt_for_mail(self, name=None):
        return """Nom : {}
Responsable : {}
Nombre d'enfants : {}
Nombre d'adultes : {}
Age : {}
Activité : {}
Période : {}
Jour : {}
Sieste : {}
        """.format(
            self.inst_name, 
            #self.inst_prov,
            self.inst_rep,
            self.nb_child,
            self.nb_adult, 
            self.child_year_string , 
            self.inst_activity or '-', 
            self.mad_string,
            self.day and my_format_date(self.day.date) or '-',
            self.sieste and 'Oui' or 'Non')
    

class MDCDayInst(ModelSQL, ModelView):
    "MDC Day Inst"
    __name__ = "pl_cust_mdc.day_inst"
    _order_name = 'date'

    name = fields.Char("Day")
    date = fields.Date("Date")
    dtype = fields.Selection(DAYInst_type, "Day type")
    dtype_string = dtype.translated("dtype")

    nb_max = fields.Integer("Nb max")
    nb_inst_max = fields.Integer("Nb inst max")

    tot_morning = fields.Function(
        fields.Integer("Tot_morning"), "on_change_with_tot_morning"
    )
    tot_afternoon = fields.Function(
        fields.Integer("Tot_afternoon"), "on_change_with_tot_afternoon"
    )
    tot_day = fields.Function(fields.Integer("Tot_day"), "on_change_with_tot_day")
    tot_sieste = fields.Function(
        fields.Integer("Tot_sieste"), "on_change_with_tot_sieste"
    )
    tot_inst_m = fields.Function(
        fields.Integer("Tot_inst morning"), "on_change_with_tot_inst_m"
    )
    tot_inst_a = fields.Function(
        fields.Integer("Tot_inst afternoon"), "on_change_with_tot_inst_a"
    )
    booking_to_valid = fields.Function(
        fields.Boolean("To valid"),
        "on_change_with_booking_to_valid",
        searcher="search_booktovalid",
    )
    bookings_inst = fields.One2Many("pl_cust_mdc.booking_inst", "day", "Bookings")

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            (
                '/tree/field[@name="name"]',
                "visual",
                If(Eval("dtype", '') != 'i', "danger", "success"),
            ),
            (
                '/tree/field[@name="tot_sieste"]',
                "visual",
                If(Eval("tot_sieste", 0) > 0, "danger", "success"),
            ),
            (
                '/tree/field[@name="tot_morning"]',
                "visual",
                If(Eval("tot_morning", 0) > 0, "danger", "success"),
            ),
            (
                '/tree/field[@name="tot_afternoon"]',
                "visual",
                If(Eval("tot_afternoon", 0) > 0, "danger", "success"),
            ),
            (
                '/tree/field[@name="tot_inst_m"]',
                "visual",
                If(Eval("tot_inst_m", 0) > 2, "danger", "success"),
            ),
            (
                '/tree/field[@name="tot_inst_a"]',
                "visual",
                If(Eval("tot_inst_a", 0) > 2, "danger", "success"),
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

    @classmethod
    def search_booktovalid(cls, name, clause):
        Book = Pool().get("pl_cust_mdc.booking_inst")

        res = []
        for b in Book.search([("state", "=", "draft")]):
            if not b.day in res:
                res.append(b.day.id)

        return ("id", "in", res)

    @fields.depends(
        "bookings_inst",
    )
    def on_change_with_booking_to_valid(self, name=None):
        for book in self.bookings_inst:
            if book.state == "draft":
                return True
        return False

    @fields.depends(
        "bookings_inst",
    )
    def on_change_with_tot_morning(self, name=None):
        tot = 0
        for book in self.bookings_inst:
            if book.state == "valid" and book.mad and book.mad in ("md"):
                if book.nb_child:
                    tot += book.nb_child
                if book.nb_adult:
                    tot += book.nb_adult
        return tot

    @fields.depends(
        "bookings_inst",
    )
    def on_change_with_tot_afternoon(self, name=None):
        tot = 0
        for book in self.bookings_inst:
            if book.state == "valid" and book.mad and book.mad in ("ad"):
                if book.nb_child:
                    tot += book.nb_child
                if book.nb_adult:
                    tot += book.nb_adult
        return tot

    @fields.depends(
        "bookings_inst",
    )
    def on_change_with_tot_day(self, name=None):
        tot = 0
        for book in self.bookings_inst:
            if book.state == "valid" and book.mad and book.mad in ("d"):
                if book.nb_child:
                    tot += book.nb_child
                if book.nb_adult:
                    tot += book.nb_adult
        return tot

    @fields.depends(
        "bookings_inst",
    )
    def on_change_with_tot_sieste(self, name=None):
        tot = 0
        for book in self.bookings_inst:
            if book.state == "valid" and book.sieste:
                if book.nb_child:
                    tot += book.nb_child
        return tot

    @fields.depends(
        "bookings_inst",
    )
    def on_change_with_tot_inst_m(self, name=None):
        tot = 0
        for book in self.bookings_inst:
            if book.mad and book.mad in ("md") and book.state == "valid":
                tot += 1
        return tot

    @fields.depends(
        "bookings_inst",
    )
    def on_change_with_tot_inst_a(self, name=None):
        tot = 0
        for book in self.bookings_inst:
            if book.mad and book.mad in ("ad") and book.state == "valid":
                tot += 1
        return tot

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        vlist = [x.copy() for x in vlist]

        for values in vlist:
            if not values.get("name") and values.get("date"):
                values["name"] = my_format_date(values.get("date"))

        return super().create(vlist)

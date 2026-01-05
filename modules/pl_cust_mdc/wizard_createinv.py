from trytond.wizard import Wizard, StateView, StateTransition, StateAction, Button
from trytond.model import ModelView, fields, ModelSingleton, ModelSQL
from trytond.pool import Pool
from trytond.transaction import Transaction
from datetime import datetime
from trytond.pyson import Eval, PYSONEncoder
from decimal import Decimal

from trytond.model.exceptions import ValidationError


class ErrorGenInvoice(ValidationError):
    pass


__all__ = ["BookingWizardInvoice", "CreateInvoice", "CreateInvoiceStart"]

CHOICE_TVA = {
    "8": {"to": datetime(2017, 12, 31).date(), "from": datetime(2011, 1, 1).date()},
    "77": {"to": datetime(2023, 12, 31).date(), "from": datetime(2018, 1, 1).date()},
    "81": {"to": datetime(2040, 12, 31).date(), "from": datetime(2024, 1, 1).date()},
}


def format_date2(date):
    y, m, d = str(date).split("-")
    return "{}.{}.{}".format(d, m, y)


class BookingWizardInvoice(ModelSingleton, ModelSQL, ModelView):
    "Configuration for invoiced wizard"
    __name__ = "pl_cust_mdc.wizardconf"

    account_deb_id = fields.Many2One("account.account", "Account H Deb", required=True)

    currency = fields.Many2One("currency.currency", "Devise", required=True)
    journal_id = fields.Many2One("account.journal", "Journal", required=True)
    journal_pp = fields.Many2One("account.move.reconcile.write_off", "Journal PP", required=False)
    payment_term = fields.Many2One("account.invoice.payment_term", "Default Customer Payment Term")
    product_tva = fields.Many2One("product.product", "Produit TVA", required=True)
    product_notva = fields.Many2One("product.product", "Produit NO TVA", required=True)

    #depl_tva = fields.Many2One("product.product", "Depl TVA", required=True)
    #depl_notva = fields.Many2One("product.product", "Depl NO TVA", required=True)

    taxe = fields.Many2One("account.tax", "TVA", required=True)


class CreateInvoiceStart(ModelView):
    "Create Invoice"
    __name__ = "pl_cust_mdc.invcreate_start"

    booking = fields.Many2One(
        "pl_cust_mdc.booking_inst", "Booking", required=True, readonly=True
    )

    with_vat = fields.Boolean("With VAT")

    @staticmethod
    def default_booking():
        if Transaction().context.get("active_model", "") == "pl_cust_mdc.booking_inst":
            return Transaction().context.get("active_id", "")
        return None


class CreateInvoice(Wizard):
    "Create Invoice"
    __name__ = "pl_cust_mdc.invcreate"

    ids_list = []
    new_inv = None

    start = StateView(
        "pl_cust_mdc.invcreate_start",
        "pl_cust_mdc.wizard_createinv_view_form",
        [
            Button("Cancel", "end", "tryton-cancel"),
            Button("Facturation", "generate_inv", "tryton-ok", default=True),
        ],
    )

    generate_inv = StateTransition()
    goto_new_inv = StateAction("account_invoice.act_invoice_out_form")

    def do_goto_new_inv(self, action):
        action["name"] = "Nouvelle Facture"
        action["pyson_domain"] = [
            ("id", "=", self.new_inv.id),
        ]

        action["pyson_domain"] = PYSONEncoder().encode(action["pyson_domain"])

        return action, {}

    def transition_generate_inv(self):

        pool = Pool()
        Date_ = Pool().get("ir.date")
        Configuration = pool.get("pl_cust_mdc.wizardconf")
        config = Configuration(1)

        tax_to_use = config.taxe

        invoice_obj = pool.get("account.invoice")
        invoice_line_obj = pool.get("account.invoice.line")

        if self.start.booking.party:
            party = self.start.booking.party
        else:
            raise ErrorGenInvoice("Pas de tiers à lier à cette facture")

        account_deb = config.account_deb_id

        pay_term = config.payment_term or None
        if pay_term:
            date_due = pay_term.compute(
                amount=300, date=Date_.today(), currency=config.currency
            )[0][0]
            print("************************* {}".format(date_due))
        else:
            date_due = None

        new_invoice = invoice_obj.create(
            [
                {
                    "party": party.id,
                    "invoice_date": Date_.today(),
                    "invoice_address": party.addresses[0].id,
                    "journal": config.journal_id,
                    "date_due": date_due,
                    "payment_term": pay_term,
                    "account": account_deb,
                    "description": '{} {}'.format(self.start.booking.inst_name, self.start.booking.name),
                    "comment" : self.start.booking.txt_for_mail,
                    # 'booking':self.start.folder_id,
                    # 'currency': self.start.folder_id.currency.id,
                }
            ]
        )
        
        if self.start.booking.mad == 'd' :
            unit_price = 5.0 
            descr = 'Billets journée entière'
        else : 
            unit_price = 3.0 
            descr = 'Billets  demi-journée'


        c = self.start.booking.nb_child
        a = self.start.booking.nb_adult
        
        if self.start.with_vat :
            new_invoice_line = invoice_line_obj.create([{'invoice': new_invoice[0].id,
                                                         'account': config.product_tva.account_category.account_revenue.id,
                                                         'unit': config.product_tva.default_uom.id,
                                                         'quantity': c,
                                                         'unit_price': unit_price,
                                                         #'product': config.product_tva,
                                                         'description': descr,
                                                         'taxes': [('add', [tax_to_use, ])],
                                                          }])
        else :
            new_invoice_line = invoice_line_obj.create([{'invoice': new_invoice[0].id,
                                                         'account': config.product_tva.account_category.account_revenue.id,
                                                         'unit': config.product_notva.default_uom.id,
                                                         'quantity': c,
                                                         'unit_price': unit_price,
                                                         #'product': config.product_notva,
                                                         'description': descr,
                                                          }])
            

        invoice_obj.update_taxes(new_invoice)
        new_invoice[0].save()
        self.start.booking.invoice = new_invoice[0]
        self.start.booking.save()

        self.new_inv = new_invoice[0]

        return "goto_new_inv"

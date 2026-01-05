from trytond.wizard import Wizard, StateView, StateTransition, StateAction, Button
from trytond.model import ModelView, fields
from trytond.pool import Pool
from trytond.transaction import Transaction
from datetime import datetime
from trytond.pyson import Eval, PYSONEncoder
from decimal import Decimal

from trytond.model.exceptions import ValidationError


class FolderFactError(ValidationError):
    pass


__all__ = ["DevisCreateInvoice", "DevisCreateInvoiceStart"]


def format_date2(date):
    y, m, d = str(date).split("-")
    return "{}.{}.{}".format(d, m, y)


class DevisCreateInvoiceStart(ModelView):
    "Devis Create Invoice Start"
    __name__ = "pl_cust_devis.devisinvcreate_start"

    folder_id = fields.Many2One(
        "pl_cust_plfolders.folders", "Folder", required=True, readonly=True
    )

    with_vat = fields.Boolean("With VAT")

    folder_devis_tot = fields.Function(
        fields.Char("Devis tot"), "on_change_with_folder_devis_tot"
    )

    devislines = fields.One2Many("pl_cust_devis.devisline", None, "Devis Lines")

    @staticmethod
    def default_folder_id():
        if Transaction().context.get("active_model", "") == "pl_cust_plfolders.folders":
            return Transaction().context.get("active_id", "")
        return None

    @staticmethod
    def default_devislines():
        pool = Pool()
        foldersheet_obj = pool.get("pl_cust_devis.devisline")
        if Transaction().context.get("active_model", "") == "pl_cust_plfolders.folders":
            res = []
            for i in foldersheet_obj.search(
                [
                    ("folder_id", "=", Transaction().context.get("active_id", "")),
                    ("invoice_id", "=", None),
                ]
            ):

                res.append(i.id)
            return res
        return None

    @fields.depends("devislines")
    def on_change_with_folder_devis_tot(self, name=None):

        tot = Decimal(0)

        if self.devislines:
            for d in self.devislines:

                tot += d.price

        return "{:.2f}".format(tot)


class DevisCreateInvoice(Wizard):
    "Devis Create Invoice"
    __name__ = "pl_cust_devis.devisinvcreate"

    ids_list = []
    new_inv = None

    start = StateView(
        "pl_cust_devis.devisinvcreate_start",
        "pl_cust_devis.wizard_deviscreateinv_view_form",
        [
            Button("Cancel", "end", "tryton-cancel"),
            Button("Facturation du devis", "generate_inv", "tryton-ok", default=True),
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
        Configuration = pool.get("pl_cust_plfolders.wizardconf")
        config = Configuration(1)
        Conf_comptable = pool.get("account.configuration")
        config_comptable = Conf_comptable(1)

        invoice_obj = pool.get("account.invoice")
        invoice_line_obj = pool.get("account.invoice.line")

        if self.start.folder_id.fact_to:
            party = self.start.folder_id.fact_to
        else:
            party = self.start.folder_id.party_id

        account_deb = config.account_deb_id

        devislines = self.start.devislines

        pay_term = config.payment_term or None
        if pay_term:
            date_due = pay_term.compute(
                amount=300, date=Date_.today(), currency=self.start.folder_id.currency
            )[0][0]
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
                    "description": self.start.folder_id.description,
                    "folder_id": self.start.folder_id,
                    "currency": self.start.folder_id.currency.id,
                    'comment': self.start.folder_id.notes,
                }
            ]
        )

        # Compute timesheet
        compute_ts = {}
        ts_list_tva = ""
        ts_list_notva = ""
        ts_price_tot_notva = 0.0

        for d in devislines:
            if not d.invoiced:
                new_invoice_line = invoice_line_obj.create(
                    [
                        {
                            "invoice": new_invoice[0].id,
                            "account": d.product.account_category.account_revenue and d.product.account_category.account_revenue.id or config_comptable.default_category_account_revenue and config_comptable.default_category_account_revenue.id or None,
                            "unit": d.product.default_uom.id,
                            "quantity": d.quantity,
                            "unit_price": "{:0.4f}".format(
                                d.product_price
                            ),
                            "product": d.product,
                            "note": d.comment,
                            "description": d.name,
                            "taxes": d.product_tva and [
                                (
                                    "add",
                                    [
                                        d.product_tva,
                                    ],
                                )
                            ] or [],
                        }
                    ]
                )
                d.invoice_id = new_invoice[0].id
                d.save()
        invoice_obj.update_taxes(new_invoice)
        new_invoice[0].save()
        self.new_inv = new_invoice[0]

        return "goto_new_inv"

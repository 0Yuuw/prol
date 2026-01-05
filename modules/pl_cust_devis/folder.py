# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import (
    ModelSQL,
    DeactivableMixin,
    Workflow,
    ModelView,
    fields,
    sequence_ordered,
)
from trytond.pyson import Eval, Bool
from datetime import datetime, timedelta
from trytond.pool import PoolMeta, Pool
from trytond.report import Report
from trytond.rpc import RPC
from trytond.transaction import Transaction
from decimal import *
from trytond.model.exceptions import ValidationError

__all__ = ["DevisFolders", "Devis"]

class UnableToDelete(ValidationError):
    pass

class Devis(sequence_ordered(), ModelSQL, ModelView):
    "PL Folder timesheet"
    __name__ = "pl_cust_devis.devisline"

    name = fields.Char(
        "Description",
        states={
            "readonly": Bool(Eval("invoiced")),
        },
        depends=["invoiced"],
    )

    comment = fields.Text(
        "Comment",
        states={
            "readonly": Bool(Eval("invoiced")),
        },
        depends=["invoiced"],
    )

    product = fields.Many2One(
        "product.product",
        "Product",
        required=True,
        states={
            "readonly": Bool(Eval("invoiced")),
        },
        depends=["invoiced"],
    )

    product_price = fields.Numeric(
        "Product Price",
        states={
            "readonly": Bool(Eval("invoiced")),
        },
        depends=["invoiced"],
    )

    product_tva = fields.Many2One(
        "account.tax",
        "TVA",
        states={
            "readonly": Bool(Eval("invoiced")),
        },
        depends=["invoiced"],
    )

    folder_id = fields.Many2One("pl_cust_plfolders.folders", "Folder", required=True)

    quantity = fields.Float(
        "Qty",
        required=True,
        states={
            "readonly": Bool(Eval("invoiced")),
        },
        depends=["invoiced"],
    )

    price = fields.Function(fields.Numeric("Price"), "on_change_with_price")

    invoiced = fields.Function(
        fields.Boolean("Invoiced"),
        "on_change_with_invoiced",
        searcher="search_invoiced",
    )
    invoice_id = fields.Many2One("account.invoice", "Invoice")
    force_invoice = fields.Boolean("Force Invoice")

    pct = fields.Selection(
        [
            ("0", "0%"),
            ("50", "50%"),
            ("100", "100%"),
            ("150", "150%"),
            ("200", "200%"),
        ],
        "PCT",
        sort=False,
        required=True,
    )

    # archived = fields.Boolean('Archived')


    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
                'copy_button': {},
                })

    @classmethod
    @ModelView.button
    def copy_button(cls, lines):
        cls.copy(lines)
        return 'reload'
        
    @fields.depends("product")
    def on_change_product(self):
        if self.product:
            self.name = self.product.name
            self.comment = self.product.description
            self.product_price = self.product.list_price
            self.product_tva = (
                self.product.customer_taxes_used
                and self.product.customer_taxes_used[0]
                or None
            )

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()

        default.setdefault('invoice_id', None)
        default.setdefault('force_invoice', None)
        
        new_lines = []
        for line in lines:
            new_line, = super().copy([line], default)
            new_lines.append(new_line)
        return new_lines

    @classmethod
    def delete(cls, lines):
        for d in lines:
            if d.invoiced:
                raise UnableToDelete("Impossible de supprimer des lignes facturées")

        super().delete(lines)

    @staticmethod
    def default_pct():
        return "100"

    @staticmethod
    def default_product_price():
        return 0

    @fields.depends("invoice_id", "force_invoice")
    def on_change_with_invoiced(self, name=None):
        if self.invoice_id or self.force_invoice: 
            return True

        return False

    @fields.depends("product", "product_price", "quantity", "pct", "folder_id")
    def on_change_with_price(self, name=None):
        if not self.folder_id:
            return

        if self.product_price is not None and self.quantity and self.pct:
            return self.product_price * Decimal(self.quantity * (int(self.pct) / 100))
        else:
            return 0


class DevisFolders(ModelSQL, ModelView):
    "Folders"
    __name__ = "pl_cust_plfolders.folders"

    price_tot = fields.Function(fields.Numeric("Price tot"), "on_change_with_price_tot")
    price_devis = fields.Function(fields.Numeric("Price devis"), "on_change_with_price_devis")
    price_manual = fields.Numeric("Price manual")

    devis_lines = fields.One2Many("pl_cust_devis.devisline", "folder_id", "Devis Line")
    contact_name = fields.Char('Contact name')
    contact_address = fields.Many2One('party.address', 'Address', domain=[
        ('party', '=', Eval('party_id'))], depends=['party_id'])

    state = fields.Selection(
        [
            ("", ""),
            ("devis", "Devis"),
            ("denied", "Denied"),
            ("open", "Open"),
            ("invoiced", "Invoiced"),
            ("close", "Close"),
        ],
        "Devis State",
        readonly=False,
        required=True,
    )

    @staticmethod
    def default_state():
        return 'devis'

    @classmethod
    def __setup__(cls):
        super().__setup__()

        cls._transitions = set((
            ('devis', 'open'),
            ('devis', 'denied'),
            ('open', 'invoiced'),
            ('open', 'close'),            
            ('invoiced', 'close'),
            ('close', 'open'),
        ))


        cls._buttons.update(
            {
                "devismake_invoice": {
                    "invisible": Eval("state") != "open",
                    "depends": ["state"],
                },
                "open": {
                    "invisible": Eval("state") != "devis",
                    "depends": ["state"],
                },
                "denied": {
                    "invisible": Eval("state") != "devis",
                    "depends": ["state"],
                },
                "close": {
                    "invisible": ~Eval("state").in_(["open","invoiced"]),
                    "depends": ["state"],
                },
                "invoiced": {
                    "invisible": Eval("state") != "open",
                    "depends": ["state"],
                },
                "reopen": {
                    "invisible": Eval("state") != "close",
                    "depends": ["state"],
                },
            }
        )

    @fields.depends("devis_lines")
    def on_change_with_price_tot(self, name=None):
        tot = 0
        for d in self.devis_lines : 
            tot += d.price
        return tot

    @fields.depends("devis_lines", "price_manual")
    def on_change_with_price_devis(self, name=None):
        tot = 0 

        if self.price_manual and self.price_manual > 0 :
            return self.price_manual
        
        for d in self.devis_lines : 
            tot += not d.invoiced and d.price or 0

        return tot

    @classmethod
    @ModelView.button_action("pl_cust_devis.act_wizard_deviscreateinv")
    def devismake_invoice(cls, folders):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition("open")
    def open(cls, periods):
        """
        Open Folder
        """
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition("denied")
    def denied(cls, periods):
        "Denied Folder"
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition("open")
    def reopen(cls, periods):
        "ReOpen Folder"
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition("close")
    def close(cls, periods):
        "Close Folder"
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition("invoiced")
    def invoiced(cls, periods):
        "Invoiced Folder"
        pass

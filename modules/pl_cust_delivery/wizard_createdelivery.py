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


__all__ = ["CreateDelivery", "CreateDeliveryStart", "DeliveryTMP"]


def format_date2(date):
    y, m, d = str(date).split("-")
    return "{}.{}.{}".format(d, m, y)


class DeliveryTMP(ModelView):
    "PL Delivery TMP"

    __name__ = "pl_cust_delivery.deliverylinetmp"

    name = fields.Char(
        "Description",
    )

    comment = fields.Text(
        "Comment",
    )

    product = fields.Many2One(
        "product.product",
        "Product",
        required=True,
    )

    devisline_id = fields.Many2One(
        "pl_cust_delivery.devisdeliveryline", "Devis Line", required=True
    )
    quantity = fields.Float(
        "Qty",
        required=True,
    )


class CreateDeliveryStart(ModelView):
    "Create Delivery Start"

    __name__ = "pl_cust_delivery.deliverycreate_start"

    delivery_date = fields.Date("Date", required=True )

    folder_id = fields.Many2One("pl_cust_plfolders.folders", "Folder", required=True, readonly=True)
    
    devislines = fields.One2Many("pl_cust_delivery.devisdeliveryline", None, "Devis Lines")

    deliverylines = fields.One2Many("pl_cust_delivery.deliverylinetmp", None, "Delivery Lines")

    @staticmethod
    def default_delivery_date():
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today() 
    
    @staticmethod
    def default_folder_id():
        if Transaction().context.get("active_model", "") == "pl_cust_plfolders.folders":
            return Transaction().context.get("active_id", "")
        return None

    @staticmethod
    def default_devislines():
        pool = Pool()
        devisline_obj = pool.get("pl_cust_delivery.devisdeliveryline")
        if Transaction().context.get("active_model", "") == "pl_cust_plfolders.folders":
            res = []
            for i in devisline_obj.search(
                [
                    ("folder_id", "=", Transaction().context.get("active_id", "")),
                ]
            ):

                res.append(i.id)
            return res
        return None

    @staticmethod
    def default_deliverylines():
        pool = Pool()
        devisline_obj = pool.get("pl_cust_delivery.devisdeliveryline")
        deliveryline_obj = pool.get("pl_cust_delivery.deliverylinetmp")

        if Transaction().context.get("active_model", "") == "pl_cust_plfolders.folders":
            res = []
            for d in devisline_obj.search(
                [
                    ("folder_id", "=", Transaction().context.get("active_id", "")),
                ]
            ):

                if d.quantity - d.delivery > 0:
                    new_delivery_line = {
                        "name": d.name,
                        "comment": d.comment,
                        "quantity": d.quantity - d.delivery,
                        "product": d.product.id,
                        "devisline_id": d.id,
                    }

                    res.append(new_delivery_line)
            return res
        return None


class CreateDelivery(Wizard):
    "Create Delivery"

    __name__ = "pl_cust_delivery.deliverycreate"

    start = StateView(
        "pl_cust_delivery.deliverycreate_start",
        "pl_cust_delivery.wizard_createdelivery_view_form",
        [
            Button("Cancel", "end", "tryton-cancel"),
            Button(
                "Génération du bulletin de livraison",
                "generate_delivery",
                "tryton-ok",
                default=True,
            ),
        ],
    )

    generate_delivery = StateTransition()
    # goto_new_inv = StateAction("account_invoice.act_invoice_out_form")

    def transition_generate_delivery(self):

        pool = Pool()
        Date_ = Pool().get("ir.date")
        DeliveryLine = Pool().get("pl_cust_delivery.deliveryline")

        delivery_lines = self.start.deliverylines

        for d in delivery_lines:

            if d.quantity == 0:
                continue

            new_delivery_line = DeliveryLine.create(
                [
                    {
                        "delivery_date" : self.start.delivery_date,    
                        "name": d.name,
                        "comment": d.comment,
                        "quantity": d.quantity,
                        "product": d.product.id,
                        "folder_id": self.start.folder_id.id,
                        "devisline_id": d.devisline_id,
                    }
                ]
            )

            # DeliveryLine.delete(tmp)

            # d.delivery = d.quantity

        return "end"

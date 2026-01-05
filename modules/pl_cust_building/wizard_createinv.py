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


__all__ = ["BuildingCreateInvoice", "BuildingCreateInvoiceStart"]

CHOICE_TVA = {'8': {'to': datetime(2017, 12, 31).date(),
                    'from': datetime(2011, 1, 1).date()},
              '77': {'to': datetime(2030, 12, 31).date(),
                     'from': datetime(2018, 1, 1).date()}}

def format_date2(date):
    y, m, d = str(date).split("-")
    return "{}.{}.{}".format(d, m, y)


class BuildingCreateInvoiceStart(ModelView):
    "Building Create Invoice Start"
    __name__ = "pl_cust_building.buildinginvcreate_start"

    folder_id = fields.Many2One(
        "pl_cust_plfolders.folders", "Folder", required=True, readonly=True
    )

    with_vat = fields.Boolean("With VAT")

    folder_devis_tot = fields.Function(
        fields.Char("Devis tot"), "on_change_with_folder_devis_tot"
    )

    devislines = fields.One2Many("pl_cust_delivery.devisdeliveryline", None, "Devis Lines")

    folder_ts_tot = fields.Function(fields.Char('Folder TS tot'),
                                    'on_change_with_folder_ts_tot')

    timesheet_ids = fields.One2Many(
        'pl_cust_plfolders.foldersheet', None, 'Timesheet')
    
    party_ids = fields.One2Many(
        'party.party', None, 'All party')
    
    party = fields.Many2One('party.party', 'Fact to', domain=[('id', 'in', Eval('party_ids',[]))], depends=['party_ids'])
    
    @staticmethod
    def default_folder_id():
        if Transaction().context.get('active_model', '') == 'pl_cust_plfolders.folders':
            return Transaction().context.get('active_id', '')
        return None

    @staticmethod
    def default_timesheet_ids():
        pool = Pool()
        foldersheet_obj = pool.get('pl_cust_plfolders.foldersheet')
        if Transaction().context.get('active_model', '') == 'pl_cust_plfolders.folders':
            res = []
            for i in foldersheet_obj.search([
                ('folder_id', '=', Transaction().context.get('active_id', '')),
                    ('invoice_id', '=', None),  ('archived', '=', False)]):

                res.append(i.id)
            return res
        return None
    
    @staticmethod
    def default_party_ids():
        pool = Pool()
        folders_obj = pool.get('pl_cust_plfolders.folders')
        
        if Transaction().context.get('active_model', '') == 'pl_cust_plfolders.folders':
            fold = folders_obj(int(Transaction().context.get('active_id', '')))
            if fold.building :
                return fold.building.get_all_party()
        return None

    @fields.depends('timesheet_ids')
    def on_change_with_folder_ts_tot(self, name=None):

        tot_ts = 0

        if self.timesheet_ids:
            for t in self.timesheet_ids:

                if t.activity and t.duration and t.duration.total_seconds():
                    tot_ts += t.duration.total_seconds()*(int(t.pct)/100)

        hours, remainder = divmod(tot_ts, 3600)
        minutes, seconds = divmod(remainder, 60)
        if int(hours) and int(minutes):
            return '{0}h {1}min'.format(int(hours), int(minutes))
        elif int(hours):
            return '{}h'.format(int(hours))
        elif int(minutes):
            return '{}min'.format(int(minutes))
        else:
            return '-'

    @staticmethod
    def default_folder_id():
        if Transaction().context.get("active_model", "") == "pl_cust_plfolders.folders":
            return Transaction().context.get("active_id", "")
        return None

    @staticmethod
    def default_devislines():
        pool = Pool()
        foldersheet_obj = pool.get("pl_cust_delivery.devisdeliveryline")
        if Transaction().context.get("active_model", "") == "pl_cust_plfolders.folders":
            res = []
            for i in foldersheet_obj.search(
                [
                    ("folder_id", "=", Transaction().context.get("active_id", ""))
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


class BuildingCreateInvoice(Wizard):
    "Building Create Invoice"
    __name__ = "pl_cust_building.buildinginvcreate"

    ids_list = []
    new_inv = None

    start = StateView(
        "pl_cust_building.buildinginvcreate_start",
        "pl_cust_building.wizard_buildingcreateinv_view_form",
        [
            Button("Cancel", "end", "tryton-cancel"),
            Button("Facturation du dossier", "generate_inv", "tryton-ok", default=True),
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

        if self.start.party : 
            party = self.start.party
        elif self.start.folder_id.fact_to:
            party = self.start.folder_id.fact_to
        else:
            party = self.start.folder_id.party_id

        account_deb = config.account_deb_id

        devislines = self.start.devislines
        ts_to_do = self.start.timesheet_ids

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
            if True :
                new_invoice_line = invoice_line_obj.create(
                    [
                        {
                            "invoice": new_invoice[0].id,
                            "account": d.product and d.product.account_category and d.product.account_category.account_revenue and d.product.account_category.account_revenue.id or config_comptable.default_category_account_revenue and config_comptable.default_category_account_revenue.id or None,
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
                d.save()
                
        #Compute timesheet
        compute_ts = {}
        ts_list_tva = ''
        ts_list_notva = ''
        ts_price_tot_notva = 0.0

        for ts in ts_to_do:
            if not ts.invoiced:
                if not compute_ts.get(ts.resp_type):
                    compute_ts[ts.resp_type] = {
                        'hour_price': ts.hour_price,
                        'tot_duration_tva77': 0,
                        'tot_duration_tva8': 0,
                        'tot_duration_notva': 0,
                        'tot_price_tva77': 0,
                        'tot_price_tva8': 0,
                        'tot_price_notva': 0,
                        'taxe_id77': 1,
                        'taxe_id8': 2
                    }

                if self.start.folder_id.folder_tax_bool:
                    for k in ('8', '77'):
                        if CHOICE_TVA[k]['from'] <= ts.date <= CHOICE_TVA[k]['to']:
                            compute_ts[ts.resp_type]['tot_duration_tva{}'.format(
                                k)] += ts.duration.total_seconds()*(int(ts.pct)/100)
                            compute_ts[ts.resp_type]['tot_price_tva{}'.format(k)] += ts.price
                            ts_list_tva += '{}-{}-{}\n'.format(ts.name,
                                                               ts.duration, ts.price)
                else:
                    compute_ts[ts.resp_type]['tot_duration_notva'] += ts.duration.total_seconds()*(int(ts.pct)/100)
                    compute_ts[ts.resp_type]['tot_price_notva'] += ts.price
                    ts_price_tot_notva += ((ts.duration.total_seconds()/3600.0) * ts.hour_price)*(int(ts.pct)/100)
                    ts_list_notva += '{}-{}-{}\n'.format(ts.name,
                                                         ts.duration, ts.price)

                print(new_invoice[0].id)
                ts.invoice_id = new_invoice[0].id
                ts.save()

        print(compute_ts)
        pool = Pool()
        EmployType = pool.get('pl_cust_plfolders.employeetype')

        corresp = {}
        for employ_id in EmployType.search([]):
            employ = EmployType(employ_id)
            corresp[employ.code] = employ.name


        for key in ['T1', 'T2', 'T3', 'T4', 'T5']:
            if not compute_ts.get(key):
                continue

            for k in ('8', '77'):
                if compute_ts[key]['tot_duration_tva{}'.format(k)]:

                    tax_to_use = config.taxe77

                    new_invoice_line = invoice_line_obj.create([{'invoice': new_invoice[0].id,
                                                                 'account': config.product_tva.account_category.account_revenue.id,
                                                                 #'avo_invoice_line_type': 'h',
                                                                 'unit': config.product_tva.default_uom.id,
                                                                 'quantity': '{:0.2f}'.format(compute_ts[key]['tot_duration_tva{}'.format(k)]/3600.0),
                                                                 'unit_price': '{:0.4f}'.format(compute_ts[key]['hour_price']),
                                                                 # 'unit_price': '{:0.2f}'.format(compute_ts[key]['tot_price_tva{}'.format(k)]),
                                                                 'product': config.product_tva,
                                                                 'note': ts_list_tva,
                                                                 'description': corresp[key],
                                                                 # 'taxes': [('add', conf.product_tva.customer_taxes_used)],
                                                                 'taxes': [('add', [tax_to_use, ])],
                                                                 }])
                    
        invoice_obj.update_taxes(new_invoice)
        new_invoice[0].save()
        self.new_inv = new_invoice[0]

        return "goto_new_inv"

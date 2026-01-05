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


__all__ = ['CreateInvoice', 'CreateInvoiceStart']

CHOICE_TVA = {'8': {'to': datetime(2017, 12, 31).date(),
                    'from': datetime(2011, 1, 1).date()},
              '77': {'to': datetime(2030, 12, 31).date(),
                     'from': datetime(2018, 1, 1).date()}}

def format_date2(date):
    y, m, d = str(date).split('-')
    return '{}.{}.{}'.format(d, m, y)

class CreateInvoiceStart(ModelView):
    "Create Invoice"
    __name__ = 'pl_cust_plfolders.invcreate_start'

    folder_id = fields.Many2One(
        'pl_cust_plfolders.folders', 'Folder', required=True, readonly=True)
    
    inv_id = fields.Many2One('account.invoice','Facture', required=False)
    
    with_vat = fields.Boolean('With VAT')

    folder_ts_tot = fields.Function(fields.Char('Folder TS tot'),
                                    'on_change_with_folder_ts_tot')

    timesheet_ids = fields.One2Many(
        'pl_cust_plfolders.foldersheet', None, 'Timesheet')

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


class CreateInvoice(Wizard):
    "Create Invoice"
    __name__ = "pl_cust_plfolders.invcreate"

    ids_list = []
    new_inv = None

    start = StateView('pl_cust_plfolders.invcreate_start',
                      'pl_cust_plfolders.wizard_createinv_view_form', [
                          Button('Cancel', 'end', 'tryton-cancel'),
                          Button('Lier à une facture', 'tstoinv',
                                 'tryton-ok', default=False),
                          Button('Facturation', 'generate_inv',
                                 'tryton-ok', default=True),
                      ])

    generate_inv = StateTransition()
    tstoinv = StateTransition()
    finalise_invoice = StateTransition()
    goto_new_inv = StateAction('account_invoice.act_invoice_out_form')

    def do_goto_new_inv(self, action):
        action['name'] = 'Nouvelle Facture'
        action['pyson_domain'] = [
            ('id', '=', self.new_inv.id),
        ]

        action['pyson_domain'] = PYSONEncoder().encode(action['pyson_domain'])

        return action, {}

    def transition_tstoinv(self):

        pool = Pool()
        Date_ = Pool().get('ir.date')

        invoice_obj = pool.get('account.invoice')
        invoice_line_obj = pool.get('account.invoice.line')
        ts_obj = pool.get('pl_cust_plfolders.foldersheet')

        ts_obj.write([ts for ts in self.start.timesheet_ids], {'invoice_id': self.start.inv_id.id})

        return 'end'

    def transition_generate_inv(self):

        pool = Pool()
        Date_ = Pool().get('ir.date')
        Configuration = pool.get('pl_cust_plfolders.wizardconf')
        config = Configuration(1)
            
        invoice_obj = pool.get('account.invoice')
        invoice_line_obj = pool.get('account.invoice.line')
    
        if self.start.folder_id.fact_to:
            party = self.start.folder_id.fact_to
        else:
            party = self.start.folder_id.party_id

        
        account_deb = config.account_deb_id 
        
        ts_to_do = self.start.timesheet_ids

        pay_term = config.payment_term or None
        if pay_term:
            date_due = pay_term.compute(amount=300,
                                        date=Date_.today(), currency=self.start.folder_id.currency)[0][0]
            print('************************* {}'.format(date_due))
        else:
            date_due = None

        new_invoice = invoice_obj.create([{'party': party.id,
                                           'invoice_date': Date_.today(),
                                           'invoice_address': party.addresses[0].id,
                                           'journal': config.journal_id,
                                           'date_due': date_due,
                                           'payment_term': pay_term,
                                           'account':account_deb,
                                           'description':self.start.folder_id.description,
                                           'folder_id':self.start.folder_id,
                                           'currency': self.start.folder_id.currency.id,
                                           'comment': self.start.folder_id.notes,
                                           }])

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
            
        # if self.start.folder_id.folder_charges and self.start.folder_id.folder_charges != 0.0:
        #     charges_notva = 0
        #     for key in ['AA', 'C', 'S', 'AS', 'ASA', 'CA']:
        #         if not compute_ts.get(key):
        #             continue

        #         charges_notva += round(compute_ts[key]['tot_duration_notva'] /
        #                                3600.0, 2) * compute_ts[key]['hour_price']

        #     if charges_notva:
        #         if self.start.invoice_foreign:
        #             new_invoice_line = invoice_line_obj.create([{'invoice': new_invoice[0].id,
        #                                                          'account': conf.charges_foreign.account_category.account_revenue.id,
        #                                                          'avo_invoice_line_type': 'c',
        #                                                          'unit': conf.charges_foreign.default_uom.id,
        #                                                          'quantity':1.0,
        #                                                          'unit_price': '{:0.4f}'.format(charges_notva * self.start.folder_id.folder_charges/100.0),
        #                                                          'product': conf.charges_foreign,
        #                                                          'description': self.start.folder_id.folder_charges > 0.0 and 'Frais divers' or 'Rabais',
        #                                                          'note': '{} % sur le total des activités'.format(self.start.folder_id.folder_charges),
        #                                                          }])
        #         else:
        #             new_invoice_line = invoice_line_obj.create([{'invoice': new_invoice[0].id,
        #                                                          'account': conf.charges_notva.account_category.account_revenue.id,
        #                                                          'avo_invoice_line_type': 'c',
        #                                                          'unit': conf.charges_notva.default_uom.id,
        #                                                          'quantity':1.0,
        #                                                          'unit_price': '{:0.4f}'.format(charges_notva * self.start.folder_id.folder_charges/100.0),
        #                                                          'product': conf.charges_notva,
        #                                                          'description': 'Frais divers',
        #                                                          'note': '{} % sur le total des activités'.format(self.start.folder_id.folder_charges),
        #                                                          }])


        # # for key in ['AA', 'C', 'S', 'AS', 'ASA', 'CA']:
        #     if not compute_depl.get(key):
        #         continue

        #     for k in ('8', '77'):

        #         tax_to_use = k == '8' and conf.taxe8 or conf.taxe77

        #         if compute_depl[key]['tot_nb_tva{}'.format(k)]:
        #             new_invoice_line = invoice_line_obj.create([{'invoice': new_invoice[0].id,
        #                                                          'account': conf.depl_tva.account_category.account_revenue.id,
        #                                                          'avo_invoice_line_type': 'd',
        #                                                          'unit': conf.depl_tva.default_uom.id,
        #                                                          'quantity':1,
        #                                                          'unit_price': '{:0.4f}'.format(compute_depl[key]['tot_nb_tva{}'.format(k)]),
        #                                                          'product': conf.depl_tva,
        #                                                          'description': 'Déplacements {}'.format(corresp[key]),
        #                                                          'note': '{} déplacements'.format(ts_depl_list_tva,),
        #                                                          # 'taxes': [('add', conf.depl_tva.customer_taxes_used)],
        #                                                          'taxes': [('add', [tax_to_use, ])],
        #                                                          }])
        #     if self.start.invoice_foreign:
        #         new_invoice_line = invoice_line_obj.create([{'invoice': new_invoice[0].id,
        #                                                      'account': conf.depl_foreign.account_category.account_revenue.id,
        #                                                      'avo_invoice_line_type': 'd',
        #                                                      'unit': conf.depl_foreign.default_uom.id,
        #                                                      'quantity':1,
        #                                                      'unit_price': '{:0.4f}'.format(compute_depl[key]['tot_nb_notva']),
        #                                                      'product': conf.depl_foreign,
        #                                                      'description': 'Déplacements {}'.format(corresp[key]),
        #                                                      'note': '{} déplacements'.format(ts_depl_list_tva,),
        #                                                      }])
        #     elif compute_depl[key]['tot_nb_notva']:
        #         new_invoice_line = invoice_line_obj.create([{'invoice': new_invoice[0].id,
        #                                                      'account': conf.depl_notva.account_category.account_revenue.id,
        #                                                      'avo_invoice_line_type': 'd',
        #                                                      'unit': conf.depl_notva.default_uom.id,
        #                                                      'quantity':1,
        #                                                      'unit_price': '{:0.4f}'.format(compute_depl[key]['tot_nb_notva']),
        #                                                      'product': conf.depl_tva,
        #                                                      'description': 'Déplacements {}'.format(corresp[key]),
        #                                                      'note': '{} déplacements'.format(ts_depl_list_tva,),
        #                                                      }])
                                                             
        # invoice_obj.update_taxes(new_invoice)
        # self.step2.invoice_id = new_invoice[0]
        # self.step2.folder_id = self.start.folder_id
        new_invoice[0].save()
        self.new_inv = new_invoice[0]

        return 'goto_new_inv'

        #return 'step2'

    # def transition_finalise_invoice(self):
    #     pool = Pool()
    #     Date_ = Pool().get('ir.date')

    #     invoice_obj = pool.get('account.invoice')
    #     invoice_line_obj = pool.get('account.invoice.line')
    #     conf_obj = pool.get('pl_cust_plfolders.wizardconf')
    #     reinv_obj = pool.get('pl_cust_plfolders.toreinvoice')

    #     conf, = conf_obj.search(
    #         [('resp_id', '=', self.step2.folder_id.resp_id.id)])

    #     account_deb = conf.account_deb_id
    #     journal = conf.journal_id

    #     tva = self.step2.folder_id.folder_tax_bool and self.step2.folder_id.resp_id.tva_from and self.step2.folder_id.resp_id.tva_from <= Date_.today()
    #     unit_line = tva and conf.prov_tva.default_uom.id or ''
    #     if self.step2.reduce_to:
    #         if self.step2.invoice_id.taxes and self.step2.tva_included:
    #             reduce_val = '{:0.4f}'.format(
    #                 ((self.step2.tot_inv - self.step2.reduce_to)/1.077)*-1)
    #         else:
    #             reduce_val = '{:0.4f}'.format((self.step2.tot_inv_ht -
    #                                            self.step2.reduce_to)*-1)

    #         new_invoice_line = invoice_line_obj.create([{'invoice': self.step2.invoice_id.id,
    #                                                      'account': tva and conf.product_tva.account_category.account_revenue.id or conf.product_notva.account_category.account_revenue.id,
    #                                                      'avo_invoice_line_type': 's',
                                                         
    #                                                      'quantity': 1.0,
    #                                                      'unit_price': reduce_val,
    #                                                      'taxes': tva and [('add', [conf.taxe77, ])] or [],
    #                                                      'description': float(reduce_val) < 0.0 and 'Rabais spécial' or 'Frais administratifs',
    #                                                      }])
    #     elif self.step2.forf: 
    #         invoice_line_obj.delete(self.step2.invoice_id.lines) 
    #         self.step2.invoice_id.save()
    #         self.step2.invoice_id.avo_invoice_type = 'fri'
    #         if self.step2.tva_included:
    #             unit_price = tva and '{:0.4f}'.format(
    #                 self.step2.forf/1.077) or '{:0.4f}'.format(self.step2.forf)
    #         else:
    #             unit_price = '{:0.4f}'.format(self.step2.forf)

    #         new_invoice_line = invoice_line_obj.create([{'invoice': self.step2.invoice_id.id,
    #                                                      'account': tva and conf.product_tva.account_category.account_revenue.id or conf.product_notva.account_category.account_revenue.id,
    #                                                      'avo_invoice_line_type': 'h',
                                                         
    #                                                      'quantity':1.0,
    #                                                      'unit_price': unit_price,
    #                                                      'taxes': tva and [('add', [conf.taxe77, ])] or [],
    #                                                      }])

    #     if self.step2.prov_to_use and self.step2.prov_to_use > 0:
    #         new_invoice_line = invoice_line_obj.create([{'invoice': self.step2.invoice_id.id,
    #                                                      'account': conf.prov_tva.account_category.account_revenue.id,
    #                                                      'avo_invoice_line_type': 'p',
    #                                                      'unit': conf.prov_tva.default_uom.id,
    #                                                      'quantity': 1.0,
    #                                                      'unit_price': '-{:0.4f}'.format(self.step2.prov_to_use),
    #                                                      'product': conf.prov_tva,
    #                                                      'description': 'Provision déduite',
    #                                                      }])

    #         self.step2.invoice_id.prov_amount = self.step2.prov_to_use

    #     # Compute re-invoice
    #     for reinv_line in self.step2.reinvoice_lines:
    #         taxes = reinv_line.tva and [('add', [conf.taxe77, ])] or []

    #         new_invoice_line = invoice_line_obj.create([{'invoice': self.step2.invoice_id.id,
    #                                                      'account': conf.reinvoice_tva.account_category.account_revenue.id,
    #                                                      'avo_invoice_line_type': 'r',
    #                                                      'unit': conf.reinvoice_tva.default_uom.id,
    #                                                      'quantity': 1.0,
    #                                                      'unit_price': '{:0.4f}'.format(reinv_line.amount),
    #                                                      'product': conf.reinvoice_tva,
    #                                                      'description': '{} {}'.format(format_date2(reinv_line.date), reinv_line.description),
    #                                                      'taxes': taxes,
    #                                                      }])
    #         reinv_line.invoice_id = self.step2.invoice_id.id
    #         reinv_line.save()
    #         #reinv_obj.write(
    #         #    [reinv_line], {'invoice_id': self.step2.invoice_id.id})

    #     self.step2.invoice_id.save()

    #     invoice_obj.update_taxes([self.step2.invoice_id, ])

    #     self.new_inv = self.step2.invoice_id

    #     return 'goto_new_inv'

    # def default_fact(self, fields):

    #     pool = Pool()
    #     invoice_obj = pool.get('account.invoice')

    #     return {
    #         'folder_id': self.fact.folder_id.id,
    #         'invoice_ids': [i.id for i in invoice_obj.search([('folder_id', '=', self.fact.folder_id.id), ('state', '=', 'posted')])],
    #         'timesheet_ids': [i.id for i in self.start.timesheet_ids]
    #     }

    # def default_step2(self, fields):

    #     tot_prov = Decimal(0)
    #     date_prov_txt = []
    #     # Compute provision
    #     for inv in self.step2.folder_id.invoice_ids[::-1]:
    #         if inv.avo_invoice_type in ('prov','o',) and not inv.invoice_id:
    #             for pl in inv.payment_lines:
    #                 tot_prov += pl.amount*-1
    #                 date_prov_txt.append('{} {:.2f}\n'.format(format_date2(pl.date), pl.amount*-1))
    #         elif inv.prov_amount and inv.prov_amount > 0:
    #             tot_prov -= Decimal(inv.prov_amount)
        
    #     reinv_lines = []
    #     for reinv_line in self.start.folder_id.reinvoice_lines:
    #         if not reinv_line.invoiced:
    #             reinv_lines.append(reinv_line.id)

    #     return {
    #         'folder_id': self.step2.folder_id.id,
    #         'invoice_id': self.step2.invoice_id.id,
    #         'tot_inv': self.step2.invoice_id.total_amount,
    #         'tot_inv_ht' : self.step2.invoice_id.untaxed_amount,
    #         'tot_prov': tot_prov,
    #         'prov_to_use': tot_prov > self.step2.invoice_id.total_amount and self.step2.invoice_id.total_amount or tot_prov,
    #         'date_prov_txt': ''.join(date_prov_txt),
    #         'reinvoice_lines': reinv_lines
    #     }

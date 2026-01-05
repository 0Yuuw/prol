from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.model import ModelView, fields
from trytond.pool import Pool
from trytond.transaction import Transaction
from datetime import datetime, date
from trytond.pyson import Eval
from decimal import Decimal
import codecs
import os
import csv

from trytond.model.exceptions import ValidationError

class InvoicesReportError(ValidationError):
    pass


__all__ = ['InvoicesReport', 'InvoicesReportStart', 'InvoicesReportRes']


class InvoicesReportStart(ModelView):
    "InvoicesReportStart"
    __name__ = 'pl_cust_account.invoicereport_start'

    inv_type = fields.Selection([('in', 'In Invoice'),('out','Out Invoice')],
                                 'Client/Fournisseur', required=True)

    check_date = fields.Date('Check Date', required=True)

class InvoicesReportRes(ModelView):
    "InvoicesReportRes"
    __name__ = 'pl_cust_account.invoicereport_result'

    name = fields.Char('File Name', readonly=True)
    file = fields.Binary('File', filename='name', readonly=True)


class InvoicesReport(Wizard):
    "InvoicesReport"
    __name__ = "pl_cust_account.invoicereport"

    start = StateView('pl_cust_account.invoicereport_start',
                      'pl_cust_account.invoicereport_start_view_form', [
                          Button('Cancel', 'end', 'tryton-cancel'),
                          Button('Generate Report', 'generate_report',
                                 'tryton-ok', default=True),
                      ])

    generate_report = StateTransition()

    result = StateView('pl_cust_account.invoicereport_result',
                       'pl_cust_account.invoicereport_result_view_form', [
                           Button('Close', 'end', 'tryton-close'),
                       ])

    def transition_generate_report(self):
        file_name = 'export_{}_{}.csv'.format(
            'CheckInvoices',
            datetime.now().strftime('%d%m%y')
        )
        delimiter = ';'
        f = codecs.open('/tmp/' + file_name,
                        'wb',
                        encoding='utf8')

        writer = csv.writer(f,
                            delimiter=delimiter)

        pool = Pool()
        INVOICE = pool.get('account.invoice')
        ACCOUNT = pool.get('account.account')
        AML = pool.get('account.move.line')

        fieldnames = ['Date',
                      'Numéro',
                      'Tiers',
                      'Hors Taxe',
                      'Taxe',
                      'Total',
                      'Tot Payé au {}'.format(self.start.check_date),
                      'Solde',
                      'Type',
                      'State',
                      'Currency'
                      ]

        writer.writerow(fieldnames)

        cond = [('type', '=', self.start.inv_type), ('invoice_date', '<=', self.start.check_date)]
        
        for inv in INVOICE.search(cond, order=[('invoice_date', 'ASC')]):

            tot_paid = Decimal(0)
            aml_do = []
            for pl in inv.payment_lines:
                if pl.date <= self.start.check_date :
                    aml_do.append(pl.id)
                    if self.start.inv_type == 'out':
                        tot_paid -= pl.debit - pl.credit
                    else:
                        tot_paid += pl.debit - pl.credit

            for rl in inv.reconciliation_lines:
                if rl.id not in aml_do and rl.date <= self.start.check_date : 
                    aml_do.append(rl.id)
                    if self.start.inv_type == 'out':
                        tot_paid -= rl.debit - rl.credit
                    else:
                        tot_paid += rl.debit - rl.credit

            tot_amount = 0 

            if inv.move : 
                for ml in inv.move.lines :
                    if ml.account == inv.account:
                        if self.start.inv_type == 'out':
                            tot_amount -= ml.credit-ml.debit
                        else:
                            tot_amount += ml.credit-ml.debit
            else :
                tot_amount = inv.total_amount

                    
            writer.writerow([
                inv.invoice_date,
                inv.number,
                inv.party.name, 
                inv.untaxed_amount,
                inv.tax_amount,
                tot_amount,
                tot_paid, 
                tot_amount - tot_paid,
                inv.type,
                inv.state,
                inv.currency.name,
            ])

        f.close()

        self.result.name = file_name

        return 'result'

    def default_result(self, fields):
        file_name = self.result.name
        cast = self.result.__class__.file.cast
        f = codecs.open('/tmp/' + file_name,
                        'rb',
                        encoding='utf8')

        data = f.read()

        f.close()

        os.unlink('/tmp/'+file_name)

        return {
            'name': file_name,
            'file': cast(data.encode('utf8')),
        }

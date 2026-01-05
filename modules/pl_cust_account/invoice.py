# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import (
    ModelView, ModelSQL, MatchMixin, DeactivableMixin, fields,
    sequence_ordered, Workflow)
from trytond.modules.account_invoice.exceptions import InvoiceNumberError
from trytond.modules.company.model import (employee_field, reset_employee, set_employee)
from trytond.pool import PoolMeta
from trytond.report import Report
from trytond.rpc import RPC
from trytond.pyson import Eval, If, Less
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.i18n import gettext
from trytond.exceptions import UserError
from itertools import groupby
from trytond.model.exceptions import AccessError

__all__ = ['PLInvoice', 'PLMove', 'PLMoveLine', 'PLPayInvoiceStart', 'PLInvoiceLine']


class PLInvoiceLine(ModelSQL, ModelView):
    __name__ = 'account.invoice.line'

    oeid = fields.Char('OEid') 

    @classmethod
    def __setup__(cls):
        super().__setup__()
        # Set account domain dynamically for kind
        cls.account.domain = [('closed', '!=', True),
                              ('company', '=', Eval('company', -1)),
                              ]

    def get_move_lines(self):
        line = super().get_move_lines()
        line[0].description = self.invoice.description
        return line

    # @classmethod
    # def check_modification(cls, mode, lines, values=None, external=False):
    #     super().check_modification(
    #         mode, lines, values=values, external=external)
    #     if mode == 'create':
    #         for line in lines:
    #             if line.invoice and line.invoice.state != 'draft':
    #                 raise AccessError(gettext(
    #                         'account_invoice.msg_invoice_line_create_draft',
    #                         invoice=line.invoice.rec_name))
    #     elif mode == 'delete':
    #         for line in lines:
    #             if line.invoice and not line.invoice.is_modifiable:
    #                 pass
    #                 # raise AccessError(gettext(
    #                 #         'account_invoice.msg_invoice_line_modify',
    #                 #         line=line.rec_name,
    #                 #         invoice=line.invoice.rec_name))
    #     elif mode == 'write' and values.keys() - cls._check_modify_exclude:
    #         for line in lines:
    #             if line.invoice and not line.invoice.is_modifiable:
    #                 raise AccessError(gettext(
    #                         'account_invoice.msg_invoice_line_modify',
    #                         line=line.rec_name,
    #                         invoice=line.invoice.rec_name))

class PLPayInvoiceStart(ModelView):
    __name__ = 'account.invoice.pay.start'

    @staticmethod
    def default_description():
        pool = Pool()
        invoice_obj = pool.get('account.invoice')
        if Transaction().context.get('active_model', '') == 'account.invoice':
            inv = invoice_obj(Transaction().context.get('active_id', ''))
            return inv.description
        return ''


class PLInvoice(ModelSQL, ModelView):
    __name__ = 'account.invoice'

    oeid = fields.Char('OEid')
    as_attachment = fields.Function(fields.Boolean('pj'), 'get_as_attachement')
    date_due = fields.Date('Date Due')
    date_pay = fields.Function(fields.Date('Date Pay'),
                               'get_date_pay')

    fourn_num = fields.Char('Fourn num')
    purchase_num = fields.Char('Purchase num')
    purchase_date = fields.Date('Purchase date')
    buyer = fields.Char('Buyer')
    employee_id = fields.Many2One('company.employee', 'Employee')

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('/tree', 'visual', If(Eval('state') == 'draft', 'warning', If(Eval('state') == 'paid', 'success', ''))),
        ]

    @classmethod
    def __setup__(cls):

        super().__setup__()

        cls._check_modify_exclude.add('purchase_num')
        cls._check_modify_exclude.add('fourn_num')
        cls._check_modify_exclude.add('purchase_date')
        cls._check_modify_exclude.add('buyer')
        cls._check_modify_exclude.add('move')
        cls._check_modify_exclude.add('invoice_id')
        cls._check_modify_exclude.add('number')

        cls._transitions |= set((('posted', 'draft'),))
        cls._buttons.update({
            'draft': {
                'invisible': (Eval('state').in_(['draft', 'paid'])),
            },
        })

    @fields.depends('party', 'type', 'accounting_date', 'invoice_date')
    def _get_account_payment_term(self):
        '''
        Return default account and payment term
        '''
        #self.account = None
        if self.party:
            with Transaction().set_context(
                    date=self.accounting_date or self.invoice_date):
                if self.type == 'out':
                    #self.account = self.party.account_receivable_used
                    if self.party.customer_payment_term:
                        self.payment_term = self.party.customer_payment_term
                elif self.type == 'in':
                    #self.account = self.party.account_payable_used
                    if self.party.supplier_payment_term:
                        self.payment_term = self.party.supplier_payment_term

    @classmethod
    def get_as_attachement(cls, invoices, name):
        pool = Pool()
        ATTACH = pool.get('ir.attachment')

        res = {i.id: False for i in invoices}
        for inv in invoices : 
            if ATTACH.search([('resource', '=', inv)]) :
                res[inv.id] = True
        return res

    @classmethod
    def search_rec_name(cls, name, clause):
        _, operator, value = clause
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('number', *clause[1:]),
            ('reference', *clause[1:]),
            ('party', *clause[1:]),
            ]
    
    @classmethod
    def check_modification(cls, mode, invoices, values=None, external=False):
        if mode == 'delete':
            for invoice in invoices:
                if not invoice.is_modifiable:
                    raise AccessError(gettext(
                            'account_invoice.msg_invoice_modify',
                            invoice=invoice.rec_name))
        elif mode == 'write' and 'state' in values.keys():
            for invoice in invoices:
                if not invoice.is_modifiable:
                    pass
                    # raise AccessError(gettext(
                    #         'account_invoice.msg_invoice_modify',
                    #         invoice=invoice.rec_name))
        elif mode == 'write' and values.keys() - cls._check_modify_exclude:
            for invoice in invoices:
                if not invoice.is_modifiable:
                    raise AccessError(gettext(
                            'account_invoice.msg_invoice_modify',
                            invoice=invoice.rec_name))
        
        if mode == 'delete':
            for invoice in invoices:
                if invoice.state not in {'cancelled', 'draft'}:
                    raise AccessError(gettext(
                            'account_invoice.msg_invoice_delete_cancel',
                            invoice=invoice.rec_name))
                if invoice.number:
                    raise AccessError(gettext(
                            'account_invoice.msg_invoice_delete_numbered',
                            invoice=invoice.rec_name))

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    @reset_employee('validated_by', 'posted_by')
    def draft(cls, invoices):
        Move = Pool().get('account.move')

        cls.write(invoices, {
                'tax_amount_cache': None,
                'untaxed_amount_cache': None,
                'total_amount_cache': None,
                })
        moves = []
        for invoice in invoices:
            if invoice.move:
                moves.append(invoice.move)
            if invoice.additional_moves:
                moves.extend(invoice.additional_moves)
            if len(invoice.alternative_payees) > 1:
                invoice.alternative_payees = []
        cls.save(invoices)
        if moves:
            Move.write(moves,{'state':'draft'})
            Move.delete(moves)

    # @classmethod
    # def draft(cls, invoices):
    #     Move = Pool().get('account.move')
    #     moves = []
    #     for invoice in invoices:
    #         if invoice.move:
    #             if invoice.move.period.state == 'close':
    #                 raise UserError(gettext(
    #                     'account_invoice_posted2draft.draft_closed_period',
    #                     invoice=invoice.rec_name,
    #                     period=invoice.move.period.rec_name,
    #                 ))
    #             moves.append(invoice.move)

    #     if moves:
    #         with Transaction().set_context(draft_invoices=True):
    #             Move.write(moves, {'state': 'draft'})
    #     cls.write(invoices, {
    #         'invoice_report_format': None,
    #         'invoice_report_cache': None,
            
    #     })
    #     super().draft(invoices)
    #     #cls.write(invoices, {
    #     #    'number': None,
    #     #})
    #     #return True

    @classmethod
    @Workflow.transition('cancelled')
    def cancel(cls, invoices):
        for invoice in invoices:
            if invoice.number:
                invoice.number = None
                invoice.save()
                # raise UserError(gettext(
                #    'account_invoice_posted2draft.cancel_invoice_with_number'))

        return super().cancel(invoices)

    @staticmethod
    def default_payment_term():
        Payment_term = Pool().get('account.invoice.payment_term')
        return Payment_term.search([]) and Payment_term.search([])[0].id or None

    @fields.depends('party', 'type')
    def on_change_with_payment_term(self):
        if hasattr(self, 'payment_term'):
            return self.payment_term and self.payment_term.id or None
        else:
            Payment_term = Pool().get('account.invoice.payment_term')
            return Payment_term.search([]) and Payment_term.search([])[0].id or None

    def print_invoice(self):
        '''
        Bypass default : Generate invoice report and store it in invoice_report field.
        '''
        return

    @fields.depends('move', 'party', 'payment_term', 'invoice_date', 'date_due', 'currency', 'state')
    def on_change_with_date_due(self, name=None):
        '''
        Function to compute date_due.
        '''

        if self.payment_term and self.invoice_date:
            print('Yalaaaa')
            print(self.payment_term.compute(amount=300,
                                            date=self.invoice_date, currency=self.currency)[0][0])
            return self.payment_term.compute(amount=300, date=self.invoice_date, currency=self.currency)[0][0]

        elif self.date_due:
            return self.date_due

        elif self.move:
            for l in self.move.lines:
                if l.maturity_date:
                    return l.maturity_date

        return None


    @classmethod
    def get_date_pay(cls, invoices, name):
        pool = Pool()
    
        res = {i.id: None for i in invoices}
        for inv in invoices : 
            if inv.reconciliation_lines : 
                res[inv.id] = inv.reconciliation_lines[-1].date or None
            else:
                res[inv.id] = inv.payment_lines and inv.payment_lines[-1].date or None
        return res

    #@fields.depends('payment_lines', 'state')
    #def on_change_with_date_pay(self, name=None):
    #    return self.payment_lines and self.payment_lines[-1].date or None

    @fields.depends('party', 'type', 'accounting_date', 'invoice_date')
    def on_change_with_account(self):
        if hasattr(self, 'account') and self.account:
            return self.account.id

        account = None
        if self.party:
            with Transaction().set_context(
                    date=self.accounting_date or self.invoice_date):
                if self.type == 'out':
                    account = self.party.account_receivable_used
                elif self.type == 'in':
                    account = self.party.account_payable_used

        return account.id if account else None

    @fields.depends('invoice_date')
    def on_change_with_accounting_date(self):
        accounting_date = None
        if self.invoice_date:
            accounting_date = self.invoice_date

        return accounting_date

    def get_move(self):
        move = super().get_move()
        move.description = self.description
        return move

    def pay_invoice(
            self, amount, payment_method, date, description=None,
            overpayment=0, party=None):
        '''
        Adds a payment of amount to an invoice using the journal, date and
        description.
        If overpayment is set, then only the amount minus the overpayment is
        used to pay off the invoice.
        Returns the payment lines.
        '''
        pool = Pool()
        Currency = pool.get('currency.currency')
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Period = pool.get('account.period')

        if party is None:
            party = self.party

        pay_line = Line(account=self.account)
        counterpart_line = Line()
        counterpart_line.description = description

        lines = [pay_line, counterpart_line]

        pay_amount = amount - overpayment
        if self.currency != self.company.currency:
            amount_second_currency = pay_amount
            second_currency = self.currency
            overpayment_second_currency = overpayment
            with Transaction().set_context(date=date):
                amount = Currency.compute(
                    self.currency, amount, self.company.currency)
                overpayment = Currency.compute(
                    self.currency, overpayment, self.company.currency)
                pay_amount = amount - overpayment
        else:
            amount_second_currency = None
            second_currency = None
            overpayment_second_currency = None
        if pay_amount >= 0:
            if self.type == 'out':
                pay_line.debit, pay_line.credit = 0, pay_amount
            else:
                pay_line.debit, pay_line.credit = pay_amount, 0
        else:
            if self.type == 'out':
                pay_line.debit, pay_line.credit = -pay_amount, 0
            else:
                pay_line.debit, pay_line.credit = 0, -pay_amount
        if amount_second_currency is not None:
            pay_line.amount_second_currency = (
                amount_second_currency.copy_sign(
                    pay_line.debit - pay_line.credit))
            pay_line.second_currency = second_currency

        if overpayment:
            overpayment_line = Line(account=self.account)
            lines.insert(1, overpayment_line)
            overpayment_line.debit = (
                abs(overpayment) if pay_line.debit else 0)
            overpayment_line.credit = (
                abs(overpayment) if pay_line.credit else 0)
            if overpayment_second_currency is not None:
                overpayment_line.amount_second_currency = (
                    overpayment_second_currency.copy_sign(
                        overpayment_line.debit - overpayment_line.credit))
                overpayment_line.second_currency = second_currency

        counterpart_line.debit = abs(amount) if pay_line.credit else 0
        counterpart_line.credit = abs(amount) if pay_line.debit else 0
        if counterpart_line.debit:
            payment_acccount = 'debit_account'
        else:
            payment_acccount = 'credit_account'
        counterpart_line.account = getattr(
            payment_method, payment_acccount).current(date=date)
        if amount_second_currency is not None:
            counterpart_line.amount_second_currency = (
                amount_second_currency.copy_sign(
                    counterpart_line.debit - counterpart_line.credit))
            counterpart_line.second_currency = second_currency

        for line in lines:
            if line.account.party_required:
                line.party = party

        period = Period.find(self.company, date=date)

        move = Move(
            journal=payment_method.journal, period=period, date=date,
            origin=self, description=description,
            company=self.company, lines=lines)
        move.save()
        Move.post([move])

        payment_lines = [l for l in move.lines if l.account == self.account]
        payment_line = [l for l in payment_lines
            if (l.debit, l.credit) == (pay_line.debit, pay_line.credit)][0]
        self.add_payment_lines({self: [payment_line]})
        return payment_lines

    @classmethod
    def set_number_to_remove(cls, invoices):
        '''
        Set number to the invoice
        '''
        pool = Pool()
        Date = pool.get('ir.date')
        Lang = pool.get('ir.lang')
        today = Date.today()

        def accounting_date(invoice):
            return invoice.accounting_date or invoice.invoice_date or today

        invoices = sorted(invoices, key=accounting_date)
        sequences = set()

        for invoice in invoices:
            # Posted and paid invoices are tested by check_modify so we can
            # not modify tax_identifier nor number
            if invoice.state in {'posted', 'paid'}:
                continue
            if not invoice.tax_identifier:
                invoice.tax_identifier = invoice.get_tax_identifier()
            # Generated invoice may not fill the party tax identifier
            if not invoice.party_tax_identifier:
                invoice.party_tax_identifier = invoice.party.tax_identifier

            if invoice.number:
                continue

            if not invoice.invoice_date and invoice.type == 'out':
                invoice.invoice_date = today
            invoice.number, invoice.sequence = invoice.get_next_number()
            if invoice.type == 'out' and invoice.sequence not in sequences:
                date = accounting_date(invoice)
                # Do not need to lock the table
                # because sequence.get_id is sequential
                after_invoices = cls.search([
                    ('sequence', '=', invoice.sequence),
                    ['OR',
                     ('accounting_date', '>', date),
                     [
                         ('accounting_date', '=', None),
                         ('invoice_date', '>', date),
                     ],
                     ],
                ], limit=1)
                if after_invoices:
                    after_invoice, = after_invoices
                    pass

                sequences.add(invoice.sequence)
        cls.save(invoices)

    # @classmethod
    # def delete(cls, invoices):
    #     cls.check_modify(invoices)
    #     # Cancel before delete
    #     cls.cancel(invoices)
    #     for invoice in invoices:
    #         if invoice.state != 'cancelled':
    #             raise AccessError(
    #                 gettext('account_invoice.msg_invoice_delete_cancel',
    #                     invoice=invoice.rec_name))
    #         #if invoice.state != 'draft' and invoice.number:
    #         #    raise AccessError(
    #         #        gettext('account_invoice.msg_invoice_delete_numbered',
    #         #            invoice=invoice.rec_name))
    #     super().delete(invoices)
        
class PLMove(metaclass=PoolMeta):
    __name__ = 'account.move'

    # @classmethod
    # def check_modification(cls, mode, moves, values=None, external=False):
       
    #     if (mode == 'write'
    #                 and values.keys() - cls._check_modify_exclude):
    #         for move in moves:
    #             if move.state == 'posted':
    #                 raise AccessError('Bon bha tu peux pas faire ça')
        
    #     elif mode == 'delete':
    #         for move in moves:
    #             if move.state == 'posted':
    #                 raise AccessError('A mettre en brouillon ')

    # @classmethod
    # def check_modify(cls, *args, **kwargs):
    #     if Transaction().context.get('draft_invoices', False):
    #         return
    #     return super().check_modify(*args, **kwargs)

class PLMoveLine(metaclass=PoolMeta):
    __name__ = 'account.move.line'

    # @classmethod
    # def check_modification(cls, mode, lines, values=None, external=False):
       
    #     pool = Pool()
    #     Move = pool.get('account.move')

    #     if (mode in {'create'}
    #             or (mode == 'write'
    #                 and values.keys() - cls._check_modify_exclude)):
    #         journal_period_done = set()
    #         for line in lines:
    #             if line.move.state == 'posted':
    #                 raise AccessError('Ici non plus')
    #             journal_period = (line.journal.id, line.period.id)
    #             if journal_period not in journal_period_done:
    #                 cls.check_journal_period_modify(
    #                     line.period, line.journal)
    #                 journal_period_done.add(journal_period)

    #     elif (mode in {'delete'}):
    #         journal_period_done = set()
    #         for line in lines:
    #             if line.move.state == 'posted':
    #                 raise AccessError('Tu es fou on peut pas')
    #             journal_period = (line.journal.id, line.period.id)
    #             if journal_period not in journal_period_done:
    #                 cls.check_journal_period_modify(
    #                     line.period, line.journal)
    #                 journal_period_done.add(journal_period)

    #     if (mode == 'delete'
    #             or (mode == 'write'
    #                 and values.keys() & cls._reconciliation_modify_disallow)):
    #         for line in lines:
    #             if line.reconciliation:
    #                 raise AccessError('bheu oin est ici')

    #     if mode in {'create', 'write'}:
    #         moves = Move.browse({l.move for l in lines})
    #         Move.validate_move(moves)
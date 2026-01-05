# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import decimal
from trytond.model import ModelView, fields
from trytond.pyson import If, Eval, Bool
from trytond.pool import PoolMeta, Pool
from itertools import groupby
from decimal import Decimal
from trytond.i18n import gettext
from trytond.transaction import Transaction
from trytond.model.exceptions import AccessError
from trytond.model.exceptions import ValidationError
from trytond.tools import (
    grouped_slice, is_full_text, lstrip_wildcard, reduce_ids)

from sql import Column, Literal, Null, Window
from sql.aggregate import Count, Max, Min, Sum
from sql.conditionals import Case, Coalesce

class MoveReconcile(ValidationError):
    pass

#from trytond.model.exceptions import ValidationError
from trytond.modules.account.exceptions import ReconciliationError

__all__ = ['Move', 'Line', 'Statement', 'Invoice',
           'InvoiceLine', 'InvoicePaymentLine', 'Reconciliation', 'Currency', 'Account']

class InvoicePaymentLine(metaclass=PoolMeta):
    'Invoice - Payment Line'
    __name__ = 'account.invoice-account.move.line'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.line.domain = [
            ('account', '=', Eval('invoice_account')),
        ]


class Invoice(metaclass=PoolMeta):
    'Invoice'
    __name__ = 'account.invoice'

    oeid = fields.Char('OEid')

    @classmethod
    def __setup__(cls):
        super().__setup__()

    def _get_move_line(self, date, amount):
        '''
        Return move line
        '''
        pool = Pool()
        Currency = pool.get('currency.currency')
        MoveLine = pool.get('account.move.line')
        line = MoveLine()
        if self.currency != self.company.currency:
            with Transaction().set_context(date=self.currency_date):
                line.amount_second_currency = Currency.compute(
                    self.company.currency, amount, self.currency)
            line.second_currency = self.currency
        else:
            line.amount_second_currency = None
            line.second_currency = None
        if amount <= 0:
            line.debit, line.credit = -amount, 0
        else:
            line.debit, line.credit = 0, amount
        if line.amount_second_currency:
            line.amount_second_currency = (
                line.amount_second_currency.copy_sign(
                    line.debit - line.credit))
        line.account = self.account
        #if self.account.party_required:
        line.party = self.party
        line.maturity_date = date
        line.description = self.description
        return line

class InvoiceLine(metaclass=PoolMeta):
    'Invoice'
    __name__ = 'account.invoice.line'

    oeid = fields.Char('OEid')

    @classmethod
    def __setup__(cls):
        super().__setup__()

    def get_move_lines(self):
        '''
        Return a list of move lines instances for invoice line
        '''
        
        pool = Pool()
        Currency = pool.get('currency.currency')
        MoveLine = pool.get('account.move.line')
        if self.type != 'line':
            return []
        line = MoveLine()
        if self.invoice.currency != self.invoice.company.currency:
            with Transaction().set_context(date=self.invoice.currency_date):
                amount = Currency.compute(self.invoice.currency,
                                          self.amount, self.invoice.company.currency)
            line.amount_second_currency = self.amount
            line.second_currency = self.invoice.currency
        else:
            amount = self.amount
            line.amount_second_currency = None
            line.second_currency = None
        if amount >= 0:
            if self.invoice.type == 'out':
                line.debit, line.credit = 0, amount
            else:
                line.debit, line.credit = amount, 0
        else:
            if self.invoice.type == 'out':
                line.debit, line.credit = -amount, 0
            else:
                line.debit, line.credit = 0, -amount
        if line.amount_second_currency:
            line.amount_second_currency = (
                line.amount_second_currency.copy_sign(
                    line.debit - line.credit))
        line.account = self.account
        # if self.account.party_required:
        line.party = self.invoice.party
        line.origin = self
        line.tax_lines = self._compute_taxes()
        return [line]


class Line(metaclass=PoolMeta):
    'Account Move Line'
    __name__ = 'account.move.line'

    oeid = fields.Char('OEid')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.party.states = {'required': Eval('party_required', False)}

    @classmethod
    def check_account(cls, lines, field_names=None):
        if field_names and not (field_names & {'account', 'party'}):
            return
        for line in lines:
            if not line.account.type or line.account.closed:
                raise AccessError(
                    gettext('account.msg_line_closed_account',
                        account=line.account.rec_name))
            # if bool(line.party) != bool(line.account.party_required):
            #     error = 'party_set' if line.party else 'party_required'
            #     raise AccessError(
            #         gettext('account.msg_line_%s' % error,
            #             account=line.account.rec_name,
            #             line=line.rec_name))

class Move(metaclass=PoolMeta):
    __name__ = 'account.move'

    oenumber = fields.Char('OENumber')
    oeid = fields.Char('OEid')

    @classmethod
    def __setup__(cls):
        super(Move, cls).__setup__()

        if not 'state' in cls._check_modify_exclude:
            cls._check_modify_exclude.add('state')
        cls._buttons.update({
            'draft': {
                'invisible': Eval('state') == 'draft',
            },
        })

    @classmethod
    @ModelView.button
    def draft(cls, moves):
        for move in moves :
            for line in move.lines:
                if line.reconciliation: 
                    raise MoveReconcile('La pièce est réconcilée')
        cls.write(moves, {
            'state': 'draft',
        })

class Reconciliation(metaclass=PoolMeta):
    'Account Move Reconciliation Lines'
    __name__ = 'account.move.reconciliation'

    oeid = fields.Char('OEid')
    
    @classmethod
    def check_lines(cls, reconciliations):
        Lang = Pool().get('ir.lang')
        for reconciliation in reconciliations:
            debit = Decimal('0.0')
            credit = Decimal('0.0')
            account = None
            if reconciliation.lines:
                party = reconciliation.lines[0].party
            for line in reconciliation.lines:
                if line.state != 'valid':
                    raise ReconciliationError(
                        gettext('account.msg_reconciliation_line_not_valid',
                                line=line.rec_name))
                debit += line.debit
                credit += line.credit
                if not account:
                    account = line.account
                elif account.id != line.account.id:
                    raise ReconciliationError(
                        gettext('account'
                                '.msg_reconciliation_different_accounts',
                                line=line.rec_name,
                                account1=line.account.rec_name,
                                account2=account.rec_name))
                if not account.reconcile:
                    raise ReconciliationError(
                        gettext('account'
                                '.msg_reconciliation_account_not_reconcile',
                                line=line.rec_name,
                                account=line.account.rec_name))
                # if line.party != party:
                #     raise ReconciliationError(
                #         gettext('account'
                #                 '.msg_reconciliation_different_parties',
                #                 line=line.rec_name,
                #                 party1=line.party and line.party.rec_name or '',
                #                 party2=party and party.rec_name or ''))
            if account and not account.company.currency.is_zero(debit - credit):
                lang = Lang.get()
                debit = lang.currency(debit, account.company.currency)
                credit = lang.currency(credit, account.company.currency)
                raise ReconciliationError(
                    gettext('account.msg_reconciliation_unbalanced',
                            debit=debit,
                            credit=credit))


class Statement(metaclass=PoolMeta):
    'Account Statement'
    __name__ = 'account.statement'

    @classmethod
    def create_move(cls, statements):
        '''Create move for the statements and try to reconcile the lines.
        Returns the list of move, statement and lines
        '''
        pool = Pool()
        Line = pool.get('account.statement.line')
        Move = pool.get('account.move')
        MoveLine = pool.get('account.move.line')

        moves = []
        for statement in statements:
            for key, lines in groupby(
                    statement.lines, key=statement._group_key):
                lines = list(lines)
                key = dict(key)
                move = statement._get_move(key)
                moves.append((move, statement, lines))

        Move.save([m for m, _, _ in moves])

        to_write = []
        for move, _, lines in moves:
            to_write.append(lines)
            to_write.append({
                'move': move.id,
            })
        if to_write:
            Line.write(*to_write)

        move_lines = []
        for move, statement, lines in moves:
            amount = 0
            amount_second_currency = 0
            for line in lines:
                move_line = line.get_move_line()
                if not move_line:
                    continue
                move_line.move = move
                move_line.party = line.party
                amount += move_line.debit - move_line.credit
                if move_line.amount_second_currency:
                    amount_second_currency += move_line.amount_second_currency
                move_lines.append((move_line, line))

            move_line = statement._get_move_line(
                amount, amount_second_currency, lines)
            move_line.move = move
            move_lines.append((move_line, None))

        MoveLine.save([l for l, _ in move_lines])

        Line.reconcile(move_lines)
        return moves

    def _get_move_line(self, amount, amount_second_currency, lines):
        'Return counterpart Move Line for the amount'
        pool = Pool()
        MoveLine = pool.get('account.move.line')

        if self.journal.currency != self.company.currency:
            second_currency = self.journal.currency
            amount_second_currency *= -1
        else:
            second_currency = None
            amount_second_currency = None

        descriptions = {l.description for l in lines}
        if len(descriptions) == 1:
            description, = descriptions
        else:
            description = ''

        party = None
        for l in lines:
            if l.party:
                party = l.party
                break

        return MoveLine(
            debit=abs(amount) if amount < 0 else 0,
            credit=abs(amount) if amount > 0 else 0,
            account=self.journal.account,
            second_currency=second_currency,
            party=party,
            amount_second_currency=amount_second_currency,
            description=description,
        )


ROUNDING_OPPOSITES = {
    decimal.ROUND_HALF_EVEN: decimal.ROUND_HALF_EVEN,
    decimal.ROUND_HALF_UP: decimal.ROUND_HALF_DOWN,
    decimal.ROUND_HALF_DOWN: decimal.ROUND_HALF_UP,
    decimal.ROUND_UP: decimal.ROUND_DOWN,
    decimal.ROUND_DOWN: decimal.ROUND_UP,
    decimal.ROUND_CEILING: decimal.ROUND_FLOOR,
    decimal.ROUND_FLOOR: decimal.ROUND_CEILING,
    }

class Currency(metaclass=PoolMeta):
    'Currency'
    __name__ = 'currency.currency'

    def round(self, amount, rounding=decimal.ROUND_HALF_EVEN, opposite=False):
        'Round the amount depending of the currency'

        print('*****************************')
        print('amount : {} / rounding: {} / opposite: {}'.format(amount,rounding,opposite))
        print('*****************************')

        if opposite:
            rounding = ROUNDING_OPPOSITES[rounding]
        return self._round(amount, self.rounding, rounding)


class Account(metaclass=PoolMeta):
    'Account'
    __name__ = 'account.account'

    @classmethod
    def get_balance(cls, accounts, name):

        print('*****************************')
        print('On est ici on va essayer de trouver')
        print('*****************************')

        pool = Pool()
        MoveLine = pool.get('account.move.line')
        FiscalYear = pool.get('account.fiscalyear')
        cursor = Transaction().connection.cursor()

        table_a = cls.__table__()
        table_c = cls.__table__()
        line = MoveLine.__table__()
        ids = [a.id for a in accounts]
        balances = dict((i, Decimal(0)) for i in ids)
        line_query, fiscalyear_ids = MoveLine.query_get(line)
        for sub_ids in grouped_slice(ids):
            red_sql = reduce_ids(table_a.id, sub_ids)
            cursor.execute(*table_a.join(table_c,
                    condition=(table_c.left >= table_a.left)
                    & (table_c.right <= table_a.right)
                    ).join(line, condition=line.account == table_c.id
                    ).select(
                    table_a.id,
                    Sum(Coalesce(line.debit, 0) - Coalesce(line.credit, 0)),
                    where=red_sql & line_query,
                    group_by=table_a.id))
            balances.update(dict(cursor))

        for account in accounts:
            # SQLite uses float for SUM
            if not isinstance(balances[account.id], Decimal):
                balances[account.id] = Decimal(str(balances[account.id]))
            balances[account.id] = account.currency.round(balances[account.id])

        fiscalyears = FiscalYear.browse(fiscalyear_ids)

        def func(accounts, names):
            return {names[0]: cls.get_balance(accounts, names[0])}
        return cls._cumulate(fiscalyears, accounts, [name], {name: balances},
            func)[name]

    @classmethod
    def _cumulate(
            cls, fiscalyears, accounts, names, values, func,
            deferral='account.account.deferral'):
        """
        Cumulate previous fiscalyear values into values
        func is the method to compute values
        """

        print('*****************************')
        print('On est ici on passe dans le cumulate')
        print('*****************************')

        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')

        youngest_fiscalyear = None
        for fiscalyear in fiscalyears:
            if (not youngest_fiscalyear
                    or (youngest_fiscalyear.start_date
                        > fiscalyear.start_date)):
                youngest_fiscalyear = fiscalyear

        fiscalyear = None
        if youngest_fiscalyear:
            fiscalyears = FiscalYear.search([
                    ('end_date', '<', youngest_fiscalyear.start_date),
                    ('company', '=', youngest_fiscalyear.company),
                    ], order=[('end_date', 'DESC')], limit=1)
            if fiscalyears:
                fiscalyear, = fiscalyears

        if not fiscalyear:
            return values

        if fiscalyear.state == 'close' and deferral:
            Deferral = pool.get(deferral)
            id2deferral = {}
            ids = [a.id for a in accounts]
            for sub_ids in grouped_slice(ids):
                deferrals = Deferral.search([
                    ('fiscalyear', '=', fiscalyear.id),
                    ('account', 'in', list(sub_ids)),
                    ])
                for deferral in deferrals:
                    id2deferral[deferral.account.id] = deferral

            for account in accounts:
                if account.id in id2deferral:
                    deferral = id2deferral[account.id]
                    for name in names:
                        values[name][account.id] += getattr(deferral, name)
        else:
            with Transaction().set_context(fiscalyear=fiscalyear.id,
                    date=None, periods=None, from_date=None, to_date=None):
                previous_result = func(accounts, names)
            for name in names:
                vals = values[name]
                for account in accounts:
                    vals[account.id] += previous_result[name][account.id]

        return values
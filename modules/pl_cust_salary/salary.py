# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.wizard import Wizard, StateView, StateTransition, StateAction, Button
from trytond.model import ModelSingleton, ModelSQL, DeactivableMixin, ModelView, fields, sequence_ordered
from trytond.pyson import Eval, Bool, If, PYSONEncoder
from datetime import datetime, timedelta
from trytond.pool import PoolMeta, Pool
from trytond.report import Report
from trytond.rpc import RPC
from trytond.transaction import Transaction
from decimal import *

from trytond.model.exceptions import ValidationError


class UnableToDelete(ValidationError):
    pass


__all__ = ['SalEmployee', 'SalaryCat',
           'SalaryConfSocialCharge', 'SocialCharges', 'CreateSalary', 'SalaryContract',
           'SalarySalaryLine', 'SalarySalary']


class SalEmployee(ModelSQL, ModelView):
    'Salary employee'
    __name__ = 'company.employee'

    avs_num = fields.Char('AVS num', required=False)
    bank_name = fields.Char('Bank name', required=False)
    iban = fields.Char('IBAN', required=False)


class SalaryCat(sequence_ordered(), ModelSQL, ModelView):
    'SalaryCat'
    __name__ = 'pl_cust_salary.cat'

    name = fields.Char('Name', required=True, translate=False)
    code = fields.Char('Code', size=3, translate=False)

    account_charge = fields.Many2One(
        'account.account', 'Account charge', required=True)
    account_cc = fields.Many2One(
        'account.account', 'Account c/c', required=True)

    socialcharge = fields.One2Many(
        'pl_cust_salary.confsocialcharge', 'cat', 'SocialCharges')


class SalaryConfSocialCharge(sequence_ordered(), ModelSQL, ModelView, DeactivableMixin):
    'SalaryConfSocialCharge'
    __name__ = 'pl_cust_salary.confsocialcharge'

    name = fields.Char('Name', required=True, translate=False)
    cat = fields.Many2One(
        'pl_cust_salary.cat', 'Cat', required=True)

    tx_boss = fields.Float('Tx Boss')
    tx_employee = fields.Float('Tx Employee')

    max_gross_salary = fields.Integer('Max Gross Salary')

    @staticmethod
    def default_max_gross_salary():
        return 0

    @staticmethod
    def default_tx_boss():
        return 0.0

    @staticmethod
    def default_tx_employee():
        return 0.0


class SocialCharges(sequence_ordered(), ModelSQL, ModelView):
    'SocialCharges'
    __name__ = 'pl_cust_salary.socialcharge'

    cat = fields.Many2One('pl_cust_salary.cat', 'Cat', required=True)
    charge = fields.Many2One(
        'pl_cust_salary.confsocialcharge', 'Charge', required=True)

    contract = fields.Many2One(
        'pl_cust_salary.contract', 'Contract', required=True, ondelete='CASCADE')

    @fields.depends('charge')
    def on_change_charge(self):
        if not self.charge:
            self.cat = None
        else:
            self.cat = self.charge.cat


class CreateSalary(Wizard):
    "Create Salary"
    __name__ = "pl_cust_salary.createsalary"

    new_sal = None

    start = StateTransition()
    goto_new_sal = StateAction('pl_cust_salary.act_salarysalary_form')

    def do_goto_new_sal(self, action):
        action['name'] = 'Fiche de salaire'
        action['pyson_domain'] = [
            ('id', '=', self.new_sal.id),
        ]

        action['pyson_domain'] = PYSONEncoder().encode(action['pyson_domain'])

        return action, {}

    def transition_start(self):

        pool = Pool()
        Salary = pool.get('pl_cust_salary.salary')
        Contract = pool.get('pl_cust_salary.contract')
        Date_ = Pool().get('ir.date')

        contract_id = Transaction().context.get('active_id', '')
        contr = Contract(contract_id)

        company = Transaction().context.get('company')

        sal = Salary(name='FS',
                     contract=contr,
                     date=Date_.today(),
                     gross_salary_contract=contr.gross_salary,
                     gross_salary=contr.gross_salary,
                     resp_id=contr.resp_id,
                     car_charge=contr.car_charge,
                     alloc_charge=contr.alloc_charge,
                     is_charge=contr.is_charge,
                     lpp_charge=contr.lpp_charge,
                     car_charge_txt=contr.car_charge_txt,
                     alloc_charge_txt=contr.alloc_charge_txt,
                     is_charge_txt=contr.is_charge_txt,
                     lpp_charge_txt=contr.lpp_charge_txt,
                     prim_txt=contr.prim_txt,
                     prim=contr.prim,
                     prim2_txt=contr.prim2_txt,
                     prim2=contr.prim2,
                     prim3_txt=contr.prim3_txt,
                     prim3=contr.prim3,
                     prim4_txt_without_tax=contr.prim4_txt_without_tax,
                     prim4_without_tax=contr.prim4_without_tax
                     )

        sal.save()

        self.new_sal = sal

        return 'goto_new_sal'


class SalaryContract(DeactivableMixin, ModelSQL, ModelView):
    'SalaryContract'
    __name__ = 'pl_cust_salary.contract'

    name = fields.Char('Name', required=True)
    function = fields.Char('Function', required=False)
    socialcharge_ids = fields.One2Many(
        'pl_cust_salary.socialcharge', 'contract', 'SocialCharges')

    salary_ids = fields.One2Many('pl_cust_salary.salary', 'contract', 'Salary')

    date_start = fields.Date('Date start', help="Date start")
    date_end = fields.Date('Date end', help="Date end")
    resp_id = fields.Many2One('company.employee', 'Employee', required=True)

    notes = fields.Text('Comment')

    gross_salary = fields.Float('Gross Salary')
    tx_activity = fields.Char('Tx Activity(%)')

    car_charge_txt = fields.Char('Car Charges txt')
    car_charge = fields.Float('Car Charges')

    alloc_charge_txt = fields.Char('Alloc txt')
    alloc_charge = fields.Float('Alloc')

    is_charge_txt = fields.Char('IS Charges txt')
    is_charge = fields.Float('IS Charges(%)')
    is_charge_cat = fields.Many2One(
        'pl_cust_salary.cat', 'IS Cat', required=True)

    lpp_charge_txt = fields.Char('LPP txt')
    lpp_charge = fields.Float('LPP')
    lpp_charge_cat = fields.Many2One(
        'pl_cust_salary.cat', 'LPP Cat', required=True)

    sal_cat = fields.Many2One('pl_cust_salary.cat', 'SAL Cat', required=True)

    prim_txt = fields.Char('Prim txt', states={'readonly': Bool(
        Eval('compta')), }, depends=['compta'])
    prim = fields.Float('Prim', states={'readonly': Bool(
        Eval('compta')), }, depends=['compta'])

    prim2_txt = fields.Char('Prim2 txt', states={'readonly': Bool(
        Eval('compta')), }, depends=['compta'])
    prim2 = fields.Float('Prim2', states={'readonly': Bool(
        Eval('compta')), }, depends=['compta'])

    prim3_txt = fields.Char('Prim3 txt', states={'readonly': Bool(
        Eval('compta')), }, depends=['compta'])
    prim3 = fields.Float('Prim3', states={'readonly': Bool(
        Eval('compta')), }, depends=['compta'])

    prim4_txt_without_tax = fields.Char('Prim4 txt without tax', states={'readonly': Bool(
        Eval('compta')), }, depends=['compta'])
    prim4_without_tax  = fields.Float('Prim4 without tax', states={'readonly': Bool(
        Eval('compta')), }, depends=['compta'])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
            'create_salary': {
            },
        })

    @classmethod
    @ModelView.button_action('pl_cust_salary.act_wizard_createsal')
    def create_salary(cls, booking):
        pass

    @staticmethod
    def default_lpp_charge_cat():
        CAT = Pool().get('pl_cust_salary.cat')
        acc = CAT.search([('name', '=', 'LPP')])
        return acc and acc[0].id or None

    @staticmethod
    def default_is_charge_cat():
        CAT = Pool().get('pl_cust_salary.cat')
        acc = CAT.search([('name', '=', 'IS')])
        return acc and acc[0].id or None

    @staticmethod
    def default_sal_cat():
        CAT = Pool().get('pl_cust_salary.cat')
        acc = CAT.search([('name', '=', 'SAL')])
        return acc and acc[0].id or None

    @staticmethod
    def default_gross_salary():
        return 0.0

    @staticmethod
    def default_car_charge():
        return 0.0

    @staticmethod
    def default_alloc_charge():
        return 0.0

    @staticmethod
    def default_is_charge():
        return 0.0

    @staticmethod
    def default_lpp_charge():
        return 0.0

    @staticmethod
    def default_prim():
        return 0.0

    @staticmethod
    def default_prim2():
        return 0.0

    @staticmethod
    def default_prim3():
        return 0.0
    
    @staticmethod
    def default_prim4_without_tax():
        return 0.0

    # @staticmethod
    # def default_socialcharge_ids():
    #     CONFSOCCHAR = Pool().get('pl_cust_salary.confsocialcharge')
    #     SOCCHAR = Pool().get('pl_cust_salary.socialcharge')

    #     res = []

    #     for sc in CONFSOCCHAR.search([]):
    #         tmp = SOCCHAR.create([{'charge': sc.id,
    #                                    'cat': sc.cat.id
    #                                    }])
    #         res.append(tmp[0].id
    #                    )
    #     return res

    @classmethod
    def create(cls, vlist):
        res = super().create(vlist)
        CONFSOCCHAR = Pool().get('pl_cust_salary.confsocialcharge')
        SOCCHAR = Pool().get('pl_cust_salary.socialcharge')
        for sc in CONFSOCCHAR.search([]):
            tmp = SOCCHAR.create([{'charge': sc.id,
                                   'cat': sc.cat.id,
                                   'contract': res[0].id
                                   }])

        return res


class SalarySalaryLine(sequence_ordered(), ModelSQL, ModelView):
    'SalarySalaryLine'
    __name__ = 'pl_cust_salary.salaryline'

    salary = fields.Many2One(
        'pl_cust_salary.salary', 'Salary', required=True, ondelete='CASCADE')

    name = fields.Char('Name', required=False)
    cat = fields.Char('Cat', readonly=True, required=False)
    #charge = fields.Many2One('pl_cust_salary.confsocialcharge', 'Charge', required=True)
    account_charge = fields.Many2One(
        'account.account', 'Account charge', readonly=True, required=True)
    account_cc = fields.Many2One(
        'account.account', 'Account c/c', readonly=True, required=True)
    tx_boss = fields.Float('Tx Boss', readonly=True)
    tx_employee = fields.Float('Tx Employee', readonly=True)
    max_gross_salary = fields.Integer('Max Gross Salary', readonly=True)

    amount_employee = fields.Function(fields.Float(
        'Amount Employ'), 'on_change_with_amount_employee')
    amount_boss = fields.Function(fields.Float(
        'Amount Boss'), 'on_change_with_amount_boss')

    @fields.depends('salary', 'tx_employee')
    def on_change_with_amount_employee(self, name=None):
        if self.salary and self.salary.gross_salary:
            tot_salary = self.salary.gross_salary + self.salary.prim + self.salary.prim2 + self.salary.prim3 + self.salary.car_charge
            if self.max_gross_salary and tot_salary > self.max_gross_salary:
                tot_salary = self.max_gross_salary
            return self.tx_employee > 0 and round((tot_salary * (self.tx_employee/100.0))/0.05)*0.05 or 0
        else:
            return 0

    @fields.depends('salary', 'tx_boss')
    def on_change_with_amount_boss(self, name=None):
        if self.salary and self.salary.gross_salary:
            tot_salary = self.salary.gross_salary + self.salary.prim + self.salary.prim2 + self.salary.prim3 + self.salary.car_charge
            if self.max_gross_salary and tot_salary > self.max_gross_salary:
                tot_salary = self.max_gross_salary
            return self.tx_boss > 0 and round((tot_salary * (self.tx_boss/100.0))/0.05)*0.05 or 0
        else:
            return 0

class SalarySalary(ModelSQL, ModelView):
    'SalarySalary'
    __name__ = 'pl_cust_salary.salary'

    name = fields.Char('Name', states={'readonly': Bool(
        Eval('compta')), }, required=True, depends=['compta'])
    period = fields.Char('Period',states={'readonly': Bool(
        Eval('compta')), }, depends=['compta'])

    line_ids = fields.One2Many(
        'pl_cust_salary.salaryline', 'salary', 'Salary Lines',states={'readonly': Bool(
        Eval('compta')), }, depends=['compta'])

    contract = fields.Many2One(
        'pl_cust_salary.contract', 'Contract', states={'readonly': Bool(
            Eval('contract')), }, depends=['contract'], required=True)

    date = fields.Date('Date', help="Date", states={'readonly': Bool(
        Eval('compta')), }, required=True, depends=['compta'])

    resp_id = fields.Many2One('company.employee', 'Employee', states={'readonly': Bool(
        Eval('compta')), }, depends=['compta'], required=True)

    notes = fields.Text('Comment', states={'readonly': Bool(
        Eval('compta')), }, depends=['compta'])

    gross_salary_contract = fields.Float('Gross Salary Contract', states={'readonly': Bool(
        Eval('compta')), }, depends=['compta'])

    gross_salary = fields.Float('Gross Salary',states={'readonly': Bool(
        Eval('compta')), }, depends=['compta'])

    net_salary = fields.Function(fields.Float(
        'Net Salary'), 'on_change_with_net_salary')

    prim_txt = fields.Char('Prim txt', states={'readonly': Bool(
        Eval('compta')), }, depends=['compta'])
    prim = fields.Float('Prim', states={'readonly': Bool(
        Eval('compta')), }, depends=['compta'])

    prim2_txt = fields.Char('Prim2 txt', states={'readonly': Bool(
        Eval('compta')), }, depends=['compta'])
    prim2 = fields.Float('Prim2', states={'readonly': Bool(
        Eval('compta')), }, depends=['compta'])

    prim3_txt = fields.Char('Prim3 txt', states={'readonly': Bool(
        Eval('compta')), }, depends=['compta'])
    prim3 = fields.Float('Prim3', states={'readonly': Bool(
        Eval('compta')), }, depends=['compta'])

    prim4_txt_without_tax = fields.Char('Prim4 txt without tax', states={'readonly': Bool(
        Eval('compta')), }, depends=['compta'])
    prim4_without_tax  = fields.Float('Prim4 without tax', states={'readonly': Bool(
        Eval('compta')), }, depends=['compta'])    

    car_charge_txt = fields.Char('Car Charges txt', states={'readonly': Bool(
        Eval('compta')), }, depends=['compta'])
    car_charge = fields.Float('Car Charges', states={'readonly': Bool(
        Eval('compta')), }, depends=['compta'])

    alloc_charge_txt = fields.Char('Alloc txt', states={'readonly': Bool(
        Eval('compta')), }, depends=['compta'])
    alloc_charge = fields.Float('Alloc', states={'readonly': Bool(
        Eval('compta')), }, depends=['compta'])

    is_charge_txt = fields.Char('IS Charges txt', states={'readonly': Bool(
        Eval('compta')), }, depends=['compta'])
    is_charge = fields.Float('IS Charges(%)', states={'readonly': Bool(
        Eval('compta')), }, depends=['compta'])
    is_charge_amount = fields.Function(fields.Float(
        'IS Amount'), 'on_change_with_is_charge_amount')

    lpp_charge_txt = fields.Char('LPP txt', states={'readonly': Bool(
        Eval('compta')), }, depends=['compta'])
    lpp_charge = fields.Float('LPP', states={'readonly': Bool(
        Eval('compta')), }, depends=['compta'])

    compta = fields.Many2One('account.move', 'Move', readonly=False)

    compta_state = fields.Function(fields.Char(
        'Compta state'), 'on_change_with_compta_state')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
            'valid_and_compta': {
                'invisible': Bool(Eval('compta')),
                'depends': ['compta'],
            },
        })

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('/tree', 'visual', If((Eval('compta_state', '') == 'ok'), 'success', '')),
        ]

    @classmethod
    def valid_and_compta(cls, salarys):
        pool = Pool()
        Journal = pool.get('account.journal')
        Currency = pool.get('currency.currency')
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Period = pool.get('account.period')

        company = Transaction().context.get('company')

        journal = Journal.search([('code', '=', 'CHA')])[0]
        sal_line_brut = None
        lpp_line_cred = None
        is_line_cred = None
        sal_line_net = None
        lpp_line_deb = None

        for salary in salarys:
            period = Period.find(company, date=salary.date)
            sal_line_brut = Line(
                party=salary.resp_id.party,
                account=salary.contract.sal_cat.account_charge,
                debit='{:.2f}'.format(round((salary.gross_salary + salary.prim + salary.prim2 + salary.prim3 + salary.prim4_without_tax), 2)))

            sal_line_net = Line(
                party=salary.resp_id.party,
                account=salary.contract.sal_cat.account_cc,
                credit='{:.2f}'.format(round(salary.net_salary, 2)))

            if salary.lpp_charge > 0:
                lpp_line_deb = Line(
                    party=salary.resp_id.party,
                    account=salary.contract.lpp_charge_cat.account_charge,
                    debit='{:.2f}'.format(round((salary.lpp_charge), 2)))

                lpp_line_cred = Line(
                    party=salary.resp_id.party,
                    account=salary.contract.lpp_charge_cat.account_cc,
                    credit='{:.2f}'.format(round(salary.lpp_charge*2, 2)))

            if salary.is_charge > 0:
                is_line_cred = Line(
                    party=salary.resp_id.party,
                    account=salary.contract.is_charge_cat.account_cc,
                    credit='{:.2f}'.format(round(salary.is_charge_amount, 2)))

            charges = {}
            for sl in salary.line_ids:
                if not charges.get(sl.cat):
                    charges[sl.cat] = {
                        'deb': 0,
                        'cred': 0,
                        'account_deb': sl.account_charge,
                        'account_cred': sl.account_cc}

                charges[sl.cat]['deb'] += sl.amount_boss
                charges[sl.cat]['cred'] += sl.amount_boss + sl.amount_employee

            lines = []
            for l in [sal_line_brut, lpp_line_cred, is_line_cred, sal_line_net, lpp_line_deb]:
                if l:
                    lines.append(l)

            for k in charges.keys():
                l_deb = Line(party=salary.resp_id.party,
                             account=charges[k]['account_deb'],
                             debit='{:.2f}'.format(round(charges[k]['deb'], 2)))
                l_cred = Line(party=salary.resp_id.party,
                              account=charges[k]['account_cred'],
                              credit='{:.2f}'.format(round(charges[k]['cred'], 2)))
                lines.append(l_deb)
                lines.append(l_cred)

            move = Move(journal=journal, state='draft', date=salary.date, period=period,
                        # origin=cls,
                        description=salary.name,
                        company=company, lines=lines)

            move.save()
            Move.post([move])
            salary.compta = move
            salary.save()

        # debit_line = Line(account=self.account)
        # counterpart_line = Line()

        # lines = [pay_line, counterpart_line]

        # pay_line.debit, pay_line.credit = 0, pay_amount

        #         pay_line.debit, pay_line.credit = pay_amount, 0

        #     overpayment_line = Line(account=self.account)
        #     lines.insert(1, overpayment_line)
        #     overpayment_line.debit = (
        #         abs(overpayment) if pay_line.debit else 0)
        #     overpayment_line.credit = (
        #         abs(overpayment) if pay_line.credit else 0)

        # counterpart_line.debit = abs(amount) if pay_line.credit else 0
        # counterpart_line.credit = abs(amount) if pay_line.debit else 0
        # if counterpart_line.debit:
        #     payment_acccount = 'debit_account'
        # else:
        #     payment_acccount = 'credit_account'
        # counterpart_line.account = getattr(
        #     payment_method, payment_acccount).current(date=date)

        # period = Period.find(self.company, date=date)

        # move = Move(
        #     journal=payment_method.journal, period=period, date=date,
        #     origin=self, description=description,
        #     company=self.company, lines=lines)
        # move.save()
        # Move.post([move])

        return True

    @staticmethod
    def default_gross_salary():
        return 0.0

    @staticmethod
    def default_prim():
        return 0.0

    @staticmethod
    def default_prim2():
        return 0.0

    @staticmethod
    def default_prim3():
        return 0.0
    
    @staticmethod
    def default_prim4_without_tax():
        return 0.0

    @staticmethod
    def default_lpp_charge():
        return 0.0

    @staticmethod
    def default_is_charge():
        return 0.0

    @fields.depends('compta')
    def on_change_with_compta_state(self, name=None):
        if self.compta and self.compta.state == 'posted':
            return 'ok'
        else:
            return 'nok'

    @fields.depends('is_charge', 'gross_salary', 'prim', 'prim2', 'prim3', 'car_charge', 'alloc_charge')
    def on_change_with_is_charge_amount(self, name=None):
        return self.is_charge > 0 and round(((self.gross_salary + self.prim + self.prim2 + self.prim3 + self.car_charge + self.alloc_charge) * (self.is_charge/100.0))/0.05)*0.05 or 0

    @fields.depends('is_charge_amount', 'gross_salary', 'prim', 'prim2', 'prim3', 'prim4_without_tax', 'car_charge', 'alloc_charge', 'line_ids', 'lpp_charge')
    def on_change_with_net_salary(self, name=None):
        tot_charge = 0
        for l in self.line_ids:
            tot_charge += l.amount_employee

        tot_charge += self.is_charge_amount
        tot_charge += self.lpp_charge
        return self.gross_salary + self.prim + self.prim2 + self.prim3 + self.prim4_without_tax - tot_charge

    @fields.depends('contract', 'resp_id', 'gross_salary', 'car_charge', 'alloc_charge', 'is_charge', 'lpp_charge')
    def on_change_contract(self):
        if self.contract:
            self.resp_id = self.contract.resp_id
            self.gross_salary_contract = self.contract.gross_salary
            self.gross_salary = self.contract.gross_salary
            self.car_charge = self.contract.car_charge
            self.alloc_charge = self.contract.alloc_charge
            self.is_charge = self.contract.is_charge
            self.lpp_charge = self.contract.lpp_charge
            self.car_charge_txt = self.contract.car_charge_txt
            self.alloc_charge_txt = self.contract.alloc_charge_txt
            self.is_charge_txt = self.contract.is_charge_txt
            self.lpp_charge_txt = self.contract.lpp_charge_txt
        else:
            self.resp_id = None
            self.gross_salary_contract = None
            self.gross_salary = None
            self.car_charge = None
            self.alloc_charge = None
            self.is_charge = None
            self.lpp_charge = None
            self.car_charge_txt = None
            self.alloc_charge_txt = None
            self.is_charge_txt = None
            self.lpp_charge_txt = None

    @classmethod
    def delete(cls, salarys):
        for salary in salarys:
            if salary.compta:
                raise UnableToDelete(
                    "Impossible de supprimer une fiche de salaire comptabilisée")

        super().delete(salarys)

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        res = super().create(vlist)
        SALARYLINE = pool.get('pl_cust_salary.salaryline')

        for sc in res[0].contract.socialcharge_ids:
            print(sc)
            print(sc.cat.account_charge)
            print(sc.charge.tx_boss)
            tmp = SALARYLINE.create([{
                                    'name': sc.charge.name,
                                    'cat': sc.cat.name,
                                    'account_charge': sc.cat.account_charge.id,
                                    'account_cc': sc.cat.account_cc.id,
                                    'tx_boss': sc.charge.tx_boss,
                                    'tx_employee': sc.charge.tx_employee,
                                    'max_gross_salary': sc.charge.max_gross_salary,
                                    'salary': res[0].id,
                                    }])

        return res

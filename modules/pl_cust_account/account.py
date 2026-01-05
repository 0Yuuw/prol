# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from io import StringIO
import re
import csv
import xml.etree.ElementTree as ET

from trytond.i18n import gettext
from trytond.pool import PoolMeta, Pool
from decimal import Decimal
from trytond.modules.account_statement.exceptions import ImportStatementError
from trytond.wizard import Wizard, StateView, StateTransition, StateAction, Button
from trytond.model import ModelSQL, ModelView, fields
from trytond.report import Report
from trytond.transaction import Transaction
from datetime import datetime
from trytond.config import config

__all__ = ['PLImportStatementStart', 'PLImportStatement', 'PLConfiguration',
           'MyStatementLine', 'PLImportIsaLineStart', 'PLImportIsaLine',
           'PLTaxTemplate', 'PLTax', 'PLGeneralLedger', 'PLBalanceSheetContext', 'PLBalanceSheetCompContext', 'PLParty']


def namespace(element):
    m = re.match('\{.*\}', element.tag)
    return m.group(0) if m else ''

def format_date2(date):
    y, m, d = str(date).split('-')
    return '{}.{}.{}'.format(d, m, y[-2:])

class MyStatementLine(ModelSQL):
    'Account Statement Line'
    __name__ = 'account.statement.line'

    @fields.depends('account')
    def on_change_with_party_required(self, name=None):
        return False

    @staticmethod
    def default_amount():
        return None

    #@staticmethod
    #def default_related_to():
    #    return 'account.invoice'

class PLConfiguration(ModelSQL, ModelView):
    'Account Configuration'
    __name__ = 'account.configuration'

    qr_iban   = fields.Char('QR IBAN')
    qr_ref    = fields.Char('QR Bank Ref')
    is_qriban = fields.Boolean('Is QR IBAN?')
    qr_label1 = fields.Char('QR Label1')
    qr_label2 = fields.Char('QR Label2')
    qr_label3 = fields.Char('QR Label3')
    qr_label4 = fields.Char('QR Label4')
    qr_label5 = fields.Char('QR Label5')

    @classmethod
    def default_is_qriban(cls):
        return True

class PLImportStatementStart(ModelView):
    "ProLibre Statement Import Start"
    __name__ = 'pl_cust_account.statement.import.start'
    company = fields.Many2One('company.company', "Company", required=True)
    file_ = fields.Binary("File", required=True)
    statement = fields.Many2One(
        'account.statement', "Statement",
        required=True)

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_statement(cls):
        if Transaction().context.get('active_model', '') == 'account.statement':
            return Transaction().context.get('active_id', '')
        return None


class PLImportStatement(Wizard):
    "ProLibre Statement Import"
    __name__ = 'pl_cust_account.statement.import'
    start = StateView('pl_cust_account.statement.import.start',
                      'pl_cust_account.statement_import_start_view_form', [
                          Button("Cancel", 'end', 'tryton-cancel'),
                          Button("Import", 'parse_camt',
                                 'tryton-ok', default=True),
                      ])

    parse_camt = StateTransition()

    def transition_parse_camt(self, encoding='windows-1252'):
        file_ = self.start.file_
        if not isinstance(file_, str):
            file_ = file_.decode(encoding)
        # file_ = StringIO(file_)
        camt_statement = {}
        root = ET.fromstring(file_)
        ns = namespace(root)
        records = []
        camt_statement['iban'] = root.find(
            "%sBkToCstmrDbtCdtNtfctn/%sNtfctn/%sAcct/%sId/%sIBAN" % (ns, ns, ns, ns, ns)).text
        camt_statement['id'] = root.find(
            "%sBkToCstmrDbtCdtNtfctn/%sNtfctn/%sId" % (ns, ns, ns)).text
        info = root.findall(
            "%sBkToCstmrDbtCdtNtfctn/%sNtfctn/%sNtry" % (ns, ns, ns))
        for val in info:
            valtmp = 0.0
            ValTot = float(val.find("%sAmt" % ns).text)
            camt_statement['tot'] = '{:.2f}'.format(ValTot)
            valdt = val.find("%sValDt/%sDt" % (ns, ns)).text
            for val2 in val.findall("%sNtryDtls/%sTxDtls" % (ns, ns)):
                if val2.find("%sRltdPties/%sUltmtDbtr" % (ns, ns)):
                    try :
                        new_line = "Nom : %s / Montant : %.2f / ref : %s" % (
                            val2.find("%sRltdPties" % (ns)) and val2.find(
                             "%sRltdPties/%sUltmtDbtr" % (ns, ns)) and val2.find(
                             "%sRltdPties/%sUltmtDbtr/%sNm" % (ns, ns, ns)).text or "???",
                            float(val2.find("%sAmt" % ns).text),
                        val2.find("%sRmtInf/%sStrd/%sCdtrRefInf/%sRef" %
                                      (ns, ns, ns, ns)).text,)
                         # val2.find("%sRltdDts/%sAccptncDtTm" %
                            #          (ns, ns)).text.split('T')[0]
                    except :
                        new_line = "???"
                    
                    dbcd = 1.0

                elif val2.find("%sRltdPties/%sDbtr" % (ns, ns)):
                    new_line = "Nom : %s / Montant : %.2f / ref : %s" % (
                        val2.find("%sRltdPties" % (ns)) and val2.find("%sRltdPties/%sDbtr/%sNm" % (
                            ns, ns, ns)) and val2.find("%sRltdPties/%sDbtr/%sNm" % (ns, ns, ns)).text or "",
                        float(val2.find("%sAmt" % ns).text),
                        val2.find("%sRmtInf/%sStrd/%sCdtrRefInf/%sRef" %
                                  (ns, ns, ns, ns)).text,
                        # val2.find("%sRltdDts/%sAccptncDtTm" %
                        #          (ns, ns)).text.split('T')[0]
                    )
                    dbcd = 1.0

                elif val2.find("%sRltdPties/%sCbtr" % (ns, ns)):
                    new_line = "Nom : %s / Montant : %.2f / Date du paiement par le client : %s" % (
                        val2.find("%sRltdPties" % (ns)) and val2.find(
                            "%sRltdPties/%sCdtr/%sNm" % (ns, ns, ns)).text or "",
                        float(val2.find("%sAmt" % ns).text),
                        val2.find("%sRltdDts/%sAccptncDtTm" %
                                  (ns, ns)).text.split('T')[0]
                    )
                    dbcd = -1.0
                else:
                    new_line = "Montant : %.2f / ref : %s" % (
                        float(val2.find("%sAmt" % ns).text),
                        val2.find("%sRmtInf/%sStrd/%sCdtrRefInf/%sRef" %
                                  (ns, ns, ns, ns)).text,
                        # val2.find("%sRltdDts/%sAccptncDtTm" %
                        #          (ns, ns)).text.split('T')[0]
                    )
                    dbcd = 1.0
                    #raise ImportStatementError("Erreur pas de nom à donner")

                record = {'reference':  val2.find("%sRmtInf/%sStrd/%sCdtrRefInf/%sRef" % (ns, ns, ns, ns)).text,
                          'amount': '{:.2f}'.format(float(val2.find("%sAmt" % ns).text) * dbcd),
                          # val2.find("%sRltdDts/%sAccptncDtTm"%(ns,ns)).text.split('T')[0],
                          'date': valdt,
                          'cost': 0,
                          'full_line': new_line,
                          }
                print('!!!!--{}'.format(record))
                valtmp += float(val2.find("%sAmt" % ns).text)
                records.append(record)
            if abs(ValTot - valtmp) > 0.01:
                raise ImportStatementError("Erreur sur le montant final")

        print(camt_statement)

        statement = self.start.statement
        origins = list(statement.origins)
        lines = list(statement.lines)
        i_start = len(lines)
        for i, move in enumerate(records):
            orig, = self.camt_origin(statement, move, i_start + i)
            origins.extend([orig])
            print('+++++++--{}'.format(move))
            lines.extend(self.camt_line(statement, orig, move, i_start + i))
        statement.origins = origins
        statement.lines = lines
        statement.save()
        return 'end'

    def camt_origin(self, statement, move, sequence):
        pool = Pool()
        Origin = pool.get('account.statement.origin')

        origin = Origin()
        origin.statement = statement
        origin.number = sequence
        origin.date = datetime.strptime(move['date'], '%Y-%m-%d')
        origin.amount = move['amount']
        origin.account = statement.journal.account
        origin.save()

        # origin.party=self.camt_party(statement, move)
        # TODO select account using transaction codes
        origin.description = move['full_line']
        origin.information = self.camt_information(move)
        return [origin]

    def camt_line(self, statement, origin, move, sequence):
        pool = Pool()
        Lines = pool.get('account.statement.line')
        Invoices = pool.get('account.invoice')

        account_conf = pool.get('account.configuration')
        conf = account_conf(1)

        line2 = None
        line = Lines()
        line.number = sequence

        line.date = datetime.strptime(move['date'], '%Y-%m-%d')
        line.amount = move['amount']
        line.statement = statement
        line.origin = origin
        line.description = ''

        ref_fmt = config.get('pl_cust', 'ref_fmt')
        if not ref_fmt:
            raise ImportStatementError(
                "Il faut configurer le format des n° de facture (demander à ProLibre)")
        if ref_fmt == 'yyyy/xxxxx':
            invoice = Invoices.search(
                [('number', '=', '{}/{}'.format(move['reference'][-10:-6], move['reference'][-6:-1]))])
        elif ref_fmt == 'yyyy/xxxx':
            invoice = Invoices.search(
                [('number', '=', '{}/{}'.format(move['reference'][-9:-5], move['reference'][-5:-1]))])
        elif ref_fmt == 'yyyy-xxx':
            invoice = Invoices.search(
                [('number', '=', '{}-{}'.format(move['reference'][-8:-4], move['reference'][-4:-1]))])
        elif ref_fmt == 'xxxxx-ddddd':
            invoice = Invoices.search(
                [('number', '=', 'F{}-{}'.format(move['reference'][-11:-6], move['reference'][-6:-1]))])
        elif ref_fmt == 'x':
            invoice = Invoices.search(
                [('number', '=', '{}'.format(int(move['reference'][-10:-1])))])
        else:
            raise ImportStatementError(
                "Format ref_fmt du fichier de conf non reconnu")

        if invoice:
            inv = Invoices(invoice[0])
            if not inv.state == 'posted':
                line.party = inv.party
                line.account = conf.default_account_receivable
                if inv.state == 'paid':
                    line.description = 'Facture déjà payée'
                else:
                    line.description = 'Vérifier état facture'
                
            else:
                if inv.amount_to_pay < Decimal(move['amount']):
                    line.amount = inv.amount_to_pay
                    line2 = Lines()
                    line2.number = sequence
                    line2.date = datetime.strptime(move['date'], '%Y-%m-%d')
                    line2.amount = Decimal(move['amount']) - inv.amount_to_pay
                    line2.statement = statement
                    line2.origin = origin
                    line2.party = inv.party
                    line2.account = conf.default_account_receivable
                    line2.description = 'Montant payé en trop'
                    line2.save()
                line.invoice = inv
                line.party = inv.party
                line.account = inv.account
        else:
            print('*************bhoueaaaa****************')
            line.account = conf.default_account_receivable

            line.description = 'Erreur de référence'

        line.save()

        if line2:
            return [line, line2]
        else:
            return [line]

    def camt_party(self, camt_statement, move):
        pool = Pool()
        AccountNumber = pool.get('bank.account.number')

        if not move.counterparty_account:
            return
        numbers = AccountNumber.search(['OR',
                                        ('number', '=', move.counterparty_account),
                                        ('number_compact', '=',
                                         move.counterparty_account),
                                        ])
        if len(numbers) == 1:
            number, = numbers
            if number.account.owners:
                return number.account.owners[0]

    def camt_information(self, move):
        information = {}
        for name in [
            'reference',
            'amount',
            'date',
            # 'cost',
            'full_line',
        ]:
            value = move[name]
            if value:
                information['camt_' + name] = value
        return information


class PLImportIsaLineStart(ModelView):
    "ProLibre Import Isa Line"
    __name__ = 'pl_cust_account.isaline.import.start'
    company = fields.Many2One('company.company', "Company", required=True)
    file_ = fields.Binary("File", required=True)
    statement = fields.Many2One(
        'account.statement', "Statement",
        required=True)

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_statement(cls):
        if Transaction().context.get('active_model', '') == 'account.statement':
            return Transaction().context.get('active_id', '')
        return None


class PLImportIsaLine(Wizard):
    "ProLibre Statement Import"
    __name__ = 'pl_cust_account.isaline.import'
    start = StateView('pl_cust_account.isaline.import.start',
                      'pl_cust_account.isaline_import_start_view_form', [
                          Button("Cancel", 'end', 'tryton-cancel'),
                          Button("Import", 'parse_file',
                                 'tryton-ok', default=True),
                      ])

    parse_file = StateTransition()

    def create_line(self, statement, importline):
        pool = Pool()
        Lines = pool.get('account.statement.line')
        Account = pool.get('account.account')

        account_conf = pool.get('account.configuration')
        conf = account_conf(1)

        line = Lines()
        line.number = importline['1']
        line.sequence = importline['1']

        if importline.get('6', False):
            line.party = int(importline['6'])

        try:
            line.date = datetime.strptime(importline['2'], '%d.%m.%y')
        except:
            line.date = datetime.strptime(importline['2'], '%d.%m.%Y')

        line.amount = importline['3']
        line.statement = statement
        line.description = importline['5']

        acc = Account.search([('code', '=', importline['4'])])

        if not acc:
            raise ImportStatementError(
                "Il y a un soucis avec le compte {}".format(importline['4']))

        line.account = acc[0]

        line.save()

        return [line]

    def transition_parse_file(self):

        isafile = self.start.file_.decode('utf-8')

        statement = self.start.statement
        lines = list(statement.lines)

        col = ['1', '2', '3', '4', '5', '6', '7']
        for l in isafile.split('\n'):
            line = dict(zip(col, l.split(';')))
            if line['1']:
                lines.extend(self.create_line(statement, line))
        statement.lines = lines
        statement.save()
        return 'end'


class PLTax(ModelSQL):
    __name__ = 'account.tax'

    oeid = fields.Char('OEid')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        clause = ('type.statement', '=', 'balance')
        if clause in cls.invoice_account.domain:
            cls.invoice_account.domain.remove(clause)
        if clause in cls.credit_note_account.domain:
            cls.credit_note_account.domain.remove(clause)


class PLTaxTemplate(ModelSQL):
    __name__ = 'account.tax.template'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        clause = ('type.statement', '=', 'balance')
        if clause in cls.invoice_account.domain:
            cls.invoice_account.domain.remove(clause)
        if clause in cls.credit_note_account.domain:
            cls.credit_note_account.domain.remove(clause)


class PLGeneralLedger(Report):
    __name__ = 'account.general_ledger'

    @classmethod
    def get_context(cls, records, header, data):
        pool = Pool()
        Company = pool.get('company.company')
        Fiscalyear = pool.get('account.fiscalyear')
        Period = pool.get('account.period')
        Lang = pool.get('ir.lang')

        context = Transaction().context
         
        report_context = super().get_context(records, header, data)
        report_context['lang'] = Lang(Lang.search([('code', '=', 'fr')])[0])
        report_context['company'] = Company(context['company'])
        report_context['fiscalyear'] = Fiscalyear(context['fiscalyear'])

        for period in ['start_period', 'end_period']:
            if context.get(period):
                report_context[period] = Period(context[period])
            else:
                report_context[period] = None
        report_context['from_date'] = context.get('from_date')
        report_context['to_date'] = context.get('to_date')

        report_context['accounts'] = records

        report_context['pl_lines'] = {}

        for account in report_context['accounts']:

            report_context['pl_lines'][account.id] = []
            for line in account.lines:
                contrepart = []
                party = line.party

                for ll in line.move.lines:
                    if not ll.id == line.id and not ll.account.code in contrepart:
                        contrepart.append(ll.account.code)
                        if not party and ll.party:
                            party = ll.party

                contrepart.sort()
                if len(contrepart) > 4 : 
                    contrepart = 'Divers'
                else : 
                    contrepart = ', '.join(contrepart)   

                descr = party and '{} - '.format(party.name) or ''

                if line.move.description == line.description :
                        descr += '{}'.format(line.move.description)
                else :
                    if line.move.description and line.description :
                        descr += '{} - {}'.format(line.move.description,line.description)
                    else : 
                        descr += '{}'.format(line.move.description or line.description)

                orig = ''

                if line.origin:
                    orig = getattr(line.origin, 'rec_name', '')
                elif line.move.origin:
                    orig = getattr(line.move.origin, 'rec_name', '')

                if ' @ ' in orig :
                    orig = orig.split(' @ ')[-1]

                report_context['pl_lines'][account.id].append([
                                                        format_date2(line.date), 
                                                        line.move.rec_name, 
                                                        '{}'.format(cls.format_currency(line.debit,
                                                                    report_context['lang'],
                                                                    report_context['company'].currency)),
                                                        
                                                        
                                                        '{}'.format(cls.format_currency(line.credit,
                                                                    report_context['lang'],
                                                                    report_context['company'].currency)),
                                                        line.second_currency and '{}'.format(cls.format_currency(line.amount_second_currency,
                                                                    report_context['lang'],
                                                                    line.second_currency)) or '', 

                                                        '{}'.format(cls.format_currency(line.balance,
                                                                    report_context['lang'],
                                                                    report_context['company'].currency)), 
                                                        descr, 
                                                        orig, 
                                                        contrepart, 
                                                        line.state == 'posted' and 'C' or ''])

        return report_context


class PLBalanceSheetContext(ModelView):
    'Balance Sheet Context'
    __name__ = 'account.balance_sheet.context'
    cumulate = fields.Boolean('Cumulate')

class PLBalanceSheetCompContext(ModelView):
    'Balance Sheet Comparison Context'
    __name__ = 'account.balance_sheet.comparison.context'
    cumulate = fields.Boolean('Cumulate')

class PLParty(metaclass=PoolMeta):
    __name__ = 'party.party'

    default_category_account_expense = fields.Many2One(
        'account.account', 'Default Account Expense'
    )
    default_category_account_revenue = fields.Many2One(
        'account.account', 'Default Account Revenue'
    )

    default_tax_expense = fields.Many2One(
        'account.tax', "Tax Expense", ondelete='RESTRICT'
    )
    default_tax_revenue = fields.Many2One(
        'account.tax', "Tax Revenue", ondelete='RESTRICT'
    )
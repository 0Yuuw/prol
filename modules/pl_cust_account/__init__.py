# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .account import *
from .move import *
from .invoice import *
from .invoice_report import * 
from .wizard_bilan import *
from .wizard_invoices_report import *
from . import wizard_qr_invoice


__all__ = ['register']

def register():
    Pool.register(
        Currency,
        Account,
        Move,
        Line,
        Statement,
        Invoice,
        InvoiceLine,
        InvoicePaymentLine,
        InvoicesReportStart,
        InvoicesReportRes,
        Reconciliation,
        PLBalanceSheetContext,
        PLBalanceSheetCompContext,
        PLInvoice,
        PLInvoiceLine,
        PLMove,
        PLMoveLine,
        PLImportStatementStart,
        PLImportIsaLineStart,
        PLBilanStart,
        PLPayInvoiceStart,
        PLConfiguration,
        MyStatementLine,
        PLTaxTemplate,
        PLTax,
        PLParty,
        module='pl_cust_account', type_='model')

    Pool.register(
        PLImportStatement,
        PLImportIsaLine,
        PLBilan,
        InvoicesReport,
        module='pl_cust_account', type_='wizard')
    
    Pool.register(
        InvoiceReport,
        module='account_invoice', type_='report')

    Pool.register(
        PLGeneralLedger,
        module='account', type_='report')
    
    Pool.register(
        wizard_qr_invoice.QrInvoiceStart,
        wizard_qr_invoice.QrInvoiceConfirm,
        module='pl_cust_account', type_='model'
    )

    Pool.register(
        wizard_qr_invoice.QrInvoiceWizard,
        module='pl_cust_account', type_='wizard'
    )

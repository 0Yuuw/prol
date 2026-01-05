# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.model import ModelView, ModelSQL
from trytond.report import Report
from trytond.rpc import RPC
from trytond.pool import Pool
from trytond.transaction import Transaction
from datetime import datetime
from decimal import *
import re

__all__ = ['InvoiceReport']

import qrcode
import qrcode.image.svg
from barcode import Code39
from barcode.writer import ImageWriter

from PIL import Image
from trytond.model.exceptions import ValidationError

class RapportValidationError(ValidationError):
    pass


def my_format_date(date):
    if not date:
        return '-'

    corresp = {
        1: 'janvier',
        2: 'février',
        3: 'mars',
        4: 'avril',
        5: 'mai',
        6: 'juin',
        7: 'juillet',
        8: 'août',
        9: 'septembre',
        10: 'octobre',
        11: 'novembre',
        12: 'décembre',
    }

    return '{} {} {}'.format(date.strftime("%-d"),
                             corresp[date.month],
                             date.strftime("%Y"),
                             )


def format_date2(date):
    if date :
        y, m, d = str(date).split('-')
        return '{}.{}.{}'.format(d, m, y)
    else :
        return '-'


_compile_get_ref = re.compile('[^0-9]')


def _space(nbr, nbrspc=5):
    """Spaces * 5"""
    res = ''
    for i in range(len(nbr)):
        res = res + nbr[i]
        if not (i-1) % nbrspc:
            res = res + ' '
    return res


def mod10r(number):
    """
    Input number : account or invoice number
    Output return: the same number completed with the recursive mod10
    key
    """
    codec = [0, 9, 4, 6, 8, 2, 7, 1, 3, 5]
    report = 0
    result = ""
    for digit in number:
        result += digit
        if digit.isdigit():
            report = codec[(int(digit) + report) % 10]
    return result + str((10 - report) % 10)


def _get_ref(inv_num, memb_num):
    """Retrieve ESR/BVR reference form invoice in order to print it"""
    member_num = '{}'.format(memb_num.zfill(6))
    invoice_number = '{}'.format(_compile_get_ref.sub('', inv_num).zfill(7))
    return mod10r(member_num + ''.rjust(26-len(member_num)-len(invoice_number), '0') + invoice_number)


def qr_gen(iban="CHxxxxxxxxxxxxxxxxxxx",
           is_qriban=True,
           amount=666.66,
           party_name='John Doe',
           party_rue='xxx',
           party_compl='xxx',
           party_zip='xxx',
           party_city='xxx',
           party_country='CH',
           ref='210000000003139471430009017',
           descr='-',
           label1='',
           label2='',
           label3='',
           id=1):
    qr = qrcode.QRCode(  # version=23,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=18,
        border=0,
    )

    txt = u"""SPC
0200
1
{}
{}
{}
{}
{}


CH







{}
CHF
S
{}
{}
{}
{}
{}
{}
{}
{}
{}
EPD
""".format(iban,
           "K",#is_qriban and "K" or "S",
           label1,
           label2,
           label3,
           amount and '{:.2f}'.format(amount) or '',
           party_name,
           party_rue,
           party_compl,
           party_zip,
           party_city,
           party_country,
           is_qriban and "QRR" or "NON",
           is_qriban and ref or "",
           descr)

    qr.add_data(txt)

    qr.make(fit=False)

    #factory = qrcode.image.svg.SvgPathImage

    #img = qrcode.make(txt, image_factory=factory)
    #img = qrcode.make(txt, )

    img = qr.make_image(fill_color="black", back_color="white")
    img.save('/tmp/test.png')

    try : 
        swiss_logo = Image.open(
            "/usr/local/lib/python3.9/dist-packages/trytond/modules/pl_cust_account/swiss.png")
    except : 
        swiss_logo = Image.open(
            "/usr/local/lib/python3.11/dist-packages/trytond/modules/pl_cust_account/swiss.png")

    code_qr = Image.open("/tmp/test.png")

    img_w, img_h = swiss_logo.size
    bg_w, bg_h = code_qr.size
    offset = ((bg_w - img_w) // 2, (bg_h - img_h) // 2)
    code_qr.paste(swiss_logo, offset)
    code_qr.save('/tmp/qr{}.png'.format(id))
    return True


class InvoiceReport(Report):
    __name__ = 'pl_cust_account.invoice_report'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__rpc__['execute'] = RPC(False)

    @classmethod
    def _execute(cls, records, header, data, action):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        # Re-instantiate because records are TranslateModel
        inv = Invoice.browse(records)
        result = super()._execute(
            records, header, data, action)
        return result

    # @classmethod
    # def execute(cls, ids, data):
    #     pool = Pool()
    #     Invoice = pool.get('account.invoice')
    #     LANG = pool.get('ir.lang')
        
    #     with Transaction().set_context(
    #             language='fr',
    #             address_with_party=True):
    #         result = super().execute(ids, data)
    #         return result

    @classmethod
    def get_context(cls, records, headers, data):
        pool = Pool()
        Date = pool.get('ir.date')
        LANG = pool.get('ir.lang')
        ACCOUNT_CONF = pool.get('account.configuration')
        configuration = ACCOUNT_CONF(1)

        context = super().get_context(records, headers, data)

        # print(context)
        context['invoice'] = context['record']
        context['lang'] = LANG(LANG.search([('code', '=', 'fr')])[0])

        context['lines'] = []
        for l in context['invoice'].lines:
            tmp = [l.description or '',
                    '{}'.format(cls.format_currency(l.amount,
                                                    context['lang'],
                                                    context['invoice'].currency)),
                    l.unit and l.unit.symbol and l.unit.symbol == 'u' and int(
                        l.quantity) or l.quantity,
                    l.unit and l.unit.symbol and l.unit.symbol == 'u' and 'unités' or (l.unit and l.unit.symbol or ''),
                    '{}'.format(cls.format_currency(l.unit_price,
                                                    context['lang'],
                                                    context['invoice'].currency)),
                    l.note or ''
                   ]
            context['lines'].append(tmp)

        tmp_taxes = {}
        for t in context['invoice'].taxes:
            if not t.tax.description in tmp_taxes.keys():
                tmp_taxes[t.tax.description] = t.amount
            else:
                tmp_taxes[t.tax.description] += t.amount

        if tmp_taxes:
            context['tax_amount'] = [(k, '{}'.format(cls.format_currency(v,
                                                                         context['lang'],
                                                                         context['invoice'].currency))) for k, v in tmp_taxes.items()]
        else :
            context['tax_amount'] = []                                                              

        context['payline'] = []
        for pay in context['invoice'].payment_lines:
            context['payline'].append(['Versement du {}'.format(format_date2(pay.date)), '{}'.format(cls.format_currency(pay.amount,
                                                                                                                         context['lang'],
                                                                                                                         context['invoice'].currency))])
        context['QRBankRef'] = configuration.qr_ref or ''
        context['QRlabel1'] = configuration.qr_label1 or ''
        context['QRlabel2'] = configuration.qr_label2 or ''
        context['QRlabel3'] = configuration.qr_label3 or ''
        context['QRlabel4'] = ''
        context['QRlabel5'] = ''
        context['is_qriban'] = configuration.is_qriban

    
        context['QRiban'] = configuration.qr_iban
        context['QRamount'] = context['invoice'].total_amount
        context['QRamount_txt'] = '{}'.format(cls.format_currency(context['invoice'].total_amount,
                                                                context['lang'],
                                                                context['invoice'].currency))

        context['QRamount_ht_txt'] = '{}'.format(cls.format_currency(context['invoice'].untaxed_amount,
                                                                context['lang'],
                                                                context['invoice'].currency))

        context['QRamount_sold_txt'] = '{}'.format(cls.format_currency(context['invoice'].amount_to_pay,
                                                                     context['lang'],
                                                                     context['invoice'].currency))
    
        context['QRamount_txt2'] = context['QRamount_sold_txt'].replace('CHF', '')
        context['QRparty'] = context['invoice'].party.name or ''
        context['QRparty_rue'] = context['invoice'].invoice_address.addr_street and '{} {}'.format(
            context['invoice'].invoice_address.addr_street or '', context['invoice'].invoice_address.addr_street_num or '') or ''
        context['QRparty_compl'] = context['invoice'].invoice_address.addr_compl or ''
        if not context['invoice'].invoice_address.postal_code or not context['invoice'].invoice_address.city: 
            raise RapportValidationError('Le code postal et la ville du client sont obligatoires pour générer une QR Facture!!')
    
        context['QRparty_zip'] = context['invoice'].invoice_address.postal_code or ''
        context['QRparty_city'] = context['invoice'].invoice_address.city or ''
        context['QRparty_country'] = context['invoice'].invoice_address.country and  context['invoice'].invoice_address.country.code or 'CH'
        context['QRref'] = _get_ref(context['invoice'].number or '00000',
                                  context['QRBankRef'])
    
        context['QRref_space'] = _space(context['QRref'])
        context['QRinfo'] = context['invoice'].description

        if context['invoice'].number:
            qr_gen(iban=context['QRiban'].replace(' ', ''),
                   is_qriban=configuration.is_qriban,
                   amount=context['invoice'].amount_to_pay or '',
                   party_name=context['QRparty'],
                   party_rue=context['QRparty_rue'],
                   party_compl=context['QRparty_compl'],
                   party_zip=context['QRparty_zip'],
                   party_city=context['QRparty_city'],
                   party_country=context['QRparty_country'],
                   ref=context['QRref'],
                   descr=context['QRinfo'],
                   label1=context['QRlabel1'],
                   label2=context['QRlabel2'],
                   label3=context['QRlabel3'],
                   id=context['invoice'].id)
            context['myimg'] = (
                open('/tmp/qr{}.png'.format(context['invoice'].id), 'rb'), 'image/png')
        else:
            try : 
                context['myimg'] = (open(
                    '/usr/local/lib/python3.9/dist-packages/trytond/modules/pl_cust_account/swiss.png', 'rb'), 'image/png')
            except :
                context['myimg'] = (open(
                    '/usr/local/lib/python3.11/dist-packages/trytond/modules/pl_cust_account/swiss.png', 'rb'), 'image/png')

        context['mytoday'] = my_format_date(context['invoice'].invoice_date)
        context['mytoday_now'] = my_format_date(Date.today())
        context['date_ech'] = context['invoice'].date_due and my_format_date(context['invoice'].date_due) or None
        context['podate'] = format_date2(context['invoice'].purchase_date)

        # context['ts_tab']=[]
        # tot_tmp = 0
        # for ts in context['invoice'].timesheet_ids[::-1] :
                     
        #     tmp_dur = round(ts.duration.seconds/3600,2)
        #     tmp_dur2 = round((ts.duration.seconds*int(ts.pct)/100)/3600,2)
        #     tot_tmp += ts.duration.seconds*int(ts.pct)/100
            
        #     context['ts_tab'].append((format_date2(ts.date),ts.name,'{:.2f}'.format(tmp_dur),ts.pct,'{:.2f}'.format(tmp_dur2),ts.resp_id.code))

        # context['tot'] = '{:.2f}'.format(round(tot_tmp/3600,2))

        return context

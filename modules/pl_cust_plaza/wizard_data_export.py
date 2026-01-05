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


class DataExportError(ValidationError):
    pass


__all__ = ['DataExport', 'DataExportStart', 'DataExportRes']


EXPORT_TYPE = [
    ('email', 'Emails'),
    ('contact', 'Infos contact')
]


class DataExportStart(ModelView):
    "DataExportStart"
    __name__ = 'pl_cust_plaza.dataexport_start'

    export_type = fields.Selection(EXPORT_TYPE, 'Type')

    @staticmethod
    def default_export_type():
        return 'email'


class DataExportRes(ModelView):
    "DataExportRes"
    __name__ = 'pl_cust_plaza.dataexport_result'

    filename = fields.Char('File Name', readonly=True)
    file_ = fields.Binary('File', filename='filename', readonly=True)
    all_mail = fields.Text('All Mails')


class DataExport(Wizard):
    "DataExport"
    __name__ = "pl_cust_plaza.dataexport"

    start = StateView('pl_cust_plaza.dataexport_start',
                      'pl_cust_plaza.dataexport_start_view_form', [
                          Button('Cancel', 'end', 'tryton-cancel'),
                          Button('Generate Export', 'generate_export',
                                 'tryton-ok', default=True),
                      ])

    generate_export = StateTransition()

    result = StateView('pl_cust_plaza.dataexport_result',
                       'pl_cust_plaza.dataexport_result_view_form', [
                           Button('Close', 'end', 'tryton-close'),
                       ])

    def transition_generate_export(self):
        file_name = 'export_{}_{}_{}.csv'.format(datetime.now().strftime('%d'),
                                                 datetime.now().strftime('%m'),
                                                 datetime.now().strftime('%y'))

        pool = Pool()
        PARTY = pool.get('party.party')
        Date_ = Pool().get('ir.date')
        
        all_party = PARTY.search(['check_import','=',False])
        all_mail = []
        if self.start.export_type == 'email':
            delimiter = ';'

            f = codecs.open('/tmp/' + file_name,
                            'wb',
                            encoding='windows-1252')

            writer = csv.writer(f, delimiter=delimiter)
            writer.writerow(['Nom complet', 'Nom', 'Prénom', 'email'])

            for party in all_party:
                for contact in party.contact_mechanisms:
                        if contact.type == 'email' and not contact.value in all_mail:
                            try:
                                writer.writerow([party.name, party.lastname, party.firstname, contact.value])
                                all_mail.append(contact.value)
                            except:
                                print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
               
            self.result.all_mail = '\n'.join(all_mail)
            f.close()

        elif self.start.export_type == 'contact' :
            delimiter = ';'
            f = codecs.open('/tmp/' + file_name,
                            'wb',
                            encoding='windows-1252')

            writer = csv.writer(f, delimiter=delimiter)
            writer.writerow([
                'Nom',
                'Prenom',
                'mail',
                'tel',
                'autre'])
            
            for party in all_party:
                mail = []
                tel = []
                other = []
               
                
                for contact in party.contact_mechanisms:
                    if contact.type == 'email' :
                        mail.append(contact.value)
                    if contact.type == 'other' :
                        other.append(contact.value)
                    if contact.type in ('mobile','phone'):
                        tel.append(contact.value)

                try:
                    writer.writerow([
                        party.lastname,
                        party.firstname,
                        ' / '.join(mail),
                        ' / '.join(tel),
                        ' / '.join(other),
                        ])
                except:
                    pass

            f.close()
            self.result.all_mail = ''
        
        self.result.filename = file_name

        return 'result'

    def default_result(self, fields):
        file_name = self.result.filename
        cast = self.result.__class__.file_.cast
        f = codecs.open('/tmp/' + file_name,
                        'rb',
                        encoding='windows-1252')

        data = f.read()

        f.close()

        os.unlink('/tmp/'+file_name)

        return {
            'all_mail' : self.result.all_mail,
            'filename': file_name,
            'file_':  cast(data.encode('cp1252')),
        }

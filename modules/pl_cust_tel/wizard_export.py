from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.model import ModelView, fields
from trytond.pool import Pool
from trytond.transaction import Transaction
from datetime import datetime, date
import codecs
import os
import csv

from trytond.model.exceptions import ValidationError


class TSReportError(ValidationError):
    pass


__all__ = ['WizardExport', 'WizardStart', 'WizardResult']

stats = {'tel': 0,
         'tel_spec': 0,
         'tchat': 0,
         'mail': 0,
         'duree': 0,
         'f': 0,
         'h': 0,
         'hf': 0,
         'quotidien': 0,
         'relation': 0,
         'couple': 0,
         'solitude': 0,
         'sociaux': 0,
         'famille': 0,
         'travail': 0,
         'violence': 0,
         'physique': 0,
         'psychique': 0,
         'sexualite': 0,
         'spiritualite': 0,
         'dependance': 0,
         'suicide': 0,
         'corona': 0,
         'guerre': 0,
         'media': 0,
         'mort': 0,
         'divers': 0,
         'vd': 0,
         'sos': 0,
         'lavi': 0,
         'vih': 0,
         'inconnu': 0,
         'ocase': 0,
         'connu': 0,
         '-18': 0,
         '19-40': 0,
         '41-65': 0,
         '+65': 0,
         'age_nd': 0,
         }


stats_vd = {'tel': 0,
            'tel_spec': 0,
            'tchat': 0,
            'duree': 0,
            'f': 0,
            'h': 0,
            'hf': 0,
            'inconnu': 0,
            'ocase': 0,
            'connu': 0,
            '-18': 0,
            '19-40': 0,
            '41-65': 0,
            '+65': 0,
            'age_nd': 0,
            'ge': 0,
            'vd': 0,
            'ne': 0,
            'vs': 0,
            'fr': 0,
            'ju': 0,
            'orig_autre': 0,
            'aut': 0,
            'vict': 0,
            'tem': 0,
            'pro': 0,
            'role_autre': 0,
            'conj': 0,
            'exconj': 0,
            'par': 0,
            'vois': 0,
            'ami': 0,
            'rel_autre': 0,
            'phys': 0,
            'psy': 0,
            'sex': 0,
            'eco': 0,
            'type_autre': 0,
            }

stats_sos = {'tel': 0,
             'tel_spec': 0,
             'tchat': 0,
             'mail': 0,
             'duree': 0,
             'f': 0,
             'h': 0,
             'hf': 0,
             'inconnu': 0,
             'ocase': 0,
             'connu': 0,
             '-18': 0,
             '19-40': 0,
             '41-65': 0,
             '+65': 0,
             'age_nd': 0,
             'ge': 0,
             'vd': 0,
             'ne': 0,
             'vs': 0,
             'fr': 0,
             'ju': 0,
             'france': 0,
             'prov_autre': 0,
             'nr': 0,
             'tech': 0,
             'rens_exl': 0,
             'rens_dep' : 0,
             'rens_prest' :0,
             'aide': 0,
             'prob_autre': 0,
             'j': 0,
             'p': 0,
             'pro': 0,
             'role_autre': 0,
             'bourse': 0,
             'lotel': 0,
             'lot': 0,
             'grat': 0,
             'par': 0,
             'pmu': 0,
             'pocker': 0,
             'mas': 0,
             'table': 0,
             'illeg': 0,
             'autre': 0,
             'call_type_terrestre': 0,
             'call_type_internet': 0,
             }

stats_vih = {'tel': 0,
             'tel_spec': 0,
             'tchat': 0,
             'mail': 0,
             'duree': 0,
             'f': 0,
             'h': 0,
             'hf': 0,
             'inconnu': 0,
             'ocase': 0,
             'connu': 0,
             '-18': 0,
             '19-40': 0,
             '41-65': 0,
             '+65': 0,
             'age_nd': 0,
             'ge': 0,
             'vd': 0,
             'ne': 0,
             'vs': 0,
             'fr': 0,
             'ju': 0,
             'autre': 0,
             'nr': 0,
             'avt_test': 0,
             'apr_test': 0,
             'rens': 0,
             'tiers': 0,
             }
               
class WizardStart(ModelView):
    """ First window to choose the export year """
    __name__ = 'pl_cust_tel.wizard_start'
    
    year_export = fields.Integer(
        "Year to Generate", required=True,
        domain=[('year_export', '>', 2000)],
        depends=['year_export']
    )

    @staticmethod
    def default_year_export():
        Date_ = Pool().get('ir.date')
        return Date_.today().year


class WizardResult(ModelView):
    """ Second window displaying file details & download option """
    __name__ = 'pl_cust_tel.wizard_result'

    name = fields.Char('File Name', readonly=True)
    file = fields.Binary('File', filename='name', readonly=True)


class WizardExport(Wizard):
    "Wizard Export"
    __name__ = "pl_cust_tel.wizard_export"

    start = StateView(
        'pl_cust_tel.wizard_start',
        'pl_cust_tel.wizard_start_view_form',
        [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Generate Report', 'generate_report', 'tryton-ok', default=True),
        ]
    )

    generate_report = StateTransition()

    result = StateView(
        'pl_cust_tel.wizard_result',
        'pl_cust_tel.wizard_result_view_form',
        [
            Button('Close', 'end', 'tryton-close'),
        ]
    )

    def transition_generate_report(self):
        """ Generates a CSV file containing call statistics """
        file_name = f'export-{self.start.year_export}.csv'
        delimiter = ';'
        file_path = f'/tmp/{file_name}'

        f = codecs.open('/tmp/' + file_name,
                        'wb',
                        encoding='utf-8')

        writer = csv.writer(f, delimiter=delimiter)       

        dict_res = {1: stats.copy(),
                    2: stats.copy(),
                    3: stats.copy(),
                    4: stats.copy(),
                    5: stats.copy(),
                    6: stats.copy(),
                    7: stats.copy(),
                    8: stats.copy(),
                    9: stats.copy(),
                    10: stats.copy(),
                    11: stats.copy(),
                    12: stats.copy(),
                    }

        dict_res_tchat = {1: stats.copy(),
                          2: stats.copy(),
                          3: stats.copy(),
                          4: stats.copy(),
                          5: stats.copy(),
                          6: stats.copy(),
                          7: stats.copy(),
                          8: stats.copy(),
                          9: stats.copy(),
                          10: stats.copy(),
                          11: stats.copy(),
                          12: stats.copy(),
                          }

        dict_res_mail = {1: stats.copy(),
                         2: stats.copy(),
                         3: stats.copy(),
                         4: stats.copy(),
                         5: stats.copy(),
                         6: stats.copy(),
                         7: stats.copy(),
                         8: stats.copy(),
                         9: stats.copy(),
                         10: stats.copy(),
                         11: stats.copy(),
                         12: stats.copy(),
                         }

        dict_res_sos = {1: stats_sos.copy(),
                        2: stats_sos.copy(),
                        3: stats_sos.copy(),
                        4: stats_sos.copy(),
                        5: stats_sos.copy(),
                        6: stats_sos.copy(),
                        7: stats_sos.copy(),
                        8: stats_sos.copy(),
                        9: stats_sos.copy(),
                        10: stats_sos.copy(),
                        11: stats_sos.copy(),
                        12: stats_sos.copy(),
                        }

        dict_res_vd = {1: stats_vd.copy(),
                       2: stats_vd.copy(),
                       3: stats_vd.copy(),
                       4: stats_vd.copy(),
                       5: stats_vd.copy(),
                       6: stats_vd.copy(),
                       7: stats_vd.copy(),
                       8: stats_vd.copy(),
                       9: stats_vd.copy(),
                       10: stats_vd.copy(),
                       11: stats_vd.copy(),
                       12: stats_vd.copy(),
                       }

        dict_res_vih = {1: stats_vih.copy(),
                        2: stats_vih.copy(),
                        3: stats_vih.copy(),
                        4: stats_vih.copy(),
                        5: stats_vih.copy(),
                        6: stats_vih.copy(),
                        7: stats_vih.copy(),
                        8: stats_vih.copy(),
                        9: stats_vih.copy(),
                        10: stats_vih.copy(),
                        11: stats_vih.copy(),
                        12: stats_vih.copy(),
                        }

        # Fetch calls from the database
        pool = Pool()
        CALLS = pool.get('pl_cust_tel.calls')
        # Get date range for the selected year
        date_start = f"{self.start.year_export}-01-01"
        date_end = f"{self.start.year_export}-12-31"
        all_calls = CALLS.search([
            ('call_date', '>=', date_start),
            ('call_date', '<=', date_end)
        ])
        # Process call records
        for call in all_calls:
            

            if call.call_date:  # Ensure call_date is not None
                month = call.call_date.month
                dict_res[month][call.call_type] += 1
                dict_res_tchat[month][call.call_type] += 1
                dict_res_mail[month][call.call_type] += 1
            #else :
            #    continue 

            
            
            if call.call_type == 'tel':
                dict_res[month][call.call_user_age] += 1
                dict_res[month][call.call_user_gender] += 1
                dict_res[month][call.call_user_type] += 1
                dict_res[month][call.contenu] += 1
                if call.contenu_2:
                    dict_res[month][call.contenu_2] += 1
                if call.contenu_3:
                    dict_res[month][call.contenu_3] += 1
                dict_res[month]['duree'] += call.call_length
                
            if call.call_type == 'tchat':
                dict_res_tchat[month][call.call_user_age] += 1
                dict_res_tchat[month][call.call_user_gender] += 1
                dict_res_tchat[month][call.call_user_type] += 1
                dict_res_tchat[month][call.contenu] += 1
                if call.contenu_2:
                    dict_res_tchat[month][call.contenu_2] += 1
                if call.contenu_3:
                    dict_res_tchat[month][call.contenu_3] += 1
                dict_res_tchat[month]['duree'] += call.call_length
            
            if call.call_type == 'mail':
                dict_res_mail[month][call.call_user_age] += 1
                dict_res_mail[month][call.call_user_gender] += 1
                dict_res_mail[month][call.call_user_type] += 1
                dict_res_mail[month][call.contenu] += 1
                if call.contenu_2:
                    dict_res_mail[month][call.contenu_2] += 1
                if call.contenu_3:
                    dict_res_mail[month][call.contenu_3] += 1
                dict_res_mail[month]['duree'] += call.call_length
                
            if call.contenu == 'sos':
                dict_res_sos[month][call.call_user_age] += 1
                dict_res_sos[month][call.call_user_gender] += 1
                dict_res_sos[month][call.call_user_type] += 1
                dict_res_sos[month][call.call_type] += 1
                dict_res_sos[month]['duree'] += call.call_length
                dict_res_sos[month][call.call_origin_sos] += 1
                dict_res_sos[month][call.call_problem_sos] += 1
                dict_res_sos[month][call.call_role_sos] += 1
                dict_res_sos[month][call.call_type_sos] += 1
                dict_res_sos[month]['call_type_terrestre'] += call.call_type_terrestre_sos and 1 or 0
                dict_res_sos[month]['call_type_internet'] += call.call_type_internet_sos and 1 or 0

            if call.contenu == 'vih':
                dict_res_vih[month][call.call_user_age] += 1
                dict_res_vih[month][call.call_user_gender] += 1
                dict_res_vih[month][call.call_user_type] += 1
                dict_res_vih[month][call.call_type] += 1
                dict_res_vih[month]['duree'] += call.call_length
                dict_res_vih[month][call.call_origin_vih] += 1
                dict_res_vih[month][call.call_motif_vih] += 1
                
            if call.contenu == 'vd':
                dict_res_vd[month][call.call_user_age] += 1
                dict_res_vd[month][call.call_user_gender] += 1
                dict_res_vd[month][call.call_user_type] += 1
                dict_res_vd[month][call.call_type] += 1
                dict_res_vd[month]['duree'] += call.call_length
                if call.call_origin_vd == 'autre':
                    dict_res_vd[month]['orig_autre'] += 1
                else :
                    dict_res_vd[month][call.call_origin_vd] += 1
                if call.call_role_vd == 'autre':
                    dict_res_vd[month]['role_autre'] += 1
                else :
                    dict_res_vd[month][call.call_role_vd] += 1
                if call.call_rel_vd == 'autre':
                    dict_res_vd[month]['rel_autre'] += 1
                else :
                    dict_res_vd[month][call.call_rel_vd] += 1
                if call.call_type_vd == 'autre':
                    dict_res_vd[month]['type_autre'] += 1
                else :
                    dict_res_vd[month][call.call_type_vd] += 1
                                        
        for k1 in ['tel_spec',
                'tel',
                'tchat',
                'mail',
                'duree',
                'f',
                'h',
                'hf',
                '-18',
                '19-40',
                '41-65',
                '+65',
                'age_nd',
                'inconnu',
                'ocase',
                'connu',
                'quotidien',
                'psychique',
                'corona',
                'physique',
                'solitude',
                'famille',
                'relation',
                'couple',
                'travail',
                'sociaux',
                'violence',
                'sexualite',
                'spiritualite',
                'dependance',
                'suicide',
                'mort',
                'guerre',
                'divers',
                'lavi',
                'vd',
                'sos',
                'vih'] :

            writer.writerow([k1]+[dict_res[i][k1] for i in range(1, 13)])
        
        writer.writerow('')
        writer.writerow(['Violences Domestiques'])
        for k2 in ['tel_spec',
                   'tel',
                   'tchat',
                   'duree',
                   'f',
                   'h',
                   'hf',
                   '-18',
                   '19-40',
                   '41-65',
                   '+65',
                   'age_nd',
                   'inconnu',
                   'ocase',
                   'connu',
                   'ge',
                   'vd',
                   'ne',
                   'vs',
                   'fr',
                   'ju',
                   'orig_autre',
                   'aut',
                   'vict',
                   'tem',
                   'pro',
                   'role_autre',
                   'conj',
                   'exconj',
                   'par',
                   'vois',
                   'ami',
                   'rel_autre',
                   'phys',
                   'psy',
                   'sex',
                   'eco',
                   'type_autre',
                   ]:

            writer.writerow([k2]+[dict_res_vd[i][k2] for i in range(1, 13)])

        writer.writerow('')
        writer.writerow(['SOS Jeux'])

        for k3 in ['tel_spec',
                   'tel',
                   'tchat',
                   'duree',
                   'f',
                   'h',
                   'hf',
                   '-18',
                   '19-40',
                   '41-65',
                   '+65',
                   'age_nd',
                   'inconnu',
                   'ocase',
                   'connu',
                   'ge',
                   'vd',
                   'ne',
                   'vs',
                   'fr',
                   'ju',
                   'france',
                   'prov_autre',
                   'nr',
                   'tech',
                   'rens_exl',
                   'rens_dep',
                   'rens_prest',
                   'aide',
                   'prob_autre',
                   'j',
                   'p',
                   'pro',
                   'role_autre',
                   'bourse',
                   'lotel',
                   'lot',
                   'grat',
                   'par',
                   'pmu',
                   'pocker',
                   'mas',
                   'table',
                   'illeg',
                   'autre',
                   'call_type_terrestre',
                   'call_type_internet',
                   ]:

            writer.writerow([k3]+[dict_res_sos[i][k3] for i in range(1, 13)])

        writer.writerow('')
        writer.writerow(['Tchat'])

        for k1 in ['tel_spec',
                   'tel',
                   'tchat',
                   'mail',
                   'duree',
                   'f',
                   'h',
                   'hf',
                   '-18',
                   '19-40',
                   '41-65',
                   '+65',
                   'age_nd',
                   'inconnu',
                   'ocase',
                   'connu',
                   'quotidien',
                   'psychique',
                   'corona',
                   'physique',
                   'solitude',
                   'famille',
                   'relation',
                   'couple',
                   'travail',
                   'sociaux',
                   'violence',
                   'sexualite',
                   'spiritualite',
                   'dependance',
                   'suicide',
                   'mort',
                   'guerre',
                   'divers',
                   'lavi',
                   'vd',
                   'sos',
                   'vih',
                   ]:

            writer.writerow([k1]+[dict_res_tchat[i][k1] for i in range(1, 13)])
        
        writer.writerow('')
        writer.writerow(['Mail'])

        for k1 in ['tel_spec',
                   'tel',
                   'tchat',
                   'mail',
                   'duree',
                   'f',
                   'h',
                   'hf',
                   '-18',
                   '19-40',
                   '41-65',
                   '+65',
                   'age_nd',
                   'inconnu',
                   'ocase',
                   'connu',
                   'quotidien',
                   'psychique',
                   'corona',
                   'physique',
                   'solitude',
                   'famille',
                   'relation',
                   'couple',
                   'travail',
                   'sociaux',
                   'violence',
                   'sexualite',
                   'spiritualite',
                   'dependance',
                   'suicide',
                   'mort',
                   'guerre',
                   'divers',
                   'lavi',
                   'vd',
                   'sos',
                   'vih',
                   ]:

            writer.writerow([k1]+[dict_res_mail[i][k1] for i in range(1, 13)])

        writer.writerow('')
        writer.writerow('')
        f.close()    
        # Assign generated file to wizard result
        self.result.name = file_name
        return 'result'

    def default_result(self, fields):
        """ Provides the generated file for download """
        file_name = self.result.name
        file_path = f"/tmp/{file_name}"

        # Read the generated file
        with codecs.open(file_path, 'rb', 'utf-8') as f:
            data = f.read()

        # Delete file after reading
        os.unlink(file_path)

        return {
            'name': file_name,
            'file': data.encode('utf8'),
        }

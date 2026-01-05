from trytond.wizard import Wizard, StateView, StateTransition, StateAction, Button
from trytond.model import ModelView, fields
from trytond.pool import Pool
from trytond.transaction import Transaction
import datetime
from trytond.pyson import Eval, PYSONEncoder
from decimal import Decimal

from trytond.model.exceptions import ValidationError

class BilanError(ValidationError):
    pass




__all__ = ["PLBilan", "PLBilanStart"]


class PLBilanStart(ModelView):
    "ProLibre Bilan Start"
    __name__ = "pl_cust_account.plbilan_start"

    date_start = fields.Date('Début')
    date_end = fields.Date('Fin')
    
    res_bilan = fields.Function(fields.Text('Bilan'),'on_change_with_res_bilan')

    @staticmethod
    def default_date_start():
        pool = Pool()
        Date = pool.get('ir.date')
        today = Date.today()
        date_string = '{}-01-01'.format(today.year)
        return datetime.datetime.strptime(date_string, '%Y-%m-%d').date()

    @staticmethod
    def default_date_end():
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today() 

    @fields.depends('date_start','date_end')
    def on_change_with_res_bilan(self, name=None):
        if not self.date_start or not self.date_end :
            return 'Donner une date de déput et de fin'
        pool = Pool()
        Account = pool.get('account.account')
        Acc_Type = pool.get('account.account.type')
        Move_Line = pool.get('account.move.line')
        INVOICES = pool.get('account.invoice')

        acc_type_id_charge = Acc_Type.search([('name', '=', 'Charges')])
        acc_type_id_produit = Acc_Type.search([('name', '=', 'Produits')])
        if not acc_type_id_charge or not acc_type_id_produit: 
            raise BilanError("Impossible de récupérer correctement les types de comptes ... contacter ProLibre")
        
        # Vérifie si le module devis est installé
        try:
            Devis_Line = Pool().get('pl_cust_devis.devisline')
            # Si on arrive ici, le module est installé
        except KeyError:
            Devis_Line = None

        # Vérifie si le module folders est installé
        try:
            Folders = Pool().get('pl_cust_plfolders.folders')
            # Si on arrive ici, le module est installé
        except KeyError:
            Folders = None
            
        all_account_charges = Account.search(['type', '=', acc_type_id_charge[0].id])
        all_account_produits = Account.search(['type', '=', acc_type_id_produit[0].id])

        all_move_line_charges = Move_Line.search([('account', 'in', (acc.id for acc in all_account_charges)),('date', '>=', self.date_start),('date', '<=', self.date_end)])
        all_move_line_produits = Move_Line.search([('account', 'in', (acc.id for acc in all_account_produits)),('date', '>=', self.date_start),('date', '<=', self.date_end)])

        tot_charges = 0
        tot_produits = 0
        tot_dl = 0
        tot_dl_open = 0


        day_now = self.date_end

        year_now = day_now.year

        premier_jour_annee = day_now.replace(day=1,month=1)
        dernier_jour_annee = day_now.replace(day=31,month=12)

        # Premier jour du mois courant
        premier_jour_mois = day_now.replace(day=1)

        # Calcul du dernier jour du mois suivant puis soustraction d'un jour pour obtenir le dernier jour du mois courant
        dernier_jour_mois = (day_now.replace(month=day_now.month % 12 + 1, day=1) - datetime.timedelta(days=1))

        # # Détermination du trimestre courant
        # trimestre = (day_now.month - 1) // 3 + 1
        # print(trimestre)
        # # Calcul du premier jour du trimestre
        # premier_jour_trimestre = datetime.date(day_now.year, 3 * trimestre - 2, 1)

        # # Calcul du dernier jour du trimestre
        # if trimestre < 4: 
        #     dernier_jour_trimestre = datetime.date(day_now.year, 3 * trimestre + 1, 1) - datetime.timedelta(days=1)
        # else:
        #     # Si c'est le dernier trimestre, calculer le dernier jour de l'année
        #     dernier_jour_trimestre = datetime.date(day_now.year, 12, 31)


        for c in all_move_line_charges :
            tot_charges += c.credit - c.debit

        for p in all_move_line_produits :
            tot_produits += p.credit - p.debit

        if Folders and Devis_Line : 
            all_fold_devis = Folders.search([('state','=','devis')])
            all_fold_open = Folders.search([('state','=','open')])

            for fold in all_fold_devis:
                for dl in fold.devis_lines :
                    if not dl.invoiced :
                        tot_dl += dl.price

            for fold in all_fold_open:
                for dl in fold.devis_lines :
                    if not dl.invoiced :
                        tot_dl_open += dl.price

        all_invoice_year = INVOICES.search([('type','=','out'),('state','in',('posted','paid')), ('invoice_date', '>=', '{}-01-01'.format(year_now)), ('invoice_date', '<=', '{}-12-31'.format(year_now))])
        all_invoice_month = INVOICES.search([('type','=','out'),('state','in',('posted','paid')), ('invoice_date', '>=', premier_jour_mois.strftime('%Y-%m-%d')), ('invoice_date', '<=', dernier_jour_mois.strftime('%Y-%m-%d'))]) 
        all_fc = INVOICES.search([('type','=','out'),('state','=','posted')]) 

        tot_fact_year = 0
        tot_fact_month = 0
        tot_fc = 0

        for inv in all_invoice_year :
            tot_fact_year += inv.untaxed_amount 
          
        for inv in all_invoice_month :
            tot_fact_month += inv.untaxed_amount 

        for inv in all_fc :
            tot_fc += inv.untaxed_amount 

        if Folders and Devis_Line :  
            return """
            Résultat : {:,.2f} (Produits : {:,.2f}  / Charges : {:,.2f})

            Facturation HT année en cours : {:,.2f} (mois en cours : {:,.2f})

            Factures clients ouvertes : {:,.2f}

            Travaux en cours à facturer : {:,.2f} 

            Devis en attente de validation : {:,.2f}""".format(tot_produits+tot_charges,tot_produits,tot_charges, tot_fact_year, tot_fact_month, tot_fc, tot_dl_open,tot_dl).replace(',',"'")
        else : 
            return """
            Résultat : {:,.2f} (Produits : {:,.2f}  / Charges : {:,.2f}

            Facturation HT année en cours : {:,.2f} (mois en cours : {:,.2f})

            Factures clients ouvertes : {:,.2f}""".format(tot_produits+tot_charges,tot_produits,tot_charges, tot_fact_year, tot_fact_month, tot_fc).replace(',',"'")
    
class PLBilan(Wizard):
    "ProLibre Bilan"
    __name__ = "pl_cust_account.plbilan"

    start = StateView(
        "pl_cust_account.plbilan_start",
        "pl_cust_account.wizard_bilanstart_view_form",
        [
            Button("Cancel", "end", "tryton-cancel"),
        ],
    )
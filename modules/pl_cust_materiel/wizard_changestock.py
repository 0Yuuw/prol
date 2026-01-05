from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.model import ModelView, fields
from trytond.pool import Pool
from trytond.transaction import Transaction
from datetime import datetime, date, timedelta, time
from trytond.pyson import Eval
from decimal import Decimal
import codecs
import os
import csv

from trytond.model.exceptions import ValidationError
from trytond.exceptions import UserWarning

class CheckWarning(UserWarning):
    pass

class NBError(ValidationError):
    pass

__all__ = ['ChangeStock', 'ChangeStockStart', 'ChangeStockStep2']

class ChangeStockStart(ModelView):
    "ChangeStockStart"
    __name__ = 'pl_cust_materiel.changestock_start'

    date_start = fields.Date("Date Start", required=True)
    date_end = fields.Date("Date End", readonly=True, required=True)

    materiel = fields.Many2One("pl_cust_materiel.materiel", "Materiel", required=True)
    qty = fields.Integer("Quantity", required=True)
    
    @staticmethod
    def default_date_start():
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today() 

    @fields.depends('date_start', 'date_end')
    def on_change_date_start(self):
        if self.date_start and not self.date_end:
            # Ajout de 2 an à la date de début
            self.date_end = self.date_start.replace(year=self.date_start.year + 2)
        
class ChangeStockStep2(ModelView):
    "ChangeStockStep2"
    __name__ = 'pl_cust_materiel.changestock_step2'

    date_start = fields.Date("Date Start", readonly=True, required=True)
    date_end = fields.Date("Date End", readonly=True, required=True)
    materiel = fields.Many2One("pl_cust_materiel.materiel", "Materiel", readonly=True, required=True)
    logs_info = fields.Selection([('other', 'Autre'),('casse', 'Cassé'), ('vol', 'Volé'), ('old', 'Obsolète')], "Logs Info", required=True)
    qty = fields.Integer("Quantity",readonly=True)
    description = fields.Text("Description")
    manifestations = fields.One2Many("pl_cust_materiel.manifestation", None, "Manifestations", readonly=True)

class ChangeStock(Wizard):
    "ChangeStock"
    __name__ = "pl_cust_materiel.changestock"

    start = StateView('pl_cust_materiel.changestock_start',
                      'pl_cust_materiel.changestock_start_view_form', [
                          Button('Cancel', 'end', 'tryton-cancel'),
                          Button('Check', 'check',
                                 'tryton-ok', default=True),
                      ])

    step2 = StateView('pl_cust_materiel.changestock_step2',
                      'pl_cust_materiel.changestock_step2_view_form', [
                          Button('Cancel', 'end', 'tryton-cancel'),
                          Button('Change Stock', 'changestock',
                                 'tryton-ok', default=True),
                      ])

    check = StateTransition()
    changestock = StateTransition()

    def transition_check(self):
        return 'step2'

    def transition_changestock(self):
        pool = Pool()
        Manifs = pool.get('pl_cust_materiel.manifestation')
        Location = pool.get('pl_cust_materiel.location')
        Logs = pool.get('pl_cust_materiel.logs')

        logs_tmp = self.step2.description and "{}\n\n".format(self.step2.description) or ""
    
        if self.step2.manifestations:
            raise NBError('Il faut règler le problème des manifestations qui vont utiliser ce matériel!!!')
        else:
            self.step2.materiel.qty += self.step2.qty
            if self.step2.materiel.qty < 0 :
                raise NBError('Opération impossible sinon il y aurait un chiffre négatif dans le stock!!!')
            self.step2.materiel.save()

        if self.start.qty > 0 :
            logs_tmp += 'Ajout de {} {}\n'.format(self.step2.qty, self.step2.materiel.name, )
        else :
            logs_tmp += 'Suppression de {} {}\n'.format(abs(self.step2.qty), self.step2.materiel.name)

        log = Logs.create([{
                    'logs_type' : 'stock',
                    'logs_info' : self.step2.logs_info,
                    'description' : logs_tmp,
                    'materiel' : self.step2.materiel.id
                }])    


        return 'end'

    def default_step2(self,fields) :
        def daterange(start, end):
            for n in range((end - start).days + 1):
                yield start + timedelta(n)

        pool = Pool()
        Materiels = pool.get('pl_cust_materiel.materiel')
        Manifs = pool.get('pl_cust_materiel.manifestation')
    
        crit1 = ('date_start', '<=', self.start.date_end)  
        crit2 = ('date_end', '>=', self.start.date_start)
                    
        all_manifs = Manifs.search([
                crit1,
                crit2,
            ])

        lines = []

        if self.start.qty < 0:
            materiel = self.start.materiel 

            daily_rented = {d: 0 for d in daterange(self.start.date_start, self.start.date_end)}

            for manif in all_manifs : 
                overlap_start = max(self.start.date_start, manif.date_start)
                overlap_end = min(self.start.date_end, manif.date_end)
                for loc in manif.locations :
                    if loc.materiel.id == materiel.id :
                        lines.append(manif.id)
                        for day in daterange(overlap_start, overlap_end):
                            daily_rented[day] += loc.qty

            peak = max(daily_rented.values(), default=0)

            if materiel.qty - peak - abs(self.start.qty) >= 0 :
                 lines = []

        return {
            'date_start' : self.start.date_start,
            'date_end' :  self.start.date_end,
            'materiel' :  self.start.materiel.id,
            'qty' :  self.start.qty,
            'manifestations' : lines,    
        }


   

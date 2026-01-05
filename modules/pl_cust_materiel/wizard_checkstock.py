from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.model import ModelView, fields
from trytond.pool import Pool
from trytond.transaction import Transaction
from datetime import datetime, date, timedelta, time
from trytond.pyson import Eval, If
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

__all__ = ['CheckStock', 'CheckStockStart', 'CheckStockStep2', 'LocationTMP2']

class LocationTMP2(ModelView):
    "LocationTMP2"
    __name__ = "pl_cust_materiel.location_tmp2"

    materiel = fields.Many2One("pl_cust_materiel.materiel", "Materiel", readonly=True)
    qty_disp = fields.Integer("Quantity Disp", readonly=True)

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('/tree', 'visual', If(Eval('qty_disp', 0) == 0, 'danger', '')),
        ]

class CheckStockStart(ModelView):
    "CheckStockStart"
    __name__ = 'pl_cust_materiel.checkstock_start'

    date_start = fields.Date("Date Start", required=True)

    @staticmethod
    def default_date_start():
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today() 

class CheckStockStep2(ModelView):
    "CheckStockStep2"
    __name__ = 'pl_cust_materiel.checkstock_step2'

    locations_tmp1 = fields.One2Many("pl_cust_materiel.location_tmp2", None, "Non disponible")
    locations_tmp2 = fields.One2Many("pl_cust_materiel.location_tmp2", None, "Disponible")
    
class CheckStock(Wizard):
    "CheckStock"
    __name__ = "pl_cust_materiel.checkstock"

    start = StateView('pl_cust_materiel.checkstock_start',
                      'pl_cust_materiel.checkstock_start_view_form', [
                          Button('Cancel', 'end', 'tryton-cancel'),
                          Button('Check', 'check',
                                 'tryton-ok', default=True),
                      ])

    step2 = StateView('pl_cust_materiel.checkstock_step2',
                      'pl_cust_materiel.checkstock_step2_view_form', [
                          Button('OK', 'end', 'tryton-ok'),
                      ])

    check = StateTransition()

    def transition_check(self):
        return 'step2'

    def default_step2(self,fields) :
        def daterange(start, end):
            for n in range((end - start).days + 1):
                yield start + timedelta(n)

        pool = Pool()
        Materiels = pool.get('pl_cust_materiel.materiel')
        Manifs = pool.get('pl_cust_materiel.manifestation')
        LocationTMPS2 = pool.get('pl_cust_materiel.location_tmp2')

        crit1 = ('date_start', '<=', self.start.date_start)
        crit2 = ('date_end', '>=', self.start.date_start)
                    
        all_manifs = Manifs.search([
                crit1,
                crit2,
            ])

        lines1 = []
        lines2 = []
        for materiel in Materiels.search([]):
            daily_rented = {d: 0 for d in daterange(self.start.date_start, self.start.date_start)}
            
            for manif in all_manifs : 
                overlap_start = max(self.start.date_start, manif.date_start)
                overlap_end = min(self.start.date_start, manif.date_end)
                for loc in manif.locations :
                    if loc.materiel.id == materiel.id :
                        for day in daterange(overlap_start, overlap_end):
                            daily_rented[day] += loc.qty

            peak = max(daily_rented.values(), default=0)
            line = {
                    'materiel' : materiel.id,
                    'qty_disp' : materiel.qty - peak,
            }

            if materiel.qty - peak > 0 : 
                lines2.append(line)
            else :
                lines1.append(line)
   

        return {
            'locations_tmp1' : lines1,    
            'locations_tmp2' : lines2,    
        }


   

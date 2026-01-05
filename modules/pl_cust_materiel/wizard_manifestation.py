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

__all__ = ['AddManif', 'AddManifStart', 'AddManifStep2', 'AddManifStep3', 'LocationTMP']

class LocationTMP(ModelView):
    "LocationTMP"
    __name__ = "pl_cust_materiel.location_tmp"

    materiel = fields.Many2One("pl_cust_materiel.materiel", "Materiel", readonly=True)
    qty_disp = fields.Integer("Quantity Disp", readonly=True)
    qty = fields.Integer("Quantity", domain=[('qty', '>=', 0)])
    check = fields.Function(fields.Boolean("qty > disp"), 'get_check')

    def get_check(self, name):
        return self.qty > self.qty_disp
    
    @fields.depends('qty', 'qty_disp')
    def on_change_with_check(self):
        return self.qty > self.qty_disp

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('/tree', 'visual', If(Eval('check'), 'danger', If(~Eval('qty_disp'), 'warning', ''))),
        ]

class AddManifStart(ModelView):
    "AddManifStart"
    __name__ = 'pl_cust_materiel.addmanif_start'

    date_start = fields.Date("Date Start", required=True)
    time_start = fields.Time('Hours Start', format='%H:%M')
    afternoon = fields.Boolean('Afternoon')
    date_end = fields.Date("Date End", required=True)
    time_end = fields.Time('Hours End', format='%H:%M')
    morning = fields.Boolean('Morning')

class AddManifStep2(ModelView):
    "AddManifStep2"
    __name__ = 'pl_cust_materiel.addmanif_step2'

    name = fields.Char("Name", required=True)
    localisation = fields.Many2One("pl_cust_materiel.lieumanif", "Localisation", required=True)
    description = fields.Text("Description")
    date_start = fields.Date("Date Start", readonly=True, required=True)
    time_start = fields.Time('Hours Start', format='%H:%M', readonly=True,)
    afternoon = fields.Boolean('Afternoon', readonly=True)
    date_end = fields.Date("Date End", readonly=True, required=True)
    time_end = fields.Time('Hours End', format='%H:%M', readonly=True)
    morning = fields.Boolean('Morning', readonly=True)
    party = fields.Many2One("party.party", "Party", required=True)
    locations_tmp = fields.One2Many("pl_cust_materiel.location_tmp", None, "Locations")
    datetime_start = fields.DateTime("DateTime Start", readonly=True)
    datetime_end = fields.DateTime("DateTime End", readonly=True)

class AddManifStep3(ModelView):
    "AddManifStep3"
    __name__ = 'pl_cust_materiel.addmanif_step3'

    name = fields.Char("Name",  readonly=True, required=True)
    localisation = fields.Many2One("pl_cust_materiel.lieumanif", "Localisation", readonly=True, required=True)
    description = fields.Text("Description", readonly=True)
    date_start = fields.Date("Date Start", readonly=True, required=True)
    time_start = fields.Time('Hours Start', format='%H:%M', readonly=True)
    afternoon = fields.Boolean('Afternoon', readonly=True)
    date_end = fields.Date("Date End", readonly=True, required=True)
    time_end = fields.Time('Hours End', format='%H:%M', readonly=True)
    morning = fields.Boolean('Morning', readonly=True)
    party = fields.Many2One("party.party", "Party", readonly=True, required=True)
    locations_tmp = fields.One2Many("pl_cust_materiel.location_tmp", None, "Locations")
    datetime_start = fields.DateTime("DateTime Start", readonly=True)
    datetime_end = fields.DateTime("DateTime End", readonly=True)

class AddManif(Wizard):
    "AddManif"
    __name__ = "pl_cust_materiel.addmanif"

    start = StateView('pl_cust_materiel.addmanif_start',
                      'pl_cust_materiel.addmanif_start_view_form', [
                          Button('Cancel', 'end', 'tryton-cancel'),
                          Button('Check', 'check',
                                 'tryton-ok', default=True),
                      ])

    step2 = StateView('pl_cust_materiel.addmanif_step2',
                      'pl_cust_materiel.addmanif_step2_view_form', [
                          Button('Cancel', 'end', 'tryton-cancel'),
                          Button('Continuer', 'final',
                                 'tryton-ok', default=True),
                      ])

    step3 = StateView('pl_cust_materiel.addmanif_step3',
                      'pl_cust_materiel.addmanif_step3_view_form', [
                          Button('Cancel', 'end', 'tryton-cancel'),
                          Button('Retour', 'check', 'tryton-cancel'),
                          Button('Create Manif', 'add_manif',
                                 'tryton-ok', default=True),
                      ])

    check = StateTransition()
    final = StateTransition()

    add_manif = StateTransition()

    def transition_check(self):

        if self.start.date_end < self.start.date_start :
            raise NBError('Merci de mettre une date de fin après la date de début')

        pool = Pool()
        MatDay = pool.get('pl_cust_materiel.matday')

        md_start = MatDay.search([('date', '=', self.start.date_start)])
        md_end = MatDay.search([('date', '=', self.start.date_end)])

        if not md_start :
            raise NBError('Il faut faire tourner le wizard des jours avant de crééer cette manifestation pour cette date {}'.format(self.start.date_start))

        if not md_end :
            raise NBError('Il faut faire tourner le wizard des jours avant de crééer cette manifestation pour cette date {}'.format(self.start.date_end))

        return 'step2'

    def transition_final(self):
        return 'step3'

    def transition_add_manif(self):
        pool = Pool()
        Manifs = pool.get('pl_cust_materiel.manifestation')
        Location = pool.get('pl_cust_materiel.location')
        Logs = pool.get('pl_cust_materiel.logs')
        MatDay = pool.get('pl_cust_materiel.matday')
        MatDayList = pool.get('pl_cust_materiel.matdaylist')
        mat_lists_txt = ''

        new_manif = Manifs.create([{
            'name' : self.step2.name,
            'localisation' : self.step2.localisation,
            'description' : self.step2.description,
            'date_start' :  self.step2.date_start,
            'time_start' : self.step2.time_start,
            'afternoon' : self.step2.afternoon,
            'date_end' : self.step2.date_end,
            'time_end' : self.step2.time_end,
            'morning' : self.step2.morning,
            'party' : self.step2.party,
            'datetime_start' : self.step2.datetime_start,
            'datetime_end' : self.step2.datetime_end
            }])

        logs_tmp = ""
        for loctmp in self.step3.locations_tmp :
            if loctmp.qty : 
                if loctmp.qty > loctmp.qty_disp :
                    raise NBError('Pas possible de louer plus que ce qui est disponible!!!')

                loc = Location.create([{
                    'materiel' : loctmp.materiel.id,
                    'qty' : loctmp.qty,
                    'manifestation' : new_manif[0].id
                }])  

                logs_tmp += '{} : {}\n'.format(loctmp.materiel.name, loctmp.qty)
                mat_lists_txt += '| {} : {}\n'.format(loctmp.qty, loctmp.materiel.name)
        
        log = Logs.create([{
                    'logs_type' : 'create',
                    'description' : logs_tmp,
                    'manifestation' : new_manif[0].id
                }])    

        md_start = MatDay.search([('date', '=', self.step2.date_start)])
        md_end = MatDay.search([('date', '=', self.step2.date_end)])


        if md_start :
            MatDayList.create([{'manifestation':new_manif[0].id,
                                'matdaystart': md_start[0],
                                'mat_list' : mat_lists_txt,
                                'mat_com' : self.step2.description or ''}])
        else :
            raise NBError('Il faut faire tourner le wizard des jours avant de crééer cette manifestation')

        
        if md_end :
            MatDayList.create([{'manifestation':new_manif[0].id,
                                'matdayend': md_end[0],
                                'mat_list' : mat_lists_txt,
                                'mat_com' : self.step2.description or ''}])
        else : 
            raise NBError('Il faut faire tourner le wizard des jours avant de crééer cette manifestation')


        return 'end'

    def default_step2(self,fields) :
        def daterange(start, end):
            for n in range((end - start).days + 1):
                yield start + timedelta(n)

        pool = Pool()
        Materiels = pool.get('pl_cust_materiel.materiel')
        Manifs = pool.get('pl_cust_materiel.manifestation')
        LocationTMPS = pool.get('pl_cust_materiel.location_tmp')

        # Récupérer toutes les manifestations qui chevauchent la période
        if self.start.morning:
            crit1 = ('OR',('date_start', '<', self.start.date_end), (('date_start', '=', self.start.date_end),('afternoon', '=', False)))
        else :
            crit1 = ('date_start', '<=', self.start.date_end)

        if self.start.afternoon: 
            crit2 = ('OR',('date_end', '>', self.start.date_start),(('date_end', '=', self.start.date_start),('morning', '=', False)))
        else :
            crit2 = ('date_end', '>=', self.start.date_start)
                    
        all_manifs = Manifs.search([
                crit1,
                crit2,
            ])
        lines = []

        for materiel in Materiels.search([]):
            daily_rented = {d: 0 for d in daterange(self.start.date_start, self.start.date_end)}
            line = None
            for manif in all_manifs : 
                overlap_start = max(self.start.date_start, manif.date_start)
                overlap_end = min(self.start.date_end, manif.date_end)
                for loc in manif.locations :
                    if loc.materiel.id == materiel.id :
                        for day in daterange(overlap_start, overlap_end):
                            daily_rented[day] += loc.qty

            peak = max(daily_rented.values(), default=0)

            if hasattr(self.step3,'locations_tmp'):
                for loctmp in self.step3.locations_tmp :
                    if loctmp.materiel.id ==  materiel.id: 
                        line = {
                            'materiel' : loctmp.materiel.id,
                            'qty_disp' : materiel.qty - peak,
                            'qty' : loctmp.qty
                    }

            if not line : 
                line = {
                    'materiel' : materiel.id,
                    'qty_disp' : materiel.qty - peak,
                    'qty' : 0
                }

            lines.append(line)

        return {
            'date_start' : self.start.date_start,
            'time_start' :  self.start.time_start,
            'afternoon' :  self.start.afternoon,
            'date_end' :  self.start.date_end,
            'time_end' :  self.start.time_end,
            'morning' :  self.start.morning,
            'locations_tmp' : lines,    
            'datetime_start' :  self.start.afternoon and datetime.combine(self.start.date_start, time(10, 0)) or datetime.combine(self.start.date_start, time(5, 59)), 
            'datetime_end' :  self.start.morning and datetime.combine(self.start.date_end, time(10, 0)) or datetime.combine(self.start.date_end, time(21, 59)),
            'name' : hasattr(self.step3,'name') and self.step3.name or None,
            'localisation' : hasattr(self.step3,'localisation') and self.step3.localisation.id or None,
            'description' : hasattr(self.step3,'description') and self.step3.description or '',
            'party' : hasattr(self.step3,'party') and self.step3.party.id or None,
        }

    def default_step3(self,fields) :
        
        lines = []
        for loctmp in self.step2.locations_tmp :
            if loctmp.qty : 
                line = {
                    'materiel' : loctmp.materiel.id,
                    'qty_disp' : loctmp.qty_disp,
                    'qty' : loctmp.qty
                }

                lines.append(line)

        return {
            'date_start' : self.step2.date_start,
            'time_start' :  self.step2.time_start,
            'afternoon' :  self.step2.afternoon,
            'date_end' :  self.step2.date_end,
            'time_end' :  self.step2.time_end,
            'morning' :  self.step2.morning,
            'locations_tmp' : lines,   
            'datetime_start' :  self.step2.datetime_start,
            'datetime_end' :  self.step2.datetime_end,
            'name' : self.step2.name,
            'localisation' : self.step2.localisation.id,
            'description' : self.step2.description,
            'party' : self.step2.party.id
        }

   

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

__all__ = ['ChangeManif', 'ChangeManifStart', 'ChangeManifStep2', 'ChangeManifStep3']

class ChangeManifStart(ModelView):
    "ChangeManifStart"
    __name__ = 'pl_cust_materiel.changemanif_start'

    manif = fields.Many2One("pl_cust_materiel.manifestation", "Manifestation", readonly=True)
    date_start = fields.Date("Date Start", required=True)
    time_start = fields.Time('Hours Start', format='%H:%M')
    afternoon = fields.Boolean('Afternoon')
    date_end = fields.Date("Date End", required=True)
    time_end = fields.Time('Hours End', format='%H:%M')
    morning = fields.Boolean('Morning')

    @staticmethod
    def default_manif():
        if Transaction().context.get("active_model", "") == "pl_cust_materiel.manifestation":
            return Transaction().context.get("active_id", "")
        return None

    @fields.depends('manif')
    def on_change_manif(self):
        if self.manif : 
           self.date_start = self.manif.date_start 
           self.date_end = self.manif.date_end
           self.time_start = self.manif.time_start
           self.time_end = self.manif.time_end
           self.afternoon = self.manif.afternoon
           self.morning = self.manif.morning

class ChangeManifStep2(ModelView):
    "ChangeManifStep2"
    __name__ = 'pl_cust_materiel.changemanif_step2'

    manif = fields.Many2One("pl_cust_materiel.manifestation", "Manifestation", readonly=True)
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

class ChangeManifStep3(ModelView):
    "ChangeManifStep2"
    __name__ = 'pl_cust_materiel.changemanif_step3'

    manif = fields.Many2One("pl_cust_materiel.manifestation", "Manifestation", readonly=True)
    name = fields.Char("Name", required=True, readonly=True)
    localisation = fields.Many2One("pl_cust_materiel.lieumanif", "Localisation", required=True, readonly=True)
    description = fields.Text("Description", readonly=True)
    date_start = fields.Date("Date Start", readonly=True, required=True)
    time_start = fields.Time('Hours Start', format='%H:%M', readonly=True,)
    afternoon = fields.Boolean('Afternoon', readonly=True)
    date_end = fields.Date("Date End", readonly=True, required=True)
    time_end = fields.Time('Hours End', format='%H:%M', readonly=True)
    morning = fields.Boolean('Morning', readonly=True)
    party = fields.Many2One("party.party", "Party", required=True, readonly=True)
    locations_tmp = fields.One2Many("pl_cust_materiel.location_tmp", None, "Locations")
    datetime_start = fields.DateTime("DateTime Start", readonly=True)
    datetime_end = fields.DateTime("DateTime End", readonly=True)

class ChangeManif(Wizard):
    "ChangeManif"
    __name__ = "pl_cust_materiel.changemanif"

    start = StateView('pl_cust_materiel.changemanif_start',
                      'pl_cust_materiel.changemanif_start_view_form', [
                          Button('Cancel', 'end', 'tryton-cancel'),
                          Button('Check', 'check',
                                 'tryton-ok', default=True),
                      ])

    step2 = StateView('pl_cust_materiel.changemanif_step2',
                      'pl_cust_materiel.changemanif_step2_view_form', [
                          Button('Cancel', 'end', 'tryton-cancel'),
                          Button('Continuer', 'final',
                                 'tryton-ok', default=True),
                      ])

    step3 = StateView('pl_cust_materiel.changemanif_step3',
                      'pl_cust_materiel.changemanif_step3_view_form', [
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
            raise NBError('Il faut faire tourner le wizard des jours avant de modifier cette manifestation pour cette date {}'.format(self.start.date_start))

        if not md_end :
            raise NBError('Il faut faire tourner le wizard des jours avant de modifier cette manifestation pour cette date {}'.format(self.start.date_end))

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

        self.step2.manif.name = self.step2.name
        self.step2.manif.localisation = self.step2.localisation.id
        self.step2.manif.description = self.step2.description
        self.step2.manif.date_start = self.step2.date_start
        self.step2.manif.time_start = self.step2.time_start
        self.step2.manif.date_end = self.step2.date_end
        self.step2.manif.time_end = self.step2.time_end
        self.step2.manif.afternoon = self.step2.afternoon
        self.step2.manif.morning = self.step2.morning
        self.step2.manif.party = self.step2.party.id
        self.step2.manif.datetime_start = self.step2.datetime_start
        self.step2.manif.datetime_end = self.step2.datetime_end
        self.step2.manif.save()

        mdl = MatDayList.search([('manifestation', '=', self.step2.manif)])

        print('MDL {}'.format(mdl))
        MatDayList.delete(mdl)
    
        Location.delete(self.step2.manif.locations)

        logs_tmp = ""
       
        for loctmp in self.step3.locations_tmp :
            if loctmp.qty : 
                if loctmp.qty > loctmp.qty_disp :
                    raise NBError('Pas possible de louer plus que ce qui est disponible!!!')

                loc = Location.create([{
                    'materiel' : loctmp.materiel.id,
                    'qty' : loctmp.qty,
                    'manifestation' : self.step2.manif.id
                }])    
                logs_tmp += '{} : {}\n'.format(loctmp.materiel.name, loctmp.qty)
                mat_lists_txt += '| {} : {}\n'.format(loctmp.qty, loctmp.materiel.name)

        log = Logs.create([{
                    'logs_type' : 'change',
                    'description' : logs_tmp,
                    'manifestation' : self.step2.manif.id
                }])    


        md_start = MatDay.search([('date', '=', self.step2.date_start)])
        md_end = MatDay.search([('date', '=', self.step2.date_end)])
       
        if md_start :
            MatDayList.create([{'manifestation': self.step2.manif.id,
                                'matdaystart': md_start[0],
                                'mat_list' : mat_lists_txt}])
        else:
            raise NBError('Il faut faire tourner le wizard des jours avant de modifier cette manifestation')

        
        if md_end :
            MatDayList.create([{'manifestation': self.step2.manif.id,
                                'matdayend': md_end[0],
                                'mat_list' : mat_lists_txt}])
        else:
            raise NBError('Il faut faire tourner le wizard des jours avant de modifier cette manifestation')


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

        manif_mat = {}

        for loc in self.start.manif.locations: 
            manif_mat[loc.materiel.id] = loc.qty

        for materiel in Materiels.search([]):
            daily_rented = {d: 0 for d in daterange(self.start.date_start, self.start.date_end)}
            line = None

            for manif in all_manifs : 
                if manif.id == self.start.manif.id :
                    continue 
                
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
                    'qty' : manif_mat.get(materiel.id,0),
                    'check' : materiel.qty > (materiel.qty - peak )
                }

            #if line['qty_disp'] > 0 or manif_mat.get(materiel.id,0):
            lines.append(line)

        return {
            'manif' : self.start.manif.id,
            'date_start' : self.start.date_start,
            'time_start' :  self.start.time_start,
            'afternoon' :  self.start.afternoon,
            'date_end' :  self.start.date_end,
            'time_end' :  self.start.time_end,
            'morning' :  self.start.morning,
            'locations_tmp' : lines,    
            'datetime_start' :  self.start.afternoon and datetime.combine(self.start.date_start, time(10, 0)) or datetime.combine(self.start.date_start, time(5, 59)), 
            'datetime_end' :  self.start.morning and datetime.combine(self.start.date_end, time(10, 0)) or datetime.combine(self.start.date_end, time(21, 59)), 
            'localisation' : self.start.manif.localisation and self.start.manif.localisation.id or None,
            'description' : self.start.manif.description,
            'name' : self.start.manif.name,
            'party' : self.start.manif.party.id,
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


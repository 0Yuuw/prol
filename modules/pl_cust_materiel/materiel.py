# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import requests
from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.report import Report
from trytond.model import (
    ModelView,
    ModelSQL,
    MultiValueMixin,
    ModelSingleton,
    ValueMixin,
    Unique,
    fields,
)
from trytond.pyson import Bool, Eval, If, Or
from trytond.transaction import Transaction
from trytond.model.exceptions import ValidationError
from datetime import datetime, time

__all__ = ["Atelier", "LieuManif", "Materiel", "Location", "Manifestation", "Logs", "MatDay", "MatDayList"]

COLOR_CHOICES = [
    ('#6D9DC5', 'Bleu pastel'),
    ('#A18594', 'Rose poussiéreux'),
    ('#B0C4A8', 'Sauge'),
    ('#A0A5D7', 'Indigo doux'),
    ('#D4A5A5', 'Rose fané'),
    ('#C1BBAF', 'Taupe'),
    ('#9C9F84', 'Gris olive'),
    ('#B4A7D6', 'Lavande grise'),
    ('#C7B299', 'Sable doux'),
    ('#C79ECF', 'Mauve'),
    ('#9FC5E8', 'Bleu ciel'),
    ('#A4D3C0', 'Vert d’eau'),
    ('#BAA0A0', 'Argile'),
    ('#ADAAA1', 'Pierre'),
    ('#B8B8D1', 'Bleu pervenche'),
    ('#CABFAB', 'Beige chaud'),
    ('#BEB7A4', 'Amande terreuse'),
    ('#C3B4D6', 'Violet doux'),
    ('#8FA5B5', 'Bleu acier'),
    ('#91C6C0', 'Brume turquoise'),
    ('#CBAACB', 'Lilas'),
    ('#D6AEDD', 'Orchidée pastel'),
    ('#D4B483', 'Camel clair'),
    ('#BFD8B8', 'Brume verte'),
    ('#D2A6A1', 'Blush'),
    ('#C5CBE1', 'Lavande froide'),
    ('#B2A198', 'Rose cendré'),
    ('#97B5C6', 'Bleu givré'),
    ('#B5B9B1', 'Brume'),
    ('#BDC4A7', 'Gris mousse'),
    ('#BBADC1', 'Violet poussiéreux'),
    ('#D6C3B8', 'Argile douce'),
    ('#95A1B1', 'Brume d’ardoise'),
    ('#B4CEB3', 'Sauge pâle'),
    ('#D3B3B0', 'Corail doux'),
    ('#C2C6D0', 'Gris poudreux'),
    ('#A6B1C3', 'Brume bleutée'),
    ('#ADA7C9', 'Brume de raisin'),
    ('#B2A8A0', 'Cacao doux'),
    ('#B7C9B8', 'Argile mentholée'),
    ('#C9ADC9', 'Brume pétale'),
    ('#ACC7B4', 'Menthe fraîche'),
    ('#C1C3D1', 'Fumée lavande'),
    ('#D5A6BD', 'Rose poussière'),
    ('#C1D1B0', 'Olive lavée'),
    ('#B3B9D6', 'Brume bleue'),
    ('#C4A69F', 'Rose antique'),
    ('#B7C2A1', 'Pistache pâle'),
    ('#B8B0A9', 'Argile grise'),
    ('#C9B2BD', 'Brume rosée'),
]

COLOR_LIST = [code for code, _ in COLOR_CHOICES]

class MatDayList(ModelSQL,ModelView):
    "MatDayList"
    __name__ = "pl_cust_materiel.matdaylist"

    matdaystart = fields.Many2One("pl_cust_materiel.matday", "MatDayStart", readonly=True, ondelete="RESTRICT")
    matdayend = fields.Many2One("pl_cust_materiel.matday", "MatDayEnd", readonly=True, ondelete="RESTRICT")

    manifestation = fields.Many2One("pl_cust_materiel.manifestation", "Manifestation", readonly=True)
    localisation = fields.Function(fields.Char("Lieu"), 'on_change_with_localisation')

    mat_list = fields.Text('Mat list', readonly=True)
    mat_com = fields.Text('Coms')
    
    @staticmethod
    def default_mat_list():
        return ''
    
    @staticmethod
    def default_mat_com():
        return ''

    @fields.depends('manifestation', 'matdaystart')
    def on_change_with_localisation(self, name=None):

        res = self.manifestation and self.manifestation.localisation and self.manifestation.localisation.name or ''

        if self.matdaystart and self.manifestation.afternoon:
            res += ' | Après midi'
        elif self.matdayend and self.manifestation.morning:
            res += ' | Matin'
        
        if self.matdaystart and self.manifestation.time_start:
            res += ' | {}'.format(self.manifestation.time_start.strftime('%H:%M'))
        elif self.matdayend and self.manifestation.time_end:
            res += ' | {}'.format(self.manifestation.time_end.strftime('%H:%M'))

        return res 

class MatDay(ModelSQL,ModelView):
    "MatDay"
    __name__ = "pl_cust_materiel.matday"

    date = fields.Date("Date Start", required=True)
    mdl_start = fields.One2Many("pl_cust_materiel.matdaylist", 'matdaystart', "MatDayLists Start", readonly=True)
    mdl_end = fields.One2Many("pl_cust_materiel.matdaylist", 'matdayend', "MatDayLists End", readonly=True)
    infos = fields.Text('Infos')
    
    @staticmethod
    def default_infos():
        return ''

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            (
                "date_uniq",
                Unique(t, t.date),
                "Attention !! Il y a déjà un jour avec cette date",
            ),
        ]
        cls._order.insert(0, ("date", "ASC"))

class Logs(ModelSQL, ModelView):
    "Logs"
    __name__ = "pl_cust_materiel.logs"

    date = fields.Date("Date Start", required=True)
    logs_type = fields.Selection([('create', 'Création'), ('change', 'Modification'), ('repair', 'Réparation'), ('stock', 'Modif. Stock')], "Logs Type", required=True)
    logs_info = fields.Selection([('other', 'Autre'),('casse', 'Cassé'), ('vol', 'Volé'), ('old', 'Obsolète')], "Logs Info")
    user = fields.Char("User", required=True)
    description = fields.Text("Description")
    materiel = fields.Many2One("pl_cust_materiel.materiel", "Materiel", ondelete="RESTRICT")
    manifestation = fields.Many2One("pl_cust_materiel.manifestation", "Manifestation", ondelete="RESTRICT")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order = [
            ("id", "DESC"),
        ]

    @staticmethod
    def default_date():
        Date = Pool().get('ir.date')
        return Date.today()

    @staticmethod
    def default_logs_info():
        return 'other' 

    @staticmethod
    def default_user():
        User = Pool().get('res.user')
        user = User(Transaction().user)
        return user.name

class LieuManif(ModelSQL, ModelView):
    "Atelier"
    __name__ = "pl_cust_materiel.lieumanif"

    name = fields.Char("Name", required=True)
    description = fields.Text("Description")
    
    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order = [
            ("name", "ASC"),
        ]

class Atelier(ModelSQL, ModelView):
    "Atelier"
    __name__ = "pl_cust_materiel.atelier"

    name = fields.Char("Name", required=True)
    description = fields.Text("Description")
    
    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order = [
            ("name", "DESC"),
        ]

class Materiel(ModelSQL, ModelView):
    "Materiel"
    __name__ = "pl_cust_materiel.materiel"

    name = fields.Char("Name", required=True)
    description = fields.Text("Description")
    price = fields.Float("Price")
    qty = fields.Integer("Quantity", states={'readonly': Bool(Eval('color',False))}, depends=['color'])
    atelier = fields.Many2One("pl_cust_materiel.atelier", "Atelier")
    locations = fields.One2Many("pl_cust_materiel.location", "materiel", "Locations", readonly=True)
    logs = fields.One2Many("pl_cust_materiel.logs", "materiel", "Logs", readonly=True)
    color = fields.Function(fields.Char("Couleur"), 'get_color')
    as_attachment = fields.Function(fields.Boolean('pj'), 'get_as_attachement')

    @classmethod
    def get_as_attachement(cls, invoices, name):
        pool = Pool()
        ATTACH = pool.get('ir.attachment')

        res = {i.id: False for i in invoices}
        for inv in invoices : 
            if ATTACH.search([('resource', '=', inv)]) :
                res[inv.id] = True
        return res

    def get_color(self, name):
        if self.id:
            index = self.id % len(COLOR_LIST)
            return COLOR_LIST[index]
        return None

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order = [
            ("name", "ASC"),
        ]

    @classmethod
    def default_qty(cls):
        return 0

  
class Location(ModelSQL, ModelView):
    "Location"
    __name__ = "pl_cust_materiel.location"

    materiel = fields.Many2One("pl_cust_materiel.materiel", "Materiel", readonly=True)

    qty = fields.Integer("Quantity", readonly=False)
    manifestation = fields.Many2One("pl_cust_materiel.manifestation", "Manifestation", ondelete="RESTRICT", readonly=True)
    repa = fields.Boolean('Repair?')
    repa_ok = fields.Boolean('Repair_ok?')

    date_start = fields.Function(fields.Date("Date Start"), 'get_vals', searcher='search_date')
    time_start = fields.Function(fields.Time('Hours Start', format='%H:%M'), 'get_vals')
    afternoon = fields.Function(fields.Boolean("Afternoon"), 'get_vals') 
    date_end = fields.Function(fields.Date("Date End"), 'get_vals', searcher='search_date')
    time_end = fields.Function(fields.Time('Hours End', format='%H:%M'), 'get_vals')
    morning = fields.Function(fields.Boolean("Morning"), 'get_vals')
    color = fields.Function(fields.Char("Color"), 'get_vals')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        
        cls._buttons.update(
            {
                "return_repair": {
                    "invisible": Or(~Eval("repa"), Eval("repa_ok")),
                    "depends": ["repa"],
                },
            
            }
        )

    @classmethod
    def search_date(cls, name, clause):
        # clause = (field_name, operator, value)
        _, operator, value = clause

        print('//////// {}'.format(clause))
        Manif = Pool().get('pl_cust_materiel.manifestation')

        # On cherche les IDs des objets liés qui ont la date demandée
        ids = Manif.search([(name, operator, value)])

        # Puis on retourne une clause de recherche sur le Many2One
        return [('manifestation', 'in', ids)]


    @classmethod
    def get_vals(cls, locations, names):
        res={ 
            'date_start' : {},
            'time_start' : {},
            'afternoon' : {},
            'date_end' : {},
            'time_end' : {},
            'morning' : {},
            'color' : {},
        }
        
        for loc in locations: 
            res['date_start'][loc.id] = loc.manifestation.date_start
            res['time_start'][loc.id] = loc.manifestation.time_start
            res['afternoon'][loc.id]  = loc.manifestation.afternoon
            res['date_end'][loc.id]   = loc.manifestation.date_end
            res['time_end'][loc.id]   = loc.manifestation.time_end
            res['morning'][loc.id]    = loc.manifestation.morning
            res['color'][loc.id]      = loc.materiel and loc.materiel.color or ''
        
        return res


    
    @classmethod
    @ModelView.button_action("pl_cust_materiel.act_wizard_returnrepa")
    def return_repair(cls, locations):
        pass
        # Date = Pool().get('ir.date')
        # loc = locations[0]
        # loc.repa_ok = True
        # loc.manifestation.date_end = Date.today()
        # loc.manifestation.datetime_end = datetime.combine(Date.today(), time(21, 59))
        # loc.manifestation.save()
        # loc.save()
        # return 'reload'

class Manifestation(ModelSQL, ModelView):
    "Manifestation"
    __name__ = "pl_cust_materiel.manifestation"

    name = fields.Char("Name", required=True)
    type = fields.Selection([('manif', 'Manifestation'), ('repa', 'Réparation'), ('delete', 'Supprimé')], "Type", required=True)
    localisation = fields.Many2One("pl_cust_materiel.lieumanif", "Localisation", required=True, ondelete="RESTRICT")
    description = fields.Text("Description")
    date_start = fields.Date("Date Start", required=True)
    time_start = fields.Time('Hours Start', format='%H:%M')
    afternoon = fields.Boolean('Afternoon')
    date_end = fields.Date("Date End", required=True)

    manif_date_start = fields.Date("Manif Date Start")
    manif_date_end = fields.Date("Manif Date End")

    time_end = fields.Time('Hours End', format='%H:%M')
    morning = fields.Boolean('Morning')
    party = fields.Many2One("party.party", "Party", ondelete="RESTRICT")
    locations = fields.One2Many("pl_cust_materiel.location", "manifestation", "Locations")
    logs = fields.One2Many("pl_cust_materiel.logs", "manifestation", "Logs", readonly=True)

    datetime_start = fields.DateTime("DateTime Start")
    datetime_end = fields.DateTime("DateTime End")

    color = fields.Function(fields.Char("Couleur"), 'get_color')

    def get_rec_name(self, name):
        return '{}/{}'.format(self.party.name,self.name)

    @classmethod
    def default_type(cls):
        return 'manif'

    @classmethod
    def get_color(cls, manifs, names):
        res={ 
            'color' : {},
        }
        
        for manif in manifs: 
            res['color'][manif.id] = COLOR_LIST[manif.id%len(COLOR_LIST)]
        
        return res

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order = [
            ("date_start", "DESC"),
        ]

        cls._buttons.update(
            {
                "change_manif": {
                    "invisible": Eval("type") != "manif",
                    "depends": ["type"],
                },
            
            }
        )

    @classmethod
    @ModelView.button_action("pl_cust_materiel.act_wizard_changemanif")
    def change_manif(cls, manifs):
        pass

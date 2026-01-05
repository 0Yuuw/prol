# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import DeactivableMixin, ModelView, ModelSQL, Workflow, fields, ModelSingleton
from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If, Not, Equal, Or
from trytond import backend
from trytond.pyson import Date
from datetime import datetime, timedelta
import time
import pytz
from trytond.model.exceptions import ValidationError


__all__ = ['CallsConfiguration', 'Calls', 'RegularCalls', 'CurrentWriter']


class CallsConfiguration(ModelSingleton, ModelSQL, ModelView):
    'Calls Configuration'
    __name__ = 'pl_cust_tel.configuration'

    call_sequence = fields.Many2One('ir.sequence', "Séquence")


class CurrentWriter(ModelSingleton, ModelSQL, ModelView,):
    'Current USer'
    __name__ = 'pl_cust_tel.currentwriter'

    call_writer = fields.Many2One(
        'party.party',
        "Écoutant",
        required=True,
        domain=[('is_writer', '=', True)]
    )

class RegularCalls(ModelSQL, ModelView, DeactivableMixin):
    'List of all regular calls'
    __name__ = 'pl_cust_tel.regularcalls'

    name = fields.Char(u'Nom')
    oe_id = fields.Integer(u'OEID')
    sexe = fields.Selection([
            ('f', u'Femme'),
            ('h', u'Homme'),
            ('hf', u'Non déterminé'),
            ], u'Genre')

    age = fields.Selection([
        (None, ''),
        ('-18', '-18'),
        ('19-40', '19-40'),
        ('41-65', '41-65'),
        ('+65', '+65'),
        ('age_nd', 'Non déterminé')],
        'Âge', sort=False,)
    
    notes = fields.Text(u'Notes')
    histo = fields.One2Many('pl_cust_tel.calls', 'call_regular', 'Historique'),
        
class Calls(ModelSQL, ModelView):
    'List of all calls'
    __name__ = 'pl_cust_tel.calls'

    SELECTION_OPTIONS = [
    (None , ''),
    ('corona' , u"Soucis dû à une infection"),
    ('guerre' , u"Guerre/Terrorisme/Paix"),
    ('quotidien' , u"Gestion du quotidien (hébergement, difficulté à aborder les choses simples de tous les jours, problèmes d'organisation, ...)"),
    ('relation' , u"Problèmes relationnels (travail, voisinage, collègues, amis , ...)" ),
    ('couple' , u"Relations de couple"),
    ('solitude', u'Solitude'),
    ('sociaux' , u"Problèmes sociaux (finances, logement, ... )"),
    ('famille' , u"Famille, éducation (problèmes familiaux, au sein de la famille)"),
    ('travail' , u"Travail et formation (travail, mobbing, chômage, problèmes d’apprentissage, d’études, ...)"),
    ('violence', u"Violence sur ligne 143 (psychique, physique, sexuelle)"),
    ('physique', u"Souffrance physique"),
    ('psychique' , u"Souffrance psychique (état dépressif, angoisse, troubles et problèmes psy)"),
    ('sexualite' , u"Sexualité"),
    ('spiritualite', u"Spiritualité, sens de la vie"),
    ('dependance', u"Dépendances (problèmes de drogues, alcool, ...)"),
    ('suicide', u"Risque de suicide et suicide"),
    ('mort' , u"Perte, deuil, mort"),
    ('media', u"Éducation aux médias"),
    ('divers' , u"Divers (double-appel, tri et renseignements)"),
    ('vd' , u'Ligne Violences domestiques'),
    ('sos', u'Ligne SOS Jeux'),
    ('vih', u'Ligne VIH'),
    ('gll', u'Ligne Gardez le lien'),
    ('lavi', u'LAVI'),
    ]

    # Liste de tout les champs lors de l'ajout d'un call

    name = fields.Char('N°', readonly=False)

    call_user = fields.Many2One(
        'res.user', 'User', required=False, readonly=True)

    call_writer = fields.Many2One(
        'party.party',
        "Écoutant",
        required=True,
        readonly=False,
        #domain=[('is_writer', '=', True)]
    )

    call_pseudo = fields.Char(
        "Pseudo",
        readonly=False,
    )

    call_date = fields.Date('Date', required=True)

    call_time = fields.Time('Heure', required=True)

    call_type = fields.Selection([('tel', 'Entretien'),
                                  ('tel_spec', "Appel (moins d'une minute)"), 
                                  ('tchat', "Tchat"), 
                                  ('mail', "E-Mails") ], 'Type', sort=False, required=True)

    call_length = fields.Integer('Durée (en minutes)', states={
        'invisible': Not(Eval('call_type').in_(['tel', 'tchat', 'mail'])),
        'required': Eval('call_type').in_(['tel', 'tchat', 'mail'])}, depends=['call_type'])

    call_special = fields.Selection([(None, ''),
                                     ('mea', 'Mis en attente (2ème, 3ème ligne)'),
                                     ('silence', 'Silencieux'),
                                     ('erreur', 'Erreur'),
                                     ('refabu', 'Refusé/Abusif')],
                                    'Raison', sort=False, states={
        'invisible': Not(Equal(Eval('call_type'), "tel_spec")),
        'required': Equal(Eval('call_type'), "tel_spec")}, depends=['call_type'])

    call_user_type = fields.Selection([(None, ''),
                                       ('inconnu', 'Premier contact'),
                                       ('ocase', 'Contact occasionnel ou répété'),
                                       ('connu', 'Contact régulier')],
                                      "Type d'appelant", sort=False, states={
        'invisible': Not(Eval('call_type').in_(['tel', 'tchat', 'mail'])),
        'required': Eval('call_type').in_(['tel', 'tchat', 'mail'])}, depends=['call_type'])


    call_regular = fields.Many2One('pl_cust_tel.regularcalls', 'Appelant régulier', states={
        'invisible': Not(Eval('call_user_type').in_(['connu',])),
        #'required': Eval('call_user_type').in_(['connu',])
        },
         depends=['call_type'])
    call_regular_notes = fields.Text('Info appelant régulier', states={
        'invisible': Not(Eval('call_user_type').in_(['connu',]))}, depends=['call_type'])

    call_user_gender = fields.Selection([(None, ''),
                                         ('f', 'Femme'),
                                         ('h', 'Homme'),
                                         ('hf', 'Non déterminé')],
                                        'Sexe', sort=False, states={
        'invisible': Not(Eval('call_type').in_(['tel', 'tchat', 'mail'])),
        'required': Eval('call_type').in_(['tel', 'tchat', 'mail']),}, depends=['call_type','call_regular'])

    call_user_age = fields.Selection([
        (None, ''),
        ('-18', '-18'),
        ('19-40', '19-40'),
        ('41-65', '41-65'),
        ('+65', '+65'),
        ('age_nd', 'Non déterminé')],
        'Âge', sort=False, states={
            'invisible': Not(Eval('call_type').in_(['tel', 'tchat', 'mail'])),
            'required': Eval('call_type').in_(['tel', 'tchat', 'mail']),}, depends=['call_type'])

    #SOS Jeux 
    call_origin_sos = fields.Selection([(None, ''),
                                        ('ge', 'Genève'),
                                        ('vd', 'Vaud'),
                                        ('ne', 'Neuchâtel'),
                                        ('vs', 'Valais'),
                                        ('fr', 'Fribourg'),
                                        ('ju', 'Jura'),
                                        ('france', 'France'),
                                        ('prov_autre', 'Autre'),
                                        ('nr', 'Non renseigné')],
                                       "Provenance de l'appel (SOS Jeux)", sort=False,
                                       states={'invisible': Not(Eval('contenu').in_(['sos'])), 'required': Eval('contenu').in_(['sos'])}, depends=['contenu'])

    call_problem_sos = fields.Selection([(None, ''),
                                     ('tech', 'Erreur (technique)'),
                                     ('rens_exl', 'Informations sur les exclusions de jeu'),
                                     ('rens_dep', 'Informations sur la dépendance'),
                                     ('rens_prest', 'Informations sur les prestations d’aide'),
                                     ('aide', 'Aide et soutien'),
                                     ('prob_autre', 'Autre')],
                                    'Motivations de l’appel (SOS Jeux)', sort=False, states={'invisible': Not(Eval('contenu').in_(['sos'])), 'required': Eval('contenu').in_(['sos'])}, depends=['contenu'])


    call_role_sos = fields.Selection([(None, ''),
                                      ('j', 'Joueur'),
                                      ('p', 'Proche'),
                                      ('pro', 'Professionnel'),
                                      ('role_autre', 'Autre')],
                                     'Rôle (SOS Jeux)', sort=False, states={'invisible': Not(Eval('contenu').in_(['sos'])), 'required': Eval('contenu').in_(['sos'])}, depends=['contenu'])

    call_type_sos = fields.Selection([(None, ''),
                                      ('bourse', 'Bourse/Marchés financiers'),
                                      ('lotel', 'Loterie électronique (tactilo, etc.)'),
                                      ('lot', 'Tirage (loto, Euromillions, etc.)'),
                                      ('grat', 'Billets à gratter'),
                                      ('par', 'Paris sportifs'),
                                      ('pmu', 'PMU/Paris chevaux'),
                                      ('pocker', 'Poker hors casino'),
                                      ('mas', 'Machines à sous'),
                                      ('table', 'Jeux de table (blackjack/roulette/poker)'),
                                      ('illeg', 'Jeux illégaux'),
                                      ('autre', 'Autres'),
                                      ],
                                     'Type (SOS Jeux)', sort=False, states={'invisible': Not(Eval('contenu').in_(['sos'])), 'required': Eval('contenu').in_(['sos'])}, depends=['contenu'])

    call_type_terrestre_sos = fields.Boolean('En Terrestre (SOS Jeux)', states={'invisible': Not(Eval('contenu').in_(['sos']))}, depends=['contenu'])

    call_type_internet_sos = fields.Boolean('En ligne (SOS Jeux)', states={'invisible': Not(Eval('contenu').in_(['sos']))}, depends=['contenu'])

    #####

    #Violence Domestique 
    call_origin_vd = fields.Selection([(None, ''),
                                       ('ge' , u'Genève'),
                                       ('vd' ,u'Vaud'),
                                       ('ne', u'Neuchâtel'),
                                       ('vs', u'Valais'),
                                       ('fr' ,u'Fribourg'),
                                       ('ju', u'Jura'),
                                       ('autre', u'Autre')],
                                       "Provenance de l'appel (vd)", sort=False,
                                       states={'invisible': Not(Eval('contenu').in_(['vd'])), 'required': Eval('contenu').in_(['vd'])}, depends=['contenu'])

    call_role_vd = fields.Selection([(None, ''),
                                     ('aut' , u'Auteur'),
                                     ('vict' , u'Victime'),
                                     ('tem' , u'Témoin'),
                                     ('pro' , u'Professionnel'),
                                     ('autre' , u'Autre'),],
                                     'Rôle (vd)', sort=False, states={'invisible': Not(Eval('contenu').in_(['vd'])), 'required': Eval('contenu').in_(['vd'])}, depends=['contenu'])


    call_rel_vd = fields.Selection([(None, ''),
                                    ('conj' , u'Conjoints ou partenaires'),
                                    ('exconj' , u'Ex-conjoints ou ex-partenaires'),
                                    ('par' , u'Parents/beaux-parents et enfants'),
                                    ('vois' , u'Voisinage'),
                                    ('ami' , u'Amis'),
                                    ('autre' , u'Autre'),],
                                    'Relation (vd)', sort=False, states={'invisible': Not(Eval('contenu').in_(['vd'])), 'required': Eval('contenu').in_(['vd'])}, depends=['contenu'])


    call_type_vd = fields.Selection([(None, ''),
                                     ('phys' , u'Physique'),
                                     ('psy' , u'Psychologique'),
                                     ('sex' , u'Sexuelle'),
                                     ('eco' , u'Économique'),
                                     ('autre' , u'Autre'),
                                      ],
                                     'Type (vd)', sort=False, states={'invisible': Not(Eval('contenu').in_(['vd'])), 'required': Eval('contenu').in_(['vd'])}, depends=['contenu'])

    ##
    
    #VIH
    call_origin_vih = fields.Selection([(None, ''),
                                       ('ge' , u'Genève'),
                                       ('vd' ,u'Vaud'),
                                       ('ne', u'Neuchâtel'),
                                       ('vs', u'Valais'),
                                       ('fr' ,u'Fribourg'),
                                       ('ju', u'Jura'),
                                       ('autre', u'Autre'),
                                       ('nr', u'Non renseigné')],
                                       "Provenance de l'appel (VIH)", sort=False,
                                       states={'invisible': Not(Eval('contenu').in_(['vih'])), 'required': Eval('contenu').in_(['vih'])}, depends=['contenu'])


    call_motif_vih = fields.Selection([(None, ''),
                                     ('avt_test', u'Inquiétude en vue du test'),
                                     ('apr_test', u'Inquiétude après le test'),
                                     ('rens', u'Demande de renseignements'),
                                     ('tiers', u'Appel pour un tiers'),],
                                     'Motif (VIH)', sort=False, states={'invisible': Not(Eval('contenu').in_(['vih'])), 'required': Eval('contenu').in_(['vih'])}, depends=['contenu'])

    ## 
    
    
    contenu = fields.Selection(
        SELECTION_OPTIONS, 'Contenu', sort=False, states={
            'invisible': Not(Eval('call_type').in_(['tel', 'tchat', 'mail'])),
            'required': Eval('call_type').in_(['tel', 'tchat', 'mail'])
        }, depends=['call_type']
    )

    contenu_2 = fields.Selection(
        SELECTION_OPTIONS, 'Contenu 2', sort=False, states={
            'invisible': Or(
                Not(Eval('call_type').in_(['tel', 'tchat', 'mail'])),
                Eval('contenu').in_(['sos', 'vih', 'vd'])
            )
        }, depends=['call_type', 'contenu']
    )

    contenu_3 = fields.Selection(
        SELECTION_OPTIONS, 'Contenu 3', sort=False, states={
            'invisible': Or(
                Not(Eval('call_type').in_(['tel', 'tchat', 'mail'])),
                Eval('contenu').in_(['sos', 'vih', 'vd'])
            )
        }, depends=['call_type', 'contenu']
    )


    call_complement = fields.Char('Complément', states={
        'invisible': Not(Eval('call_type').in_(['tel', 'tchat', 'mail']))}, depends=['call_type'])
    
    interv_umus = fields.Boolean("UMUS", states={
        'invisible': Not(Eval('call_type').in_(['tel', 'tchat', 'mail']))}, depends=['call_type'])

    interv_police = fields.Boolean("Police", states={
        'invisible': Not(Eval('call_type').in_(['tel', 'tchat', 'mail']))}, depends=['call_type'])

    interv_medecins = fields.Boolean("Médecins", states={
        'invisible': Not(Eval('call_type').in_(['tel', 'tchat', 'mail']))}, depends=['call_type'])

    interv_autres = fields.Boolean("Autres", states={
        'invisible': Not(Eval('call_type').in_(['tel', 'tchat', 'mail']))}, depends=['call_type'])

    call_orientation = fields.Text('Orientation (LAVI, Solidarité Femme, Rien ne va plus...)', states={
        'invisible': Not(Eval('call_type').in_(['tel', 'tchat', 'mail']))}, depends=['call_type'])

    call_action = fields.Text('Action choisie', states={
        'invisible': Not(Eval('call_type').in_(['tel', 'tchat', 'mail']))}, depends=['call_type'])

    call_resume = fields.Text("Résumé de l'appel", states={
        'invisible': Not(Eval('call_type').in_(['tel', 'tchat', 'mail']))}, depends=['call_type'])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        #pool = Pool()
        #CurrentWriter = pool.get('pl_cust_tel.currentwriter')
        #cls._fields['call_writer'].default = CurrentWriter(1).call_writer and CurrentWriter(1).call_writer.id or None 
        cls._order = [
            ("call_date", "DESC"),
            ("call_time", "DESC"),
        ]
        cls._buttons.update({
            'save': {},
            'save_and_new': {},
            'close_tab': {
                'save': False,  # <-- ne sauvegarde pas avant d’exécuter
            },
        })
    
    def close_tab(self):
        # Retourne une action de fermeture
        return {
            'type': 'ir.action.act_window_close',
        }
    
    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ("/form/separator[@id='appelant']", 'states', {
                    'invisible': Not(Eval('call_type').in_(['tel', 'tchat', 'mail'])),
                    }),
            ("/form/separator[@id='obj']", 'states', {
                    'invisible': Not(Eval('call_type').in_(['tel', 'tchat', 'mail'])),
                    }),
            ("/form/separator[@id='inter']", 'states', {
                    'invisible': Not(Eval('call_type').in_(['tel', 'tchat', 'mail'])),
                    }),
            ("/form/separator[@id='suivi']", 'states', {
                    'invisible': Not(Eval('call_type').in_(['tel', 'tchat', 'mail'])),
                    }),
            ]

    @classmethod
    @ModelView.button
    def save(cls, records):
        return ''

    @classmethod
    @ModelView.button
    def save_and_new(cls, records):
        return 'new'

    @staticmethod
    def default_call_user():
        return Transaction().user
        
    @fields.depends('call_user')
    def on_change_with_call_writer(self, name=None):
        pool = Pool()
        CurrentWriter = pool.get('pl_cust_tel.currentwriter')
        return CurrentWriter(1).call_writer and CurrentWriter(1).call_writer.id or None 

    @fields.depends('call_user')
    def on_change_with_call_pseudo(self, name=None):
        pool = Pool()
        CurrentWriter = pool.get('pl_cust_tel.currentwriter')
        return CurrentWriter(1).call_writer and CurrentWriter(1).call_writer.pseudo or '' 

    #@fields.depends('call_writer', 'call_pseudo')
    #def on_change_call_writer(self, name=None):
    #    self.call_pseudo = self.call_writer and self.call_writer.pseudo or None
    
    #@staticmethod
    #def default_call_writer():
    #    pool = Pool()
    #    CurrentWriter = pool.get('pl_cust_tel.currentwriter')
    #    return CurrentWriter(1).call_writer and CurrentWriter(1).call_writer.id or None 
        
    @staticmethod
    def default_call_date():
        Date_ = Pool().get('ir.date')
        return Transaction().context.get('date') or Date_.today()

    @staticmethod
    def default_call_time():
        #t = time.localtime()
        #current_time = time.strftime("%H:%M:%S", t)
        return datetime.now(tz=pytz.timezone("Europe/Paris")).time()

    @classmethod
    def validate(cls, records):
        super().validate(records)
        for record in records:
            #record.check_contenu_unique()
            record.check_call_spec_rules()
            record.check_contenu_block()
    
    @fields.depends('call_regular')
    def on_change_call_regular(self) :
        if self.call_regular :
            self.call_user_gender = self.call_regular.sexe
            self.call_user_age = self.call_regular.age
            self.call_regular_notes = self.call_regular.notes
        else: 
            self.call_user_gender = None
            self.call_user_age = None

    @fields.depends('call_type')
    def on_change_call_type(self):
        if self.call_type == 'mail' :
            self.call_length = 120
        else :
            self.call_length = None

        self.call_special = None
        self.call_user_type = None
        self.call_user_gender = None
        self.call_user_age = None
        self.call_origin_sos = None
        # self.call_problem = None
        self.contenu = None
        self.contenu_2 = None
        self.contenu_3 = None
        
        # self.call_role_sos = None
        # self.call_type_sos = None
        self.call_complement = ""
        self.call_action = ""
        self.call_resume = ""

    def check_contenu_unique(self):
        if self.contenu and self.contenu == self.contenu_2:
            raise ValidationError("pl_cust_tel.calls", "Les champs 'Contenu' et 'Contenu 2' doivent être différents!")
        if self.contenu and self.contenu == self.contenu_3:
            raise ValidationError("pl_cust_tel.calls", "Les champs 'Contenu' et 'Contenu 3' doivent être différents!")
        if self.contenu_2 and self.contenu_2 == self.contenu_3:
            raise ValidationError("pl_cust_tel.calls", "Les champs 'Contenu 2' et 'Contenu 3' doivent être différents!")
        
    
    def check_contenu_block(self):
    # Blocage si contenu principal est "sos jeux", "vih", "violences domestiques"
        if self.contenu in ('sos', 'vih', 'vd'):
            if self.contenu_2 or self.contenu_3:
                raise ValidationError(
                    "pl_cust_tel.calls",
                    "Impossible d’ajouter 'Contenu 2' ou 'Contenu 3' si 'Contenu' est SOS Jeux, VIH, ou Violences domestiques."
                )

        
    def check_call_spec_rules(self):
        if self.call_type == 'tel_spec':
            if not self.call_special:
                raise ValidationError("pl_cust_tel.calls", "Le champ 'Raison' est requis pour les appels de moins d'une minute.")

            if any([
                self.call_length,
                self.call_user_type,
                self.call_user_gender,
                self.call_user_age,
                self.call_origin_sos,
                self.contenu,
                self.contenu_2,
                self.call_complement,
                self.interv_umus,
                self.interv_police,
                self.interv_medecins,
                self.interv_autres,
                self.call_orientation,
                self.call_action,
                self.call_resume,
            ]):
                pass
                #raise ValidationError("pl_cust_tel.calls", "Pour les appels de moins d'une minute, seul le champ 'Raison' doit être rempli.")


    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Config = pool.get('pl_cust_tel.configuration')
        Sequence = pool.get('ir.sequence')
        config = Config(1)  # charge la config active
    
        vlist = [x.copy() for x in vlist]
        for values in vlist:
            if not values.get('name'):
                values['name'] = config.call_sequence and config.call_sequence.get() or ''
        return super().create(vlist)
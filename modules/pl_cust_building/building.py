from trytond.model import ModelSQL, ModelView, fields, DeactivableMixin
from trytond.pool import Pool, PoolMeta
from trytond.exceptions import UserError,UserWarning
from trytond.pyson import Eval

class BuildingWarning(UserWarning):
    pass

__all__ = ["Building", "BuildingLoc", "BuildingFolders"]


class BuildingLoc(ModelSQL, ModelView):
    "BuildingLoc"

    __name__ = "pl_cust_building.buildingloc"

    party = fields.Many2One("party.party", "Party", required=True)
    apartment = fields.Char("Apartment Number")
    building = fields.Many2One("pl_cust_building.building", "Building")

    def get_rec_name(self, name):
        return '{}'.format(self.party.name or '')
    
    @classmethod
    def search_rec_name(cls, name, clause):
        _, operator, value = clause
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('party', *clause[1:]),
            ]
        
class Building(ModelSQL, ModelView):
    "Building"

    __name__ = "pl_cust_building.building"

    street = fields.Char('Address Street')
    street_num = fields.Char('Address Num')    
    zip = fields.Char('ZIP')
    city = fields.Char('City')    
    proprio = fields.Many2One("party.party", "Proprio",required=True)
    regie = fields.Many2One("party.party", "Regie",required=True)
    locs = fields.One2Many("pl_cust_building.buildingloc", "building", "Loc")
    
    @classmethod
    def search_rec_name(cls, name, clause):
        _, operator, value = clause
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('proprio', *clause[1:]),
            ('regie', *clause[1:]),
            ('locs', *clause[1:]),
            ]

    def get_rec_name(self, name):
        return '{} {} {} ({}/{})'.format(self.street or '', self.street_num or '', self.city or '', self.proprio.name, self.regie.name)

    def get_all_party(self):
        """Retourne un set (ou une liste) de tous les parties liés à cet objet."""
        all_parties = set()

        # Ajouter les Many2One directs
        for field_name in ['proprio', 'regie']:
            party = getattr(self, field_name, None)
            if party:
                all_parties.add(party.id)

        # Ajouter ceux des lignes
        for line in self.locs or []:
            if line.party:
                all_parties.add(line.party.id)

        return list(all_parties)
    
class BuildingFolders(ModelSQL, ModelView):
    "Building Folders"
    __name__ = "pl_cust_plfolders.folders"

    building = fields.Many2One("pl_cust_building.building", "Building")

    @fields.depends("building","party_id")
    def on_change_party_id(self):
        pool = Pool()
        BuildingLoc = pool.get('pl_cust_building.buildingloc')
        Building = pool.get('pl_cust_building.building')

        if self.party_id:
            
            loc = BuildingLoc.search([('party', '=', self.party_id)])    
            if len(loc) > 1 :
                Warning = Pool().get('res.user.warning')
                warning_name = 'mywarning,%s' % self
                if Warning.check(warning_name):
                    raise UserWarning(
                        warning_name, "Plusieurs immeubles peuvent être lié à ce contact")
            elif len(loc) == 1 :
                self.building = loc[0].building
            else : 
                self.building = None
                
            if not self.building : 
                loc = Building.search(['OR', ('proprio', '=', self.party_id), ('regie', '=', self.party_id) ])
                if len(loc) > 1 :
                    Warning = Pool().get('res.user.warning')
                    warning_name = 'mywarning,%s' % self
                    if Warning.check(warning_name):
                        raise UserWarning(
                            warning_name, "Plusieurs immeubles peuvent être lié à ce contact")
                elif len(loc) == 1 :
                    self.building = loc[0]
                else : 
                    self.building = None
        else : 
            self.building = None
            
    @classmethod
    def __setup__(cls):
        super().__setup__()

        cls._buttons.update(
            {
                "buildingmake_invoice": {
                    
                },
            })
                    
    @classmethod
    @ModelView.button_action("pl_cust_building.act_wizard_buildingcreateinv")
    def buildingmake_invoice(cls, folders):
        pass

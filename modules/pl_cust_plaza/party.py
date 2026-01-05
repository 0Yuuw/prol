# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.model import ModelView, ModelSQL
from trytond.pyson import Bool, Eval
from trytond.transaction import Transaction
from trytond.model.exceptions import ValidationError


class CheckError(ValidationError):
    pass


__all__ = ['PlazaParty',  'PlazaAddress']


class PlazaParty(ModelSQL, ModelView):
    __name__ = 'party.party'

    vip = fields.Boolean('VIP')
    part = fields.Boolean('Partenaire')
    fourn = fields.Boolean('Fournisseur')
    hub_mbc = fields.Boolean('Hub MBC')
    med_mod = fields.Boolean('Médiation/ Modération')

    check_import = fields.Boolean('Check Import')
    change_import = fields.Boolean('Change Import') 

    c_archi = fields.Boolean('Architecture')
    c_artvisu = fields.Boolean('Arts Visuels')
    c_cine = fields.Boolean('Cinema')
    c_danse = fields.Boolean('Danse')
    c_design = fields.Boolean('Design') 
    c_digit = fields.Boolean('Digital / VR')
    c_ecolo = fields.Boolean('Ecologie')
    c_enseign = fields.Boolean('Enseignement')
    c_queer = fields.Boolean('Feminisme / Queer')
    c_hotel = fields.Boolean('Gastronomie / Hotellerie')
    c_geneva = fields.Boolean('Genève internationale')
    c_litera = fields.Boolean('Littérature')
    c_bd = fields.Boolean('Illustration / BD / Anim')
    c_mode = fields.Boolean('Mode')
    c_music = fields.Boolean('Musique')
    c_photo = fields.Boolean('Photographie')
    c_science = fields.Boolean('Science')
    c_social = fields.Boolean('Social')
    c_theat = fields.Boolean('Théâtre / Arts Vivants')
    c_tour = fields.Boolean('Tourisme')
    c_video = fields.Boolean('Vidéo')

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'

        return [bool_op,
                ('lastname', *clause[1:]),
                ('firstname', *clause[1:]),
                ('nickname', *clause[1:]),
                ('organisation', *clause[1:]),
                ('addresses.contact_name', *clause[1:]),
                ('contact_mechanisms.value_compact', *clause[1:]),
                ('notes', *clause[1:]),
                ]

    @staticmethod
    def default_check_import():
        return True

    @classmethod
    def __setup__(cls):
        super().__setup__()

        cls._buttons.update({
            'valid_change_button': {'invisible':~Bool(Eval('change_import')),'depends':['change_import']},
            'valid_and_next_button': {},
            'remove_and_next_button': {},
            'change_and_next_button': {},    
        })

    @staticmethod
    def _check_bool(party):

        for cb in [
                party.c_archi,
                party.c_artvisu,
                party.c_cine,
                party.c_danse,
                party.c_design,
                party.c_digit,
                party.c_ecolo,
                party.c_enseign,
                party.c_queer,
                party.c_hotel,
                party.c_geneva,
                party.c_litera,
                party.c_bd,
                party.c_mode,
                party.c_music,
                party.c_photo,
                party.c_science,
                party.c_social,
                party.c_theat,
                party.c_tour,
                party.c_video,
            ]:

            if cb:
                return True
        
        
    @classmethod
    def change_and_next_button(cls, party):
        party = party[0]
        if party.party_type == '-':
            raise CheckError("Le type est obligatoire")

        if not cls._check_bool(party):
            raise CheckError("Il faut cocher au minimum une case")

        party.change_import = True
        party.check_import = False
        party.save()
        return 'next'

    @classmethod
    def valid_change_button(cls, party):
        party = party[0]
        party.change_import = False
        party.save()
        return 'next'

    @classmethod
    def valid_and_next_button(cls, party):
        party = party[0]
        if party.party_type == '-':
            raise CheckError("Le type est obligatoire")

        if not cls._check_bool(party):
            raise CheckError("Il faut cocher au minimum une case")

        party.check_import = False
        party.save()
        return 'next'

    @ classmethod
    def remove_and_next_button(cls, party):
        party = party[0]
        party.active = False
        party.check_import = False
        party.save()
        return 'next'

    @classmethod
    def create(cls, vlist):
        vlist = [x.copy() for x in vlist]
        for values in vlist:
            if not values.get('party_type') or values.get('party_type') == '-':
                raise CheckError("Le type est obligatoire")

            for cb in [
                    values.get('c_archi'),
                    values.get('c_artvisu'),
                    values.get('c_cine'),
                    values.get('c_danse'),
                    values.get('c_design'),
                    values.get('c_digit'),
                    values.get('c_ecolo'),
                    values.get('c_enseign'),
                    values.get('c_queer'),
                    values.get('c_hotel'),
                    values.get('c_geneva'),
                    values.get('c_litera'),
                    values.get('c_bd'),
                    values.get('c_mode'),
                    values.get('c_music'),
                    values.get('c_photo'),
                    values.get('c_science'),
                    values.get('c_social'),
                    values.get('c_theat'),
                    values.get('c_tour'),
                    values.get('c_video')
                    ]:

                if cb:
                    break
            else:
                raise CheckError("Il faut cocher au minimum une discipline")

        return super().create(vlist)


class PlazaAddress(ModelSQL, ModelView):
    __name__ = 'party.address'

    pro = fields.Boolean('Pro?')

    @ classmethod
    def default_format_(cls):
        return """${organisation}
${party_name}
${contact_name}
${compl}
${street} ${num_street}
${compl2}
${postal_code} ${city}
${country}"""

    def get_organisation(self):
        return self.party and self.pro and self.party.organisation or ''

    def _get_address_substitutions(self):
        context = Transaction().context
        subdivision_code = ''
        if getattr(self, 'subdivision', None):
            subdivision_code = self.subdivision.code or ''
            if '-' in subdivision_code:
                subdivision_code = subdivision_code.split('-', 1)[1]
        substitutions = {
            'organisation': self.get_organisation(),
            'party_name': self.myparty_full_name(),
            'attn': '',
            'name': getattr(self, 'name', None) or '',
            'contact_name': getattr(self, 'contact_name', None) or '',
            'compl': getattr(self, 'addr_compl', None) or '',
            'street': getattr(self, 'addr_street', None) or '',
            'num_street': getattr(self, 'addr_street_num', None) or '',
            'compl2': getattr(self, 'addr_compl2', None) or '',
            'postal_code': getattr(self, 'postal_code', None) or '',
            'city': getattr(self, 'city', None) or '',
            'subdivision': (self.subdivision.name
                            if getattr(self, 'subdivision', None) else ''),
            'subdivision_code': subdivision_code,
            'country': (self.country.name
                        if getattr(self, 'country', None) and self.country.code != 'CH' else ''),
            'country_code': (self.country.code or ''
                             if getattr(self, 'country', None) else ''),
        }
        if context.get('address_from_country') == getattr(self, 'country', ''):
            substitutions['country'] = ''
        if context.get('address_attention_party', False):
            substitutions['attn'] = (
                context['address_attention_party'].full_name)
        for key, value in list(substitutions.items()):
            substitutions[key.upper()] = value.upper()
        return substitutions

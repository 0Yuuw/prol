from trytond.pool import Pool
from trytond.report import Report
from trytond.transaction import Transaction
from trytond.exceptions import UserError
from datetime import date
import locale

__all__ = ['DonsAttestation', 'DonsAttestationSingle', 'DonsThanks']


today = date.today()

def get_full_month(month_index):
    months = [
        'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
        'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'
    ]
    return months[month_index - 1]


def format_chf(amount):
    locale.setlocale(locale.LC_NUMERIC, 'C')
    parts = f"{amount:,.2f}".split(".")
    parts[0] = parts[0].replace(",", "'")
    return ".".join(parts)


class BaseDonsAttestation(Report):

    @classmethod
    def get_common_context(cls, donator, report_date):
        if not donator.addresses:
            raise UserError("Impossible de créer le rapport", "Le contact n'a pas d'adresse enregistrée")

        address = donator.addresses[0]
        if not address.addr_street or not address.addr_street_num:
            raise UserError("Impossible de créer le rapport", "L'adresse est incomplète")

        adresse_l1 = address.addr_compl or ''
        adresse_l2 = f"{address.addr_street} {address.addr_street_num}"
        adresse_l3 = address.addr_compl2 or ''
        adresse_l4 = f"{address.postal_code} {address.city}"

        nom_complet = donator.get_full_name('')
        titre_extrait = nom_complet.split(' ')[0].strip().lower()

        salutation_mapping = {
            'madame': 'Chère Madame',
            'monsieur': 'Cher Monsieur',
            'maître': 'Cher Maître',
            'docteur': 'Cher Docteur',
            'monsieur & madame': 'Chers Monsieur & Madame',
        }

        salutation = salutation_mapping.get(titre_extrait, 'Cher Monsieur, Madame')

        context = {
            'salutation': salutation,
            'nomComplet': nom_complet,
            'adresse_l1': adresse_l1,
            'adresse_l2': adresse_l2,
            'adresse_l3': adresse_l3,
            'adresse_l4': adresse_l4,
            'adresse': [line for line in [adresse_l1, adresse_l2, adresse_l3, adresse_l4] if line],
            'date': f"{get_full_month(today.month)} {today.year}",
            'montantTotal': 0,
            'montantTotalStr': '',
            'anneeActuelle': report_date.year,
        }

        return context

    @classmethod
    def mark_donations_as_sent(cls, donations):
        if donations:
            with Transaction().new_transaction():
                Pool().get('pl_cust_dons.dons').write(donations, {'attestation_sent': True})
                Transaction().commit()


class DonsAttestation(BaseDonsAttestation):
    __name__ = 'pl_cust_dons.dons_attestation'

    @classmethod
    def get_context(cls, records, header, data):
        if not records:
            raise UserError("Aucun enregistrement trouvé")

        donator = records[0].donator
        today = date.today()

        annees_dons = {don.date.year for don in records}

        if len(annees_dons) != 1:
            raise UserError("Les dons sélectionnés doivent être tous de la même année.")

        annee_selectionnee = annees_dons.pop()

        context = cls.get_common_context(donator, today)
        context.update({
            'anneeActuelle': annee_selectionnee,
            'anneeAvant': annee_selectionnee - 1,
            'complement': getattr(records[0], 'complement', ''),
        })

        dons_utilises = [
            don for don in donator.dons
            if don.date.year == annee_selectionnee
        ]

        if not dons_utilises:
            raise UserError(f"Aucun don trouvé pour l'année {annee_selectionnee}")

        context['montantTotal'] = sum(d.amount for d in dons_utilises)
        context['montantTotalStr'] = format_chf(context['montantTotal'])

        cls._dons_a_marquer = [
            don for don in dons_utilises if not don.attestation_sent
        ]

        return context

    @classmethod
    def execute(cls, ids, data):
        result = super().execute(ids, data)
        cls.mark_donations_as_sent(getattr(cls, '_dons_a_marquer', []))
        return result


class DonsAttestationSingle(BaseDonsAttestation):
    __name__ = 'pl_cust_dons.dons_attestation_single'

    @classmethod
    def get_context(cls, records, header, data):
        #if len(records) != 1:
        #    raise UserError("Une seule donation doit être sélectionnée")

        don = records[0]
        context = cls.get_common_context(don.donator, don.date)

        context.update({
            'anneeActuelle': don.date.year,
            'anneeAvant': don.date.year - 1,
            'montantTotal': don.amount,
            'montantTotalStr': format_chf(don.amount),
            'complement': getattr(don, 'complement', ''),
        })

        cls._dons_a_marquer = [] if don.attestation_sent else [don]

        return context

    @classmethod
    def execute(cls, ids, data):
        result = super().execute(ids, data)
        cls.mark_donations_as_sent(getattr(cls, '_dons_a_marquer', []))
        return result


class DonsThanks(BaseDonsAttestation):
    __name__ = "pl_cust_dons.donsthanks"

    @classmethod
    def get_context(cls, records, headers, data):
        pool = Pool()
        Date_ = pool.get("ir.date")
        LANG = pool.get("ir.lang")

        #context = super().get_context(records, headers, data)
        
        context = {'alldons' : []}
        cls._dons_a_marquer = []

        for don in records :

            context_tmp = cls.get_common_context(don.donator, don.date)
            
            context_tmp['addr'] = don.donator.addresses[0]
            context_tmp.update({
                'anneeActuelle': don.date.year,
                'anneeAvant': don.date.year - 1,
                'montantTotal': don.amount,
                'montantTotalStr': format_chf(don.amount),
                'complement': don.complement or '',
            })

            cls._dons_a_marquer.append(don)
            context['alldons'].append(context_tmp)

        return context

    @classmethod
    def execute(cls, ids, data):
        result = super().execute(ids, data)
        cls.mark_donations_as_sent(getattr(cls, '_dons_a_marquer', []))
        return result   

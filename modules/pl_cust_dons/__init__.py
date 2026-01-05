from trytond.pool import Pool
from . import dons
from . import party
from . import dons_report

__all__ = ['register']

# Déclaration des nouvelles classes dans le module
def register():
    Pool.register(
        dons.Dons,
        dons.TypeDonateur,
        dons.TypeDons,
        party.Party,
        module='pl_cust_dons', type_='model')
    
    Pool.register(
        dons_report.DonsAttestation,
        dons_report.DonsAttestationSingle,
        dons_report.DonsThanks,
        module='pl_cust_dons', type_='report')

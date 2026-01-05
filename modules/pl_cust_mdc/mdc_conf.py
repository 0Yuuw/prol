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
from trytond.pyson import Bool, Eval
from trytond.transaction import Transaction
from trytond.model.exceptions import ValidationError
from trytond.tools.qrcode import generate_png

__all__ = ["MDCConfiguration", "BookingConfigurationSequence"]

booking_sequence = fields.Many2One(
    "ir.sequence", "Booking Sequence", help="Used to generate the booking id."
)


class MDCConfiguration(ModelSingleton, ModelSQL, ModelView, MultiValueMixin):
    "MDC Configuration"
    __name__ = "pl_cust_mdc.configuration"

    booking_sequence = fields.MultiValue(booking_sequence)
    nb_max = fields.Integer("Nb max")
    nb_inst_max = fields.Integer("Nb inst max")
    nb_sieste_max = fields.Integer("Nb sieste max")
    price_2 = fields.Integer("Price 4 2")
    price_4 = fields.Integer("Price 4 4")
    price_10 = fields.Integer("Price 4 10")
    price_adult = fields.Integer("Price adult")
    price_asso = fields.Integer("Price association")
    price_02 = fields.Integer("Price 0-2")
    price_34 = fields.Integer("Price 3-4")
    price_56 = fields.Integer("Price 5-6")
    price_78 = fields.Integer("Price 7-8")
    price_gift = fields.Integer("Price for Gift")

    merchant_id = fields.Char("Merchant_id")
    merchant_password = fields.Char("Merchant passwd")
    datatrans_url = fields.Char("Datatrans url")
    datatrans_successUrl = fields.Char("Datatrans Successurl")
    datatrans_giftSuccessUrl = fields.Char("Datatrans Gift Successurl")
    datatrans_cancelUrl = fields.Char("Datatrans Cancelurl")
    datatrans_errorUrl = fields.Char("Datatrans Errorurl")
    checkticketUrl = fields.Char("Check ticket url")
    checktgiftUrl = fields.Char("Check Gift url")

    @classmethod
    def default_nb_max(cls):
        return 120

    @classmethod
    def default_nb_inst_max(cls):
        return 4

    @classmethod
    def default_price_2(cls):
        return 3

    @classmethod
    def default_price_4(cls):
        return 12

    @classmethod
    def default_price_10(cls):
        return 30

    @classmethod
    def default_price_adult(cls):
        return 3

    @classmethod
    def default_price_asso(cls):
        return 0

    @classmethod
    def default_price_02(cls):
        return 0

    @classmethod
    def default_price_34(cls):
        return 3

    @classmethod
    def default_price_56(cls):
        return 3

    @classmethod
    def default_price_78(cls):
        return 3
    
    @classmethod
    def default_price_gift(cls):
        return 0


class _MBCConfigurationValue(ModelSQL):

    _configuration_value_field = None

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append(cls._configuration_value_field)
        value_names.append(cls._configuration_value_field)
        migrate_property(
            "pl_cust_mdc.configuration", field_names, cls, value_names, fields=fields
        )


class BookingConfigurationSequence(_MBCConfigurationValue, ModelSQL, ValueMixin):
    "MDC Booking Configuration Sequence"
    __name__ = "pl_cust_mdc.configuration.booking_sequence"
    booking_sequence = booking_sequence
    _configuration_value_field = "booking_sequence"

    @classmethod
    def check_xml_record(cls, records, values):
        return True

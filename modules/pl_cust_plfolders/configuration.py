# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.model import ModelSingleton, ModelSQL, ModelView, MultiValueMixin, ValueMixin, fields
#from trytond.tools.multivalue import migrate_property
from trytond.pyson import Eval,Bool

__all__ = ['FoldersConfiguration', 'FoldersConfigurationSequence',
           'FolderType','FoldersWizardInvoice']

folders_sequence = fields.Many2One('ir.sequence', 'Folder Sequence',                                   
                                   help="Used to generate the folder name.")

class FoldersWizardInvoice(ModelSingleton,ModelSQL, ModelView):
    'Configuration for invoiced wizard'
    __name__ = 'pl_cust_plfolders.wizardconf'

    account_deb_id = fields.Many2One(
        'account.account', 'Account H Deb', required=True)
    
    journal_id = fields.Many2One('account.journal', 'Journal', required=True)
    journal_pp = fields.Many2One('account.move.reconcile.write_off', 'Journal PP', required=False)
    payment_term = fields.Many2One(
            'account.invoice.payment_term', "Default Customer Payment Term")
    product_tva = fields.Many2One(
        'product.product', 'Produit TVA', required=True)
    product_notva = fields.Many2One(
        'product.product', 'Produit NO TVA', required=True)
    
    depl_tva = fields.Many2One(
        'product.product', 'Depl TVA', required=True)
    depl_notva = fields.Many2One(
        'product.product', 'Depl NO TVA', required=True)
    
    taxe77 = fields.Many2One(
        'account.tax', 'TVA 7.7%', required=True)


class FoldersConfiguration(ModelSingleton, ModelSQL, ModelView, MultiValueMixin):
    'Folder Configuration'
    __name__ = 'pl_cust_plfolders.configuration'

    folders_sequence = fields.MultiValue(folders_sequence)

class _FoldersConfigurationValue(ModelSQL):

    _configuration_value_field = None

    #@classmethod
    #def __register__(cls, module_name):
    #    TableHandler = backend.get('TableHandler')
    #    exist = TableHandler.table_exist(cls._table)

    #    super(_FoldersConfigurationValue, cls).__register__(module_name)

    #    if not exist:
    #        cls._migrate_property([], [], [])

    # @classmethod
    # def _migrate_property(cls, field_names, value_names, fields):
    #     field_names.append(cls._configuration_value_field)
    #     value_names.append(cls._configuration_value_field)
    #     migrate_property(
    #         'pl_cust_plfolders.configuration', field_names, cls, value_names,
    #         fields=fields)


class FolderType(ModelSQL, ModelView):
    'Folder timesheet'
    __name__ = 'pl_cust_plfolders.foldertype'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True, translate=False)
    folder_price1 = fields.Integer('T1')
    folder_price2 = fields.Integer('T2')
    folder_price3 = fields.Integer('T3')
    folder_price4 = fields.Integer('T4')
    folder_price5 = fields.Integer('T5')
    folder_price_depl = fields.Integer('Deplacement Price')
    folder_charges = fields.Float('Folder Charges(%)')

    @staticmethod
    def default_folder_price1():
        return 0
    
    @staticmethod
    def default_folder_price2():
        return 0
    
    @staticmethod
    def default_folder_price3():
        return 0
    
    @staticmethod
    def default_folder_price4():
        return 0
    
    @staticmethod
    def default_folder_price5():
        return 0

class FoldersConfigurationSequence(_FoldersConfigurationValue, ModelSQL, ValueMixin):
    'Folders Configuration Sequence'
    __name__ = 'pl_cust_plfolders.configuration.folders_sequence'
    folders_sequence = folders_sequence
    _configuration_value_field = 'folders_sequence'

    @classmethod
    def check_xml_record(cls, records, values):
        return True

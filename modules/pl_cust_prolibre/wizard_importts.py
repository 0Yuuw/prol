from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.model import ModelView, fields
from trytond.pool import Pool
from trytond.transaction import Transaction
import csv
from datetime import timedelta,datetime

__all__ = ['ImportTS', 'ImportTSStart']


class ImportTSStart(ModelView):
    "ImportTSStart"
    __name__ = 'pl_cust_prolibre.importts_start'

    folder_id = fields.Many2One('pl_cust_plfolders.folders', 'Folder', required=True)
    import_file = fields.Binary('Import file')

    @staticmethod
    def default_folder_id():
        if Transaction().context.get('active_model', '') == 'pl_cust_plfolders.folders':
            return Transaction().context.get('active_id', '')
        return None


class ImportTS(Wizard):
    "CreateNewInvoice"
    __name__ = "pl_cust_prolibre.importts"

    start = StateView('pl_cust_prolibre.importts_start',
                      'pl_cust_prolibre.wizard_importts_view_form', [
                          Button('Cancel', 'end', 'tryton-cancel'),
                          Button('Import', 'import_ts',
                                 'tryton-ok', default=True),
                      ])

    import_ts = StateTransition()

    def transition_import_ts(self):
        pool = Pool()
        Act = pool.get('pl_cust_plfolders.sheetact')
        Task = pool.get('pl_cust_plfolders.sheettasks')
        Employee = pool.get('company.employee')
        FolderSheet = pool.get('pl_cust_plfolders.foldersheet')
        delimiter = ';'
        col = ['1', '2', '3', '4', '5', '6', '7', '8', '9']

        lines = self.start.import_file.decode('utf-8')
        for l in lines.split('\n'):
            line = dict(zip(col, l.split(';')))
            
            if self.start.folder_id.name == line['1'] :
                act = Act.search([('name','=',line['2'])])[0]
                task = Task.search([('name','=',line['3'])])[0]
                empl = Employee(line['5'])
                date_task = datetime.strptime(line['6'],"%d.%m.%Y")
                duration = timedelta(minutes=int(line['7']))
                print('{} ++++ {} ++++++ {} ///// {}***{}'.format(act.name,task.name,empl.party.name,duration,date_task))
                new_ts = FolderSheet.create([{
                    'activity' : act.id,
                    'task' :task.id,
                    'name' : line['4'],
                    'date' : date_task,
                    'folder_id' : self.start.folder_id.id,
                    'resp_id' : empl.id,
                    'duration' : duration,
                    'pct' : line['8'],
                    'archived' : line['9'] == 'x',
                }])
            else: 
                print("-----{}----".format(line))
                print("On est pas dans le bon dossier {} {}".format(self.start.folder_id.name,line['1']))
                
                

        return 'end'

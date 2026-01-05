from proteus import config, Model
import csv
import locale
import string
import getopt
import sys
import unicodedata as ud
import sys
from decimal import Decimal
from datetime import datetime, timedelta

config = config.set_trytond(database=sys.argv[1])

FOLDERS = Model.get('pl_cust_plfolders.folders')

for f in FOLDERS.find([]):
    f.click('update_infos')
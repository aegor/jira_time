import os
docks = './docs/'


files_folder = os.getcwd() + '/docks/'

gitlab_url = 'https://projects.rtk-sdo.ru'
#db_path = docks + 'localbase(bak).db'
#db_path = docks+'testbase.db'
db_path = docks+'localbase.db'
projects_to_update = 'rtk'
issues_csv_file = docks+'issues.csv'
xls_file = files_folder+'{0}.ods'
email = 'antonpaly@ya.ru'
password = 'ppoezth10m9atzam49ASlOr'

dbname = docks+'issues'

#  libre connection
soport = 2002
sohost = 'localhost'

glog = False
plog = True
ilog = True

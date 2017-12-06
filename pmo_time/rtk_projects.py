#!/usr/bin/python3
# -*- coding: utf-8 -*-

# from IPython import embed
# call iPython shell for debug in context:
# embed()
# sys.exit()
# start date =

import datetime
import json
import shelve
import sys

import unotools

import gitlab
# imported libs
import pyoo
###  system libs
import unicodecsv as csv
from peewee import *
# created modules
from models import OLAP
from config import *

# Issues global DB
issues = []
# Assignees global DB
# format: {'assignee email': {'time_estimate': secs, 'time_spent': secs}}
assignees = {}


# End of globals

class Issue:
    """methods and structure of issue"""

    def _convert_time(self, time_string: str):
        """:returns int of UNIX time from string in format '%Y-%m-%dT%H:%M:%S.%fZ' or '%Y-%m-%d'"""
        if time_string is not None:
            if 'T' in time_string:
                date, time = time_string.split('T')
                converted_date = datetime.datetime.strptime(date, '%Y-%m-%d')
                converted_time = datetime.datetime.strptime(time[:-5], '%H:%M:%S')
                converted_datetime = (converted_date + datetime.timedelta(hours=converted_time.hour,
                                                                          minutes=converted_time.minute,
                                                                          seconds=converted_time.second))
            elif time_string != '':
                converted_datetime = datetime.datetime.strptime(time_string, '%Y-%m-%d')
            else:
                converted_datetime = datetime.datetime.fromtimestamp(0)

            return int(converted_datetime.timestamp())
        else:
            return ''

    def __init__(self, issue):
        # todo see down
        # updating created time for issue in db, remove it after updating


        self.project_id = str(issue.project_id)
        self.issue_id = str(issue.id)
        self.title = xstr(getattr(issue, 'title', ''))
        self.description = xstr(getattr(issue, 'description', ''))
        self.assignee = xstr(getattr(issue.assignee, 'name', ''))
        self.author = xstr(getattr(issue.author, 'name', ''))
        self._convert_time(getattr(issue, 'created_at', ''))
        self.created = self._convert_time(getattr(issue, 'created_at', ''))
        self.updated = self._convert_time(getattr(issue, 'updated_at', ''))
        self.due_date = self._convert_time(getattr(issue, 'due_date', ''))
        self.labels = json.dumps(getattr(issue, 'labels', ''))
        self.state = getattr(issue, 'state', '')
        self.milestone_title = xstr(getattr(issue.milestone, 'title', ''))
        self.milestone_description = xstr(getattr(issue.milestone, 'description', ''))
        self.milestone_due_date = self._convert_time(xstr(getattr(issue.milestone, 'due_date', '')))
        time_stats = issue.time_stats()
        self.time_estimate = xstr(time_stats['human_time_estimate'])
        self.time_spent = xstr(time_stats['human_total_time_spent'])
        self.time_estimate_secs = time_stats['time_estimate']
        self.time_spent_secs = time_stats['total_time_spent']
        # print(time_stats, self.time_estimate, self.time_spent, self.time_estimate_secs, self.time_spent_secs)
        self.project = xstr(getattr(issue, 'project', ''))

        if xstr(getattr(issue.milestone, 'created_at', '')):
            self.milestone_created = self._convert_time(xstr(getattr(issue.milestone, 'created_at', '')))
        else:
            self.milestone_created = ''  # todo

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return json.dumps(self.__dict__, indent=4, ensure_ascii=False)


def xstr(s):
    return '' if s is None else str(s)


def seconds_to_time(seconds):
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return "%d:%02d" % (h, m)


def check_server(address, port):
    # Create a TCP socket
    try:
        unotools.connect(unotools.Socket(address, port))
        return True
    except:
        return False


def print_groups(gl):
    groups = gl.groups.list(per_page=1000)
    print('\nGROUPS:')
    for group in groups:
        if group.parent_id is not None:
            report = gl.groups.get(group.parent_id).name + '/'
        else:
            report = ''
        print(report + group.name)


def write_issues_to_csv(issues):
    """write issues into issues.csv"""
    with open(issues_csv_file, 'wb') as f:
        writer = csv.writer(f, encoding='utf-8')
        writer.writerow(
            ('id', 'title', 'description', 'projects', 'assignee', 'author', 'created', 'updated', 'due_date',
             'labels', 'state', 'milestone_title', 'milestone_description', 'milestone_created',
             'milestone_due_date', 'time_estimate', 'time_spent'))
        for issue in issues:
            writer.writerow((issue.title, issue.description, issue.project, issue.assignee, issue.author, issue.created,
                             issue.updated,
                             issue.due_date, issue.labels, issue.state, issue.milestone_title, issue.milestone_created,
                             issue.milestone_due_date, issue.time_estimate, issue.time_spent))
            issue = None
        f.close()


def fill_field(issue, entry, new: bool, up_time: int):
    """
    fill database field received issue
    assignee, state, time estimate, time spent, updated, query time
    """
    # todo refactor this trash

    if new:
        # these fields for
        # if enrty issue is new, fill fields of this issue
        entry.assignee = issue.assignee
        entry.state = issue.state
        entry.created = issue.created
        entry.issue_title = issue.title
        entry.time_estimate = issue.time_estimate_secs
        entry.time_spent = issue.time_spent_secs
        entry.updated = issue.updated
        entry.query_time = up_time
        entry.project_name = issue.project
        entry.project_id = issue.project_id
        entry.milestone_date = issue.milestone_due_date
        entry.milestone_title = issue.milestone_title
        entry.save()
    else:
        # if id of this issue was in table
        iss, new = OLAP.get_or_create(updated=issue.updated,
                                      issue_id=issue.issue_id)
        if not new:
            _iss, new = OLAP.get_or_create(updated=issue.updated,
                                           time_spent=issue.time_spent_secs,
                                           issue_id=issue.issue_id)
            if new:
                _iss.issue_id = issue.issue_id
                _iss.issue_title = issue.title
                _iss.assignee = issue.assignee
                _iss.state = issue.state
                _iss.created = issue.created
                _iss.time_estimate = issue.time_estimate_secs
                _iss.time_spent = issue.time_spent_secs
                _iss.updated = issue.updated
                _iss.query_time = up_time
                _iss.project_id = issue.project_id
                _iss.project_name = issue.project
                _iss.milestone_date = issue.milestone_due_date
                _iss.milestone_title = issue.milestone_title
                _iss.save()

        else:
            iss.issue_id = issue.issue_id
            iss.issue_title = issue.title
            iss.assignee = issue.assignee
            iss.state = issue.state
            iss.created = issue.created
            iss.time_estimate = issue.time_estimate_secs
            iss.time_spent = issue.time_spent_secs
            iss.updated = issue.updated
            iss.project_id = issue.project_id
            iss.project_name = issue.project
            iss.query_time = up_time
            iss.milestone_date = issue.milestone_due_date
            iss.milestone_title = issue.milestone_title
            iss.save()


def calc_times(issues):
    """for assignees in db calculate estimate and spent time and add this on db localbase.db(sqlite3)"""
    # Assignees DB
    # format: assignees = {'assignee email': {'time_estimate': secs, 'time_spent': secs}}
    up_time = int(datetime.datetime.now().timestamp())

    for issue in issues:
        key = issue.assignee
        if key is not '':
            if key in assignees:
                # assignees[key] = {'time_estimate': issue.time_estimate_secs + te, 'time_spent': issue.time_spent_secs + ts}
                entry, new = OLAP.get_or_create(issue_id=issue.issue_id)
                fill_field(issue, entry, new, up_time)
            else:
                assignees[key] = {'time_estimate': issue.time_estimate_secs, 'time_spent': issue.time_spent_secs}
                entry, new = OLAP.get_or_create(issue_id=issue.issue_id)
                fill_field(issue, entry, new, up_time)


def prepare_issues(gl):
    """read issues from gitlab whose starts with on key phrase """
    iss = []
    projects = gl.projects.list(per_page=1000)

    if plog:
        print('Projects:')
    # Prepare issues database
    for project in projects:
        if project.path_with_namespace.startswith('rtk'):
            if plog:
                print(project.path_with_namespace)
            project_issues = project.issues.list(per_page=1000)
            for i in project_issues:
                i.project = project.path_with_namespace
                # print(i)
            iss.extend(project_issues)
    # possible shelve flags: c - create if need, then read/write, r - readonly, w - rw, n - always create new db
    db = shelve.open(dbname, writeback=True, flag='c')
    idx = 0
    for i in iss:
        # print(i.updated_at)
        db[str(idx)] = Issue(i)
        idx = idx + 1
    db.close()


def read_issues(dbname):
    """read issues from 'issues'"""
    db = shelve.open(dbname, writeback=True, flag='w')  # flag='r'
    for i in db.keys():
        issues.append(db[i])
        # db.close() !!! strange... always call sync, even on readonly file??? Why?


def print_assignees():
    """print assignees with estimate time and spent time"""
    for key, value in assignees.items():
        print(key,
              seconds_to_time(value['time_estimate']),
              seconds_to_time(value['time_spent']))


def get_date_closing(issue):
    last_issue = OLAP.select(OLAP.issue_id, fn.Min(OLAP.updated)).where((OLAP.issue_id == issue.issue_id) &
                                                                        (OLAP.state == 'closed')).get()
    return '' if last_issue.updated is None else datetime.datetime.fromtimestamp(last_issue.updated)


def write_to_xls():
    # connect
    """

    from unotools.unohelper import convert_path_to_url
    context = unotools.connect(unotools.Socket(host=sohost, port=soport))
    calc = Calc(context, convert_path_to_url(xls_file))

#    sheets_count = calc.get_sheets_count()

    # create tables of assignees
    for assignee in assignees:

        try:
            name, _ = map(lambda x: x.strip(), assignee.split('@'))
        except ValueError:
            name = assignee.strip()

        try:
            sheet = calc.get_sheet_by_name(name)
        except:
            calc.insert_sheets_new_by_name(name, 0)
            sheet = calc.get_sheet_by_name(name)

            name_cell = sheet.get_cell_by_position(0,0)
            name_cell.setString(name)

            total_cell = sheet.get_cell_by_position(0,3)
            total_cell.setString('Итого: ')
            sheet.get_cell_by_position(1,3).setString('Задача')
            sheet.get_cell_by_position(2,3).setString('Проект')

            sheet.get_cell_by_position(3, 3).setString('opened')
            sheet.get_cell_by_position(4, 3).setString('closed')
            sheet.get_cell_by_position(5, 3).setString('Статус, час')

        bcol = sheet.get_cell_range_by_position(6,4,6,100)


        issues_of_assignee = OLAP.select().distinct().where(OLAP.assignee==assignee)
        ioa = tuple(ioa.issue_title for ioa in issues_of_assignee)
        print(assignee, len(ioa))
        last_cell = 4
        issues_in_table = []
        while sheet.get_cell_by_position(0,last_cell):
            if sheet.get_cell_by_position(0,last_cell).getString() != '':
                if sheet.get_cell_by_position(0,last_cell).getString() in ioa:
                    pass
                    # update issue info
                else:
                    pass
                    # add this issue
               # for ioa in issues_of_assignee:
               #     if sheet.get_cell_by_position(0, last_cell).getString() == ioa.issue_title:
               #         pass
                        # todo make updating info


                issues_in_table.append(sheet.get_cell_by_position(0,last_cell).getString())
                last_cell += 1
            else:
                break




        # todo here creation list of issues
        pass
        # todo updating state and date of issue
        # todo updating dates of issues


"""
    desktop = pyoo.Desktop(sohost, soport)
    doc = desktop.create_spreadsheet()

    for assignee in assignees:
        try:
            name, _ = map(lambda x: x.strip(), assignee.split('@'))
        except ValueError:
            name = assignee.strip()
        doc.sheets.create(name, index=0)

        issues_sheet = doc.sheets[name]
        try:
            del doc.sheets['Sheet1']
        except:
            pass
        # set cell 0.0 to name os assignee
        # issues_sheet[row, column]
        issues_sheet[0, 0].value = name
        # fill service data

        issues_sheet[1, 0].value = 'Проект'
        issues_sheet[1, 1].value = 'Задача'
        issues_sheet[1, 2].value = 'opened'
        issues_sheet[1, 3].value = 'closed'
        issues_sheet[1, 4].value = 'План'
        issues_sheet[1, 5].value = 'Факт'
        start_issues = 2

        for issue in issues:
            if issue.assignee == assignee:
                iss = OLAP.select().where(OLAP.issue_id == issue.issue_id).get()
                issues_sheet[start_issues, 1].value = iss.issue_title
                issues_sheet[start_issues, 0].value = iss.project_name
                issues_sheet[start_issues, 2].value = str(datetime.datetime.fromtimestamp(issue.created))
                issues_sheet[start_issues, 2].inner_border_width = 50
                date_closing = get_date_closing(issue)
                if date_closing != '':
                    issues_sheet[start_issues, 0:10].background_color = 0xdedede
                issues_sheet[start_issues, 3].value = str(date_closing)
                issues_sheet[start_issues, 4].value = seconds_to_time(iss.time_estimate) + ' h'
                issues_sheet[start_issues, 5].value = seconds_to_time(iss.time_spent) + ' h'

                # todo get color of marks
                start_issues += 1

                # issues_sheet[1:10, 5].border_right_width = 1


                # todo $3
                # doc.save(xls_file, pyoo.FILTER_EXCEL_2007)
                # doc.close()


def check_office_server():
    """:returns bool """
    if not check_server(sohost, soport):
        print('LibreOffice server not started.')
        with open("libre.log", "wb") as out, open("libre.err", "wb") as err:
            # command = '/Applications/LibreOffice.app/Contents/MacOS/soffice --accept="socket,host={0},port={1};urp;" --norestore --nologo --nodefault --headless'.format(
            # sohost, str(soport))
            # subprocess.Popen(command.split(), stdout=out, stderr=err) # close_fds=True
            print('Please start libreoffice server with command:')
            print(
                "soffice --accept='socket,host={0},port={1};urp;StarOffice.Service'".format(
                    sohost, str(soport)))
            sys.exit()
    else:
        print('LibreOfice server already running... Good!')
        return True


def login_gl():
    # open connection to gitlab server
    gl = gitlab.Gitlab(gitlab_url, email=email, password=password)
    try:
        gl.auth()
    except:
        print('error auth gl')
        sys.exit()
    return gl


# Main entrance
if __name__ == '__main__':
    # Start main processing pipeline
    print('connect to db')
    db = SqliteDatabase(db_path)  # temp db on sqlite3
    db.connect()
    tables = (db.get_tables(OLAP))
    if len(tables) == 0:
        print('empty db, create table')
        db.create_table(OLAP)
    db.close()
    print('Check office server:')
    check_office_server()
    print('Init gl')
    gl = login_gl()
    print('Prepare issues...')
    prepare_issues(gl)
    read_issues(dbname)
    print('Write to csv file...')
    write_issues_to_csv(issues)
    print()
    print('Calculate times...')
    print('Assignee \t\t\t estimate time \t spent time')
    calc_times(issues)
    print_assignees()

    print('writing to xlsx')
    write_to_xls()

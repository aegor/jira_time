#!/usr/bin/python3
# -*- coding: utf-8 -*-

#  system libs
import datetime
import json
import shelve
import sys
import logging
import argparse
from collections import namedtuple

# imported libs
import unotools
from unotools.component.calc import Calc
import uno
import gitlab
import unicodecsv as csv
from peewee import *

# created modules
from models import OLAP
from config import *

# config of argparser
# todo make help of args
parser = argparse.ArgumentParser(description='Args of this module')
parser.add_argument('-t', action='store')
args = parser.parse_args()


# set level of logging
logging.basicConfig(level=logging.INFO, format=u'%(filename)s[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s')
# Issues global DB
issues = []
# Assignees global DB
# format: {'assignee email': {'time_estimate': secs, 'time_spent': secs}}
assignees = {}

UNDERLINE_SINGLE = uno.getConstantByName('com.sun.star.awt.FontUnderline.SINGLE')

# End of globals

class Issue:
    """methods and structure of issue"""

    @staticmethod
    def _convert_time(time_string: str):
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

            return int(converted_datetime.timestamp())  # 18000 - +5h - Ekaterinburg
        else:
            return ''

    def __init__(self, issue):
        # todo see down
        # updating created time for issue in db, remove it after updating

        q = OLAP.update(created=self._convert_time(issue.created_at)).where(OLAP.issue_id == issue.id)
        q.execute()

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
        self.url = getattr(issue, 'web_url', '')
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
            self.milestone_created = ''

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
    logging.info('\nGROUPS:')
    for group in groups:
        if group.parent_id is not None:
            report = gl.groups.get(group.parent_id).name + '/'
        else:
            report = ''
        logging.info(report + group.name)


def write_issues_to_csv(issues):
    """write issues into issues.csv"""
    with open(issues_csv_file, 'wb') as f:
        writer = csv.writer(f, encoding='utf-8')
        writer.writerow(
            ('id', 'title', 'description', 'projects', 'assignee', 'author', 'created', 'updated', 'due_date',
             'labels', 'state', 'milestone_title', 'milestone_description', 'milestone_created',
             'milestone_due_date', 'time_estimate', 'time_spent', 'url'))
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
    up_time = int(datetime.datetime.now().timestamp()) - 18000

    for issue in issues:
        key = issue.assignee
        if key is not '':
            if key in assignees:
                # assignees[key] = {'time_estimate': issue.time_estimate_secs + te, 'time_spent': issue.time_spent_secs + ts}
                entry, new = OLAP.get_or_create(issue_id=issue.issue_id)
                fill_field(issue, entry, new, up_time)
            else:
                try:
                    name, tg = map(lambda x: x.strip(), key.split('@'))
                except ValueError:
                    name = key.strip()
                assignees[key] = {'name': name}
                entry, new = OLAP.get_or_create(issue_id=issue.issue_id)
                fill_field(issue, entry, new, up_time)


def prepare_issues(gl):
    """read issues from gitlab whose starts with on key phrase """
    iss = []
    projects = gl.projects.list(per_page=1000)

    if plog:
        logging.info('Projects:')
    # Prepare issues database
    for project in projects:
        #if project.path_with_namespace.startswith('p2p-test'):
        if project.path_with_namespace.startswith('rtk'):
            if plog:
                logging.info(project.path_with_namespace)
            project_issues = project.issues.list(per_page=1000)
            for i in project_issues:
                i.project = project.path_with_namespace
                # print(i)
            iss.extend(project_issues)
    # possible shelve flags: c - create if need, then read/write, r - readonly, w - rw, n - always create new db
    db = shelve.open(dbname, writeback=True, flag='c')
    idx = 0
    for i in iss:
        db[str(idx)] = Issue(i)
        idx = idx + 1
    db.close()


def read_issues(dbname):
    """read issues from 'issues'"""
    db = shelve.open(dbname, writeback=True, flag='w')  # flag='r'
    for i in db.keys():
        issues.append(db[i])
        # db.close() !!! strange... always call sync, even on readonly file??? Why?


class ReportIssue:
    def __init__(self, issue, before: datetime.datetime, ranges):

        self.issue = issue
        self.before = before
        self.ranges = ranges

    def generate_report(self):
        """preparing report for current issue"""
        OLAP_data = OLAP.select().where(OLAP.issue_id == self.issue.issue_id)
        created = self.issue.created
        # old issues
        issue_data = []

        closed_day = OLAP.select(OLAP.issue_id,
                                 fn.Min(OLAP.updated),
                                 OLAP.time_estimate,
                                 OLAP.time_spent).where((OLAP.issue_id == self.issue.issue_id) &
                                                        (OLAP.state == 'closed')).get()
        range_template = namedtuple('dates_range', ['begin', 'end'])
        issue_range = range_template(self.issue.created, closed_day.updated)

        if closed_day.updated is not None:
            # here working
            if closed_day.updated < self.before.timestamp():
                return (seconds_to_time(closed_day.time_estimate) + ' h'
                        , seconds_to_time(closed_day.time_spent) + ' h',
                        '',  '', '', '', '', '', '', '')
            else:
                report = ['', '']
                previous_spent = 0
                _ranges = range_template(ReportCalc.get_first_sec(self.ranges[0][0]), ReportCalc.get_last_sec(self.ranges[len(self.ranges) - 1][1]))
                for w in self.ranges:
                    current_issue_OLAP = OLAP.select(fn.Max(OLAP.updated),
                                                     OLAP.time_estimate,
                                                     OLAP.time_spent).where(
                        (OLAP.updated < ReportCalc.get_last_sec(w[1])) &
                        (OLAP.issue_id == self.issue.issue_id)).get()
                    if (self.issue.created > ReportCalc.get_first_sec(w[0])) and (closed_day.updated < ReportCalc.get_last_sec(w[1])):
                        report.append(seconds_to_time(closed_day.time_estimate) + ' h')
                        report.append(seconds_to_time(closed_day.time_spent) + ' h')
                    elif self.issue.created > ReportCalc.get_first_sec(w[0]):
                        if previous_spent == 0:
                            if current_issue_OLAP.time_spent:
                                previous_spent += current_issue_OLAP.time_spent
                                report.append(seconds_to_time(previous_spent) + ' h')
                                report.append(seconds_to_time(current_issue_OLAP.time_spent) + ' h')
                            else:
                                # todo check on this value
                                report.append(seconds_to_time(previous_spent) + ' h')
                                report.append(seconds_to_time(self.issue.time_spent_secs) + ' h')
                        else:
                            report.append('e')
                            report.append('e')
                    else:
                        if issue_range.begin < _ranges.begin and issue_range.end < datetime.datetime.timestamp(w[1]):
                            report.append(seconds_to_time(current_issue_OLAP.time_estimate) + ' h')
                            report.append(seconds_to_time(current_issue_OLAP.time_spent) + ' h')
                            pass
                        else:
                            report.append('')
                            report.append('')
                if self.issue.created > _ranges.end:
                    # print(self.issue.created.fromtimestamp(), datetime.dated ranges_end, self.issue.created > ranges_end)
                    report.append(seconds_to_time(closed_day.time_estimate) + ' h')
                    report.append(seconds_to_time(closed_day.time_spent) + ' h')
                else:
                    report.append('')
                    report.append('')
                return tuple(report)
        else:
            # todo make report on non complete issue

            pass
            return ('', '', '', '', '', '', '', '', '', '')


class ReportCalc:

    date_format = '%d %m %Y'
    line = uno.createUnoStruct('com.sun.star.table.BorderLine2')
    line.OuterLineWidth = 1
    keys = ('TopBorder', 'RightBorder', 'BottomBorder', 'LeftBorder')
    border_lines = (line, line, line, line)  # uno vars for border lines
    column_names = [
        'Проект',
        'Задача',
        'Открыто',
        'Закрыто',
        'План',
        'Факт']

    project_column = 0
    issues_column = 1
    opened_column = 2
    closed_column = 3
    estimate_column = 4
    spend_column = 5

    def __init__(self):
        self.write_to_xls()
    # uno vars for border lines

    @staticmethod
    def get_date_closing(issue):
        """:return date of cloising of current issue"""
        last_issue = OLAP.select(OLAP.issue_id, fn.Min(OLAP.updated)).where((OLAP.issue_id == issue.issue_id) &
                                                                            (OLAP.state == 'closed')).get()
        return '' if last_issue.updated is None else datetime.datetime.fromtimestamp(
            last_issue.updated).strftime(
            '%d-%m-%Y %H:%M')

    @staticmethod
    def get_day(day: datetime.datetime, index: int):
        """count of index starts from zero"""
        if day.weekday() == index:
            pass
        elif day.weekday()  > index:
            while (day.weekday() != index):
                day = day - datetime.timedelta(days=1)
        elif day.weekday() < index:
            while (day.weekday() != index):
                day = day + datetime.timedelta(days=1)
        return day

    @staticmethod
    def get_first_sec(day: datetime.datetime):
        """:return timestamp of 00.01 of current day"""
        d = datetime.datetime(day.year,
                              day.month,
                              day.day,
                              00, 1)
        return datetime.datetime.timestamp(d)

    @staticmethod
    def get_last_sec(day: datetime.datetime):
        """return timestamp of 23.59 of current day"""
        d = datetime.datetime(day.year,
                              day.month,
                              day.day,
                              23, 59)
        return datetime.datetime.timestamp(d)

    def get_middle_day_of_week(self, week_number):
        counted_week = datetime.datetime.today()
        while counted_week.isocalendar()[1] != week_number:
            if counted_week.isocalendar()[1] < week_number:
                counted_week = counted_week + datetime.timedelta(weeks=1)
            elif counted_week.isocalendar()[1] > week_number:
                counted_week = counted_week - datetime.timedelta(weeks=1)
            else:
                pass

        # set on middle
        while counted_week.weekday() != 2:
            if counted_week.weekday() > 2:
                counted_week = counted_week - datetime.timedelta(days=1)
            elif counted_week.weekday() < 2:
                counted_week = counted_week + datetime.timedelta(days=1)
            else:
                pass

        return counted_week

    def get_range_days_of_week(self, week_number, min, max):
        middle_day = self.get_middle_day_of_week(week_number)
        min = self.get_day(middle_day, min)
        max = self.get_day(middle_day, max)
        return (min, max)

    def fill_header(self, sheet, name):
        """fill header of sheet with current assignee"""

        # data of columns
        columns = [self.project_column,
                   self.issues_column,
                   self.opened_column,
                   self.closed_column,
                   self.estimate_column,
                   self.spend_column]
        # fill service data

        sheet.get_cell_range_by_position(0, 2, 5, 2).setDataArray(((tuple(self.column_names)),))
        # for text in columns:
        #    sheet.get_cell_by_position(text, 1).setDataArray(((self.column_names[columns.index(text)],),))
        sheet.get_cell_range_by_position(2, 0, 3, 2).Columns.Width = 4000

        sheet.get_cell_range_by_name("A1:B1").merge(True)
        # set cell 0.0 to name os assignee
        sheet.get_cell_by_position(0, 0).setDataArray(((name,),))
        # data of columns

        sheet.get_cell_by_position(0, 3).setDataArray((("Итого",),))
        # make row of result green with borders
        # green background for total time

        green_row = sheet.get_cell_range_by_position(0, 3, 13, 3)
        green_row.setPropertyValue('CellBackColor', 0x00aa00)
        green_row.setPropertyValues(self.keys, self.border_lines)

    def write_to_xls(self):
        # connect
        from unotools.unohelper import convert_path_to_url

        context = unotools.connect(unotools.Socket(host=sohost, port=soport))
        calc = Calc(context)
        filled_issue = 0

        # create tables of assignees
        for assignee in assignees:
            if assignee:
                # get name of assignee
                try:
                    name, _ = map(lambda x: x.strip(), assignee.split('@'))
                except ValueError:
                    name = assignee.strip()

                calc.insert_sheets_new_by_name(name, 0)  # returns None

                sheet = calc.get_sheet_by_name(name)

                self.fill_header(sheet, name)

                w4_end = self.get_day(datetime.datetime.now(), 4)
                w4_start = self.get_day(datetime.datetime.now(), 0)

                weeks = []
                weeks_timestamp = []
                this_week_num = w4_end.isocalendar()[1]
                before_date = ''
                for week in reversed(range(1, 4)):
                    days_range = self.get_range_days_of_week(this_week_num-week, 0, 6)
                    weeks_timestamp.append(days_range)
                    weeks.append(days_range[0].strftime(self.date_format) + ' - ' + days_range[1].strftime(self.date_format))
                    if before_date == '':
                        before_date = self.get_range_days_of_week(this_week_num-week-1, 0, 6)[1]

                weeks.append(str(w4_start.strftime(self.date_format)) + ' - ' + str(w4_end.strftime(self.date_format)))
                # filling before
                before = sheet.get_cell_range_by_position(4, 1, 5, 1)

                before.setDataArray((('< ' + before_date.strftime(self.date_format), ''),))
                before.merge(True)
                align = before.getPropertyValue('HoriJustify')
                align.value = 'CENTER'
                before.setPropertyValue('HoriJustify', align)

                for w in weeks:
                    cell = sheet.get_cell_by_position(6 + weeks.index(w) * 2, 1)
                    cell.setString(w)
                    cells = sheet.get_cell_range_by_position(6 + weeks.index(w) * 2, 1, 7 + weeks.index(w) * 2, 1)
                    cells.merge(True)
                    align = cell.getPropertyValue('HoriJustify')  # property of align 'VertJustify' had too
                    align.value = 'CENTER'
                    cells.setPropertyValue('HoriJustify', align)
                    sheet.get_cell_by_position(6 + weeks.index(w) * 2, 2).setString("План")
                    sheet.get_cell_by_position(7 + weeks.index(w) * 2, 2).setString("Факт")
                logging.info('filling report of: ' + assignee)
                # make headers:

                # total ts and te of assignee
                lines = 4  # start count from 1 row [in GUI 2]
                ts, te = 0, 0
                for issue in issues:

                    if issue.assignee == assignee:
                        report_issue = ReportIssue(issue, before_date, weeks_timestamp)
                        report_issue.generate_report()
                        iss = OLAP.select().where(OLAP.issue_id == issue.issue_id).get()
                        line = sheet.get_cell_range_by_position(0, lines, 3, lines)

                        date_closing = self.get_date_closing(issue)
                        if date_closing != '':
                            row = sheet.get_cell_range_by_position(0, lines, 13, lines)
                            row.setPropertyValue('CellBackColor', 0xdedede)

                            row.setPropertyValues(self.keys, self.border_lines)

                        line.setDataArray(((iss.project_name,
                                           iss.issue_title,
                                           str(datetime.datetime.fromtimestamp(issue.created + 18000).strftime(
                                               '%d-%m-%Y %H:%M')),
                                           date_closing,),))
                        line = sheet.get_cell_range_by_position(4, lines, 13, lines)
                        t = report_issue.generate_report()
                        line.setDataArray(((t),))
                        hyperlink_issue = issue.url
                        title = sheet.get_cell_by_position(1, lines)
                        title.Text.Hyperlink = hyperlink_issue
                        title.Text.CharUnderline = UNDERLINE_SINGLE
                        title.Text.CharColor = 0x0000aa
                        title.Rows.Height = 600

                        ts += iss.time_spent
                        te += iss.time_estimate
                        filled_issue += 1

                        lines += 1
                        del issue

                # sheet.get_cell_by_position(self.estimate_column, 3).setString(seconds_to_time(te) + ' h')
                # sheet.get_cell_by_position(self.spend_column, 3).setString(seconds_to_time(ts) + ' h')
                sheet.get_cell_range_by_position(1, 0, 1, 0).Columns.Width = 6000
                sheet.get_cell_range_by_position(4, 0, 5, 2).Columns.OptimalWidth = True
        calc.remove_sheets_by_name('Sheet1')
        calc.insert_sheets_new_by_name('Список', 0)
        assignee_sheet = calc.get_sheet_by_index(0)
        assignee_list = []
        for assignee in assignees:
            try:
                name, _ = map(lambda x: x.strip(), assignee.split('@'))
            except ValueError:
                name = assignee.strip()
            assignee_list.append(name)
        assignee_list = sorted(assignee_list)
        for assignee in assignee_list:
            cell = assignee_sheet.get_cell_by_position(0, assignee_list.index(assignee))
            cell.setString(assignee)
            cell.Text.Hyperlink = '#{0}'.format(assignee)

        # here filling hyperlinks of assignee
        logging.info(str(filled_issue) + ' issues from ' +  str(len(issues)) + ' have assignee')
        # issues_sheet[1:10, 5].border_right_width = 1

        # todo $3
        # doc.save(xls_file, pyoo.FILTER_EXCEL_2007)
        # doc.close()


def check_office_server():
    """:returns bool """
    if not check_server(sohost, soport):
        logging.error('LibreOffice server not started.')
        with open("libre.log", "wb") as out, open("libre.err", "wb") as err:
            # command = '/Applications/LibreOffice.app/Contents/MacOS/soffice --accept="socket,host={0},port={1};urp;" --norestore --nologo --nodefault --headless'.format(
            # sohost, str(soport))
            # subprocess.Popen(command.split(), stdout=out, stderr=err) # close_fds=True
            logging.error('Please start libreoffice server with command:\n')
            logging.warning("soffice --accept='socket,host={0},port={1};urp;StarOffice.Service'".format(
                    sohost, str(soport)))
            sys.exit()
    else:
        logging.info('LibreOfice server already running... Good!')
        return True


def login_gl():
    # open connection to gitlab server
    gl = gitlab.Gitlab(gitlab_url, email=email, password=password)
    try:
        gl.auth()
    except:
        logging.warning('error auth gl')
        sys.exit()
    return gl


# Main entrance
if __name__ == '__main__':
    # Start main processing pipeline
    logging.info('connect to db')
    db = SqliteDatabase(db_path)  # temp db on sqlite3
    db.connect()
    tables = (db.get_tables(OLAP))
    if len(tables) == 0:
        logging.warning('empty db, create table')
        db.create_table(OLAP)

    db.close()

    logging.info('Init gl')
    gl = login_gl()

    logging.info('Prepare issues...')
    prepare_issues(gl)

    read_issues(dbname)
    logging.info('Write to csv file...')
    write_issues_to_csv(issues)
    logging.info('Calculate times...')
#    print('Assignee \t\t\t estimate time \t spent time')
    calc_times(issues)

    if args.t == 'y':
        logging.info('Check office server:')
        check_office_server()
        logging.info('writing to xlsx')
        filled_report = ReportCalc()


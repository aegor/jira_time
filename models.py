import json

from peewee import *

from config import db_path
db = SqliteDatabase(db_path)


class ChoiceField(IntegerField):
    def db_value(self, value):
        return self.choices.index(value)

    def python_value(self, value):
        return self.choices[value]


class OLAP(Model):
    """contain data for analysis"""
    issue_id = IntegerField(null=True)
    issue_title = CharField(null=True)
    assignee = CharField(null=True)
    created = IntegerField(null=True)
    state = ChoiceField(choices=('closed', 'opened', 'reopened'), default='opened')
    time_estimate = IntegerField(null=True)
    time_spent = IntegerField(null=True)
    updated = IntegerField(null=True)
    query_time = IntegerField(null=True)  # time stamp
    project_name = CharField(null=True)
    project_id = IntegerField(null=True)
    milestone_title = TextField(null=True)
    milestone_date = IntegerField(null=True)

    def __str__(self):
        r = {}
        for k in self._data.keys():
            try:
                r[k] = str(getattr(self, k))
            except:
                r[k] = json.dumps(getattr(self, k))
        return str(r)


    class Meta:
        database = db

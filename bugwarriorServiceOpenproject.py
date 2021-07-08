# -*- coding: utf-8 -*-
# This file is part of BugWarriorOpenProjectService.
#
# BugWarriorOpenProjectService is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BugWarriorOpenProjectService is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with BugWarriorOpenProjectService. If not, see <http://www.gnu.org/licenses/>.

# Heavily based on bugwarrior.services.redmine
#
# Author:
#   "Emir Herrera González" 

import six
import requests
import re
import html

from bugwarrior.config import die, asbool
from bugwarrior.services import Issue, IssueService, ServiceClient
from taskw import TaskWarriorShellout

from datetime import timedelta
from isodate import parse_duration

from pytz import timezone,UTC
from dateutil.tz import tzutc

import logging

log = logging.getLogger(__name__)

class OpenProjectClient(ServiceClient):
    def __init__(self, url, key, auth, issue_limit, verify_ssl):
        self.url = url
        self.key = key
        self.auth = auth
        self.issue_limit = issue_limit
        self.verify_ssl = verify_ssl

    def getFilters(self, only_if_assigned=False, project=None):
        filters = """["""
        filters +=  """{"status": {"operator": "o"} }"""
        if(only_if_assigned):
            filters +=  """,{"assignee": {"operator": "=", "values": ["me"]}}"""
        if (project):
            filters += f""",{{"project": {{"operator": "=", "values": ["{project}"] }} }}"""

        filters += """]"""

        return filters

    def find_issues(self, issue_limit=100, only_if_assigned=False, project=None):

        filters = self.getFilters(only_if_assigned, project)


        args = {
          "sortBy": """[
            ["priority", "desc"],
            ["dueDate", "asc"],
            ["startDate", "asc"],
            ["status", "desc"],
            ["type", "desc"],
            ["percentageDone", "desc"],
            ["assignee", "desc"]
          ]""",
          "filters": filters
        }
        # TODO: if issue_limit is greater than 100, implement pagination to return all issues.
        # Leave the implementation of this to the unlucky soul with >100 issues assigned to them.
        if issue_limit is not None:
            args["pageSize"] = issue_limit

        return self.call_api("/", args)["_embedded"]["elements"]

    def call_api(self, uri, params):
        url = self.url.rstrip("/") + uri
        kwargs = {
            'headers': {'X-OpenProject-API-Key': self.key},
            'params': params}

        if self.auth:
            kwargs['auth'] = self.auth

        kwargs['verify'] = self.verify_ssl

        openproject_api_get_workpackage_response = requests.get(url, **kwargs);
        json_workpackage_response = self.json_response(openproject_api_get_workpackage_response);

        return json_workpackage_response;


class OpenProjectIssue(Issue):
    URL = 'openprojecturl'
    SUBJECT = 'openprojectsubject'
    TYPE = 'openprojecttype'
    ID = 'openprojectid'
    DESCRIPTION = 'openprojectdescription'
    TRACKER = 'openprojecttracker'
    STATUS = 'openprojectstatus'
    AUTHOR = 'openprojectauthor'
    CATEGORY = 'openprojectcategory'
    START_DATE = 'scheduled'
    SPENT_HOURS = 'openprojectspenthours'
    ESTIMATED_HOURS = 'etc'
    CREATED_ON = 'entry'
    UPDATED_ON = 'openprojectupdatedon'
    DUEDATE = 'due'
    ASSIGNED_TO = 'openprojectassignedto'
    PROJECT_NAME = 'project'
    TAGS = 'tags'
    PRIORITY = 'priority'
    ANNOTATIONS = 'annotations'

    UDAS = {
        URL: {
            'type': 'string',
            'label': 'OpenProject URL',
        },
        SUBJECT: {
            'type': 'string',
            'label': 'OpenProject Subject',
        },
        ID: {
            'type': 'numeric',
            'label': 'OpenProject ID',
        },
        DESCRIPTION: {
            'type': 'string',
            'label': 'OpenProject Description',
        },
        TRACKER: {
            'type': 'string',
            'label': 'OpenProject Tracker',
        },
        STATUS: {
            'type': 'string',
            'label': 'OpenProject Status',
        },
        AUTHOR: {
            'type': 'string',
            'label': 'OpenProject Author',
        },
        CATEGORY: {
            'type': 'string',
            'label': 'OpenProject Category',
        },
        SPENT_HOURS: {
            'type': 'duration',
            'label': 'OpenProject Spent Hours',
        },
        ESTIMATED_HOURS: {
            'type': 'duration',
            'label': 'OpenProject Estimated Hours',
        },
        UPDATED_ON: {
            'type': 'date',
            'label': 'OpenProject Updated On',
        },
        ASSIGNED_TO: {
            'type': 'string',
            'label': 'OpenProject Assigned To',
        },
        TYPE:{
            'type': 'string',
            'label': 'OpenProject Type',
        }
    }
    UNIQUE_KEY = (ID, )

    PRIORITY_MAP = {
        'Low': 'L',
        'Normal': 'M',
        'High': 'H',
        'Urgent': 'U',
        'Immediate': 'I',
    }

    def to_taskwarrior(self):
        start_date      = self.record.get('startDate')
        due_date        = self.record.get('dueDate') if self.record["_links"]['type']['title'] != "Milestone" else self.record.get('date')
        created_on      = self.record.get('createdAt')
        spent_hours     = parse_duration(self.record.get('spentTime')).seconds/3600 if self.record.get('spentTime') else None
        estimated_hours = parse_duration(self.record.get('estimatedTime')).seconds/3600 if self.record.get('estimatedTime') else None
        subject         = self.record['subject']
        
        category = self.record.get('category')
        assigned_to = self.record.get('_links', {'assignee': None}).get('assignee')
        localtz = timezone('America/Mexico_City')

        if due_date:
            due_date = localtz.localize(self.parse_date(due_date).replace(microsecond=0, hour=23, minute=59, second=59, tzinfo=None)).astimezone(tzutc())
        if start_date:
            start_date = localtz.localize(self.parse_date(start_date).replace(microsecond=0, tzinfo=None)).astimezone(tzutc())
        if created_on:
            created_on = localtz.localize(self.parse_date(created_on).replace(microsecond=0, tzinfo=None))
        if spent_hours:
            spent_hours = str(spent_hours) + ' hours'
            spent_hours = self.get_converted_hours(spent_hours)
        elif spent_hours == 0.0:
            spent_hours = None
        if estimated_hours:
            estimated_hours = str(estimated_hours) + ' hours'
            estimated_hours = self.get_converted_hours(estimated_hours)
        elif estimated_hours == 0.0:
            estimated_hours = None
        if category:
            category = category['name']
        if assigned_to:
            assigned_to = assigned_to.get('title')
        if subject:
            subject = html.unescape(subject)


        return {
            self.ANNOTATIONS: self.extra.get('annotations', []),
            self.PRIORITY: self.get_priority(),
            self.SUBJECT: self.record['subject'],
            self.ID: self.record['id'],
            self.DESCRIPTION: self.record.get('description', {}).get('raw', ''),
            self.TRACKER: self.record["_links"]['author']['title'],
            self.STATUS: self.record["_links"]['status']['title'],
            self.AUTHOR: self.record["_links"]['author']['title'],
            self.TYPE: self.record["_links"]['type']['title'],
            self.PROJECT_NAME: self.record["_links"]['project']['title'],
            self.ASSIGNED_TO: assigned_to,
            self.CATEGORY: category,
            self.START_DATE: start_date,
            self.CREATED_ON: created_on,
            self.DUEDATE: due_date,
            self.ESTIMATED_HOURS: estimated_hours,
            self.SPENT_HOURS: spent_hours,
            self.TAGS:[
                "OP#" + str(self.record['id']),
                self.get_project_name()
            ],
        }

    def get_priority(self):
        return self.PRIORITY_MAP.get(
            self.record["_links"].get('priority', {}).get('title'),
            self.origin['default_priority']
        )

    def get_converted_hours(self, estimated_hours):
        tw = TaskWarriorShellout()
        calc = tw._execute('calc', estimated_hours)
        return (
            calc[0].rstrip()
        )

    def get_project_name(self):
        if self.origin['project_name']:
            return self.origin['project_name']
        # TODO: It would be nice to use the full project hierarchy, but this would require (1) an API call
        # to get the list of projects, and then a look up between the
        # project ID contained in self record and the list of projects.
        return re.sub(r'[^a-zA-Z0-9]', '', self.record["_links"]["project"]["title"]).lower()

    def build_default_description(self, title, number, cls):
        return f"(bw){cls}#{number} - {title}"

    def get_default_description(self):
        return self.build_default_description(
            title=html.unescape(self.record['subject']),
            number=self.record['id'],
            cls=self.record["_links"]['type']['title'],
        )


class OpenProjectService(IssueService):
    ISSUE_CLASS = OpenProjectIssue
    CONFIG_PREFIX = 'openproject'

    def __init__(self, *args, **kw):
        super(OpenProjectService, self).__init__(*args, **kw)

        self.url = self.config.get('url').rstrip("/")
        self.key = self.get_password('key')
        self.issue_limit = self.config.get('issue_limit')

        self.verify_ssl = self.config.get(
            'verify_ssl', default=True, to_type=asbool
        )

        login = self.config.get('login')
        auth = ('apikey', self.key) if (self.key) else None
        self.client = OpenProjectClient(self.url, self.key, auth, self.issue_limit, self.verify_ssl)

        self.project_name = self.config.get('project_name')

    def get_service_metadata(self):
        return {
            'project_name': self.project_name,
            'url': self.url,
        }

    @staticmethod
    def get_keyring_service(service_config):
        url = service_config.get('url')
        login = service_config.get('login')
        return "openproject://%s@%s/" % (login, url)

    @classmethod
    def validate_config(cls, service_config, target):
        for k in ('url', 'key'):
            if k not in service_config:
                die("[%s] has no 'openproject.%s'" % (target, k))

        IssueService.validate_config(service_config, target)

    def issues(self):
        only_if_assigned = self.config.get('only_if_assigned', False)
        filter_project_id = self.config.get('filter_project_id', None)
        issues = self.client.find_issues(self.issue_limit, only_if_assigned, filter_project_id)
        log.debug(" Found %i total.", len(issues))
        for issue in issues:
            yield self.get_issue_for_record(issue)

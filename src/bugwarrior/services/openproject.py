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

from collections.abc import Iterator
import html
import logging
import re
import typing
from typing import Any

from dateutil.parser import isoparse
from dateutil.tz import tzlocal, tzutc
from isodate import parse_duration
import requests
from taskw import TaskWarriorShellout

from bugwarrior import config
from bugwarrior.services import Client, Issue, Service

log = logging.getLogger(__name__)


class OpenProjectConfig(config.ServiceConfig):
    _DEPRECATE_PROJECT_NAME: typing.ClassVar[bool] = True
    project_name: str = ""

    service: typing.Literal["openproject"]
    KEYRING_SERVICE: typing.ClassVar[str] = "openproject://{login}@{url}/"
    url: config.StrippedTrailingSlashUrl
    key: str

    issue_limit: int = 100
    login: str = ""
    password: str = ""
    verify_ssl: bool = True
    only_if_assigned: bool = False
    filter_project_id: str = ""


class OpenProjectClient(Client):
    def __init__(
        self,
        url: str,
        key: str,
        auth: tuple[str, str] | None,
        issue_limit: int | None,
        verify_ssl: bool,
    ) -> None:
        self.url = url
        self.key = key
        self.auth = auth
        self.issue_limit = issue_limit
        self.verify_ssl = verify_ssl

    def get_filters(self, only_if_assigned: bool = False, project: str = "") -> str:
        filters = "["
        filters += '{"status": {"operator": "o"} }'
        if only_if_assigned:
            filters += ',{"assignee": {"operator": "=", "values": ["me"]}}'
        if project:
            filters += (f', {{"project": {{"operator": "=", "values": ["'
                        f'{project}"] }} }}')
        filters += "]"
        return filters

    def find_issues(
        self, issue_limit: int | None, only_if_assigned: bool = False, project: str = ""
    ) -> list[dict[str, Any]]:
        filters = self.get_filters(only_if_assigned, project)
        args = {
            "sortBy": '[["priority", "desc"], ["dueDate", "asc"], ["startDate", "asc"], ["status", "desc"], ["type", "desc"], ["percentageDone", "desc"], ["assignee", "desc"]]',
            "filters": filters,
        }
        if issue_limit is not None:
            args["pageSize"] = issue_limit

        return self.call_api("/", args)["_embedded"]["elements"]

    def call_api(self, uri: str, params: dict[str, Any]) -> dict[str, Any]:
        url = self.url.rstrip("/") + uri
        kwargs: dict[str, Any] = {
            "headers": {"X-OpenProject-API-Key": self.key},
            "params": params,
            "verify": self.verify_ssl,
        }

        if self.auth:
            kwargs["auth"] = self.auth

        return self.json_response(requests.get(url, **kwargs))


class OpenProjectIssue(Issue):
    URL = "openprojecturl"
    SUBJECT = "openprojectsubject"
    TYPE = "openprojecttype"
    ID = "openprojectid"
    DESCRIPTION = "openprojectdescription"
    TRACKER = "openprojecttracker"
    STATUS = "openprojectstatus"
    AUTHOR = "openprojectauthor"
    CATEGORY = "openprojectcategory"
    START_DATE = "scheduled"
    SPENT_HOURS = "openprojectspenthours"
    ESTIMATED_HOURS = "etc"
    CREATED_ON = "entry"
    UPDATED_ON = "openprojectupdatedon"
    DUEDATE = "due"
    ASSIGNED_TO = "openprojectassignedto"
    PROJECT_NAME = "project"
    TAGS = "tags"
    PRIORITY = "priority"
    ANNOTATIONS = "annotations"

    UDAS = {
        URL: {
            "type": "string",
            "label": "OpenProject URL",
        },
        SUBJECT: {
            "type": "string",
            "label": "OpenProject Subject",
        },
        ID: {
            "type": "numeric",
            "label": "OpenProject ID",
        },
        DESCRIPTION: {
            "type": "string",
            "label": "OpenProject Description",
        },
        TRACKER: {
            "type": "string",
            "label": "OpenProject Tracker",
        },
        STATUS: {
            "type": "string",
            "label": "OpenProject Status",
        },
        AUTHOR: {
            "type": "string",
            "label": "OpenProject Author",
        },
        CATEGORY: {
            "type": "string",
            "label": "OpenProject Category",
        },
        SPENT_HOURS: {
            "type": "duration",
            "label": "OpenProject Spent Hours",
        },
        ESTIMATED_HOURS: {
            "type": "duration",
            "label": "OpenProject Estimated Hours",
        },
        UPDATED_ON: {
            "type": "date",
            "label": "OpenProject Updated On",
        },
        ASSIGNED_TO: {
            "type": "string",
            "label": "OpenProject Assigned To",
        },
        TYPE: {
            "type": "string",
            "label": "OpenProject Type",
        },
    }
    UNIQUE_KEY = (ID,)

    PRIORITY_MAP: dict[str, str] = {
        "Low": "L",
        "Normal": "M",
        "High": "H",
        "Urgent": "U",
        "Immediate": "I",
    }

    def to_taskwarrior(self) -> dict[str, Any]:
        start_date = self.record.get("startDate")
        due_date = (
            self.record.get("dueDate")
            if self.record["_links"]["type"]["title"] != "Milestone"
            else self.record.get("date")
        )
        created_on = self.record.get("createdAt")
        spent_hours = (
            parse_duration(self.record.get("spentTime")).seconds / 3600
            if self.record.get("spentTime")
            else None
        )
        estimated_hours = (
            parse_duration(self.record.get("estimatedTime")).seconds / 3600
            if self.record.get("estimatedTime")
            else None
        )
        subject = self.record["subject"]

        category = self.record.get("category")
        assigned_to = self.record.get(
            "_links", {"assignee": None}).get("assignee")
        if due_date:
            # Date-only value: end of that day in the system local zone.
            due_date = (
                isoparse(due_date)
                .replace(hour=23, minute=59, second=59, microsecond=0, tzinfo=tzlocal())
                .astimezone(tzutc())
            )
        if start_date:
            # Date-only value: start of that day in the system local zone.
            start_date = (
                isoparse(start_date)
                .replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=tzlocal())
                .astimezone(tzutc())
            )
        if created_on:
            # Full UTC timestamp from the API: convert to the system local zone.
            created_on = isoparse(created_on)
            if created_on.tzinfo is None:
                created_on = created_on.replace(tzinfo=tzutc())
            created_on = created_on.astimezone(tzlocal()).replace(microsecond=0)
        if spent_hours:
            spent_hours = str(spent_hours) + " hours"
            spent_hours = self.get_converted_hours(spent_hours)
        elif spent_hours == 0.0:
            spent_hours = None
        if estimated_hours:
            estimated_hours = str(estimated_hours) + " hours"
            estimated_hours = self.get_converted_hours(estimated_hours)
        elif estimated_hours == 0.0:
            estimated_hours = None
        if category:
            category = category["name"]
        if assigned_to:
            assigned_to = assigned_to.get("title")
        if subject:
            subject = html.unescape(subject)

        return {
            self.ANNOTATIONS: self.extra.get("annotations", []),
            self.PRIORITY: self.get_priority(),
            self.SUBJECT: subject,
            self.ID: self.record["id"],
            self.DESCRIPTION: self.record.get("description", {}).get("raw", ""),
            self.TRACKER: self.record["_links"]["author"]["title"],
            self.STATUS: self.record["_links"]["status"]["title"],
            self.AUTHOR: self.record["_links"]["author"]["title"],
            self.TYPE: self.record["_links"]["type"]["title"],
            self.PROJECT_NAME: self.record["_links"]["project"]["title"],
            self.ASSIGNED_TO: assigned_to,
            self.CATEGORY: category,
            self.START_DATE: start_date,
            self.CREATED_ON: created_on,
            self.DUEDATE: due_date,
            self.ESTIMATED_HOURS: estimated_hours,
            self.SPENT_HOURS: spent_hours,
            self.TAGS: [
                "OP#" + str(self.record["id"]),
                self.get_project_name(),
            ],
            self.URL: self.get_issue_url(),
        }

    def get_issue_url(self) -> str:
        return self.config.url.rstrip("/") + "/work_packages/" + str(self.record["id"])

    def get_priority(self) -> str:
        return self.PRIORITY_MAP.get(
            self.record["_links"].get("priority", {}).get("title"),
            self.config.default_priority,
        )

    def get_converted_hours(self, estimated_hours: str) -> str:
        tw = TaskWarriorShellout(config_filename=self.main_config.taskrc)
        calc = tw._execute("calc", estimated_hours)
        return calc[0].rstrip()

    def get_project_name(self) -> str:
        if self.config.project_name:
            return self.config.project_name
        return re.sub(r"[^a-zA-Z0-9]", "", self.record["_links"]["project"]["title"]).lower()

    def get_default_description(self) -> str:
        return self.build_default_description(
            title=html.unescape(self.record["subject"]),
            url=self.get_issue_url(),
            number=self.record["id"],
            cls=self.record["_links"]["type"]["title"],
        )


class OpenProjectService(Service):
    API_VERSION = 1.0
    ISSUE_CLASS = OpenProjectIssue
    CONFIG_SCHEMA = OpenProjectConfig

    def __init__(
        self, config: OpenProjectConfig, main_config: config.MainSectionConfig
    ) -> None:
        super().__init__(config, main_config)

        self.key = self.config.key or self.get_secret("key")

        # OpenProject requires the username to literally be "apikey" when using Basic Auth with a token
        auth = ("apikey", self.key) if self.key else None

        self.client = OpenProjectClient(
            self.config.url,
            self.key,
            auth,
            self.config.issue_limit,
            self.config.verify_ssl,
        )

    @staticmethod
    def get_keyring_service(service_config: OpenProjectConfig) -> str:
        return "openproject://{login}@{url}/".format(
            login=service_config.login,
            url=service_config.url,
        )

    def issues(self) -> Iterator[OpenProjectIssue]:
        issues = self.client.find_issues(
            self.config.issue_limit,
            self.config.only_if_assigned,
            self.config.filter_project_id,
        )
        log.debug(" Found %i total.", len(issues))
        for issue in issues:
            yield self.get_issue_for_record(issue)

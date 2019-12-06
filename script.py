#!/usr/bin/env python
# -*- coding: utf-8 -*-

import click
import os
import shlex
import subprocess
import tqdm

from git import Repo
from transliterate import translit
from urllib.request import urlopen

# Google Sheets import.
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle

# Google Sheets access scopes.
# Not likely to edit.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# Default settings.
# Not likely to edit.
CREDENTIALS_FILENAME = 'credentials.json'
MAX_ACTIVE_PROCESSES = 5
TOKEN_FILENAME = 'token.pickle'
WORK_DIR = 'tmp'

# Spreadsheet ID.
SPREADSHEET_ID = '1yErkGh85qOT2JLBE8H0gI29X1RE6nzj1N9SsPLY3kNQ'

# How repository url and name are formed.
REPOSIRORY_NAME_GENERATOR = lambda surname, name: '{}{}-hw1'.format(surname, name[:2])
REPOSITORY_URL_PATTERN = 'git@gitlab.atp-fivt.org:tpos2019/{repository_name}.git'
PROHIBITED_SYMBOLS = ['\'', ' ']

# Spreadsheet ranges.
SURNAME_RANGE = 'Оценки!C4:C'
NAME_RANGE = 'Оценки!D4:D'
SCORE_RANGE = 'Оценки!L4:L'

# How score is formed.
DEADLINE = 1569272400  # Sep 24 2019, 00:00
DEFAULT_SCORE = 1
AFTER_DEADLINE_SCORE_GENERATOR = lambda extra_time: 0.5
EMPTY_REPOSITORY_SCORE = 0


class Repository(object):
    def __init__(self, name, surname):
        self._name = name
        self._surname = surname
        self._repository_name = self._build_repository_name()
        self._score = DEFAULT_SCORE

    def _build_repository_name(self):
        translit_surname = translit(self._surname, 'ru', reversed=True)
        translit_name = translit(self._name, 'ru', reversed=True)
        repository_name = REPOSIRORY_NAME_GENERATOR(translit_surname, translit_name)
        for prohibited_symbol in PROHIBITED_SYMBOLS:
            repository_name = repository_name.replace(prohibited_symbol, '')
        return repository_name.lower()

    def run_clone(self):
        repository_url = REPOSITORY_URL_PATTERN.format(repository_name=self._repository_name)
        command = shlex.split('git clone {url}'.format(url=repository_url))
        return subprocess.Popen(command, cwd=WORK_DIR,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)

    def apply_deadline_score(self):
        oldest_commit_time = self._get_oldest_commit_time()
        if oldest_commit_time is None:
            self._score = EMPTY_REPOSITORY_SCORE
        elif oldest_commit_time >= DEADLINE:
            self._score = AFTER_DEADLINE_SCORE_GENERATOR(oldest_commit_time - DEADLINE)

    def _get_oldest_commit_time(self):
        local_repository_path = os.path.join(WORK_DIR, self._repository_name)
        if not os.path.exists(local_repository_path):
            return None
        repository = Repo(local_repository_path)
        master = repository.head.reference 
        if not master.is_valid():
            return None
        oldest_commit_time = None
        for commit in repository.iter_commits(rev=master):
            if oldest_commit_time is None or oldest_commit_time > commit.committed_date:
                oldest_commit_time = commit.committed_date
        return oldest_commit_time

    @property
    def owner(self):
        return "{name} {surname}".format(name=self._name, surname=self._surname)

    @property
    def score(self):
        return self._score


class Spreadsheet(object):
    def __init__(self, spreadsheet_id):
        credentials = Spreadsheet._get_credentials()
        self._sheets = Spreadsheet._get_sheets(credentials)
        self._id = spreadsheet_id

    def read(self, sheet_range):
        result = self._sheets.values().get(spreadsheetId=self._id,
                                           range=sheet_range).execute()
        values = result.get('values', [])
        return values

    def write(self, values, sheet_range):
        body = {
            'values': values
        }
        self._sheets.values().update(
            spreadsheetId=self._id, range=sheet_range,
            valueInputOption='RAW', body=body).execute()

    @staticmethod
    def _get_sheets(credentials):
        service = build('sheets', 'v4', credentials=credentials)
        return service.spreadsheets()

    @staticmethod
    def _get_credentials():
        credentials = None
        if os.path.exists(TOKEN_FILENAME):
            with open(TOKEN_FILENAME, 'rb') as token:
                credentials = pickle.load(token)

        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    CREDENTIALS_FILENAME, SCOPES)
                credentials = flow.run_local_server(port=0)
            with open(TOKEN_FILENAME, 'wb') as token:
                pickle.dump(credentials, token)

        return credentials


def make_work_dir_if_needed():
    if not os.path.exists(WORK_DIR):
        os.mkdir(WORK_DIR)


def wait_for_running_processes_if_needed(running_processes, force):
    if len(running_processes) < MAX_ACTIVE_PROCESSES and not force:
        return running_processes

    for process in running_processes:
        output_lines = process.communicate()
        output = "\n".join(line.decode() for line in output_lines)
        if 'fatal' in output:
            tqdm.tqdm.write(output)
    return []


def get_repositories(names_row, surnames_row):
    running_processes = []
    repositories = []
    users = [(name[0], surname[0]) for name, surname in zip(names_row, surnames_row)]
    for name, surname in tqdm.tqdm(users):
        running_processes = wait_for_running_processes_if_needed(running_processes, False)
        repository = Repository(name, surname)
        running_processes.append(repository.run_clone())
        repositories.append(repository)

    wait_for_running_processes_if_needed(running_processes, True)
    return repositories


def apply_new_scores(repositories, scores_row):
    new_scores_row = []
    for repository, score in zip(repositories, scores_row):
        repository.apply_deadline_score()
        current_score = float(score[0].replace(',', '.'))
        if current_score != repository.score:
            print("Score for {owner} will be changed: {old}->{new}".format(owner=repository.owner,
                                                                           old=current_score,
                                                                           new=repository.score))
        new_scores_row.append([repository.score])
    return new_scores_row


def main():
    make_work_dir_if_needed()
    sheet = Spreadsheet(SPREADSHEET_ID)
    names_row = sheet.read(NAME_RANGE)
    surnames_row = sheet.read(SURNAME_RANGE)
    scores_row = sheet.read(SCORE_RANGE)
    repositories = get_repositories(names_row, surnames_row)
    scores_row = apply_new_scores(repositories, scores_row)
    if click.confirm('Publish new score?', default=True):
        sheet.write(scores_row, SCORE_RANGE)


if __name__ == '__main__':
    main()

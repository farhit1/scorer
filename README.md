# Scorer
Автоматизированное снижение баллов за более позднюю сдачу задания 😈

## Настройка

1. Получаем файл `credentials.json` для работы с апи гугл таблиц (например, [здесь](https://developers.google.com/sheets/api/quickstart/python), нажав на синюю кнопку _Enable the Google Sheets API_). Положим его туда же, где лежит сам скрипт.
2. Скачаем питономодули:
```
pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
pip install --upgrade transliterate
pip install --upgrade tqdm
pip install --upgrade gitpython
```
3. Настраиваем константы в _script.py_:
```py
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
```

## Запуск

```
python script.py
```
Это запустит скрипт: склонирует репозитории, принадлежащие людям из таблицы, проверит даты коммитов и проставит в таблицу баллы за своевременность сдачи.

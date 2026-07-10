---
name: youtrack
description: "Создать, найти, обновить задачу в YouTrack. Назначить исполнителя, изменить статус, добавить тег. Получить информацию о задаче (IREG, TMK, FER, ADM, BI). Статистика по тегам. Создать подзадачу. Инцидент YouTrack."
aliases: [yt, youtrack-manager, issue-manager]
---

# YouTrack Issue Manager

Управление задачами в YouTrack через CLI (`yt_client.py`) и bash-скрипты.

## Конфигурация

**API параметры в `~/.env`:**
```
YOUTRACK_URL=https://yt.pkzdrav.ru        # либо YOUTRACK_BASE_URL — клиент читает оба
YOUTRACK_API_KEY=your_permanent_token_here
```

Внешних зависимостей нет — только стандартная библиотека Python 3 (≥3.7, скрипты используют `from __future__ import annotations` для совместимости с 3.9 на macOS).

**Env уже в shell.** `$YOUTRACK_URL` и `$YOUTRACK_API_KEY` экспортируются через `~/.zshrc`, поэтому `source ~/.env` в командах **не нужен** ни для `curl`, ни для `python3`. Пиши голый `curl -H "Authorization: Bearer $YOUTRACK_API_KEY" "$YOUTRACK_URL/api/..."`. `yt_client.py` дополнительно зовёт `load_env()` сам — это страховка на случай отсутствия экспорта.

**Прямой curl — когда нужен:** multipart-загрузка вложений, кастомные query-параметры YouTrack REST (например, `fields=...,customFields(...)`), которые ещё не обёрнуты в `yt_client.py`. Для info/search/create/update/stats — используй CLI/модуль, он короче и форматирует вывод. **Создание задач с типом/регионом/произвольными кастомными полями — тоже через CLI** (`create -t Epic -f "Контур=..."`): он сам определяет `$type` полей из схемы и не ловит `400 Incompatible field type`. См. «Кастомные поля — формат значений».

## CLI Reference — `yt_client.py`

Все команды поддерживают флаг `--json` для машиночитаемого вывода.

```bash
SCRIPTS="$HOME/.claude/skills/youtrack-skill/scripts"

# Информация о задаче (с описанием)
python3 "$SCRIPTS/yt_client.py" info IREG-755

# Комментарии (получить список)
python3 "$SCRIPTS/yt_client.py" comments IREG-755

# Добавить комментарий
python3 "$SCRIPTS/yt_client.py" comment IREG-755 "Текст комментария"

# Поиск задач (YouTrack query language)
python3 "$SCRIPTS/yt_client.py" search "project: IREG status: Open"
python3 "$SCRIPTS/yt_client.py" search "project: TMK assignee: bmv" --top 10

# Создание задачи
python3 "$SCRIPTS/yt_client.py" create IREG "Название задачи" \
  -d "Описание задачи" -a bmv -r "Запорожская область"

# Создание с типом (Epic/Bug/Task) и произвольными кастомными полями.
# $type полей определяется автоматически из схемы проекта (1 запрос, кэш) —
# НЕ угадывай Single/Multi вручную и НЕ уходи в raw curl ради Type/Контур.
python3 "$SCRIPTS/yt_client.py" create FER "Запуск в прод витрины v2 ХМАО" \
  -t Epic -r ХМАО -f "Контур=ХМАО: Рабочий контур" -f "Priority=Major"

# Обновление задачи (через YouTrack commands)
python3 "$SCRIPTS/yt_client.py" update IREG-755 --status "НАЗНАЧЕНО" --assignee bmv
python3 "$SCRIPTS/yt_client.py" update IREG-755 --tag ai
python3 "$SCRIPTS/yt_client.py" update IREG-755 --cmd "priority Critical"

# Статистика по тегу
python3 "$SCRIPTS/yt_client.py" stats --tag ai --from 2026-01-01 --list
```

### Подкоманды

| Подкоманда | Описание | Основные аргументы |
|-----------|----------|-------------------|
| `info` | Информация о задаче | `<issue_id>` |
| `comments` | Комментарии задачи | `<issue_id>` |
| `comment` | Добавить комментарий | `<issue_id> <text>` |
| `search` | Поиск задач | `<query>` `--top N` |
| `create` | Создание задачи | `<project> <summary>` `-d` `-a` `-r` `-t/--type` `-f/--field NAME=VALUE` (повторяемый) |
| `update` | Обновление через команды | `<issue_id>` `--status` `--assignee` `--tag` `--cmd` |
| `stats` | Статистика по тегу | `--tag` `--from` `--to` `--list` |

## Использование как модуля Python

```python
import sys
sys.path.insert(0, '$HOME/.claude/skills/youtrack-skill/scripts')
from yt_client import YouTrackClient, PROJECTS

client = YouTrackClient()

# Получить задачу
issue = client.get_issue("IREG-755")

# Создать задачу
result = client.create_issue("IREG", "Название", description="Описание", assignee="bmv")

# Выполнить команду
client.execute_command("IREG-755", "Статус НАЗНАЧЕНО Assignee bmv")

# Добавить комментарий
client.add_comment("IREG-755", "Текст комментария")

# Поиск
issues = client.search_issues("project: TMK status: Open")
```

## Создание подзадачи

```bash
SCRIPTS="$HOME/.claude/skills/youtrack-skill/scripts"

# Через bash-скрипт (создание + привязка к родителю)
bash "$SCRIPTS/create_subtask.sh" IREG-700 IREG "Название подзадачи" "Описание"

# Или вручную: создать задачу + связать командой
python3 "$SCRIPTS/yt_client.py" create IREG "Подзадача"
python3 "$SCRIPTS/yt_client.py" update IREG-756 --cmd "subtask of IREG-700"
```

## Прикрепление файлов

```bash
curl -X POST "$YOUTRACK_URL/api/issues/FER-1913/attachments?fields=id,name" \
  -H "Authorization: Bearer $YOUTRACK_API_KEY" \
  -F "file=@/path/to/file.docx"
```

## Admin API — проекты и настройки

```bash
# Список всех проектов (вкл. archived)
curl -s -H "Authorization: Bearer $YOUTRACK_API_KEY" \
  "$YOUTRACK_URL/api/admin/projects?fields=id,shortName,name,archived&\$top=500" | jq '.'

# Time Tracking настройки проекта
curl -s -H "Authorization: Bearer $YOUTRACK_API_KEY" \
  "$YOUTRACK_URL/api/admin/projects/{id}/timeTrackingSettings?fields=enabled,estimate(field(name)),timeSpent(field(name)),workItemTypes(name)" | jq '.'

# Work items по проекту за период (для аналитики трудозатрат)
curl -s -H "Authorization: Bearer $YOUTRACK_API_KEY" \
  "$YOUTRACK_URL/api/workItems?fields=id,duration(minutes),date,author(login),issue(idReadable)&\$top=1000&query=project:%20{IREG}%20work%20date:%202026-01-01%20..%20Today" | jq '.'

# Готовый аудит TT по всем проектам — см. ниже секцию «Аудит Time Tracking»
```

## Администрирование пользователей

Для задач вида «создать учетную запись сотруднику», «добавить доступ к проектам» или «отправить доступ в Bitrix24» открой подробный runbook: [`runbooks/create-user.md`](runbooks/create-user.md).

Ключевые инварианты:
- Display name / имя пользователя: `Имя Фамилия`; login: `Имя_Фамилия` без пробелов.
- `yt_client.py` не управляет пользователями; используй Hub REST API.
- Временный пароль нельзя печатать, сохранять в файлы, Obsidian или YouTrack-комментарии.
- При достижении лимита лицензии автоматически деактивируй двух наименее активных несервисных пользователей по `lastAccessTime`; всегда указывай `banReason`.
- После создания делай read-back verification: email, `banned=false`, группы, `passwordChangeRequired=true`.

## Связи между задачами

```bash
SCRIPTS="$HOME/.claude/skills/youtrack-skill/scripts"

# Подзадача
python3 "$SCRIPTS/yt_client.py" update IREG-749 --cmd "subtask of IREG-700"

# Связана с
python3 "$SCRIPTS/yt_client.py" update IREG-750 --cmd "relates to IREG-700"

# Зависит от
python3 "$SCRIPTS/yt_client.py" update IREG-750 --cmd "depends on IREG-700"

# Дубликат
python3 "$SCRIPTS/yt_client.py" update IREG-750 --cmd "duplicate of IREG-700"
```

## Бизнес-правила

### Создание задачи — обязательные проверки

1. **Критерии приёмки** — каждая задача ДОЛЖНА содержать раздел `# Критерии приёмки` с чекбоксами `- [ ]`. Если не очевидны из контекста — СПРОСИ пользователя через `AskUserQuestion`
2. **Регион** — если пользователь не указал регион, СПРОСИ через `AskUserQuestion` перед созданием
3. **Статус "Done"** — НИКОГДА не устанавливай при создании новой задачи
4. **При назначении исполнителя** — всегда устанавливай статус "НАЗНАЧЕНО"

### Шаблон описания инцидента

```
# Описание
<что произошло>

# Шаги воспроизведения
1. ...
2. ...

# Ожидаемый результат
<что должно быть>

# Фактический результат
<что на самом деле>

# Критерии приёмки
- [ ] Первый критерий
- [ ] Второй критерий
```

## Справочная информация

### Проекты

| Проект | Short Name | ID |
|--------|-----------|-----|
| Администрирование | ADM | 0-26 |
| Комтек.Аналитика | BI | 0-14 |
| ФЭР шлюз | FER | 0-40 |
| Телемедицина.Пациент | TMK | 0-39 |
| Интеграция с реестрами | IREG | 0-42 |
| ИСМЛП | ismlp | 0-21 |
| МЛОК | mlok | 0-23 |

Если проекта нет в списке — `create_issue` сам резолвит shortName → id через `/api/admin/projects` (этот инстанс YouTrack не принимает `{"shortName": ...}` в качестве project ref). **Не запрашивай список проектов ради id — бери из таблицы выше.**

### Кастомные поля — формат значений (грабли `$type`)

Главная причина ошибок `HTTP 400 Incompatible field type` при создании/обновлении через raw — неверный `$type` в `customFields`. **Не угадывай Single/Multi.** `yt_client.py create` определяет это сам из схемы проекта (`-t/--type`, `-f "Поле=Значение"`), поэтому предпочитай CLI, а не raw curl.

Правила формата (если всё же raw):

| Поле | valueType | Card. | IssueCustomField `$type` | `value` |
|------|-----------|-------|--------------------------|---------|
| Type, Priority, Контракт | enum | single | `SingleEnumIssueCustomField` | `{"name": "..."}` |
| **Регион, Контур, Необходимость описания** | enum | **multi** | `MultiEnumIssueCustomField` | `[{"name": "..."}]` |
| Статус | state | single | `StateIssueCustomField` | `{"name": "..."}` |
| Релиз | version | single | `SingleVersionIssueCustomField` | `{"name": "..."}` |
| Спринты | version | multi | `MultiVersionIssueCustomField` | `[{"name": "..."}]` |
| **Assignee** | user | single | `SingleUserIssueCustomField` | `{"login": "..."}` ← login, НЕ отображаемое имя |

Ключевой подвох: `$type` **проектного** поля (`EnumProjectCustomField`) НЕ кодирует cardinality — Регион/Контур выглядят как одиночные enum, но на issue-уровне они `Multi`. Cardinality живёт в `fieldType.isMultiValue`.

Discovery одним запросом (когда поле/проект незнакомы) — читай `valueType` + `isMultiValue`, не issue-уровневый `$type`:

```bash
curl -s -H "Authorization: Bearer $YOUTRACK_API_KEY" \
  "$YOUTRACK_URL/api/admin/projects/0-40/customFields?fields=field(name,fieldType(valueType,isMultiValue))&\$top=100" | jq '.'
```

### Статусы IREG

| Статус | ID |
|--------|-----|
| Submitted | 86-0 |
| In Progress | 86-2 |
| НАЗНАЧЕНО | 86-34 |
| Done | 86-37 |
| Отклонена | 86-38 |

### Приоритеты

| Приоритет | ID |
|-----------|-----|
| Show-stopper | 84-0 |
| Critical | 84-1 |
| Major | 84-2 |
| Normal | 84-3 |
| Minor | 84-4 |

### Часто используемые пользователи

| Имя | Login |
|-----|-------|
| Глеб Дунюшкин | dgk |
| Михаил Батраков | bmv |
| Елизавета Лаврова | Елизавета_Лаврова |

## Доступные скрипты

| Скрипт | Описание |
|--------|----------|
| `scripts/yt_client.py` | Основной CLI и Python-модуль (info, create, update, search, comments, comment, stats) |
| `scripts/create_subtask.sh` | Создание подзадачи с привязкой к родителю (bash, требует jq) |
| `scripts/tt_audit.py` | Аудит Time Tracking по всем проектам: enabled? сколько issues и work items за N дней |

### Аудит Time Tracking

```bash
python3 ~/.claude/skills/youtrack-skill/scripts/tt_audit.py --days 90 --json
# либо человекочитаемая таблица:
python3 ~/.claude/skills/youtrack-skill/scripts/tt_audit.py --days 90
```

Категории в выводе:
- 🟢 TT включён + work items пишутся
- 🔴 TT включён, но work items=0 при наличии активности (≥20 issues за период)
- 🟠 TT не включён, активная разработка (≥20 issues за период)
- ⚪ нет активности — пропускаем

## Troubleshooting

### Ошибка 401 Unauthorized
Убедитесь, что `YOUTRACK_API_KEY` задан в `~/.env`.

### Ошибка при создании задачи
Проверьте что short name проекта корректный (ADM, FER, TMK, IREG). Регистр важен.

### Файл ~/.env не найден
```bash
echo "YOUTRACK_URL=https://yt.pkzdrav.ru" >> ~/.env
echo "YOUTRACK_API_KEY=your_token_here" >> ~/.env
```

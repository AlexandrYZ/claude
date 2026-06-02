---
name: bitrix24
description: Работа с Bitrix24 через REST webhook. Чтение/отправка сообщений в чатах (IM), поиск пользователей, работа с задачами, календарём. Универсальный — портал и владелец токена задаются через окружение.
aliases: [bitrix, b24, bitrix-skill]
---

# Bitrix24 REST Skill

Тонкая обёртка над входящим webhook Bitrix24. Покрывает: scope-инспекцию, поиск людей, IM-диалоги (recent/messages/send), задачи, календарь.

Скилл универсальный — никакой портал-специфичной информации (id владельца, список реальных scope, маппинг чатов/проектов/сотрудников) здесь нет. Заводи отдельный профиль на портал: vault `<knowledge-base>/<организация>/Bitrix24/…` или `~/.claude/skills/bitrix24/profiles/<org>.md`.

## Конфигурация

| Переменная | Назначение |
|---|---|
| `$BITRIX_WEBHOOK` | **Единственный контракт.** URL входящего webhook: `https://<portal>.bitrix24.ru/rest/<userId>/<token>/`. Без слеша на конце — `_lib.sh` дописывает. |

Скилл переменные **не загружает** — это забота инфраструктуры (shell init, launchd plist, secret manager).

При отсутствии переменной скрипты упадут с понятной ошибкой через `${VAR:?...}` в `_lib.sh`.

## Скоупы и реальные права

`scope.sh` показывает *декларированные* scope, но это не гарантирует прав на каждый метод этой группы. Реальные права определяются по факту ответа `insufficient_scope` — какие методы и фильтры доступны конкретно этому webhook'у, проверяй вызовом.

Типовые ограничения, которые встречаются:

- Нет scope `user` → `user.search` / `user.get` не работают. Поиск людей → `im.search.user.list`.
- Для tasks REST через webhook фактически нужен набор `task` + `tasks` + `tasks_extended` (одного `tasks` мало, REST вернёт `insufficient_scope`). Если методы недоступны даже после расширения — пересоздать webhook от админа портала.
- Нет scope `telephony` / `voximplant` / `crm` — звонки и CRM-сущности недоступны.

⚠️ **`insufficient_scope` бывает ложным сигналом** — Bitrix отдаёт его не только при отсутствии прав, но и при синтаксической ошибке в query. Прежде чем расширять scope — проверь параметры.

Декларированный список и пройденные/непройденные методы → фиксируй в портал-профиле, не в SKILL.md.

## Паттерн вызова

- `curl -o /tmp/<file>.json` → разбор отдельным шагом (`python3 -c "..."`).
- Файл сохраняется всегда — даже при ошибке Bitrix вызывающий разбирает `error_description` сам.

## Скрипты

| Скрипт | Назначение | Использование | Результат |
|---|---|---|---|
| `call.sh` | Универсальный вызов любого метода | `bash scripts/call.sh <method> [k=v ...]` | `/tmp/b24_call.json` |
| `scope.sh` | Список декларированных скоупов webhook | `bash scripts/scope.sh` | `/tmp/b24_scope.json` |
| `im_search_user.sh` | Поиск пользователя по ФИО (через IM, скоуп `im`) | `bash scripts/im_search_user.sh "Иванов"` | `/tmp/b24_users.json` |
| `im_recent.sh` | Последние диалоги | `bash scripts/im_recent.sh [limit]` | `/tmp/b24_recent.json` |
| `im_messages.sh` | Сообщения диалога (личного / группового) | `bash scripts/im_messages.sh <DIALOG_ID> [limit] [date_from_YYYY-MM-DD]` | `/tmp/b24_messages.json` |
| `im_send.sh` | Отправить сообщение в диалог | `bash scripts/im_send.sh <DIALOG_ID> "текст"` | `/tmp/b24_send.json` |
| `tasks_list.sh` | Список задач с фильтром | `bash scripts/tasks_list.sh [filterKey=value ...]` | `/tmp/b24_tasks.json` |

Поведение скриптов при ошибке Bitrix: файл с ответом **всегда сохраняется**, ошибка выводится в stderr, exit-код = 0. Это сделано специально — чтобы вызывающий мог разобрать `error_description` сам и не уничтожить полезный JSON в цепочке команд.

## Как узнать свой user id

```bash
bash scripts/call.sh profile
python3 -c "import json; print(json.load(open('/tmp/b24_call.json'))['result']['ID'])"
```

Не доверяй внешним описаниям — `profile` всегда возвращает фактического владельца токена.

## DIALOG_ID

- Личный чат с пользователем → числовой ID пользователя (`50`).
- Групповой чат → `chat<ID>` (`chat42`).
- Открытая линия / OL → `imol|<connector>|<id>`.

`im.dialog.messages.get` возвращает сообщения **в обратном хронологическом порядке** (новые первыми). Серверного `?date_from` нет — фильтр по дате на клиенте (это делает `im_messages.sh`).

## Поиск пользователей без scope `user`

- `im.search.user.list?FIND=<query>` — по ФИО, возвращает id, name, position, phones, status.
- `department.get` + `department.user.get` — навигация по оргструктуре.

## Отправка сообщений

`im.message.add` обязательные параметры:
- `DIALOG_ID` — куда
- `MESSAGE` — текст (BB-разметка: `[B]bold[/B]`, `[URL=...]link[/URL]`, `[CODE]code[/CODE]`)

⚠️ **Не отправляй сообщения без явного подтверждения пользователя** — это видимое действие, попадает собеседнику.

## Задачи

`tasks.task.list` принимает `filter[<KEY>]=<VAL>`:
- `filter[RESPONSIBLE_ID]=<userId>` — ответственный
- `filter[STATUS]=2` (1=новая, 2=ждёт, 3=в работе, 4=ожидает контроля, 5=завершена, 6=отложена, 7=отклонена)
- `filter[!STATUS]=5` — исключить завершённые
- `filter[DEADLINE]=2026-05-31T23:59:59`

⚠️ **Скобки `[]`/`{}` в URL ломают curl URL-globbing**. Пустые скобки `select[]=ID` дают `curl: (3) bad range specification` — curl завершается ошибкой и `-o` файл вообще не пишется (выглядит как «нет ответа», не как ошибка Bitrix). Лечится флагом `curl -g` (отключает globbing), его уже ставят `call.sh`/`tasks_list.sh`. При вызове curl вручную — добавляй `-g` либо url-encode скобки.

⚠️ **Filter-аргументы — только в одинарных кавычках в shell**: `'filter[!STATUS]=5'`. В двойных кавычках `!` интерпретируется как history expansion (bash interactive / zsh). 

⚠️ **Shape результата канонический**: `tasks.task.list` всегда отдаёт `result.tasks: [...]` + `total` (поля задач зависят от `select`). Никакого «плавающего» top-level — парсь `d['result']['tasks']`.

Если метод недоступен — добавить scope `task` + `tasks_extended` к webhook, либо пересоздать webhook от админа.

## Календарь

`calendar.event.get` обязателен `ownerId`:
- Личный календарь юзера: `type=user&ownerId=<userId>&from=YYYY-MM-DD&to=YYYY-MM-DD`
- Корпоративный календарь: `type=company_calendar&ownerId=0&from=...&to=...`

События возвращают:
- `DATE_FROM`, `DATE_TO` — строки `DD.MM.YYYY HH:MM:SS` в TZ из `TZ_FROM`/`TZ_TO` (часто `Europe/Moscow`, может быть любой)
- `DATE_FROM_TS_UTC` — **ненадёжно** для прямого использования, по опыту бывает смещено. Конвертируй через `TZ_FROM` → целевая TZ.

`calendar.section.get` тоже требует `ownerId`.

## Паттерны парсинга

Top-level shape:
- success → `{result, time}` или `{result, total, time}` или `{result, next, total, time}`
- error → `{error, error_description}` (нет `result`!)

Не путать: парсер должен сначала проверить `error`, иначе `KeyError: 'result'` или попытка обратиться `.get` к строке/списку с непредсказуемой shape.

```python
import json
with open('/tmp/b24_call.json') as f:
    d = json.load(f)
if 'error' in d:
    raise RuntimeError(f"{d['error']}: {d.get('error_description','')}")
result = d['result']  # формат зависит от метода: list, dict, или вложенный {tasks: []}
```

```python
# Сообщения за конкретный день
import json
date = '2026-05-12'
with open('/tmp/b24_messages.json') as f:
    d = json.load(f)
users = {u['id']: u['name'] for u in d['result']['users']}
for m in d['result']['messages']:
    if m['date'].startswith(date):
        print(f"[{m['date']}] {users.get(m['author_id'], '?')}: {m['text']}")
```

```python
# Конвертация события календаря в локальную TZ
from datetime import datetime
from zoneinfo import ZoneInfo
import json

target_tz = ZoneInfo('Asia/Yekaterinburg')  # замени на свою TZ
d = json.load(open('/tmp/b24_call.json'))
for e in d['result']:
    src = ZoneInfo(e['TZ_FROM'])
    dt = datetime.strptime(e['DATE_FROM'], '%d.%m.%Y %H:%M:%S').replace(tzinfo=src)
    print(dt.astimezone(target_tz), '—', e['NAME'])
```

## Troubleshooting

| Ошибка | Причина | Решение |
|---|---|---|
| `insufficient_scope` | Метод требует scope, которого нет / роль не позволяет / синтаксическая ошибка query | Сначала проверь параметры (кавычки на filter, формат). Если синтаксис ОК — `scope.sh`, добавить недостающий scope (`task` + `tasks_extended` для tasks REST), пересоздать webhook от админа. |
| `curl: (3) bad range specification` / файл ответа не создан | Скобки `[]`/`{}` в URL съел curl URL-globbing | Добавь `curl -g` (уже стоит в скриптах скилла) либо url-encode скобки. |
| `INVALID_REQUEST` | Параметры в неверном формате / регистре | Bitrix чувствителен к регистру: `DIALOG_ID` (не `dialog_id`), `RESPONSIBLE_ID` (не `responsibleId`). |
| Shell history expansion на `!` | `filter[!STATUS]=5` в двойных кавычках | Использовать одинарные кавычки: `'filter[!STATUS]=5'`. |
| `expired_token` | Webhook отозван | Создать новый входящий webhook, обновить `$BITRIX_WEBHOOK`. |
| `ownerId не задан` | Метод требует обязательный параметр | Для `calendar.*` — добавь `ownerId=<userId>` (или `0` для company_calendar). |
| Пустой `result` | DIALOG_ID не существует / нет доступа | Проверь `im_recent.sh` — диалог должен быть в недавних. |

## Безопасность

- Webhook = bearer-токен. Не коммить в git, не публикуй в чатах.
- Все вызовы идут от имени пользователя, чьим webhook это создано. Узнать конкретного владельца — `bash scripts/call.sh profile`.
- `im.message.add` шлёт сообщение от твоего имени → собеседник видит сообщение от тебя.

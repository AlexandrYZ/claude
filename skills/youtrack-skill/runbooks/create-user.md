# Runbook — создание нового пользователя YouTrack

Используй этот runbook для административных задач вида «создать учетную запись сотруднику», «добавить доступ к проектам», «отправить доступ в Bitrix24». Обычный `yt_client.py` не покрывает управление пользователями; для этого нужен Hub REST API текущего инстанса.

## Правила безопасности

1. **Никогда не сохраняй и не печатай временный пароль** в stdout, файлы, Obsidian, YouTrack-комментарии или логи.
2. **Пароль отправляй только в согласованный личный канал** (например, Bitrix24 IM) и только после однозначного поиска получателя.
3. **После каждой мутации делай read-back verification**: пользователь создан, email задан, `banned=false`, группы назначены, `passwordChangeRequired=true`.
4. **В YouTrack-комментарии не публикуй пароль** — только факт создания, login, email, группы и канал доставки.
5. Если создание упирается в лицензию, автоматически деактивируй двух наименее активных несервисных пользователей по `lastAccessTime` без отдельного вопроса пользователю. При деактивации всегда указывай `banReason` с причиной, номером задачи и датой.

## Форматы имени и логина

- Display name / имя пользователя: `Имя Фамилия` (например, `Тимофей Пиголев`).
- Login: `Имя_Фамилия` (например, `Тимофей_Пиголев`).
- Hub отклоняет login с пробелом ошибкой `invalid login`; не пытайся создавать `Имя Фамилия` как login.

## Предварительные проверки

```bash
# Дубли по login/email/ФИО
curl -s -H "Authorization: Bearer $YOUTRACK_API_KEY" \
  "$YOUTRACK_URL/hub/api/rest/users?fields=id,login,name,banned,profile(email(email))&query=login:%20Имя_Фамилия&\$top=10" | jq '.'

curl -s -H "Authorization: Bearer $YOUTRACK_API_KEY" \
  "$YOUTRACK_URL/hub/api/rest/users?fields=id,login,name,banned,profile(email(email))&query=email:%20user@example.ru&\$top=10" | jq '.'

# Группы YouTrack и их Hub ringId
curl -s -H "Authorization: Bearer $YOUTRACK_API_KEY" \
  "$YOUTRACK_URL/api/admin/groups?fields=id,ringId,name,usersCount&query=bi-users&\$top=20" | jq '.'
```

Важно: на инстансах YouTrack 2021.x группы в `/api/admin/groups` имеют короткий ID вида `3-60`, но Hub endpoints принимают `ringId` (UUID). Для project team группа может иметь Hub ID с суффиксом `_team`, например `565b..._team`. Проверяй фактический ID через:

```bash
curl -s -H "Authorization: Bearer $YOUTRACK_API_KEY" \
  "$YOUTRACK_URL/hub/api/rest/usergroups?fields=id,name,users(id,login)&query=НазваниеГруппы&\$top=10" | jq '.'
```

## Создание пользователя через Hub API

Hub 2021.1 принимает JSON-типы из фактических ответов API: `EmailuserdetailsJSON`, `EmailJSON`, `CoreauthmoduleJSON`, `PlainpasswordJSON`. Типы без `JSON` могут дать ошибку `Unknown details type: DetailsJSON`.

Минимальный шаблон (адаптируй переменные; пароль не печатай):

```python
import json
import os
import secrets
import string
import urllib.parse
import urllib.request

YT = os.environ["YOUTRACK_URL"].rstrip("/")
TOKEN = os.environ["YOUTRACK_API_KEY"]

login = "Имя_Фамилия"
display_name = "Имя Фамилия"
email = "user@example.ru"
auth_module_id = "d1fb8f1a-0f83-4fa0-8013-f286136dad84"  # Hub
group_ids = [
    "7d7a66ec-a663-4291-97a5-4969597dda6c",       # bi-users, пример
    "565b9851-534e-445f-a605-11cc148cb0eb_team",  # ИСМЛП Team, пример
]

def hub(method, path, body=None):
    headers = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{YT}/hub/api/rest{path}", data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else None

alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
password = "".join(secrets.choice(alphabet) for _ in range(20))

created = hub("POST", "/users?fields=id,login,name,banned,profile(email(email,verified)),details(id,type,email(email),authModuleName,passwordChangeRequired)", {
    "type": "user",
    "login": login,
    "name": display_name,
    "profile": {"email": {"type": "EmailJSON", "email": email}},
    "details": [{
        "type": "EmailuserdetailsJSON",
        "email": {"type": "EmailJSON", "email": email},
        "authModule": {"type": "CoreauthmoduleJSON", "id": auth_module_id},
        "password": {"type": "PlainpasswordJSON", "value": password},
        "passwordChangeRequired": True,
    }],
})

user_id = created["id"]
for group_id in group_ids:
    hub("POST", f"/users/{urllib.parse.quote(user_id)}/groups?fields=id,name", {
        "type": "userGroup",
        "id": group_id,
    })

# Read-back verification.
verified = hub("GET", f"/users/{urllib.parse.quote(user_id)}?" + urllib.parse.urlencode({
    "fields": "id,login,name,banned,profile(email(email,verified)),groups(id,name),transitiveGroups(id,name),details(id,type,email(email),authModuleName,passwordChangeRequired)",
}))
```

После создания используй `password` только для отправки в личное сообщение; не печатай объект с паролем.

## Сброс пароля существующему пользователю

Для задач вида «обнули пароль пользователю и отправь в Bitrix24» используй тот же Hub REST API. На текущем YouTrack 2021.x endpoint вида `/users/{id}/details/{detailId}` может возвращать `404`; рабочий путь — обновлять embedded `details` через `POST /hub/api/rest/users/{userId}`.

Порядок:

1. Найди пользователя по `login` и убедись, что результат ровно один:

```bash
curl -s -H "Authorization: Bearer $YOUTRACK_API_KEY" \
  "$YOUTRACK_URL/hub/api/rest/users?fields=id,login,name,banned,profile(email(email,verified)),details(id,type,email(email),authModuleName,passwordChangeRequired)&query=login:%20Имя_Фамилия&\$top=10" | jq '.'
```

2. Возьми из ответа `user.id`, `details[].id`, email и auth module Hub. Если `details` несколько — меняй только запись нужного auth module.
3. Сгенерируй пароль в памяти процесса и обнови пользователя через `POST /users/{userId}`. Не печатай payload и не сохраняй пароль в файлы:

```python
import json
import os
import secrets
import string
import urllib.parse
import urllib.request

YT = os.environ["YOUTRACK_URL"].rstrip("/")
TOKEN = os.environ["YOUTRACK_API_KEY"]

user_id = "hub-user-id"
detail_id = "email-details-id"
login = "Имя_Фамилия"
display_name = "Имя Фамилия"
email = "user@example.ru"
auth_module_id = "d1fb8f1a-0f83-4fa0-8013-f286136dad84"  # Hub

def hub(method, path, body=None):
    headers = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{YT}/hub/api/rest{path}", data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else None

alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
password = "".join(secrets.choice(alphabet) for _ in range(22))
fields = "id,login,name,banned,profile(email(email,verified)),details(id,type,email(email),authModuleName,passwordChangeRequired)"

hub("POST", f"/users/{urllib.parse.quote(user_id)}?" + urllib.parse.urlencode({"fields": fields}), {
    "type": "user",
    "id": user_id,
    "login": login,
    "name": display_name,
    "profile": {"email": {"type": "EmailJSON", "email": email}},
    "details": [{
        "type": "EmailuserdetailsJSON",
        "id": detail_id,
        "email": {"type": "EmailJSON", "email": email},
        "authModule": {"type": "CoreauthmoduleJSON", "id": auth_module_id},
        "password": {"type": "PlainpasswordJSON", "value": password},
        "passwordChangeRequired": True,
    }],
})

verified = hub("GET", f"/users/{urllib.parse.quote(user_id)}?" + urllib.parse.urlencode({"fields": fields}))
```

4. Проверь read-back: `login`, `banned=false`, email и `details[].passwordChangeRequired=true`.
5. Отправь `password` только в согласованный личный канал, например Bitrix24 IM. В заметках, комментариях и stdout фиксируй только факт доставки, dialog/message ID и проверочные поля без секрета.

## Деактивация пользователя для освобождения лицензии

Если Hub вернул `license_users_number_exceeded`, найди активных неблокированных пользователей и автоматически деактивируй двух наименее активных несервисных пользователей по `lastAccessTime` без отдельного вопроса пользователю:

```bash
curl -s -H "Authorization: Bearer $YOUTRACK_API_KEY" \
  "$YOUTRACK_URL/hub/api/rest/users?fields=id,login,name,banned,guest,lastAccessTime,profile(email(email))&\$top=100" | jq '.'
```

Не деактивируй очевидные системные/сервисные учетные записи: `guest`, `admin`, `teamcity`, `youtrack`, `hub`, ботов, интеграционные логины, учетные записи без человека в `name`, а также уже `banned=true`. Если два безопасных кандидата не набираются, остановись и опиши найденный риск.

Деактивация делается через `banned=true` и обязательный `banReason`:

```bash
curl -s -X POST -H "Authorization: Bearer $YOUTRACK_API_KEY" \
  -H "Content-Type: application/json" \
  "$YOUTRACK_URL/hub/api/rest/users/{hubUserId}?fields=id,login,name,banned,banReason" \
  -d '{"type":"user","banned":true,"banReason":"Освобождение лицензии YouTrack для регистрации нового сотрудника по ADM-XXXX, согласовано YYYY-MM-DD."}' | jq '.'
```

Hub может вернуть пустой body на успешный update. Не считай это ошибкой автоматически; после update перечитай пользователя и проверь `banned` + `banReason`.

## Bitrix24 delivery

Если постановка просит отправить доступ в Bitrix24, используй `bitrix24` skill:

1. Найди получателя через `im.search.user.list` (`im_search_user.sh`) по ФИО/email.
2. Если в постановке дана прямая ссылка вида `/company/personal/user/<id>/`, перед отправкой перечитай `user.get ID=<id>` и проверь совпадение ФИО, email и `ACTIVE=true`.
3. Если найдено не ровно одно совпадение или данные из ссылки не совпадают с создаваемой учеткой — остановись и спроси пользователя.
4. Если отправка явно подтверждена и получатель однозначен — отправь login, временный пароль и ссылку на YouTrack через `im.message.add` в личный диалог (`DIALOG_ID=<Bitrix user id>`).
5. В YouTrack-комментарии укажи только факт отправки, Bitrix24 user/dialog ID и без пароля.

## Завершение задачи

1. Проверить пользователя в Hub: `login`, `name`, `email`, `banned=false`, нужные группы, `passwordChangeRequired=true`.
2. Добавить комментарий в исходную задачу без пароля.
3. Перевести задачу в `Done` только после успешной доставки доступа.
4. Если по правилам проекта требуется persistence, обновить runbook/заметку в `docs/` или Obsidian без секретов.

# Runbook — создание релиза YouTrack

Используй для запросов «создай релиз/версию», «добавь пустой релиз» или «создай релиз без задач». Релиз — это значение `version` в поле `Релиз`, а не issue: `yt_client.py` таких значений не создаёт.

## Инварианты

1. Не создавай и не изменяй issues, если пользователь просит пустой релиз.
2. До создания найди bundle поля `Релиз` в указанном проекте; не подставляй ID bundle из памяти.
3. Проверь отсутствие версии с тем же именем, включая архивные значения. При совпадении остановись и сообщи пользователю.
4. `released=false` и `archived=false` при создании. Не помечай планируемый релиз выпущенным.
5. Даты периода: начало — `startDate`, конец — `releaseDate` в миллисекундах Unix. Конец задавай как `23:59:59.999` локального дня.
6. После мутации обязателен read-back: имя, даты, `released`, `archived`, описание и отсутствие задач.

## 1. Найти bundle и проверить права

Выполни подставив short name проекта, например `FER`:

```bash
PROJECT=FER

PROJECT_ID=$(curl --fail-with-body -sS \
  -H "Authorization: Bearer $YOUTRACK_API_KEY" \
  "$YOUTRACK_URL/api/admin/projects?fields=id,shortName,archived&\$top=500" \
  | jq -er --arg project "$PROJECT" '[.[] | select(.shortName == $project and .archived != true) | .id] | if length == 1 then .[0] else error("project not found or ambiguous") end')

BUNDLE_ID=$(curl --fail-with-body -sS \
  -H "Authorization: Bearer $YOUTRACK_API_KEY" \
  "$YOUTRACK_URL/api/admin/projects/$PROJECT_ID/customFields?fields=field(name,fieldType(valueType)),bundle(id,name)&\$top=100" \
  | jq -er '[.[] | select(.field.name == "Релиз" and .field.fieldType.valueType == "version") | .bundle.id] | if length == 1 then .[0] else error("one version field Релиз is required") end')

curl --fail-with-body -sS \
  -H "Authorization: Bearer $YOUTRACK_API_KEY" \
  "$YOUTRACK_URL/api/admin/customFieldSettings/bundles/version/$BUNDLE_ID?fields=id,name,isUpdateable" \
  | jq -e '.isUpdateable == true'
```

Один bundle может использоваться несколькими проектами. Проверь это до POST:

```bash
curl --fail-with-body -sS \
  -H "Authorization: Bearer $YOUTRACK_API_KEY" \
  "$YOUTRACK_URL/api/admin/projects?fields=id,shortName,archived&\$top=500" \
  | jq -r '.[] | select(.archived != true) | [.id, .shortName] | @tsv' \
  | while IFS=$'\t' read -r id short_name; do
      curl --fail-with-body -sS \
        -H "Authorization: Bearer $YOUTRACK_API_KEY" \
        "$YOUTRACK_URL/api/admin/projects/$id/customFields?fields=field(name),bundle(id)&\$top=100" \
        | jq -r --arg bundle "$BUNDLE_ID" --arg project "$short_name" \
          '.[] | select(.bundle.id == $bundle) | [$project, .field.name] | @tsv'
    done | awk -F '\t' '!seen[$1]++'
```

Каждая строка показывает один проект. Если в выводе больше одного проекта, добавление версии сделает её доступной во всех них. До POST явно сообщи об этом пользователю, если это расширяет исходную постановку.

На текущем инстансе endpoint `/api/admin/projects/{projectId}/versions` возвращает `404`. Используй endpoint version bundle ниже.

## 2. Проверить уникальность и подготовить даты

```bash
RELEASE=26.08

curl --fail-with-body -sS -G \
  -H "Authorization: Bearer $YOUTRACK_API_KEY" \
  --data-urlencode 'fields=id,name,archived' \
  --data-urlencode '$top=500' \
  "$YOUTRACK_URL/api/admin/customFieldSettings/bundles/version/$BUNDLE_ID/values" \
  | jq -e --arg release "$RELEASE" '[.[] | select(.name == $release)] | length == 0'
```

Для периода 17–30 августа 2026 года в `Asia/Yekaterinburg`:

```bash
python3 - <<'PY'
from datetime import datetime
from zoneinfo import ZoneInfo

tz = ZoneInfo("Asia/Yekaterinburg")
for value in ("2026-08-17 00:00:00.000", "2026-08-30 23:59:59.999"):
    print(value, int(datetime.fromisoformat(value).replace(tzinfo=tz).timestamp() * 1000))
PY
```

Для примера результат: `startDate=1786906800000`, `releaseDate=1788116399999`. Всегда пересчитывай значения для реальных дат запроса.

## 3. Создать пустой релиз

`description` содержит период как видимый fallback для старых версий YouTrack, которые не сохраняют `startDate`.

```bash
curl --fail-with-body -sS -X POST \
  -H "Authorization: Bearer $YOUTRACK_API_KEY" \
  -H "Content-Type: application/json" \
  "$YOUTRACK_URL/api/admin/customFieldSettings/bundles/version/$BUNDLE_ID/values?fields=id,name,description,startDate,releaseDate,released,archived" \
  --data '{
    "name": "26.08",
    "description": "Период: 17.08.2026–30.08.2026",
    "startDate": 1786906800000,
    "releaseDate": 1788116399999,
    "released": false,
    "archived": false,
    "$type": "VersionBundleElement"
  }' | jq '.'
```

Сохрани `id` из ответа. Ни `POST /api/issues`, ни команды обновления issue в этом runbook не используются.

Не повторяй POST автоматически после сетевой ошибки или отсутствия ответа: сервер мог создать версию. Сначала перечитай bundle, найди все значения с точным именем `RELEASE` и сообщи их IDs. Если точных совпадений нет, допустима ровно одна ручная повторная попытка; при следующей ошибке остановись и сообщи о сбое.

## 4. Read-back и отсутствие задач

```bash
VERSION_ID=<id-из-POST>

curl --fail-with-body -sS \
  -H "Authorization: Bearer $YOUTRACK_API_KEY" \
  "$YOUTRACK_URL/api/admin/customFieldSettings/bundles/version/$BUNDLE_ID/values/$VERSION_ID?fields=id,name,description,startDate,releaseDate,released,archived" \
  | jq '.'

curl --fail-with-body -sS -G \
  -H "Authorization: Bearer $YOUTRACK_API_KEY" \
  --data-urlencode "query=project: $PROJECT Релиз: $RELEASE" \
  --data-urlencode 'fields=id,idReadable,summary' \
  --data-urlencode '$top=1' \
  "$YOUTRACK_URL/api/issues" | jq -e 'length == 0'
```

Заверши операцию, только если версия активна, не выпущена, даты и описание соответствуют запросу, а второй запрос вернул `[]`.

Если POST вернул успех, но read-back по `VERSION_ID` не удался, не создавай версию повторно. Перечитай список bundle, найди точное имя, проверь каждую найденную версию по ID и сообщи пользователю результат либо необходимость ручной проверки.

## Совместимость текущего инстанса

После создания текущий экземпляр может не возвращать `startDate`, даже если поле было передано в POST. Это ограничение сервера, а не основание менять дату окончания или помечать релиз выпущенным. В этом случае:

1. Убедись, что `releaseDate` сохранена.
2. Убедись, что `description` содержит полный период.
3. В отчёте пользователю явно укажи, что начало хранится в описании, а не в атрибуте `startDate`.

Если POST отклонил `startDate` с HTTP 400, сначала выполни проверку точного имени в bundle. Если значения нет, повтори POST ровно один раз без `startDate`, сохраняя `description` с полным периодом и исходный `releaseDate`; затем выполни read-back. Если значение уже есть, не делай повторный POST.

Если `releaseDate` или описание не совпадают с постановкой, не считай операцию завершённой.

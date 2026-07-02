#!/bin/bash
# Создание подзадачи в YouTrack
# Использование: ./create_subtask.sh <parent_issue> <project> <summary> [description]
# Пример: ./create_subtask.sh adm-2223 adm "Создать ВМ для БД" "Описание задачи"

set -e

# Загрузка API ключа (приоритет ~/.env)
if [[ -f "$HOME/.env" ]]; then
    export YOUTRACK_API_KEY=$(sed -n 's/^YOUTRACK_API_KEY=//p' "$HOME/.env")
    export YOUTRACK_BASE_URL=$(sed -n 's/^YOUTRACK_BASE_URL=//p' "$HOME/.env")
    # Fallback to YOUTRACK_URL if YOUTRACK_BASE_URL not set
    [[ -z "$YOUTRACK_BASE_URL" ]] && export YOUTRACK_BASE_URL=$(sed -n 's/^YOUTRACK_URL=//p' "$HOME/.env")
elif [[ -f "$(dirname "$0")/../.env" ]]; then
    export YOUTRACK_API_KEY=$(sed -n 's/^YOUTRACK_API_KEY=//p' "$(dirname "$0")/../.env")
    export YOUTRACK_BASE_URL=$(sed -n 's/^YOUTRACK_BASE_URL=//p' "$(dirname "$0")/../.env")
    # Fallback to YOUTRACK_URL if YOUTRACK_BASE_URL not set
    [[ -z "$YOUTRACK_BASE_URL" ]] && export YOUTRACK_BASE_URL=$(sed -n 's/^YOUTRACK_URL=//p' "$(dirname "$0")/../.env")
fi

YOUTRACK_BASE_URL="${YOUTRACK_BASE_URL:-https://yt.pkzdrav.ru}"

# Проверка аргументов
if [[ $# -lt 3 ]]; then
    echo "Использование: $0 <parent_issue> <project> <summary> [description]"
    echo "Пример: $0 adm-2223 adm \"Создать ВМ для БД\" \"Описание задачи\""
    echo ""
    echo "Проекты:"
    echo "  adm  - Администрирование (0-26)"
    echo "  FER  - ФЭР шлюз (0-40)"
    echo "  TMK  - Телемедицина.Пациент (0-39)"
    echo "  IREG - Интеграция с реестрами (0-42)"
    exit 1
fi

PARENT_ISSUE="$1"
PROJECT="$2"
SUMMARY="$3"
DESCRIPTION="${4:-}"

# Маппинг проектов на ID
declare -A PROJECT_IDS=(
    ["adm"]="0-26"
    ["ADM"]="0-26"
    ["FER"]="0-40"
    ["fer"]="0-40"
    ["TMK"]="0-39"
    ["tmk"]="0-39"
    ["IREG"]="0-42"
    ["ireg"]="0-42"
)

PROJECT_ID="${PROJECT_IDS[$PROJECT]}"
if [[ -z "$PROJECT_ID" ]]; then
    echo "Ошибка: Неизвестный проект '$PROJECT'"
    echo "Доступные проекты: adm, FER, TMK, IREG"
    exit 1
fi

echo "Создание подзадачи..."
echo "  Родитель: $PARENT_ISSUE"
echo "  Проект: $PROJECT ($PROJECT_ID)"
echo "  Название: $SUMMARY"

# Создание JSON для задачи (через jq для безопасного экранирования)
JSON_PAYLOAD=$(jq -n \
  --arg pid "$PROJECT_ID" \
  --arg sum "$SUMMARY" \
  --arg desc "$DESCRIPTION" \
  '{project: {id: $pid}, summary: $sum, description: $desc}')

# Создание задачи
RESPONSE=$(curl -s -X POST "$YOUTRACK_BASE_URL/api/issues?fields=id,idReadable,summary" \
  -H "Authorization: Bearer $YOUTRACK_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d "$JSON_PAYLOAD")

# Проверка результата
ISSUE_ID=$(echo "$RESPONSE" | jq -r '.idReadable // empty')
if [[ -z "$ISSUE_ID" ]]; then
    echo "Ошибка создания задачи:"
    echo "$RESPONSE" | jq '.'
    exit 1
fi

echo "Задача создана: $ISSUE_ID"

# Связывание с родителем
echo "Связывание с родительской задачей $PARENT_ISSUE..."
LINK_JSON=$(jq -n \
  --arg iid "$ISSUE_ID" \
  --arg parent "$PARENT_ISSUE" \
  '{issues: [{idReadable: $iid}], query: ("subtask of " + $parent)}')

LINK_RESPONSE=$(curl -s -X POST "$YOUTRACK_BASE_URL/api/commands" \
  -H "Authorization: Bearer $YOUTRACK_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d "$LINK_JSON")

# Проверка связи
LINK_CHECK=$(curl -s "$YOUTRACK_BASE_URL/api/issues/$ISSUE_ID?fields=links(direction,linkType(name),issues(idReadable))" \
  -H "Authorization: Bearer $YOUTRACK_API_KEY" \
  -H "Accept: application/json" | jq -r '.links[] | select(.linkType.name == "Subtask" and .direction == "INWARD") | .issues[0].idReadable // empty')

if [[ "$LINK_CHECK" == "$PARENT_ISSUE" ]]; then
    echo "Подзадача успешно связана с $PARENT_ISSUE"
else
    echo "Предупреждение: связь может не установиться"
fi

echo ""
echo "Результат:"
echo "  Подзадача: $YOUTRACK_BASE_URL/issue/$ISSUE_ID"
echo "  Родитель:  $YOUTRACK_BASE_URL/issue/$PARENT_ISSUE"

#!/bin/bash
# Отправка сообщения в диалог через im.message.add
# ВНИМАНИЕ: видимое действие — собеседник получит сообщение от твоего имени.
# Использование: bash scripts/im_send.sh <DIALOG_ID> "Текст сообщения"
# Результат: /tmp/b24_send.json — содержит ID отправленного сообщения
set -e
source "$(dirname "$0")/_lib.sh"
DIALOG_ID="${1:?Укажи DIALOG_ID}"
MESSAGE="${2:?Укажи текст сообщения}"
OUTFILE="/tmp/b24_send.json"

# POST с form-encoded body — корректно обрабатывает спецсимволы и длинные тексты
curl -s -o "$OUTFILE" \
  --data-urlencode "DIALOG_ID=${DIALOG_ID}" \
  --data-urlencode "MESSAGE=${MESSAGE}" \
  "${BITRIX_WEBHOOK}im.message.add.json"

python3 -c "
import json
with open('$OUTFILE') as f:
    d = json.load(f)
if 'error' in d:
    raise SystemExit(f'Error: {d}')
print(f'Sent. message_id={d[\"result\"]}')
"

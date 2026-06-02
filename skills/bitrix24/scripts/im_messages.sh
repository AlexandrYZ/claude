#!/bin/bash
# Сообщения диалога через im.dialog.messages.get
# Использование: bash scripts/im_messages.sh <DIALOG_ID> [LIMIT] [DATE_FROM_YYYY-MM-DD]
#   DIALOG_ID: число (личный чат с user_id) или chatN (групповой)
#   LIMIT: количество сообщений (по умолчанию 50, max 200)
#   DATE_FROM: фильтр на клиенте, выводятся только сообщения с этой даты и позже
# Результат: /tmp/b24_messages.json
set -e
source "$(dirname "$0")/_lib.sh"
DIALOG_ID="${1:?Укажи DIALOG_ID — id пользователя или chatN}"
LIMIT="${2:-50}"
DATE_FROM="${3:-}"
OUTFILE="/tmp/b24_messages.json"

curl -s -o "$OUTFILE" "${BITRIX_WEBHOOK}im.dialog.messages.get.json?DIALOG_ID=${DIALOG_ID}&LIMIT=${LIMIT}"

python3 -c "
import json
date_from = '$DATE_FROM' or None
with open('$OUTFILE') as f:
    d = json.load(f)
if 'error' in d:
    raise SystemExit(f'Error: {d}')
res = d.get('result', {})
users = {u['id']: u.get('name','?') for u in res.get('users', [])}
msgs = res.get('messages', [])
# хронологический порядок (сервер отдаёт в обратном)
msgs = sorted(msgs, key=lambda m: m.get('date',''))
shown = 0
for m in msgs:
    date = m.get('date','')
    if date_from and date[:10] < date_from:
        continue
    author = users.get(m.get('author_id'), str(m.get('author_id','?')))
    text = (m.get('text','') or '').replace('\n', ' ')
    print(f'[{date}] {author}: {text[:500]}')
    shown += 1
print(f'--- shown: {shown}/{len(msgs)} ---')
"

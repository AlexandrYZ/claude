#!/bin/bash
# Поиск пользователя по ФИО через im.search.user.list (scope `im`)
# Использование: bash scripts/im_search_user.sh "Кокорин"
# Результат: /tmp/b24_users.json
set -e
source "$(dirname "$0")/_lib.sh"
QUERY="${1:?Укажи ФИО или его часть}"
OUTFILE="/tmp/b24_users.json"

QENC=$(python3 -c "import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=''))" "$QUERY")
curl -s -o "$OUTFILE" "${BITRIX_WEBHOOK}im.search.user.list.json?FIND=${QENC}"

python3 -c "
import json
with open('$OUTFILE') as f:
    d = json.load(f)
if 'error' in d:
    raise SystemExit(f'Error: {d}')
users = d.get('result', {})
total = d.get('total', len(users))
print(f'Найдено: {total}')
for uid, u in users.items():
    pos = u.get('work_position') or '—'
    status = u.get('status', '')
    print(f'  id={uid:<6} {u.get(\"name\",\"?\"):<30} | {pos} | {status}')
"

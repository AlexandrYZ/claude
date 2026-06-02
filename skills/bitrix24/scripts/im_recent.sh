#!/bin/bash
# Список последних диалогов (im.recent.get)
# Использование: bash scripts/im_recent.sh [limit]
# Результат: /tmp/b24_recent.json
set -e
source "$(dirname "$0")/_lib.sh"
LIMIT="${1:-30}"
OUTFILE="/tmp/b24_recent.json"

curl -s -o "$OUTFILE" "${BITRIX_WEBHOOK}im.recent.get.json?LIMIT=${LIMIT}"

python3 -c "
import json
with open('$OUTFILE') as f:
    d = json.load(f)
if 'error' in d:
    raise SystemExit(f'Error: {d}')
res = d.get('result')
items = res if isinstance(res, list) else (res.get('items') if isinstance(res, dict) else [])
print(f'Recent dialogs: {len(items)}')
for it in items:
    did = it.get('id') or it.get('chat_id') or it.get('user_id')
    title = it.get('title') or (it.get('user') or {}).get('name') or '?'
    typ = it.get('type','?')
    print(f'  DIALOG_ID={did:<15} type={typ:<8} {title}')
"

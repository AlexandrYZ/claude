#!/bin/bash
# Универсальный вызов метода Bitrix24 REST через webhook
# Использование: bash scripts/call.sh <method> [k=v ...]
# Результат: /tmp/b24_call.json
#
# Примеры:
#   bash scripts/call.sh scope
#   bash scripts/call.sh im.recent.get LIMIT=20
#   bash scripts/call.sh im.dialog.messages.get DIALOG_ID=50 LIMIT=50

set -eu
source "$(dirname "$0")/_lib.sh"
set +e  # ошибки Bitrix не должны уничтожать /tmp/b24_call.json — пусть вызывающий разберёт JSON сам

METHOD="${1:?Укажи метод, например im.recent.get}"
shift
OUTFILE="/tmp/b24_call.json"

# Собираем query string из k=v параметров с url-encode
QS=""
for kv in "$@"; do
  k="${kv%%=*}"
  v="${kv#*=}"
  v_enc=$(python3 -c "import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=''))" "$v")
  if [ -z "$QS" ]; then
    QS="?${k}=${v_enc}"
  else
    QS="${QS}&${k}=${v_enc}"
  fi
done

URL="${BITRIX_WEBHOOK}${METHOD}.json${QS}"

# -g: отключить curl URL-globbing — значения уже url-encoded, но ключи (filter[..],
# select[..]) идут как есть; без -g скобки ломают запрос ("bad range specification")
curl -gs -o "$OUTFILE" "$URL"

python3 -c "
import json, sys
try:
    with open('$OUTFILE') as f:
        d = json.load(f)
except Exception as e:
    print(f'Cannot parse $OUTFILE: {e}', file=sys.stderr)
    sys.exit(0)
print('Saved to: $OUTFILE')
if 'error' in d:
    print(f'Bitrix24 error: {d.get(\"error\")}: {d.get(\"error_description\", \"\")}', file=sys.stderr)
else:
    print('Top-level keys:', list(d.keys()))
"
exit 0

#!/bin/bash
# Список доступных скоупов webhook
# Использование: bash scripts/scope.sh
# Результат: /tmp/b24_scope.json
set -e
source "$(dirname "$0")/_lib.sh"
OUTFILE="/tmp/b24_scope.json"
curl -s -o "$OUTFILE" "${BITRIX_WEBHOOK}scope.json"
python3 -c "
import json
with open('$OUTFILE') as f:
    d = json.load(f)
if 'error' in d:
    raise SystemExit(f'Error: {d}')
print('Scopes:')
for s in d['result']:
    print(f'  - {s}')
"

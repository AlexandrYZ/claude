#!/bin/bash
# Список задач Bitrix24 через tasks.task.list
# Использование: bash scripts/tasks_list.sh [filter[KEY]=VAL ...]
# Примеры:
#   bash scripts/tasks_list.sh 'filter[RESPONSIBLE_ID]=28'
#   bash scripts/tasks_list.sh 'filter[STATUS]=3' 'order[DEADLINE]=asc'
# Результат: /tmp/b24_tasks.json
set -eu
source "$(dirname "$0")/_lib.sh"
set +e  # ошибки Bitrix не должны уничтожать /tmp/b24_tasks.json
OUTFILE="/tmp/b24_tasks.json"

QS="?select[]=ID&select[]=TITLE&select[]=STATUS&select[]=DEADLINE&select[]=RESPONSIBLE_ID&select[]=CREATED_DATE"
for kv in "$@"; do
  k="${kv%%=*}"
  v="${kv#*=}"
  k_enc=$(python3 -c "import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe='[]'))" "$k")
  v_enc=$(python3 -c "import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=''))" "$v")
  QS="${QS}&${k_enc}=${v_enc}"
done

# -g: отключить curl URL-globbing, иначе скобки в select[]/filter[] трактуются
# как range-паттерны ("bad range specification") и файл не записывается
curl -gs -o "$OUTFILE" "${BITRIX_WEBHOOK}tasks.task.list.json${QS}"

python3 -c "
import json, sys
status_map = {'1':'Новая','2':'Ждёт','3':'В работе','4':'Контроль','5':'Завершена','6':'Отложена','7':'Отклонена'}
try:
    with open('$OUTFILE') as f:
        d = json.load(f)
except Exception as e:
    print(f'Cannot parse $OUTFILE: {e}', file=sys.stderr); sys.exit(0)
if 'error' in d:
    print(f'Bitrix24 error: {d.get(\"error\")}: {d.get(\"error_description\",\"\")}', file=sys.stderr)
    sys.exit(0)
tasks = d.get('result', {}).get('tasks', [])
total = d.get('total', len(tasks))
print(f'Tasks: {len(tasks)} (total {total})')
for t in tasks:
    st = status_map.get(str(t.get('status','')), t.get('status',''))
    deadline = (t.get('deadline') or '—')[:10]
    print(f'  #{t[\"id\"]:<6} [{st:<10}] resp={t.get(\"responsibleId\",\"?\"):<5} due={deadline}  {t.get(\"title\",\"\")}')
"
exit 0

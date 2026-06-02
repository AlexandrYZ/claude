#!/bin/bash
# Общий preamble для всех скриптов скилла.
# Контракт: задан $BITRIX_WEBHOOK.
# Скилл универсальный — конкретный портал и владелец токена в окружении / профиле.

: "${BITRIX_WEBHOOK:?BITRIX_WEBHOOK не задан. Установи переменную окружения с URL входящего webhook (https://<portal>.bitrix24.ru/rest/<userId>/<token>/).}"

case "$BITRIX_WEBHOOK" in
  */) ;;
  *) BITRIX_WEBHOOK="${BITRIX_WEBHOOK}/" ;;
esac
export BITRIX_WEBHOOK

---
name: reviewing-investment-portfolio
description: Use when the user asks to проверить/разобрать портфель (ИИС, брокерский счёт), оценить куда вложить свободные деньги, ребалансировать, or review holdings in T-Invest / Т-Инвестиции via the t-invest MCP.
---

# Reviewing an Investment Portfolio

## Overview
Phases, in order: **retro → analyze → recommend → verify → log**. A recommendation is not delivered until phase 3 is done; a session is not finished until the log is written. Personal financial data stays out of code repos (`docs/` of a project) — it lives only in the Obsidian log.

**Log location:** `$OBSIDIAN_HOME/01 - Projects/Личные/Инвестиции/Анализ портфеля/YYYY.MM.DD - Анализ портфеля <счёт>.md` (one file per session per account; second session same day → suffix ` (2)`). Filename date = local date (`date +%Y.%m.%d`); `ops_to` = UTC (`date -u +%Y-%m-%dT%H:%M:%SZ`). Format: `log-template.md` in this skill's directory.

Load tools in one ToolSearch `select:` call: `invest_list_accounts, invest_get_portfolio, invest_get_positions, invest_get_operations, invest_get_market_values, invest_get_bond, invest_find_instrument, invest_get_forecast`.

## Phase 0 — Retro since last analysis

1. Find the latest log for this account in the log folder (`ls | sort | tail -1`). None → this is the baseline session, skip to Phase 1, set `ops_from` blank.
2. Read its frontmatter `ops_to` and section «4. Рекомендации».
3. `invest_get_operations(accountId, from=<ops_to>, to=now, state=EXECUTED, responseView=[PAYMENTS])`; follow `nextCursor` while `hasNext`. `payment` of BUY includes НКД (`accruedInt`); price of bonds is per bond in ₽.
4. Map every BUY/SELL to a recommendation ID or mark «вне рекомендаций». Summarize INPUT/OUTPUT, COUPON/DIVIDEND, BOND_REPAYMENT*, fees separately.
5. For each past recommendation: status (done/partial/not_done/rejected/obsolete) + outcome = price then → now (`invest_get_market_values`), in % and ₽ on the recommended amount. Constraints («не докупать X») are scored too: did X fall or rise?
6. Conclusions: which recommendation types worked, which sources/targets missed. Feed into Phase 2.

## Phase 1 — Analyze state

1. `invest_list_accounts(status=OPEN)` → pick account by type (`ACCOUNT_TYPE_TINKOFF_IIS` for ИИС). Note `accessLevel`: READ_ONLY = no orders possible.
2. `invest_get_portfolio(responseView=[FULL])` + `invest_get_positions` (free cash = `money[rub]`).
3. Current value per position = `averagePositionPrice × quantity + expectedYield`. Compute weights with python, don't eyeball.
4. Classify — API buckets mislead:
   - `totalAmountCurrencies` includes metals: `GLDRUB_TOM` (gold), `SLVRUB_TOM` (silver) on CETS.
   - `SPBXM` foreign shares (AAPL…) and positions with avg price 0 (FIVE) = **frozen**, exclude from investable allocation. Their value = `totalAmountPortfolio` − sum of all other positions − cash (AAPL is priced in USD, avg×qty is not ₽).
   - Bond with `BOND_REPAYMENT_FULL` in operations may still be listed in positions/portfolio (API lag) — exclude it.
   - Bonds: `invest_get_bond` → nominal currency (USD nominal = currency-linked «замещайка»), amortization (current nominal < initial).
5. Market data: `invest_get_market_values([...ticker_classCode], [LAST_PRICE, YIELD])`. Bond price is % of current nominal.
6. Flag: YTM > 2× key rate, sector concentration (banks, oil), tail of positions < 1% deep in loss, idle cash share.

## Phase 2 — Recommend

1. Macro anchor first: key rate + OFZ YTM curve (26238, 26240, 26243, 26247, 26248 via market_values).
2. Analyst consensus: `invest_list_consensus_forecasts` has no tickers — useless. Use `invest_find_instrument(query, INSTRUMENT_TYPE_SHARE, apiTradeAvailableFlag=true)` → uid → `invest_get_forecast(uid)`.
3. Allocate free cash by gaps, not by picks: underweight classes first (bonds/OFZ, money-market fund TMON@ for buffer), then top up existing core holdings; no new micro-positions; don't add to already-overweight classes.
4. Give amounts per bucket as a table; for each red-flag position, give hold/sell trade-off, not a command.

## Phase 3 — Verify

**REQUIRED SUB-SKILL:** Use verifying-market-data before presenting final recommendations.

## Phase 4 — Log

Write the log from `log-template.md`: all sections filled, recommendations **after** verification with IDs `YYYY-MM-DD-R<n>` and price at recommendation time, position snapshot, `ops_to` = session time (UTC). If the user rejects/changes a recommendation later in the same session, update the log before finishing. Recommendations revised during verification: log only the final version, note what changed in section 5.

## Output (chat)

1. Retro: trades since last analysis, status of past recommendations.
2. Allocation table (class, ₽, %), frozen assets separated.
3. Observations (concentration, red flags).
4. Recommendation table for free cash.
5. «Подтвердилось / Изменилось» after verification + `Sources:`.
6. Link to the log file.
7. Disclaimer: not individual advice; goals/horizon unknown unless stated. Mention if account is READ_ONLY.

## Common mistakes
- Treating metals in the currency bucket as cash.
- Counting frozen SPB shares as equity allocation.
- Using API consensus upside as expected return — broker targets are systematically optimistic.
- Delivering phase 2 without phase 3.
- Ending the session without a log, or logging pre-verification recommendations.
- Scoring only executed recommendations — skipped ones and constraints need an outcome too, otherwise the retro is biased.
- Writing portfolio data into a project repo.

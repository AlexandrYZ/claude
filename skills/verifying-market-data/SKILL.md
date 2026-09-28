---
name: verifying-market-data
description: Use when giving investment conclusions or recommendations (portfolio review, "куда вложить", bond/stock picks) based on broker API data (T-Invest MCP etc.), or when the user asks to перепроверить, найти независимые источники, verify against third-party sources. Also when a bond shows abnormal YTM (>2x key rate), a position has price 0, or analyst targets look implausible.
---

# Verifying Market Data with Independent Sources

## Overview
Broker API numbers are primary data; web search summaries are the least reliable layer — they mix stale articles into "current" figures. Every number that drives a recommendation needs a second source you actually opened, or your own calculation.

## Source reliability (high → low)

| Layer | Use for | Trap |
|---|---|---|
| Broker API (MCP) | prices, YTM, positions, consensus | consensus targets optimistic; YTM of distressed bonds is real, not a bug |
| Own calculation (python) | YTM from price/coupon/maturity, weights | semi-annual vs effective annual rate differ ~0.5 pp |
| Quote pages (smart-lab.ru/q/…, moex, cbonds) via WebFetch | cross-check price/YTM | page may time out — retry another source, don't skip |
| Regulator (cbr.ru), dated news of the decision | key rate, next meeting date | — |
| Dated analysis posts (smart-lab blog, broker research) | *why* a number is abnormal | author bias; take facts, not verdict |
| WebSearch summary text | finding URLs only | **stale/wrong numbers** (seen: bond at 105% / YTM 19% when real was 84% / 63%; target prices from before a split) |

## Checklist per recommendation

1. **Macro anchor**: key rate + date of last decision + next meeting (cbr.ru or dated news). Compare OFZ YTM to it — spread tells market expectations.
2. **Each number used in a verdict**: API value + one opened page (WebFetch) or own calc. Mismatch → trust the dated primary page, state the discrepancy.
3. **Red-flag positions** (YTM > 2× key rate, price 0, frozen venue like SPBXM): search `<issuer> облигации дефолт/проблемы <month year>`, open a dated post, extract: cash vs debt, covenant breaches, nearest large repayment date, rating date.
4. **Analyst targets**: use direction (favorite / not) across 2+ brokers; drop target numbers whose implied current price ≠ today's price (stale).
5. **Forecast track record**: check if the source's earlier forecasts (rate, index) already missed — say so, discount accordingly.

## Output contract
- Section "Подтвердилось" / "Изменилось" with the concrete number from each source.
- Explicit note which search snippets were stale and discarded.
- `Sources:` list with markdown links to pages actually used.
- Not individual investment advice; horizon/goals unknown unless stated.

## Common mistakes
- Citing a WebSearch summary number without opening the page.
- Treating 60%+ YTM as an API glitch instead of a default-risk signal.
- Counting frozen foreign shares (AAPL on SPBXM) as investable allocation.
- One WebFetch timeout → dropping the check instead of trying another source.

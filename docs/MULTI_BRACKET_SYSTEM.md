# Multi-Bracket Order System — Just Trades Platform

> **Architecture reference for the native multi-bracket order system (Feb 17-18, 2026).**

---

## How It Works

One REST API call creates the entire bracket: entry + multiple TP legs + SL (fixed or trailing).

```
risk_config built in ultra_simple_server.py (~16829-16914)
  → take_profit: [{ticks, trim}, {ticks, trim}, ...]
  → trail: {trigger, frequency}
  → stop_loss: {ticks, type}
  → break_even: {enabled, ticks, offset}
  → trim_units: "Contracts" or "Percent"
```

## Critical Code Locations

**recorder_service.py (bracket builder):**

| Line | What | DO NOT TOUCH |
|------|------|-------------|
| ~2089 | `has_multi_tp` detection | Gate for multi-bracket path |
| ~2094-2097 | `use_bracket_order` gate | Must NOT have `not has_multi_tp` |
| ~2100-2141 | Trail/autoTrail/break-even extraction | Reads risk_config |
| ~2143-2182 | Multi-bracket leg builder | Builds multi_brackets_list |
| ~2189-2197 | `place_bracket_order()` call | Passes multi_brackets param |

**tradovate_integration.py (REST order builder):**

| Line | What | DO NOT TOUCH |
|------|------|-------------|
| ~1840-2080 | `place_bracket_order()` | Universal REST bracket builder |
| ~1916-1962 | Multi-bracket mode | Builds brackets[] from multi_brackets param |
| ~2005-2012 | Strategy payload | accountId, symbol, orderStrategyTypeId=2 |
| ~2022-2042 | REST POST + response parsing | orderStrategy/startOrderStrategy |

**ultra_simple_server.py (risk_config builder):**

| Line | What |
|------|------|
| ~16829-16914 | risk_config builder (take_profit, trail, stop_loss, break_even) |
| ~16919-16951 | broker_task queued with risk_config |
| ~14597 | Broker worker extracts risk_config |
| ~14659 | Passes risk_config to execute_trade_simple() |

---

*Source: CLAUDE.md "MULTI-BRACKET ORDER SYSTEM" section*

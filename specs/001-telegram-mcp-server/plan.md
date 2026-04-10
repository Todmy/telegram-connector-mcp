# Implementation Plan: Godmode Telegram MCP

**Branch**: `001-telegram-mcp-server` | **Date**: 2026-04-09 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-telegram-mcp-server/spec.md`

## Summary

MCP server exposing full Telegram client capabilities to Claude Code. 5 static MCP tools + dynamic operations catalog (23 ops). Speakeasy Dynamic Toolsets pattern for token efficiency. Telethon User API (MTProto) for channel reading, search, interaction, folder management, and analytics. SQLite cache with TTL. TOON format for list responses.

## Technical Context

**Language/Version**: Python 3.11+ (async generators, ExceptionGroup support)
**Primary Dependencies**: mcp SDK (pip), telethon >=1.36, aiosqlite >=0.20, python-dotenv >=1.0, cryptg >=0.4
**Storage**: SQLite with WAL mode (aiosqlite) — channel index, message cache, folder structure
**Testing**: pytest >=8.0, pytest-asyncio >=0.24
**Target Platform**: macOS/Linux — Claude Code terminal (MCP stdio transport)
**Project Type**: MCP server (Python package, `python -m tg_mcp`)
**Performance Goals**: 5s first request (incl. connection), 2s cached requests, 30% token reduction via TOON
**Constraints**: ≤5 static MCP tools, async throughout, no print(), TOON for lists, 4-part structured errors
**Scale/Scope**: 200+ channels, single user, 23 initial operations across 5 categories

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Token Efficiency First | Exactly 5 static tools; TOON for lists; Dynamic Toolsets for catalog | ✅ Pass — 5 tools: tg_feed, tg_overview, tg_search_ops, tg_describe_op, tg_execute |
| II. Async Throughout | All code async/await; no sync I/O | ✅ Pass — Telethon async, aiosqlite async, MCP SDK async |
| III. Outcome-Oriented Ops | Ops answer questions, not wrap APIs | ✅ Pass — who_posted_first, find_duplicates, engagement_ranking vs raw get_messages |
| IV. Defensive by Default | Destructive ops require confirm; lazy connect; TTL cache | ✅ Pass — confirm=true for unsubscribe/delete; lazy Telethon connect; TTL cache per data type |
| V. Extensibility Without Context Cost | New ops via @operation() in ops/; no server.py changes | ✅ Pass — decorator-based registration, auto-import from ops/ |
| VI. Structured Error Communication | 4-part errors; isError flag; three-tier severity | ✅ Pass — FR-016 requires what/expected/example/recovery |

**Result**: All gates pass. No violations.

## Project Structure

### Documentation (this feature)

```text
specs/001-telegram-mcp-server/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── mcp-tools.md     # MCP tool schemas
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
src/tg_mcp/
├── __init__.py
├── __main__.py          # Entry: python -m tg_mcp
├── server.py            # MCP server — 5 static tools, stdio transport
├── client.py            # Telethon client wrapper (lazy connect, reconnect)
├── cache.py             # SQLite cache layer (read/write, TTL checks)
├── catalog.py           # Operations registry, search, describe, execute
├── toon.py              # TOON formatter (list → TOON string)
├── config.py            # Settings from .env + defaults
├── auth.py              # CLI auth flow (python -m tg_mcp.auth)
├── ops/                 # Operations catalog
│   ├── __init__.py      # Auto-imports all modules in ops/
│   ├── channels.py      # list, info, stats, subscribe, unsubscribe, mute
│   ├── messages.py      # search, get, history, who_posted_first
│   ├── interact.py      # react, comment, forward, mark_read
│   ├── folders.py       # list, contents, move, create
│   └── analytics.py     # compare, duplicates, inactive, top_posts, ranking
└── db/
    ├── __init__.py
    ├── schema.sql        # SQLite DDL
    └── migrations.py     # Schema versioning

tests/
├── test_catalog.py      # Operation registration + search
├── test_toon.py         # TOON formatter
├── test_cache.py        # Cache TTL + invalidation
└── test_tools.py        # MCP tool responses
```

**Structure Decision**: Single project layout. Source in `src/tg_mcp/` (Python package), tests in `tests/` at repo root. No frontend, no separate backend — this is a pure Python MCP server.

## Complexity Tracking

> No violations detected. Table empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

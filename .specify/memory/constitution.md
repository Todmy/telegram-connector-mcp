<!--
Sync Impact Report
==================
Version change: N/A → 1.0.0 (initial ratification)
Modified principles: N/A (first version)
Added sections:
  - Core Principles (6 principles)
  - Technology Constraints
  - Development Workflow
  - Governance
Removed sections: N/A
Templates requiring updates:
  - .specify/templates/plan-template.md — ✅ compatible (Constitution Check section already generic)
  - .specify/templates/spec-template.md — ✅ compatible (no principle-specific refs)
  - .specify/templates/tasks-template.md — ✅ compatible (phase structure aligns)
Follow-up TODOs: none
-->

# Telegram MCP Server Constitution

## Core Principles

### I. Token Efficiency First

Every design decision MUST minimize context window consumption.

- The MCP layer exposes **exactly 5 static tools**. Adding a 6th
  tool is a constitutional violation requiring an amendment.
- All list responses MUST use TOON format (30-60% token reduction
  over JSON).
- The Dynamic Toolsets pattern (Speakeasy §8.2) MUST be used for
  all operations beyond the 5 static tools. Context cost stays O(1)
  regardless of catalog size.
- Default response fields MUST be minimal. Extended fields are
  opt-in via the `fields` parameter.
- Content MUST be truncated by default with hints for full retrieval.

**Rationale:** This server runs inside Claude Code's context window.
Every wasted token reduces the AI's ability to reason about results.
The 5-tool cap + Dynamic Toolsets achieved 96.7% token reduction in
benchmarks.

### II. Async Throughout

All code MUST use async/await. No synchronous blocking calls.

- Telethon is an async library; synchronous wrappers break the
  event loop and cause deadlocks.
- Database access (aiosqlite) MUST be async.
- The MCP server event loop MUST never be blocked by I/O.

**Rationale:** A single synchronous call in the request path blocks
the entire MCP server. There is no thread pool fallback — async is
the only correct execution model.

### III. Outcome-Oriented Operations

Operations MUST answer user questions, not expose raw API surfaces.

- Good: `who_posted_first`, `find_duplicates`, `trending_topics`.
- Bad: `get_messages`, `list_participants`, `get_entity`.
- Each operation MUST have a clear purpose statement that describes
  the question it answers, not the API it wraps.
- Pre-computed aggregates MUST be preferred over returning raw data
  for the AI to process.

**Rationale:** Raw API wrappers force the AI to make multiple calls
and stitch results together, wasting tokens and increasing latency.
Outcome-oriented ops deliver value in a single round-trip.

### IV. Defensive by Default

All operations MUST be safe to call without side effects unless
explicitly confirmed.

- Destructive operations (unsubscribe, delete, mark-as-read) MUST
  require `confirm=true` parameter.
- The Telethon client MUST connect lazily on first tool call, not
  at MCP server startup.
- SQLite cache MUST use TTL-based expiration to avoid stale data
  without manual invalidation.
- FloodWait errors from Telegram MUST be handled gracefully with
  automatic retry and user-visible wait indication.

**Rationale:** An MCP server is called by an AI agent that may
invoke tools speculatively. Destructive actions without explicit
confirmation can cause irreversible damage to the user's Telegram
account state.

### V. Extensibility Without Context Cost

New operations MUST be addable without increasing context window
consumption.

- New ops = new file in `ops/`, auto-registered via `@operation()`
  decorator in `catalog.py`.
- Operation metadata (name, description, schema) is stored in the
  catalog, not in MCP tool definitions.
- Discovery follows the 3-step pattern: `tg_search_ops` →
  `tg_describe_op` → `tg_execute`.
- No changes to `server.py` are required to add a new operation.

**Rationale:** The catalog will grow from ~23 initial ops to 50+
over time. The Dynamic Toolsets pattern ensures this growth has
zero impact on context budget.

### VI. Structured Error Communication

Every error response MUST include four components:

1. **What happened** — the specific failure.
2. **What was expected** — the correct state or input.
3. **Example** — a concrete correct usage example.
4. **Recovery hint** — actionable next step.

Errors MUST use the MCP `isError` flag with three-tier severity
(user error, transient, fatal).

**Rationale:** The AI agent consuming these errors needs enough
context to self-correct without additional round-trips. Bare error
messages like "not found" force wasteful retry loops.

## Technology Constraints

- **Language:** Python 3.11+ (async generators, ExceptionGroup)
- **Telegram API:** Telethon 1.x (User API / MTProto). Bot API is
  NOT sufficient — it cannot read subscribed channels.
- **Transport:** stdio (MCP standard for Claude Code servers)
- **Storage:** SQLite with WAL mode (aiosqlite). Single-file,
  no external database dependencies.
- **Config:** `.env` file for API_ID, API_HASH, PHONE. Loaded via
  python-dotenv.
- **Session/cache path:** `~/.tg-mcp/` (never in repo)
- **Secrets:** `.env` and `session.session` MUST NOT be committed.
- **MCP SDK:** `mcp` package from pip (stdio transport)

## Development Workflow

- **Type hints** on all function signatures. No untyped public APIs.
- **Operations** registered via `@operation()` decorator — never
  by manual catalog insertion.
- **No print()** — use MCP logging or structured log calls.
- **Responses** use TOON format for lists, plain text for single
  items (per Principle I).
- **Testing** via pytest. Operations MUST be testable in isolation
  from the MCP transport layer.
- **Commits** are small and discrete — one logical change per commit.

## Governance

This constitution is the supreme authority for architectural and
design decisions in the Telegram MCP Server project. All feature
work, code reviews, and refactoring MUST comply with these
principles.

**Amendment procedure:**
1. Propose the change with rationale and impact assessment.
2. Update this document with a version bump (semver):
   - MAJOR: principle removal or incompatible redefinition.
   - MINOR: new principle or material scope expansion.
   - PATCH: clarifications, typo fixes, non-semantic edits.
3. Update dependent templates if principles change.
4. Record the amendment in the Sync Impact Report (top comment).

**Compliance review:** Every plan created via `/speckit.plan` MUST
pass a Constitution Check gate before implementation begins.

**Runtime guidance:** `CLAUDE.md` at project root serves as the
operational reference for day-to-day development. It MUST remain
consistent with this constitution.

**Version**: 1.0.0 | **Ratified**: 2026-04-09 | **Last Amended**: 2026-04-09

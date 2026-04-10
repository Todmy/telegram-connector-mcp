# Feature Specification: Godmode Telegram MCP

**Feature Branch**: `001-telegram-mcp-server`
**Created**: 2026-04-09
**Status**: Draft
**Input**: Design specification from `docs/spec.md`

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read Channel Feed (Priority: P1)

As a user with 200+ Telegram channel subscriptions, I want to read recent messages from my channels directly from the terminal so I can stay informed without opening the Telegram app.

**Why this priority**: This is the core value proposition — consuming channel content accounts for ~60% of all expected interactions. Without this, the server has no purpose.

**Independent Test**: Can be fully tested by requesting messages from a single channel and verifying that text, date, and engagement metrics are returned within seconds.

**Acceptance Scenarios**:

1. **Given** I am subscribed to multiple channels, **When** I request a feed without specifying a channel, **Then** I receive a cross-channel digest sorted by time from the last 24 hours with up to 20 messages.
2. **Given** I want to read a specific channel, **When** I provide a channel handle (e.g., @example), **Then** I receive messages only from that channel with text, date, and view count.
3. **Given** a message exceeds 300 characters, **When** I view it in the feed, **Then** the text is truncated with a character count and a hint on how to retrieve the full text.
4. **Given** I want messages from a specific time window, **When** I set the hours parameter (e.g., 48), **Then** only messages within that window are returned.
5. **Given** I want additional metadata, **When** I specify extra fields (reactions, author, replies), **Then** those fields appear in the response alongside defaults.

---

### User Story 2 - Channel Overview & Discovery (Priority: P1)

As a user, I want to see an overview of all my subscribed channels with activity metrics so I can identify which channels are active, which have unread messages, and which are dead.

**Why this priority**: Equally critical as feed reading — the user needs orientation ("what do I have?") before diving into content. This is the second highest-frequency operation (~25%).

**Independent Test**: Can be tested by requesting a channel overview and verifying that channel names, unread counts, and last post dates are returned.

**Acceptance Scenarios**:

1. **Given** I am subscribed to 200+ channels, **When** I request an overview, **Then** I receive a list of all channels sorted by unread count (most unread first) with name, unread count, and last post date.
2. **Given** I want to filter by channel type, **When** I specify "channels" or "groups", **Then** only matching entities are returned.
3. **Given** I have Telegram folders configured, **When** I filter by folder name, **Then** only channels within that folder appear.
4. **Given** I want to sort differently, **When** I specify sort by activity, subscribers, or name, **Then** the list is reordered accordingly.

---

### User Story 3 - Discover & Execute Operations (Priority: P1)

As a user, I want to discover available operations by keyword and execute them so I can perform any Telegram action without memorizing a fixed set of commands.

**Why this priority**: This is the extensibility mechanism that makes the server viable long-term. Without it, every new capability would require adding a new static tool, breaking the token efficiency model.

**Independent Test**: Can be tested by searching for "react", getting the schema for a returned operation, and executing it successfully.

**Acceptance Scenarios**:

1. **Given** I need to find an operation, **When** I search by keyword (e.g., "folder"), **Then** I receive a list of matching operations with names and one-line descriptions.
2. **Given** I found an operation name, **When** I request its schema, **Then** I receive the full parameter list with types, defaults, and an example invocation.
3. **Given** I have the schema, **When** I execute the operation with valid parameters, **Then** the operation runs and returns results in a compact format.
4. **Given** I try to execute a destructive operation (e.g., unsubscribe), **When** I do not include a confirmation flag, **Then** I receive a warning describing the consequence and instructions to confirm.
5. **Given** I confirm a destructive operation, **When** I include the confirmation flag, **Then** the operation executes and returns a success message with an undo hint.

---

### User Story 4 - Search Messages Across Channels (Priority: P2)

As a user, I want to search for messages by keyword across all my channels so I can find specific information without manually browsing each channel.

**Why this priority**: High-value but less frequent than feed reading. Enables the "intelligence" use case — finding who posted what first, tracking topics.

**Independent Test**: Can be tested by searching for a known keyword and verifying that matching messages are returned from multiple channels with source attribution.

**Acceptance Scenarios**:

1. **Given** I want to find messages about a topic, **When** I search by keyword with optional date filters, **Then** I receive matching messages across all subscribed channels, sorted by relevance.
2. **Given** I want to know which channel broke a story first, **When** I use the "who posted first" operation with a keyword, **Then** I receive a chronologically ordered list of channels with timestamps.

---

### User Story 5 - Interact with Content (Priority: P2)

As a user, I want to react to messages, post comments, and forward content from the terminal so I can engage with channels without switching to the Telegram app.

**Why this priority**: Enables write operations. Lower priority than read because the primary use case is consumption, but essential for a complete experience.

**Independent Test**: Can be tested by reacting to a message with an emoji and verifying the reaction was applied.

**Acceptance Scenarios**:

1. **Given** I want to react to a message, **When** I specify the channel, message ID, and emoji, **Then** the reaction is applied and I receive confirmation with the updated reaction count.
2. **Given** I want to comment on a channel post, **When** I specify the channel, message, and comment text, **Then** the comment is posted in the linked discussion group.
3. **Given** I want to save a message, **When** I forward it to Saved Messages, **Then** the message appears in my Saved Messages on Telegram.
4. **Given** I have unread messages, **When** I mark a channel as read, **Then** the unread count resets to zero.

---

### User Story 6 - Manage Folders & Subscriptions (Priority: P3)

As a user, I want to organize my channels into folders and manage my subscriptions so I can keep my channel list curated and manageable.

**Why this priority**: Organizational capability. Less frequent than reading or searching, but necessary for managing 200+ channels over time.

**Independent Test**: Can be tested by creating a folder, moving a channel into it, and verifying the folder contents.

**Acceptance Scenarios**:

1. **Given** I want to see my folder structure, **When** I list folders, **Then** I receive all folders with channel counts.
2. **Given** I want to organize a channel, **When** I move it to a specific folder, **Then** the channel appears in that folder on subsequent queries.
3. **Given** I want a new organizational category, **When** I create a folder with a name, **Then** the folder is created and ready to receive channels.
4. **Given** I want to leave a channel, **When** I unsubscribe with confirmation, **Then** I am removed from the channel and receive a re-subscribe hint.

---

### User Story 7 - Channel Analytics & Comparison (Priority: P3)

As a user, I want to analyze and compare channels by engagement, activity, and content quality so I can make informed decisions about what to follow.

**Why this priority**: Power-user feature. Valuable for curation decisions but not essential for daily use.

**Independent Test**: Can be tested by comparing two channels and verifying that comparative metrics (post frequency, views, engagement) are returned.

**Acceptance Scenarios**:

1. **Given** I want to compare channels, **When** I provide 2+ channel handles, **Then** I receive a side-by-side comparison of key metrics.
2. **Given** I want to find inactive channels, **When** I search for channels with no posts in N days, **Then** I receive a list of dormant channels.
3. **Given** I want to find the best content, **When** I search for top posts by engagement across channels, **Then** I receive the highest-engagement posts within a time window.
4. **Given** I suspect content overlap, **When** I search for duplicate content, **Then** channels posting similar content are identified.

---

### Edge Cases

- What happens when the user is not authenticated? The server MUST return a clear error with authentication instructions, not crash or hang.
- What happens when Telegram rate-limits the server? The server MUST return the wait time and suggest retrying, not block indefinitely.
- What happens when a channel is private or the user was banned? The server MUST return a specific error explaining the access issue.
- What happens when no messages match a search? The server MUST return a definitive empty state with suggestions for broadening the search.
- What happens when the network connection to Telegram drops? The server MUST timeout within 30 seconds and return a recoverable error.
- What happens when a channel title substring matches multiple channels? The server MUST return results from all matches and indicate which channels were included, rather than erroring or picking one.

## Clarifications

### Session 2026-04-09

- Q: How should media content (photos, videos, documents) be handled? → A: Metadata + download link — include media type, filename, file size, and a retrieval URL or Telegram link. No local caching or binary proxying.
- Q: How should ambiguous channel title substring matches be resolved? → A: Return results from all matching channels, indicating which channels matched. User can narrow down with exact @handle.
- Q: What observability requirements should the spec include? → A: Structured logging — log operations, errors, and rate-limit events to file. No metrics infrastructure or session summaries needed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST fetch messages from any subscribed channel or group with configurable time window and message count.
- **FR-002**: System MUST provide a cross-channel feed combining messages from all subscribed channels, sorted by time.
- **FR-003**: System MUST list all subscribed channels with activity metrics (unread count, last post date, post frequency, subscriber count).
- **FR-004**: System MUST support filtering channels and messages by Telegram folder.
- **FR-005**: System MUST provide a searchable operations catalog where users can discover available actions by keyword or category.
- **FR-006**: System MUST display the full parameter schema (types, defaults, examples) for any operation on demand.
- **FR-007**: System MUST execute any catalog operation with user-provided parameters and return results.
- **FR-008**: System MUST require explicit confirmation before executing destructive operations (unsubscribe, delete).
- **FR-009**: System MUST search messages by keyword across all subscribed channels with date filtering.
- **FR-010**: System MUST support reactions, comments, forwarding, and marking messages as read.
- **FR-011**: System MUST list, create, and manage Telegram folders and move channels between them.
- **FR-012**: System MUST provide analytics: channel comparison, inactive channel detection, top posts, engagement ranking, and duplicate content detection.
- **FR-013**: System MUST truncate long message text by default with a hint on how to retrieve the full content.
- **FR-014**: System MUST return pre-computed aggregates (counts, averages, summaries) with every list response.
- **FR-015**: System MUST append contextual next-step hints to every response.
- **FR-016**: System MUST return structured errors with four components: what happened, what was expected, example of correct usage, and recovery hint.
- **FR-017**: System MUST handle authentication errors by directing the user to run the authentication command.
- **FR-018**: System MUST handle rate-limiting by returning the wait duration and retry instructions.
- **FR-019**: System MUST cache frequently accessed data (channel list, messages) with appropriate expiration to avoid redundant queries.
- **FR-020**: System MUST connect to Telegram lazily on first use, not at server startup.
- **FR-021**: System MUST support adding new operations without modifying core server code.
- **FR-022**: System MUST include media metadata (type, filename, file size) and a download link for messages containing media attachments.
- **FR-023**: When a channel title substring matches multiple channels, the system MUST return results from all matching channels and indicate which channels matched.
- **FR-024**: System MUST log all operations, errors, and rate-limit events using structured logging to a log file.

### Key Entities

- **Channel**: A Telegram channel or group the user is subscribed to. Key attributes: name, handle, subscriber count, unread count, post frequency, folder membership, last post date.
- **Message**: A post in a channel. Key attributes: text content, author, date, view count, reactions, reply count, forwarded-from source, media type, media filename, media file size, media download link.
- **Folder**: A Telegram organizational folder containing channels. Key attributes: name, list of member channels.
- **Operation**: A discoverable action in the catalog. Key attributes: name, category, description, parameter schema, destructive flag.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: User can retrieve a channel feed within 5 seconds of the first request (including initial connection).
- **SC-002**: Subsequent feed requests complete within 2 seconds (cached connection).
- **SC-003**: The server exposes no more than 5 tools to the AI, regardless of how many operations are available in the catalog.
- **SC-004**: Adding a new operation requires creating only one file, with no changes to server core — verified by adding a test operation.
- **SC-005**: List responses consume at least 30% fewer tokens compared to equivalent JSON representation.
- **SC-006**: All destructive operations are blocked unless explicitly confirmed — verified by attempting an unconfirmed destructive action.
- **SC-007**: Every error response includes all four required components (what/expected/example/recovery) — verified by triggering each error type.
- **SC-008**: The server operates with 23+ distinct operations available for discovery and execution on day one.
- **SC-009**: 100% of edge cases (auth failure, rate limit, private channel, empty results, network timeout) produce user-friendly, actionable error messages.
- **SC-010**: User can discover, describe, and execute any catalog operation in 3 steps or fewer.

## Assumptions

- The user has a personal Telegram account with 200+ channel subscriptions.
- The user has obtained API credentials (API_ID, API_HASH) from my.telegram.org.
- Authentication is a one-time setup performed before the MCP server is used.
- The server is used exclusively from Claude Code's terminal (single-user, single-session).
- Telegram's rate limits (FloodWait) are respected; the server does not attempt to bypass them.
- The server runs as an on-demand process (no background daemon), started by Claude Code when a Telegram tool is invoked.
- Network connectivity to Telegram servers is generally available; transient failures are handled gracefully.

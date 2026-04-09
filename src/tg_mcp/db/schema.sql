-- Telegram MCP Server — SQLite schema
-- Applied on first connect via migrations.py.
-- WAL mode is set programmatically, not here.

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Channel index (cached from Telegram)
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY,              -- Telegram channel ID
    title TEXT NOT NULL,
    handle TEXT,                          -- @handle, may be NULL for private channels
    subscribers INTEGER,
    is_channel BOOLEAN NOT NULL,          -- true=channel, false=group
    folder TEXT,
    last_post_date TEXT,                  -- ISO 8601
    posts_per_week REAL,
    unread_count INTEGER NOT NULL DEFAULT 0,
    cached_at TEXT NOT NULL               -- ISO 8601, for TTL checks
);

-- Message cache
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER NOT NULL,                  -- Telegram message ID
    channel_id INTEGER NOT NULL REFERENCES channels(id),
    date TEXT NOT NULL,                   -- ISO 8601
    text TEXT,
    author TEXT,
    views INTEGER DEFAULT 0,
    reactions_json TEXT,                  -- JSON: {"emoji": count}
    replies INTEGER DEFAULT 0,
    forward_from TEXT,
    media_type TEXT,                      -- photo, video, document, or NULL
    media_filename TEXT,
    media_file_size INTEGER,
    media_download_link TEXT,
    cached_at TEXT NOT NULL,              -- ISO 8601, for TTL checks
    PRIMARY KEY (channel_id, id)
);

-- Folder structure
CREATE TABLE IF NOT EXISTS folders (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    channel_ids_json TEXT,               -- JSON array of channel IDs
    cached_at TEXT NOT NULL               -- ISO 8601
);

-- Cache metadata for TTL tracking
CREATE TABLE IF NOT EXISTS cache_meta (
    key TEXT PRIMARY KEY,                 -- e.g. "channels_list", "feed_@handle_24h"
    cached_at TEXT NOT NULL,              -- ISO 8601
    ttl_seconds INTEGER NOT NULL
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_messages_channel_date ON messages(channel_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_messages_date ON messages(date DESC);
CREATE INDEX IF NOT EXISTS idx_channels_handle ON channels(handle);
CREATE INDEX IF NOT EXISTS idx_channels_folder ON channels(folder);

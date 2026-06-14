PRAGMA foreign_keys = ON;

-- Main table: one row per work session.
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_time TEXT NOT NULL,
    end_time TEXT,
    note TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (end_time IS NULL OR end_time >= start_time)
);

-- Keep an audit trail of manual edits for trust and recoverability.
CREATE TABLE IF NOT EXISTS session_edits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    old_start_time TEXT,
    old_end_time TEXT,
    new_start_time TEXT,
    new_end_time TEXT,
    reason TEXT DEFAULT '',
    edited_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

-- Speeds up date range filters and calendar summaries.
CREATE INDEX IF NOT EXISTS idx_sessions_start_time ON sessions(start_time);
CREATE INDEX IF NOT EXISTS idx_sessions_end_time ON sessions(end_time);

-- Fast lookup for currently active session.
CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions(end_time) WHERE end_time IS NULL;

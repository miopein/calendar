PRAGMA foreign_keys = ON;

-- Keep updated_at fresh on every record update.
CREATE TRIGGER IF NOT EXISTS trg_sessions_updated_at
AFTER UPDATE ON sessions
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE sessions
    SET updated_at = datetime('now')
    WHERE id = OLD.id;
END;

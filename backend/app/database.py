import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "tousmeslikes.db"


def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'like',
            title TEXT,
            content TEXT,
            url TEXT,
            author TEXT,
            created_at TEXT,
            imported_at TEXT DEFAULT (datetime('now')),
            raw_json TEXT,
            categories TEXT DEFAULT '[]'
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
            title, content, author, platform,
            content='items',
            content_rowid='id'
        );

        CREATE TRIGGER IF NOT EXISTS items_ai AFTER INSERT ON items BEGIN
            INSERT INTO items_fts(rowid, title, content, author, platform)
            VALUES (new.id, new.title, new.content, new.author, new.platform);
        END;

        CREATE TRIGGER IF NOT EXISTS items_ad AFTER DELETE ON items BEGIN
            INSERT INTO items_fts(items_fts, rowid, title, content, author, platform)
            VALUES ('delete', old.id, old.title, old.content, old.author, old.platform);
        END;

        CREATE TRIGGER IF NOT EXISTS items_au AFTER UPDATE ON items BEGIN
            INSERT INTO items_fts(items_fts, rowid, title, content, author, platform)
            VALUES ('delete', old.id, old.title, old.content, old.author, old.platform);
            INSERT INTO items_fts(rowid, title, content, author, platform)
            VALUES (new.id, new.title, new.content, new.author, new.platform);
        END;
    """)
    conn.close()

import Database from "better-sqlite3";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";

export type NoteRecord = {
  id: string;
  created_at: string;
  source: string | null;
  tags: string[];
  related_paths: string[];
  text: string;
  score?: number;
};

export type TranscriptRecord = {
  id: string;
  created_at: string;
  session_id: string;
  source_client: string;
  kind: string;
  text: string;
};

export class Storage {
  private db: Database.Database;

  constructor(private dbPath: string) {
    const dir = path.dirname(dbPath);
    fs.mkdirSync(dir, { recursive: true });
    this.db = new Database(dbPath);
  }

  init(): void {
    this.db.pragma("journal_mode = WAL");
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS notes (
        id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        source TEXT,
        tags_json TEXT NOT NULL,
        related_paths_json TEXT NOT NULL,
        text TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS transcripts (
        id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        session_id TEXT NOT NULL,
        source_client TEXT NOT NULL,
        kind TEXT NOT NULL,
        text TEXT NOT NULL
      );
    `);
  }

  insertNote(params: {
    text: string;
    source?: string;
    tags?: string[];
    related_paths?: string[];
  }): { id: string } {
    const id = crypto.randomUUID();
    const createdAt = new Date().toISOString();
    const tags = params.tags ?? [];
    const relatedPaths = params.related_paths ?? [];
    const stmt = this.db.prepare(
      `INSERT INTO notes (id, created_at, source, tags_json, related_paths_json, text)
       VALUES (?, ?, ?, ?, ?, ?)`
    );
    stmt.run(
      id,
      createdAt,
      params.source ?? null,
      JSON.stringify(tags),
      JSON.stringify(relatedPaths),
      params.text
    );
    return { id };
  }

  searchNotes(params: {
    query?: string;
    tags?: string[];
    limit: number;
  }): NoteRecord[] {
    const limit = Math.max(1, Math.min(50, params.limit));
    const query = params.query?.trim();
    const rows = query
      ? (this.db
          .prepare(
            `SELECT id, created_at, source, tags_json, related_paths_json, text
             FROM notes
             WHERE text LIKE ?
             ORDER BY created_at DESC
             LIMIT ?`
          )
          .all(`%${query}%`, limit * 5) as Array<Record<string, unknown>>)
      : (this.db
          .prepare(
            `SELECT id, created_at, source, tags_json, related_paths_json, text
             FROM notes
             ORDER BY created_at DESC
             LIMIT ?`
          )
          .all(limit * 5) as Array<Record<string, unknown>>);

    const tagFilter = params.tags?.map((tag) => tag.toLowerCase()) ?? [];

    const results: NoteRecord[] = [];
    for (const row of rows) {
      const tags = safeParseJsonArray(row.tags_json);
      const relatedPaths = safeParseJsonArray(row.related_paths_json);
      const text = String(row.text ?? "");
      if (tagFilter.length > 0) {
        const lowerTags = tags.map((tag) => tag.toLowerCase());
        const hasAll = tagFilter.every((tag) => lowerTags.includes(tag));
        if (!hasAll) {
          continue;
        }
      }
      let score = 0;
      if (query) {
        const terms = query
          .toLowerCase()
          .split(/\s+/)
          .filter(Boolean);
        const lowerText = text.toLowerCase();
        for (const term of terms) {
          if (lowerText.includes(term)) {
            score += 1;
          }
        }
      }
      results.push({
        id: String(row.id),
        created_at: String(row.created_at),
        source: row.source ? String(row.source) : null,
        tags,
        related_paths: relatedPaths,
        text,
        score,
      });
      if (results.length >= limit) {
        break;
      }
    }
    return results;
  }

  insertTranscript(params: {
    session_id: string;
    source_client: string;
    kind: string;
    text: string;
  }): { id: string } {
    const id = crypto.randomUUID();
    const createdAt = new Date().toISOString();
    const stmt = this.db.prepare(
      `INSERT INTO transcripts (id, created_at, session_id, source_client, kind, text)
       VALUES (?, ?, ?, ?, ?, ?)`
    );
    stmt.run(id, createdAt, params.session_id, params.source_client, params.kind, params.text);
    return { id };
  }

  getTranscriptsBySession(sessionId: string): TranscriptRecord[] {
    const rows = this.db
      .prepare(
        `SELECT id, created_at, session_id, source_client, kind, text
         FROM transcripts
         WHERE session_id = ?
         ORDER BY created_at ASC`
      )
      .all(sessionId) as Array<Record<string, unknown>>;
    return rows.map((row) => ({
      id: String(row.id),
      created_at: String(row.created_at),
      session_id: String(row.session_id),
      source_client: String(row.source_client),
      kind: String(row.kind),
      text: String(row.text),
    }));
  }
}

function safeParseJsonArray(value: unknown): string[] {
  try {
    if (typeof value === "string") {
      const parsed = JSON.parse(value);
      if (Array.isArray(parsed)) {
        return parsed.map((entry) => String(entry));
      }
    }
  } catch {
    return [];
  }
  return [];
}

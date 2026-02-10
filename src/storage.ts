import Database from "better-sqlite3";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";

export type NoteRecord = {
  id: string;
  created_at: string;
  source: string | null;
  source_client: string | null;
  source_model: string | null;
  source_agent: string | null;
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
  source_model: string | null;
  source_agent: string | null;
  kind: string;
  text: string;
  score?: number;
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
        source_client TEXT,
        source_model TEXT,
        source_agent TEXT,
        tags_json TEXT NOT NULL,
        related_paths_json TEXT NOT NULL,
        text TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS transcripts (
        id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        session_id TEXT NOT NULL,
        source_client TEXT NOT NULL,
        source_model TEXT,
        source_agent TEXT,
        kind TEXT NOT NULL,
        text TEXT NOT NULL
      );
    `);
    this.ensureColumn("notes", "source_client", "TEXT");
    this.ensureColumn("notes", "source_model", "TEXT");
    this.ensureColumn("notes", "source_agent", "TEXT");
    this.ensureColumn("transcripts", "source_model", "TEXT");
    this.ensureColumn("transcripts", "source_agent", "TEXT");
  }

  insertNote(params: {
    text: string;
    source?: string;
    source_client?: string;
    source_model?: string;
    source_agent?: string;
    tags?: string[];
    related_paths?: string[];
  }): { id: string } {
    const id = crypto.randomUUID();
    const createdAt = new Date().toISOString();
    const tags = params.tags ?? [];
    const relatedPaths = params.related_paths ?? [];
    const stmt = this.db.prepare(
      `INSERT INTO notes (id, created_at, source, source_client, source_model, source_agent, tags_json, related_paths_json, text)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
    );
    stmt.run(
      id,
      createdAt,
      params.source ?? null,
      params.source_client ?? null,
      params.source_model ?? null,
      params.source_agent ?? null,
      JSON.stringify(tags),
      JSON.stringify(relatedPaths),
      params.text
    );
    return { id };
  }

  searchNotes(params: {
    query?: string;
    tags?: string[];
    source_client?: string;
    source_model?: string;
    source_agent?: string;
    limit: number;
  }): NoteRecord[] {
    const limit = Math.max(1, Math.min(50, params.limit));
    const query = params.query?.trim();
    const rows = query
      ? (this.db
          .prepare(
            `SELECT id, created_at, source, source_client, source_model, source_agent, tags_json, related_paths_json, text
             FROM notes
             WHERE text LIKE ?
             ORDER BY created_at DESC
             LIMIT ?`
          )
          .all(`%${query}%`, limit * 5) as Array<Record<string, unknown>>)
      : (this.db
          .prepare(
            `SELECT id, created_at, source, source_client, source_model, source_agent, tags_json, related_paths_json, text
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
      const sourceClient = row.source_client ? String(row.source_client) : null;
      const sourceModel = row.source_model ? String(row.source_model) : null;
      const sourceAgent = row.source_agent ? String(row.source_agent) : null;
      if (tagFilter.length > 0) {
        const lowerTags = tags.map((tag) => tag.toLowerCase());
        const hasAll = tagFilter.every((tag) => lowerTags.includes(tag));
        if (!hasAll) {
          continue;
        }
      }
      if (params.source_client && sourceClient !== params.source_client) {
        continue;
      }
      if (params.source_model && sourceModel !== params.source_model) {
        continue;
      }
      if (params.source_agent && sourceAgent !== params.source_agent) {
        continue;
      }
      const score = computeTermScore(text, query);
      results.push({
        id: String(row.id),
        created_at: String(row.created_at),
        source: row.source ? String(row.source) : null,
        source_client: sourceClient,
        source_model: sourceModel,
        source_agent: sourceAgent,
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
    source_model?: string;
    source_agent?: string;
    kind: string;
    text: string;
  }): { id: string } {
    const id = crypto.randomUUID();
    const createdAt = new Date().toISOString();
    const stmt = this.db.prepare(
      `INSERT INTO transcripts (id, created_at, session_id, source_client, source_model, source_agent, kind, text)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
    );
    stmt.run(
      id,
      createdAt,
      params.session_id,
      params.source_client,
      params.source_model ?? null,
      params.source_agent ?? null,
      params.kind,
      params.text
    );
    return { id };
  }

  getTranscriptsBySession(sessionId: string): TranscriptRecord[] {
    const rows = this.db
      .prepare(
        `SELECT id, created_at, session_id, source_client, source_model, source_agent, kind, text
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
      source_model: row.source_model ? String(row.source_model) : null,
      source_agent: row.source_agent ? String(row.source_agent) : null,
      kind: String(row.kind),
      text: String(row.text),
    }));
  }

  searchTranscripts(params: {
    query?: string;
    session_id?: string;
    source_client?: string;
    source_model?: string;
    source_agent?: string;
    limit: number;
  }): TranscriptRecord[] {
    const limit = Math.max(1, Math.min(50, params.limit));
    const query = params.query?.trim();
    const rows = query
      ? (this.db
          .prepare(
            `SELECT id, created_at, session_id, source_client, source_model, source_agent, kind, text
             FROM transcripts
             WHERE text LIKE ?
             ORDER BY created_at DESC
             LIMIT ?`
          )
          .all(`%${query}%`, limit * 5) as Array<Record<string, unknown>>)
      : (this.db
          .prepare(
            `SELECT id, created_at, session_id, source_client, source_model, source_agent, kind, text
             FROM transcripts
             ORDER BY created_at DESC
             LIMIT ?`
          )
          .all(limit * 5) as Array<Record<string, unknown>>);

    const results: TranscriptRecord[] = [];
    for (const row of rows) {
      const sessionId = String(row.session_id);
      const sourceClient = String(row.source_client);
      const sourceModel = row.source_model ? String(row.source_model) : null;
      const sourceAgent = row.source_agent ? String(row.source_agent) : null;
      const text = String(row.text ?? "");
      if (params.session_id && params.session_id !== sessionId) {
        continue;
      }
      if (params.source_client && params.source_client !== sourceClient) {
        continue;
      }
      if (params.source_model && params.source_model !== sourceModel) {
        continue;
      }
      if (params.source_agent && params.source_agent !== sourceAgent) {
        continue;
      }
      const score = computeTermScore(text, query);
      results.push({
        id: String(row.id),
        created_at: String(row.created_at),
        session_id: sessionId,
        source_client: sourceClient,
        source_model: sourceModel,
        source_agent: sourceAgent,
        kind: String(row.kind),
        text,
        score,
      });
      if (results.length >= limit) {
        break;
      }
    }
    return results;
  }

  private ensureColumn(table: "notes" | "transcripts", column: string, type: "TEXT"): void {
    const rows = this.db.prepare(`PRAGMA table_info(${table})`).all() as Array<Record<string, unknown>>;
    const exists = rows.some((row) => String(row.name) === column);
    if (!exists) {
      this.db.exec(`ALTER TABLE ${table} ADD COLUMN ${column} ${type}`);
    }
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

function computeTermScore(text: string, query?: string): number {
  if (!query) {
    return 0;
  }
  const terms = query
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean);
  const lowerText = text.toLowerCase();
  let score = 0;
  for (const term of terms) {
    if (lowerText.includes(term)) {
      score += 1;
    }
  }
  return score;
}

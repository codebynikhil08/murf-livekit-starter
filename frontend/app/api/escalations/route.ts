import { NextResponse } from 'next/server';
import { DatabaseSync } from 'node:sqlite';
import path from 'path';

const dbPath = path.join(process.cwd(), '..', 'backend', 'user_memory.db');

function getDb() {
  const db = new DatabaseSync(dbPath);
  db.exec(`
    CREATE TABLE IF NOT EXISTS escalations (
      id TEXT PRIMARY KEY,
      reference_id TEXT UNIQUE NOT NULL,
      caller_name TEXT NOT NULL,
      issue_summary TEXT NOT NULL,
      urgency TEXT NOT NULL,
      language_preference TEXT DEFAULT 'Hindi',
      contact_method TEXT DEFAULT 'Phone Call',
      location TEXT DEFAULT '',
      status TEXT DEFAULT 'Open',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
  `);
  return db;
}

export async function GET() {
  try {
    const db = getDb();
    const query = db.prepare(`
      SELECT id, reference_id, caller_name, issue_summary, urgency, language_preference, contact_method, location, status, created_at, updated_at
      FROM escalations
      ORDER BY created_at DESC
    `);
    const rows = query.all();
    db.close();
    return NextResponse.json({ success: true, escalations: rows });
  } catch (error) {
    console.error('Error fetching escalations:', error);
    return NextResponse.json({ success: false, error: String(error) }, { status: 500 });
  }
}

export async function PATCH(req: Request) {
  try {
    const body = await req.json();
    const { reference_id, status } = body;
    if (!reference_id || !status) {
      return NextResponse.json(
        { success: false, error: 'reference_id and status are required' },
        { status: 400 }
      );
    }

    const db = getDb();
    const nowIso = new Date().toISOString();
    const updateStmt = db.prepare(`
      UPDATE escalations
      SET status = ?, updated_at = ?
      WHERE reference_id = ? OR id = ?
    `);
    updateStmt.run(status, nowIso, reference_id, reference_id);
    db.close();

    return NextResponse.json({ success: true, reference_id, status });
  } catch (error) {
    console.error('Error updating escalation:', error);
    return NextResponse.json({ success: false, error: String(error) }, { status: 500 });
  }
}

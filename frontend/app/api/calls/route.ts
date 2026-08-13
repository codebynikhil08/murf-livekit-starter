import { NextResponse } from 'next/server';
import { DatabaseSync } from 'node:sqlite';
import path from 'path';

const dbPath = path.join(process.cwd(), '..', 'backend', 'user_memory.db');

function getDb() {
  const db = new DatabaseSync(dbPath);
  db.exec(`
    CREATE TABLE IF NOT EXISTS calls (
      session_id TEXT PRIMARY KEY,
      caller_name TEXT,
      status TEXT DEFAULT 'active',
      outcome TEXT DEFAULT 'failed',
      reason TEXT DEFAULT 'Call initiated',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
  `);
  return db;
}

export async function GET() {
  try {
    const db = getDb();
    
    // Get analytics stats
    const totalStmt = db.prepare("SELECT COUNT(*) as count FROM calls");
    const total = (totalStmt.get() as { count: number }).count;
    
    const successStmt = db.prepare("SELECT COUNT(*) as count FROM calls WHERE outcome = 'success'");
    const successful = (successStmt.get() as { count: number }).count;
    
    const failedStmt = db.prepare("SELECT COUNT(*) as count FROM calls WHERE outcome = 'failed'");
    const failed = (failedStmt.get() as { count: number }).count;
    
    // Get recent calls list (with protected/sanitized transcripts - we don't store transcripts in DB anyway, so this is fully safe)
    const recentStmt = db.prepare(`
      SELECT session_id, caller_name, status, outcome, reason, created_at, updated_at
      FROM calls
      ORDER BY created_at DESC
      LIMIT 10
    `);
    const recentCalls = recentStmt.all();
    db.close();
    
    return NextResponse.json({
      success: true,
      stats: {
        total,
        successful,
        failed,
      },
      recent_calls: recentCalls
    });
  } catch (error) {
    console.error('Error fetching call analytics:', error);
    return NextResponse.json({ success: false, error: String(error) }, { status: 500 });
  }
}

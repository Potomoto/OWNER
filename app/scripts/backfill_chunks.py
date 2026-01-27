# app/scripts/backfill_chunks.py
from __future__ import annotations

import argparse
import time

from sqlalchemy.orm import Session

from app.ai.rag.chunk_service import upsert_note_chunks
from app.db import SessionLocal
from app.models import Note


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill note_chunks from existing notes.")
    p.add_argument("--note-id", type=int, default=None, help="Only process one note_id")
    p.add_argument("--limit", type=int, default=None, help="Limit number of notes processed")
    p.add_argument("--dry-run", action="store_true", help="Do not write chunks, only print stats")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    t0 = time.perf_counter()

    db: Session = SessionLocal()
    try:
        q = db.query(Note).order_by(Note.id.asc())
        if args.note_id is not None:
            q = q.filter(Note.id == args.note_id)
        if args.limit is not None:
            q = q.limit(args.limit)

        notes = q.all()
        if not notes:
            print("No notes found.")
            return

        total_chunks = 0
        ok = 0
        failed = 0

        for n in notes:
            try:
                if args.dry_run:
                    # dry-run：只估算 chunks 数
                    from app.ai.rag.chunking import split_note

                    c = split_note(n.content)
                    total_chunks += len(c)
                    ok += 1
                    print(f"[dry-run] note_id={n.id} chunks={len(c)}")
                else:
                    r = upsert_note_chunks(db, n.id)
                    total_chunks += int(r["chunks"])
                    ok += 1
                    print(f"note_id={n.id} chunks={r['chunks']} cost_ms={r['cost_ms']:.1f}")
            except Exception as e:
                failed += 1
                print(f"[error] note_id={n.id} err={str(e)[:200]}")

        cost_ms = (time.perf_counter() - t0) * 1000
        print(
            f"\nDone. notes={len(notes)} ok={ok} \
                failed={failed} total_chunks={total_chunks} \
                cost_ms={cost_ms:.1f}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()

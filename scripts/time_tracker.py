#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from manage_db import DEFAULT_DB_PATH, apply_migrations


def utc_now() -> datetime:
    return datetime.now(UTC)


def to_storage_utc(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def from_storage_utc(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def display_local(value: str) -> str:
    return from_storage_utc(value).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def parse_user_datetime(value: str) -> datetime:
    normalized = value.strip().replace("T", " ")

    with_tz_formats = ["%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M%z"]
    without_tz_formats = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]

    for fmt in with_tz_formats:
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            pass

    for fmt in without_tz_formats:
        try:
            local_tz = datetime.now().astimezone().tzinfo
            return datetime.strptime(normalized, fmt).replace(tzinfo=local_tz)
        except ValueError:
            pass

    raise ValueError(
        "Unsupported datetime format. Use 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD HH:MM+0300'"
    )


def get_conn(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def get_active_session(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT id, start_time, end_time FROM sessions WHERE end_time IS NULL ORDER BY start_time DESC LIMIT 1"
    ).fetchone()


def cmd_start(db_path: Path, note: str) -> None:
    apply_migrations(db_path)
    with get_conn(db_path) as conn:
        active = get_active_session(conn)
        if active is not None:
            raise RuntimeError(
                f"Active session already exists (id={active['id']}, start={display_local(active['start_time'])})"
            )

        now_utc = to_storage_utc(utc_now())
        cur = conn.execute(
            "INSERT INTO sessions(start_time, note) VALUES (?, ?)",
            (now_utc, note),
        )
        conn.commit()
        print(f"Started session id={cur.lastrowid} at {display_local(now_utc)}")


def cmd_stop(db_path: Path) -> None:
    apply_migrations(db_path)
    with get_conn(db_path) as conn:
        active = get_active_session(conn)
        if active is None:
            raise RuntimeError("No active session to stop")

        end_utc = to_storage_utc(utc_now())
        conn.execute("UPDATE sessions SET end_time = ? WHERE id = ?", (end_utc, active["id"]))
        conn.commit()

        start_dt = from_storage_utc(active["start_time"])
        end_dt = from_storage_utc(end_utc)
        duration = end_dt - start_dt
        hours = duration.total_seconds() / 3600
        print(
            f"Stopped session id={active['id']} at {display_local(end_utc)} | duration={hours:.2f}h"
        )


def cmd_status(db_path: Path) -> None:
    apply_migrations(db_path)
    with get_conn(db_path) as conn:
        active = get_active_session(conn)
        if active is None:
            print("No active session")
            return

        start_dt = from_storage_utc(active["start_time"])
        hours = (utc_now() - start_dt).total_seconds() / 3600
        print(
            f"Active session id={active['id']} | start={display_local(active['start_time'])} | running={hours:.2f}h"
        )


def resolve_list_filter(args: argparse.Namespace) -> tuple[str, tuple]:
    if args.day:
        day_start = parse_user_datetime(f"{args.day} 00:00")
        day_end = parse_user_datetime(f"{args.day} 23:59")
        return (
            "start_time >= ? AND start_time <= ?",
            (to_storage_utc(day_start), to_storage_utc(day_end)),
        )

    if args.month:
        month_start = parse_user_datetime(f"{args.month}-01 00:00")
        if month_start.month == 12:
            next_month = month_start.replace(year=month_start.year + 1, month=1)
        else:
            next_month = month_start.replace(month=month_start.month + 1)
        return (
            "start_time >= ? AND start_time < ?",
            (to_storage_utc(month_start), to_storage_utc(next_month)),
        )

    if args.from_dt and args.to_dt:
        from_dt = parse_user_datetime(args.from_dt)
        to_dt = parse_user_datetime(args.to_dt)
        if to_dt < from_dt:
            raise ValueError("--to must be greater than or equal to --from")
        return (
            "start_time >= ? AND start_time <= ?",
            (to_storage_utc(from_dt), to_storage_utc(to_dt)),
        )

    return ("1=1", ())


def cmd_list(db_path: Path, args: argparse.Namespace) -> None:
    apply_migrations(db_path)
    where_sql, params = resolve_list_filter(args)

    with get_conn(db_path) as conn:
        query = (
            "SELECT id, start_time, end_time, note FROM sessions "
            f"WHERE {where_sql} ORDER BY start_time DESC LIMIT ?"
        )
        rows = conn.execute(query, (*params, args.limit)).fetchall()

    if not rows:
        print("No sessions found")
        return

    print(f"Found sessions: {len(rows)}")
    for row in rows:
        end_text = display_local(row["end_time"]) if row["end_time"] else "ACTIVE"
        duration_text = "-"
        if row["end_time"]:
            duration = from_storage_utc(row["end_time"]) - from_storage_utc(row["start_time"])
            duration_text = f"{duration.total_seconds() / 3600:.2f}h"

        print(
            f"id={row['id']} | {display_local(row['start_time'])} -> {end_text} | duration={duration_text} | note={row['note']}"
        )


def cmd_edit(db_path: Path, args: argparse.Namespace) -> None:
    if not args.start and not args.end and args.note is None:
        raise ValueError("Provide at least one field to edit: --start, --end, --note")

    apply_migrations(db_path)
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT id, start_time, end_time, note FROM sessions WHERE id = ?",
            (args.id,),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Session not found: id={args.id}")

        old_start = row["start_time"]
        old_end = row["end_time"]

        new_start = old_start
        new_end = old_end
        new_note = row["note"]

        if args.start:
            new_start = to_storage_utc(parse_user_datetime(args.start))
        if args.end:
            new_end = to_storage_utc(parse_user_datetime(args.end))
        if args.note is not None:
            new_note = args.note

        if new_end is not None:
            start_dt = from_storage_utc(new_start)
            end_dt = from_storage_utc(new_end)
            if end_dt < start_dt:
                raise ValueError("end_time cannot be earlier than start_time")

        if new_end is None:
            another_active = conn.execute(
                "SELECT id FROM sessions WHERE end_time IS NULL AND id != ? LIMIT 1",
                (args.id,),
            ).fetchone()
            if another_active is not None:
                raise ValueError(
                    f"Cannot make session active: another active session exists (id={another_active['id']})"
                )

        conn.execute(
            "UPDATE sessions SET start_time = ?, end_time = ?, note = ? WHERE id = ?",
            (new_start, new_end, new_note, args.id),
        )

        conn.execute(
            """
            INSERT INTO session_edits(
                session_id,
                old_start_time,
                old_end_time,
                new_start_time,
                new_end_time,
                reason
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                args.id,
                old_start,
                old_end,
                new_start,
                new_end,
                args.reason,
            ),
        )
        conn.commit()

    print(f"Session id={args.id} updated")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Console work time tracker")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH, help="Path to DB file")

    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="Start new work session")
    start.add_argument("--note", default="", help="Optional note")

    sub.add_parser("stop", help="Stop active work session")
    sub.add_parser("status", help="Show active session status")

    list_cmd = sub.add_parser("list", help="List sessions")
    list_cmd.add_argument("--day", help="Filter by day: YYYY-MM-DD")
    list_cmd.add_argument("--month", help="Filter by month: YYYY-MM")
    list_cmd.add_argument("--from", dest="from_dt", help="Filter range start: YYYY-MM-DD HH:MM")
    list_cmd.add_argument("--to", dest="to_dt", help="Filter range end: YYYY-MM-DD HH:MM")
    list_cmd.add_argument("--limit", type=int, default=20, help="Max rows")

    edit = sub.add_parser("edit", help="Edit session by id")
    edit.add_argument("--id", type=int, required=True, help="Session id")
    edit.add_argument("--start", help="New start datetime")
    edit.add_argument("--end", help="New end datetime")
    edit.add_argument("--note", help="New note")
    edit.add_argument("--reason", default="manual edit", help="Reason for audit log")

    return parser


def validate_args(args: argparse.Namespace) -> None:
    if args.command == "list":
        filters = [bool(args.day), bool(args.month), bool(args.from_dt or args.to_dt)]
        if sum(filters) > 1:
            raise ValueError("Use only one list filter: --day OR --month OR --from/--to")
        if bool(args.from_dt) != bool(args.to_dt):
            raise ValueError("Use both --from and --to together")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    validate_args(args)

    if args.command == "start":
        cmd_start(args.db_path, args.note)
    elif args.command == "stop":
        cmd_stop(args.db_path)
    elif args.command == "status":
        cmd_status(args.db_path)
    elif args.command == "list":
        cmd_list(args.db_path, args)
    elif args.command == "edit":
        cmd_edit(args.db_path, args)
    else:
        parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()

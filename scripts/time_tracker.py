#!/usr/bin/env python3
from __future__ import annotations

import argparse
import calendar
import csv
import json
import sqlite3
from datetime import UTC, datetime, timedelta
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


def local_date(value: str) -> str:
    return from_storage_utc(value).astimezone().strftime("%Y-%m-%d")


def format_hours(hours: float) -> str:
    return f"{hours:.2f}h"


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


def resolve_time_window(
    day: str | None,
    month: str | None,
    from_dt: str | None,
    to_dt: str | None,
) -> tuple[str, tuple]:
    if day:
        day_start = parse_user_datetime(f"{day} 00:00")
        day_end = parse_user_datetime(f"{day} 23:59")
        return (
            "start_time >= ? AND start_time <= ?",
            (to_storage_utc(day_start), to_storage_utc(day_end)),
        )

    if month:
        month_start = parse_user_datetime(f"{month}-01 00:00")
        if month_start.month == 12:
            next_month = month_start.replace(year=month_start.year + 1, month=1)
        else:
            next_month = month_start.replace(month=month_start.month + 1)
        return (
            "start_time >= ? AND start_time < ?",
            (to_storage_utc(month_start), to_storage_utc(next_month)),
        )

    if from_dt and to_dt:
        from_parsed = parse_user_datetime(from_dt)
        to_parsed = parse_user_datetime(to_dt)
        if to_parsed < from_parsed:
            raise ValueError("--to must be greater than or equal to --from")
        return (
            "start_time >= ? AND start_time <= ?",
            (to_storage_utc(from_parsed), to_storage_utc(to_parsed)),
        )

    return ("1=1", ())


def build_filter_clause(args: argparse.Namespace) -> tuple[str, tuple]:
    where_sql, params = resolve_time_window(args.day, args.month, args.from_dt, args.to_dt)
    if args.note_contains:
        where_sql = f"({where_sql}) AND note LIKE ?"
        params = (*params, f"%{args.note_contains}%")
    return where_sql, params


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


def cmd_list(db_path: Path, args: argparse.Namespace) -> None:
    apply_migrations(db_path)
    where_sql, params = build_filter_clause(args)

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
            duration_text = format_hours(duration.total_seconds() / 3600)

        print(
            f"id={row['id']} | {display_local(row['start_time'])} -> {end_text} | duration={duration_text} | note={row['note']}"
        )


def cmd_summary(db_path: Path, args: argparse.Namespace) -> None:
    apply_migrations(db_path)
    where_sql, params = build_filter_clause(args)

    with get_conn(db_path) as conn:
        rows = conn.execute(
            (
                "SELECT id, start_time, end_time, note FROM sessions "
                f"WHERE {where_sql} ORDER BY start_time"
            ),
            params,
        ).fetchall()

    if not rows:
        print("No sessions found")
        return

    closed_rows = [r for r in rows if r["end_time"] is not None]
    total_hours = sum(
        (
            from_storage_utc(r["end_time"]) - from_storage_utc(r["start_time"])
        ).total_seconds()
        / 3600
        for r in closed_rows
    )

    buckets: dict[str, float] = {}
    for row in closed_rows:
        start_dt = from_storage_utc(row["start_time"]).astimezone()
        end_dt = from_storage_utc(row["end_time"]).astimezone()
        hours = (end_dt - start_dt).total_seconds() / 3600

        if args.group_by == "day":
            bucket = start_dt.strftime("%Y-%m-%d")
        elif args.group_by == "week":
            year, week, _ = start_dt.isocalendar()
            bucket = f"{year}-W{week:02d}"
        else:
            bucket = start_dt.strftime("%Y-%m")

        buckets[bucket] = buckets.get(bucket, 0.0) + hours

    print(f"Total sessions: {len(rows)}")
    print(f"Closed sessions: {len(closed_rows)}")
    print(f"Active sessions: {len(rows) - len(closed_rows)}")
    print(f"Total hours: {format_hours(total_hours)}")
    print(f"Group by: {args.group_by}")

    for bucket, hours in sorted(buckets.items()):
        print(f"  {bucket}: {format_hours(hours)}")


def cmd_calendar(db_path: Path, args: argparse.Namespace) -> None:
    apply_migrations(db_path)
    month_start = parse_user_datetime(f"{args.month}-01 00:00")
    if month_start.month == 12:
        next_month = month_start.replace(year=month_start.year + 1, month=1)
    else:
        next_month = month_start.replace(month=month_start.month + 1)

    with get_conn(db_path) as conn:
        rows = conn.execute(
            (
                "SELECT start_time, end_time FROM sessions "
                "WHERE start_time >= ? AND start_time < ?"
            ),
            (to_storage_utc(month_start), to_storage_utc(next_month)),
        ).fetchall()

    by_day: dict[int, float] = {}
    for row in rows:
        local_start = from_storage_utc(row["start_time"]).astimezone()
        day = local_start.day
        if row["end_time"]:
            local_end = from_storage_utc(row["end_time"]).astimezone()
            hours = (local_end - local_start).total_seconds() / 3600
        else:
            hours = (datetime.now().astimezone() - local_start).total_seconds() / 3600
        by_day[day] = by_day.get(day, 0.0) + max(hours, 0.0)

    year = month_start.year
    month = month_start.month
    print(calendar.month(year, month))
    print("Hours by day:")
    if not by_day:
        print("  no data")
        return

    for day in sorted(by_day):
        print(f"  {year:04d}-{month:02d}-{day:02d}: {format_hours(by_day[day])}")


def cmd_export(db_path: Path, args: argparse.Namespace) -> None:
    apply_migrations(db_path)
    where_sql, params = build_filter_clause(args)

    with get_conn(db_path) as conn:
        rows = conn.execute(
            (
                "SELECT id, start_time, end_time, note, created_at, updated_at FROM sessions "
                f"WHERE {where_sql} ORDER BY start_time"
            ),
            params,
        ).fetchall()

    payload = []
    for row in rows:
        duration_hours = None
        if row["end_time"]:
            duration_hours = (
                from_storage_utc(row["end_time"]) - from_storage_utc(row["start_time"])
            ).total_seconds() / 3600

        payload.append(
            {
                "id": row["id"],
                "start_time_utc": row["start_time"],
                "end_time_utc": row["end_time"],
                "start_local_date": local_date(row["start_time"]),
                "duration_hours": duration_hours,
                "note": row["note"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.format == "json":
        args.output.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    else:
        with args.output.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "id",
                    "start_time_utc",
                    "end_time_utc",
                    "start_local_date",
                    "duration_hours",
                    "note",
                    "created_at",
                    "updated_at",
                ],
            )
            writer.writeheader()
            writer.writerows(payload)

    print(f"Exported {len(payload)} rows to {args.output}")


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
    list_cmd.add_argument("--note-contains", help="Filter sessions by note substring")
    list_cmd.add_argument("--limit", type=int, default=20, help="Max rows")

    summary = sub.add_parser("summary", help="Show aggregated report")
    summary.add_argument("--day", help="Filter by day: YYYY-MM-DD")
    summary.add_argument("--month", help="Filter by month: YYYY-MM")
    summary.add_argument("--from", dest="from_dt", help="Filter range start: YYYY-MM-DD HH:MM")
    summary.add_argument("--to", dest="to_dt", help="Filter range end: YYYY-MM-DD HH:MM")
    summary.add_argument("--note-contains", help="Filter sessions by note substring")
    summary.add_argument("--group-by", choices=["day", "week", "month"], default="day")

    calendar_cmd = sub.add_parser("calendar", help="Show monthly calendar with hour totals")
    calendar_cmd.add_argument("--month", required=True, help="Month in YYYY-MM format")

    export_cmd = sub.add_parser("export", help="Export sessions to CSV or JSON")
    export_cmd.add_argument("--day", help="Filter by day: YYYY-MM-DD")
    export_cmd.add_argument("--month", help="Filter by month: YYYY-MM")
    export_cmd.add_argument("--from", dest="from_dt", help="Filter range start: YYYY-MM-DD HH:MM")
    export_cmd.add_argument("--to", dest="to_dt", help="Filter range end: YYYY-MM-DD HH:MM")
    export_cmd.add_argument("--note-contains", help="Filter sessions by note substring")
    export_cmd.add_argument("--format", choices=["csv", "json"], required=True)
    export_cmd.add_argument("--output", type=Path, required=True)

    edit = sub.add_parser("edit", help="Edit session by id")
    edit.add_argument("--id", type=int, required=True, help="Session id")
    edit.add_argument("--start", help="New start datetime")
    edit.add_argument("--end", help="New end datetime")
    edit.add_argument("--note", help="New note")
    edit.add_argument("--reason", default="manual edit", help="Reason for audit log")

    return parser


def validate_args(args: argparse.Namespace) -> None:
    if args.command in {"list", "summary", "export"}:
        filters = [bool(args.day), bool(args.month), bool(args.from_dt or args.to_dt)]
        if sum(filters) > 1:
            raise ValueError("Use only one list filter: --day OR --month OR --from/--to")
        if bool(args.from_dt) != bool(args.to_dt):
            raise ValueError("Use both --from and --to together")

    if args.command == "calendar":
        try:
            parse_user_datetime(f"{args.month}-01 00:00")
        except ValueError as exc:
            raise ValueError("--month must be in YYYY-MM format") from exc


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
    elif args.command == "summary":
        cmd_summary(args.db_path, args)
    elif args.command == "calendar":
        cmd_calendar(args.db_path, args)
    elif args.command == "export":
        cmd_export(args.db_path, args)
    elif args.command == "edit":
        cmd_edit(args.db_path, args)
    else:
        parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()

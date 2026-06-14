from __future__ import annotations

import csv
import json
import random
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "time_tracker.py"


class TimeTrackerCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.db_path = Path(self.tmpdir.name) / "test_calendar.db"

    def run_cli(self, *args: str, expect_ok: bool = True) -> subprocess.CompletedProcess[str]:
        cmd = [sys.executable, str(SCRIPT), "--db-path", str(self.db_path), *args]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if expect_ok and proc.returncode != 0:
            self.fail(f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
        if not expect_ok and proc.returncode == 0:
            self.fail(f"Command unexpectedly succeeded: {' '.join(cmd)}\nSTDOUT:\n{proc.stdout}")
        return proc

    def get_rows(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(sql, params).fetchall()

    def test_start_stop_and_list(self) -> None:
        self.run_cli("start", "--note", "focus")
        self.run_cli("stop")
        out = self.run_cli("list", "--limit", "5").stdout

        self.assertIn("Found sessions: 1", out)
        self.assertIn("note=focus", out)

    def test_cannot_start_second_active_session(self) -> None:
        self.run_cli("start", "--note", "first")
        proc = self.run_cli("start", "--note", "second", expect_ok=False)

        self.assertIn("Active session already exists", proc.stderr)

    def test_stop_without_active_session_fails(self) -> None:
        proc = self.run_cli("stop", expect_ok=False)
        self.assertIn("No active session to stop", proc.stderr)

    def test_edit_invalid_interval_fails(self) -> None:
        self.run_cli("start", "--note", "bad edit")
        self.run_cli("stop")

        proc = self.run_cli(
            "edit",
            "--id",
            "1",
            "--start",
            "2026-06-14 18:00",
            "--end",
            "2026-06-14 09:00",
            expect_ok=False,
        )

        self.assertIn("end_time cannot be earlier than start_time", proc.stderr)

    def test_edit_writes_audit_log(self) -> None:
        self.run_cli("start", "--note", "audit")
        self.run_cli("stop")
        self.run_cli(
            "edit",
            "--id",
            "1",
            "--start",
            "2026-06-14 09:00",
            "--end",
            "2026-06-14 18:00",
            "--reason",
            "test audit",
        )

        rows = self.get_rows("SELECT session_id, reason FROM session_edits")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["session_id"], 1)
        self.assertEqual(rows[0]["reason"], "test audit")

    def test_timezone_offset_is_normalized_to_utc(self) -> None:
        self.run_cli("start", "--note", "tz")
        self.run_cli("stop")
        self.run_cli(
            "edit",
            "--id",
            "1",
            "--start",
            "2026-03-30 09:00+0300",
            "--end",
            "2026-03-30 18:00+0300",
            "--reason",
            "tz test",
        )

        row = self.get_rows("SELECT start_time, end_time FROM sessions WHERE id = 1")[0]
        self.assertEqual(row["start_time"], "2026-03-30T06:00:00Z")
        self.assertEqual(row["end_time"], "2026-03-30T15:00:00Z")

    def test_summary_and_note_filter(self) -> None:
        self.run_cli("start", "--note", "alpha")
        self.run_cli("stop")
        self.run_cli(
            "edit",
            "--id",
            "1",
            "--start",
            "2026-06-01 09:00",
            "--end",
            "2026-06-01 12:00",
            "--reason",
            "seed",
        )

        self.run_cli("start", "--note", "beta bugfix")
        self.run_cli("stop")
        self.run_cli(
            "edit",
            "--id",
            "2",
            "--start",
            "2026-06-03 10:00",
            "--end",
            "2026-06-03 16:30",
            "--reason",
            "seed",
        )

        out = self.run_cli(
            "summary",
            "--month",
            "2026-06",
            "--note-contains",
            "bugfix",
            "--group-by",
            "week",
        ).stdout

        self.assertIn("Total sessions: 1", out)
        self.assertIn("Total hours: 6.50h", out)

    def test_calendar_and_export(self) -> None:
        self.run_cli("start", "--note", "export")
        self.run_cli("stop")
        self.run_cli(
            "edit",
            "--id",
            "1",
            "--start",
            "2026-06-05 08:00",
            "--end",
            "2026-06-05 17:00",
            "--reason",
            "seed",
        )

        calendar_out = self.run_cli("calendar", "--month", "2026-06").stdout
        self.assertIn("Hours by day:", calendar_out)
        self.assertIn("2026-06-05", calendar_out)

        json_path = Path(self.tmpdir.name) / "export.json"
        csv_path = Path(self.tmpdir.name) / "export.csv"

        self.run_cli(
            "export",
            "--month",
            "2026-06",
            "--format",
            "json",
            "--output",
            str(json_path),
        )
        self.run_cli(
            "export",
            "--month",
            "2026-06",
            "--format",
            "csv",
            "--output",
            str(csv_path),
        )

        data = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["note"], "export")

        with csv_path.open("r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["note"], "export")

    def test_list_invalid_day_rejected(self) -> None:
        proc = self.run_cli("list", "--day", "2026-02-30", expect_ok=False)
        self.assertIn("Unsupported datetime format", proc.stderr)

    def test_calendar_invalid_month_rejected(self) -> None:
        proc = self.run_cli("calendar", "--month", "2026-13", expect_ok=False)
        self.assertIn("--month must be in YYYY-MM format", proc.stderr)

    def test_list_limit_out_of_range_rejected(self) -> None:
        proc = self.run_cli("list", "--limit", "0", expect_ok=False)
        self.assertIn("--limit must be a positive integer", proc.stderr)

    def test_conflicting_filters_rejected(self) -> None:
        proc = self.run_cli("summary", "--day", "2026-06-14", "--month", "2026-06", expect_ok=False)
        self.assertIn("Use only one list filter", proc.stderr)

    def test_range_requires_both_from_and_to(self) -> None:
        proc = self.run_cli("summary", "--from", "2026-06-01 00:00", expect_ok=False)
        self.assertIn("Use both --from and --to together", proc.stderr)

    def test_edit_rejects_invalid_time_format(self) -> None:
        self.run_cli("start", "--note", "invalid time")
        self.run_cli("stop")

        proc = self.run_cli(
            "edit",
            "--id",
            "1",
            "--start",
            "2026-06-14 99:99",
            expect_ok=False,
        )
        self.assertIn("Unsupported datetime format", proc.stderr)

    def test_summary_rejects_invalid_range_datetime(self) -> None:
        proc = self.run_cli(
            "summary",
            "--from",
            "2026-06-01 99:99",
            "--to",
            "2026-06-30 23:59",
            expect_ok=False,
        )
        self.assertIn("Unsupported datetime format", proc.stderr)

    def test_edit_nonexistent_large_id_fails(self) -> None:
        proc = self.run_cli(
            "edit",
            "--id",
            "999999999999",
            "--note",
            "x",
            expect_ok=False,
        )
        self.assertIn("Session not found", proc.stderr)

    def test_property_like_invalid_datetime_inputs_rejected(self) -> None:
        self.run_cli("start", "--note", "prop")
        self.run_cli("stop")

        impossible_times = ["24:00", "25:61", "99:99", "12:60", "-01:00", "ab:cd"]
        impossible_dates = [
            "2026-02-30",
            "2026-13-01",
            "2026-00-10",
            "2026-11-00",
            "2026-04-31",
            "abcd-ef-gh",
        ]
        separators = [" ", "T"]

        rng = random.Random(20260614)
        candidates: list[str] = []
        for _ in range(15):
            date_part = rng.choice(impossible_dates)
            time_part = rng.choice(impossible_times)
            sep = rng.choice(separators)
            candidates.append(f"{date_part}{sep}{time_part}")

        for bad_dt in candidates:
            edit_proc = self.run_cli("edit", "--id", "1", "--start", bad_dt, expect_ok=False)
            self.assertIn("Unsupported datetime format", edit_proc.stderr)

            summary_proc = self.run_cli(
                "summary",
                "--from",
                bad_dt,
                "--to",
                "2026-06-30 23:59",
                expect_ok=False,
            )
            self.assertIn("Unsupported datetime format", summary_proc.stderr)

    def test_property_like_invalid_cli_filter_combinations_rejected(self) -> None:
        rng = random.Random(20260615)

        conflict_cases: list[list[str]] = [
            ["summary", "--day", "2026-06-14", "--month", "2026-06"],
            ["export", "--day", "2026-06-14", "--from", "2026-06-01 00:00", "--to", "2026-06-30 23:59", "--format", "json", "--output", str(Path(self.tmpdir.name) / "x1.json")],
            ["list", "--month", "2026-06", "--from", "2026-06-01 00:00", "--to", "2026-06-30 23:59"],
        ]

        missing_range_cases: list[list[str]] = [
            ["summary", "--from", "2026-06-01 00:00"],
            ["summary", "--to", "2026-06-30 23:59"],
            ["export", "--from", "2026-06-01 00:00", "--format", "csv", "--output", str(Path(self.tmpdir.name) / "x2.csv")],
            ["export", "--to", "2026-06-30 23:59", "--format", "json", "--output", str(Path(self.tmpdir.name) / "x3.json")],
        ]

        bad_limit_cases: list[list[str]] = [
            ["list", "--limit", "0"],
            ["list", "--limit", "-1"],
            ["list", "--day", "2026-06-14", "--limit", "-999"],
        ]

        all_cases = conflict_cases + missing_range_cases + bad_limit_cases
        rng.shuffle(all_cases)

        for case in all_cases:
            proc = self.run_cli(*case, expect_ok=False)
            err = proc.stderr
            self.assertTrue(
                (
                    "Use only one list filter" in err
                    or "Use both --from and --to together" in err
                    or "--limit must be a positive integer" in err
                ),
                msg=f"Unexpected error for case {case}: {err}",
            )

    def test_note_with_quotes_and_symbols_is_saved_and_listed(self) -> None:
        note = "fix 'quote' \"double\" %_ [] {} ; --"
        self.run_cli("start", "--note", note)
        self.run_cli("stop")

        out = self.run_cli("list", "--limit", "5").stdout
        self.assertIn("Found sessions: 1", out)
        self.assertIn("note=fix 'quote' \"double\" %_ [] {} ; --", out)

    def test_very_long_note_is_persisted(self) -> None:
        long_note = "n" * 5000
        self.run_cli("start", "--note", long_note)
        self.run_cli("stop")

        row = self.get_rows("SELECT note FROM sessions WHERE id = 1")[0]
        self.assertEqual(len(row["note"]), 5000)
        self.assertEqual(row["note"], long_note)

    def test_multiline_note_roundtrip_via_edit_and_export_json(self) -> None:
        self.run_cli("start", "--note", "seed")
        self.run_cli("stop")

        multiline_note = "line1\\nline2\\tindent"
        self.run_cli("edit", "--id", "1", "--note", multiline_note, "--reason", "note test")

        json_path = Path(self.tmpdir.name) / "notes_export.json"
        self.run_cli(
            "export",
            "--format",
            "json",
            "--output",
            str(json_path),
        )

        data = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["note"], multiline_note)

    def test_note_contains_filter_handles_sql_like_characters(self) -> None:
        self.run_cli("start", "--note", "100% done")
        self.run_cli("stop")
        self.run_cli("start", "--note", "plain note")
        self.run_cli("stop")

        out = self.run_cli("summary", "--note-contains", "%", "--group-by", "day").stdout
        self.assertIn("Total sessions: 2", out)


if __name__ == "__main__":
    unittest.main()

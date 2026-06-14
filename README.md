# Calendar Work Tracker

Консольное приложение для учета рабочего времени с долгим хранением истории и будущим переходом в Android.

Статус проекта:
- Фаза 1 выполнена
- Фаза 2 выполнена
- Фаза 3 выполнена
- Фаза 4 выполнена
- Фаза 5 выполнена

Документы:
- План фаз: docs/ROADMAP.md
- Первая фаза: docs/PHASE_1_FOUNDATION.md
- Вторая фаза: docs/PHASE_2_STORAGE.md
- Третья фаза: docs/PHASE_3_CLI_MVP.md
- Четвертая фаза: docs/PHASE_4_CALENDAR_REPORTS.md
- Пятая фаза: docs/PHASE_5_RELIABILITY.md
- Черновая схема БД: db/schema.sql

Управление БД:
- Инициализация: python3 scripts/manage_db.py init
- Миграции: python3 scripts/manage_db.py migrate
- Статус: python3 scripts/manage_db.py status
- Бэкап: python3 scripts/manage_db.py backup
- Восстановление: python3 scripts/manage_db.py restore --backup-file backups/<file>.db
- Проверка целостности: python3 scripts/manage_db.py integrity-check

Проверка производительности:
- python3 scripts/benchmark_storage.py --rows 100000 --years 15

CLI трекер времени:
- Старт: python3 scripts/time_tracker.py start --note "coding"
- Статус: python3 scripts/time_tracker.py status
- Стоп: python3 scripts/time_tracker.py stop
- Список: python3 scripts/time_tracker.py list --day 2026-06-14
- Редактирование: python3 scripts/time_tracker.py edit --id 1 --start "2026-06-14 09:00" --end "2026-06-14 18:00"
- Календарь: python3 scripts/time_tracker.py calendar --month 2026-06
- Summary: python3 scripts/time_tracker.py summary --month 2026-06 --group-by day
- Экспорт: python3 scripts/time_tracker.py export --month 2026-06 --format csv --output exports/june.csv

Тесты:
- Все тесты: python3 -m unittest discover -s tests -p "test_*.py" -v
- Один файл: python3 -m unittest tests/test_time_tracker_cli.py -v

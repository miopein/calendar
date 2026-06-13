# Calendar Work Tracker

Консольное приложение для учета рабочего времени с долгим хранением истории и будущим переходом в Android.

Статус проекта:
- Фаза 1 начата
- Фаза 2 выполнена

Документы:
- План фаз: docs/ROADMAP.md
- Первая фаза: docs/PHASE_1_FOUNDATION.md
- Вторая фаза: docs/PHASE_2_STORAGE.md
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

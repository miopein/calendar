# Фаза 3: CLI MVP

Статус: Done

## Что реализовано

1. Добавлен консольный трекер: scripts/time_tracker.py.
2. Реализованы команды:
   - start
   - stop
   - status
   - list
   - edit
3. Встроены проверки:
   - нельзя стартовать вторую активную сессию
   - нельзя завершить несуществующую активную сессию
   - нельзя сохранить end раньше start
   - нельзя сделать вторую активную сессию через edit
4. Добавлен аудит изменений через таблицу session_edits при команде edit.

## Примеры команд

1. Старт сессии:
   - python3 scripts/time_tracker.py start --note "coding"
2. Статус:
   - python3 scripts/time_tracker.py status
3. Стоп:
   - python3 scripts/time_tracker.py stop
4. Список за день:
   - python3 scripts/time_tracker.py list --day 2026-06-14
5. Список за месяц:
   - python3 scripts/time_tracker.py list --month 2026-06
6. Список по диапазону:
   - python3 scripts/time_tracker.py list --from "2026-06-01 00:00" --to "2026-06-30 23:59"
7. Редактирование:
   - python3 scripts/time_tracker.py edit --id 1 --start "2026-06-14 09:00" --end "2026-06-14 18:00" --reason "fixed typo"

## Критерии завершения

1. Основные команды работают на реальной БД.
2. Ошибки пользователя обрабатываются понятными сообщениями.
3. Изменения записей сохраняются в session_edits.

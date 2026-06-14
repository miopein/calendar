# Фаза 4: Календарь и отчеты

Статус: Done

## Что реализовано

1. Команда calendar:
   - помесячный календарный вывод
   - суммарные часы по дням месяца
2. Команда summary:
   - агрегаты по сессиям и часам
   - группировка day/week/month
   - фильтр по дню, месяцу, диапазону, подстроке заметки
3. Команда export:
   - экспорт в CSV и JSON
   - те же фильтры, что в summary/list
4. Расширена команда list:
   - добавлен фильтр по подстроке заметки

## Новые команды

1. Календарь:
   - python3 scripts/time_tracker.py calendar --month 2026-06
2. Summary за месяц:
   - python3 scripts/time_tracker.py summary --month 2026-06 --group-by day
3. Summary за диапазон:
   - python3 scripts/time_tracker.py summary --from "2026-06-01 00:00" --to "2026-06-30 23:59" --group-by week
4. Экспорт в JSON:
   - python3 scripts/time_tracker.py export --month 2026-06 --format json --output exports/june.json
5. Экспорт в CSV:
   - python3 scripts/time_tracker.py export --month 2026-06 --format csv --output exports/june.csv

## Критерии завершения

1. Календарный просмотр доступен из CLI.
2. Можно получить summary по диапазону дат.
3. Экспорт CSV/JSON работает и пишет файл.

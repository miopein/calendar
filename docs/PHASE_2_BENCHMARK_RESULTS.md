# Результаты бенчмарка хранилища (Фаза 2)

Дата прогона: 2026-06-13

Команда:
python3 scripts/benchmark_storage.py --rows 100000 --years 15

Результаты:
1. Inserted rows: 100000
2. Insert time: 1.520s
3. range_filter_10y: avg=1.36ms, best=1.13ms
4. monthly_summary: avg=63.30ms, best=60.44ms
5. active_lookup: avg=0.01ms, best=0.00ms
6. integrity_check: ok

Вывод:
- Индексы работают корректно для диапазонных запросов и поиска активной сессии.
- Агрегации по месяцам на 100k записей выполняются быстро для CLI-сценария.
- Целостность БД подтверждена после массовой загрузки.

"""Точка входа. Запуск этапов пайплайна поиска трендов.

    python main.py              - все этапы по порядку
    python main.py collect      - только сбор постов и картинок
    python main.py analyze      - только поиск выбросов и разбор моделью
    python main.py report       - только отчет
    python main.py analyze report   - несколько этапов подряд
"""
import argparse
import sys
import time

from src import analyze, collect, report

STAGES = {
    "collect": ("Сбор постов и картинок", collect.run),
    "analyze": ("Поиск выбросов и разбор картинок", analyze.run),
    "report": ("Расчет трендов и отчет", report.run),
}


def main():
    parser = argparse.ArgumentParser(description="T-shirt trends: Instagram -> тренды принтов")
    parser.add_argument(
        "stages", nargs="*", choices=list(STAGES), metavar="stage",
        help="этапы: collect, analyze, report (по умолчанию все)",
    )
    args = parser.parse_args()
    stages = args.stages or list(STAGES)

    for i, name in enumerate(stages, 1):
        title, func = STAGES[name]
        print(f"\n=== [{i}/{len(stages)}] {title} ===")
        start = time.time()
        try:
            func()
        except KeyboardInterrupt:
            print("\nОстановлено пользователем.")
            sys.exit(1)
        print(f"--- {name}: готово за {time.time() - start:.0f} с")


if __name__ == "__main__":
    main()

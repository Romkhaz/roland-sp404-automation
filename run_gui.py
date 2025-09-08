#!/usr/bin/env python3
"""
Быстрый запуск GUI приложения Roland SP-404 MKII Automation
"""

import sys
import subprocess
from pathlib import Path

def check_dependencies():
    """Проверка зависимостей"""
    try:
        import soundfile
        import scipy
        import numpy
        import tkinter
        return True
    except ImportError as e:
        print(f"Ошибка: Не установлены необходимые зависимости: {e}")
        print("Установите зависимости: pip install soundfile scipy")
        return False

def main():
    """Основная функция"""
    print("Roland SP-404 MKII GUI Automation")
    print("=" * 40)
    
    # Проверяем зависимости
    if not check_dependencies():
        return 1
    
    # Запускаем GUI
    try:
        script_path = Path(__file__).parent / "roland_sp404_gui.py"
        subprocess.run([sys.executable, str(script_path)])
        return 0
    except Exception as e:
        print(f"Ошибка запуска GUI: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

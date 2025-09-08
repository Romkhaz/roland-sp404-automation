#!/usr/bin/env python3
"""
Скрипт для сборки standalone приложения Roland SP-404 MKII Automation
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def run_command(cmd, description):
    """Выполняет команду и выводит результат"""
    print(f"\n🔄 {description}...")
    print(f"Команда: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"✅ {description} завершено успешно")
        if result.stdout:
            print("Вывод:", result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при {description.lower()}")
        print("Код ошибки:", e.returncode)
        if e.stdout:
            print("Вывод:", e.stdout)
        if e.stderr:
            print("Ошибка:", e.stderr)
        return False

def main():
    """Основная функция сборки"""
    print("🚀 Сборка Roland SP-404 MKII Automation App")
    print("=" * 50)
    
    # Проверяем наличие PyInstaller
    try:
        import PyInstaller
        print(f"✅ PyInstaller найден: версия {PyInstaller.__version__}")
    except ImportError:
        print("❌ PyInstaller не найден. Установите: pip install pyinstaller")
        return 1
    
    # Проверяем наличие spec файла
    spec_file = Path("roland_sp404.spec")
    if not spec_file.exists():
        print("❌ Файл roland_sp404.spec не найден")
        return 1
    
    # Очищаем предыдущие сборки
    print("\n🧹 Очистка предыдущих сборок...")
    dirs_to_clean = ["build", "dist", "__pycache__"]
    for dir_name in dirs_to_clean:
        if Path(dir_name).exists():
            shutil.rmtree(dir_name)
            print(f"Удалена папка: {dir_name}")
    
    # Собираем приложение
    if not run_command([
        "python3", "-m", "PyInstaller", 
        "--clean", 
        "roland_sp404.spec"
    ], "Сборка приложения"):
        return 1
    
    # Проверяем результат
    app_path = Path("dist/Roland SP-404 MKII Automation.app")
    if app_path.exists():
        print(f"\n🎉 Приложение успешно собрано!")
        print(f"📁 Путь: {app_path.absolute()}")
        print(f"📊 Размер: {get_folder_size(app_path)}")
        
        # Создаем архив для распространения
        print("\n📦 Создание архива для распространения...")
        archive_name = "Roland_SP404_Automation_macOS.zip"
        if run_command([
            "zip", "-r", archive_name, 
            str(app_path)
        ], "Создание архива"):
            print(f"✅ Архив создан: {archive_name}")
            print(f"📊 Размер архива: {get_file_size(archive_name)}")
        
        print("\n🎯 Готово! Приложение можно:")
        print("1. Запустить двойным кликом")
        print("2. Перетащить в папку Applications")
        print("3. Распространить через архив")
        
        return 0
    else:
        print("❌ Приложение не было создано")
        return 1

def get_folder_size(folder_path):
    """Возвращает размер папки в удобном формате"""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(folder_path):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            if os.path.exists(filepath):
                total_size += os.path.getsize(filepath)
    
    return format_size(total_size)

def get_file_size(file_path):
    """Возвращает размер файла в удобном формате"""
    if os.path.exists(file_path):
        return format_size(os.path.getsize(file_path))
    return "0 B"

def format_size(size_bytes):
    """Форматирует размер в байтах в удобный формат"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"

if __name__ == "__main__":
    sys.exit(main())

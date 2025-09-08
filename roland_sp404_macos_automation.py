#!/usr/bin/env python3
"""
Roland SP-404 MKII macOS File Automation Script

Версия скрипта, оптимизированная для macOS, которая использует
встроенные возможности системы для работы с сетевыми папками.

Этот скрипт автоматизирует процесс подготовки файлов для Roland SP-404 MKII:
1. Создает структуру папок на SD карте в папке IMPORT
2. Нормализует названия папок и файлов (только латиница, цифры, подчеркивания)
3. Конвертирует WAV файлы в нужный формат (16-bit/24-bit, 44.1/48 kHz)
4. Копирует только WAV файлы в новую структуру

Требования:
- macOS
- Python 3.7+
- soundfile, scipy, numpy (для конвертации аудио)
"""

import os
import re
import shutil
import logging
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional
import unicodedata

try:
    import soundfile as sf
    import numpy as np
    from scipy import signal
except ImportError:
    print("Ошибка: Не установлены soundfile и scipy. Установите: pip install soundfile scipy")
    exit(1)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('roland_macos_automation.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class RolandSP404MacOSAutomation:
    def __init__(self):
        """
        Инициализация класса для автоматизации Roland SP-404 MKII
        """
        # Поддерживаемые форматы для SP-404 MKII
        self.supported_sample_rates = [44100, 48000]
        self.supported_bit_depths = [16, 24]
        
    def normalize_name(self, name: str, counter: int = 0) -> str:
        """
        Нормализует название файла или папки для SP-404 MKII
        
        Args:
            name: Исходное название
            counter: Счетчик для уникальности имен
            
        Returns:
            Нормализованное название (только латиница, цифры, подчеркивания)
        """
        # Удаляем расширение для обработки
        name_without_ext = Path(name).stem
        extension = Path(name).suffix.lower()
        
        # Нормализуем Unicode символы
        normalized = unicodedata.normalize('NFKD', name_without_ext)
        
        # Заменяем пробелы на подчеркивания
        normalized = normalized.replace(' ', '_')
        
        # Удаляем все символы кроме латиницы, цифр и подчеркиваний
        normalized = re.sub(r'[^a-zA-Z0-9_]', '', normalized)
        
        # Удаляем множественные подчеркивания
        normalized = re.sub(r'_+', '_', normalized)
        
        # Удаляем подчеркивания в начале и конце
        normalized = normalized.strip('_')
        
        # Если название стало пустым, используем дефолтное с номером
        if not normalized:
            normalized = f"unnamed_{counter:03d}"
        elif counter > 0:
            # Добавляем номер для уникальности
            normalized = f"{normalized}_{counter:03d}"
            
        return normalized + extension
    
    def convert_audio_file(self, input_path: str, output_path: str) -> bool:
        """
        Конвертирует аудиофайл в формат, поддерживаемый SP-404 MKII
        
        Args:
            input_path: Путь к исходному файлу
            output_path: Путь для сохранения конвертированного файла
            
        Returns:
            True если конвертация успешна, False иначе
        """
        try:
            # Загружаем аудиофайл
            data, sample_rate = sf.read(input_path)
            
            # Проверяем текущие параметры
            current_channels = 1 if data.ndim == 1 else data.shape[1]
            current_sample_rate = sample_rate
            
            logger.info(f"Исходный файл: {current_sample_rate}Hz, {current_channels}ch")
            
            # Выбираем ближайшую поддерживаемую частоту дискретизации
            target_sample_rate = min(self.supported_sample_rates, 
                                   key=lambda x: abs(x - current_sample_rate))
            
            # Конвертируем частоту дискретизации если нужно
            if current_sample_rate != target_sample_rate:
                # Используем scipy для ресэмплинга
                num_samples = int(len(data) * target_sample_rate / current_sample_rate)
                if data.ndim == 1:
                    data = signal.resample(data, num_samples)
                else:
                    data = signal.resample(data, num_samples, axis=0)
                logger.info(f"Изменена частота дискретизации: {current_sample_rate} -> {target_sample_rate}")
            
            # Сохраняем стерео, если исходный файл стерео (SP-404 MKII поддерживает стерео)
            if current_channels > 1:
                logger.info(f"Сохраняем стерео ({current_channels} каналов)")
            
            # Нормализуем данные для 16-bit
            if np.max(np.abs(data)) > 0:
                data = data / np.max(np.abs(data)) * 0.95  # Оставляем небольшой запас
            
            # Конвертируем в 16-bit
            data_16bit = (data * 32767).astype(np.int16)
            
            # Сохраняем как WAV файл
            sf.write(output_path, data_16bit, target_sample_rate, subtype='PCM_16')
            logger.info(f"Файл конвертирован: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка конвертации файла {input_path}: {e}")
            return False
    
    def mount_smb_share(self, server: str, share: str, username: str = "", password: str = "") -> Optional[str]:
        """
        Подключает SMB шару через встроенные возможности macOS
        
        Args:
            server: IP адрес сервера
            share: Имя шары
            username: Имя пользователя
            password: Пароль
            
        Returns:
            Путь к подключенной папке или None при ошибке
        """
        try:
            # Формируем URL для подключения
            if username and password:
                smb_url = f"smb://{username}:{password}@{server}/{share}"
            elif username:
                smb_url = f"smb://{username}@{server}/{share}"
            else:
                smb_url = f"smb://{server}/{share}"
            
            logger.info(f"Подключаемся к SMB шаре: {smb_url}")
            
            # Используем osascript для подключения через AppleScript
            script = f'''
            tell application "Finder"
                try
                    mount volume "{smb_url}"
                    return "success"
                on error errMsg
                    return "error: " & errMsg
                end try
            end tell
            '''
            
            result = subprocess.run(['osascript', '-e', script], 
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0 and "success" in result.stdout:
                # Ищем подключенную папку в /Volumes
                mount_path = f"/Volumes/{share}"
                if Path(mount_path).exists():
                    logger.info(f"SMB шара успешно подключена: {mount_path}")
                    return mount_path
                else:
                    logger.error(f"Папка не найдена после подключения: {mount_path}")
                    return None
            else:
                logger.error(f"Ошибка подключения SMB: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error("Таймаут при подключении к SMB шаре")
            return None
        except Exception as e:
            logger.error(f"Ошибка подключения к SMB шаре: {e}")
            return None
    
    def unmount_smb_share(self, mount_path: str):
        """
        Отключает SMB шару
        
        Args:
            mount_path: Путь к подключенной папке
        """
        try:
            subprocess.run(['umount', mount_path], check=True)
            logger.info(f"SMB шара отключена: {mount_path}")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Не удалось отключить SMB шару {mount_path}: {e}")
        except Exception as e:
            logger.warning(f"Ошибка при отключении SMB шары: {e}")
    
    def process_directory(self, source_path: Path, target_path: Path):
        """
        Обрабатывает директорию рекурсивно
        
        Args:
            source_path: Путь к исходной папке
            target_path: Путь к целевой папке на SD карте
        """
        logger.info(f"Обрабатываем директорию: {source_path}")
        
        # Создаем целевую папку если не существует
        target_path.mkdir(parents=True, exist_ok=True)
        
        try:
            # Получаем список элементов в папке
            items = list(source_path.iterdir())
            
            # Счетчик для уникальности имен файлов
            file_counter = 0
            
            for item in items:
                if item.is_file():
                    # Обрабатываем файл
                    if item.suffix.lower() == '.wav':
                        logger.info(f"Обрабатываем WAV файл: {item.name}")
                        
                        # Создаем нормализованное имя файла с уникальным номером
                        normalized_name = self.normalize_name(item.name, file_counter)
                        output_file = target_path / normalized_name
                        
                        # Конвертируем файл
                        if self.convert_audio_file(str(item), str(output_file)):
                            logger.info(f"Успешно обработан: {item.name} -> {normalized_name}")
                            file_counter += 1
                        else:
                            logger.error(f"Ошибка конвертации: {item.name}")
                    else:
                        logger.info(f"Пропускаем не-WAV файл: {item.name}")
                        
                elif item.is_dir():
                    # Обрабатываем папку
                    logger.info(f"Обрабатываем папку: {item.name}")
                    
                    # Создаем нормализованную папку
                    normalized_folder_name = self.normalize_name(item.name)
                    normalized_folder = target_path / normalized_folder_name
                    
                    # Рекурсивно обрабатываем содержимое папки
                    self.process_directory(item, normalized_folder)
                    
        except PermissionError as e:
            logger.error(f"Ошибка доступа к папке {source_path}: {e}")
        except Exception as e:
            logger.error(f"Ошибка обработки папки {source_path}: {e}")
    
    def run_automation_with_smb(self, server: str, share: str, source_path: str, 
                               sd_card_path: str, username: str = "", password: str = ""):
        """
        Запускает автоматизацию с подключением к SMB шаре
        
        Args:
            server: IP адрес SMB сервера
            share: Имя SMB шары
            source_path: Путь к исходной папке на SMB сервере
            sd_card_path: Путь к SD карте SP-404 MKII
            username: Имя пользователя SMB
            password: Пароль SMB
        """
        logger.info("Запуск автоматизации Roland SP-404 MKII (macOS версия с SMB)")
        
        mount_path = None
        try:
            # Подключаемся к SMB шаре
            mount_path = self.mount_smb_share(server, share, username, password)
            if not mount_path:
                logger.error("Не удалось подключиться к SMB шаре")
                return False
            
            # Формируем полный путь к исходной папке
            full_source_path = Path(mount_path) / source_path
            if not full_source_path.exists():
                logger.error(f"Исходная папка не найдена: {full_source_path}")
                return False
            
            # Создаем целевую папку
            target = Path(sd_card_path)
            target.mkdir(parents=True, exist_ok=True)
            
            # Обрабатываем исходную папку
            self.process_directory(full_source_path, target)
            
            logger.info("Автоматизация завершена успешно!")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка во время автоматизации: {e}")
            return False
        finally:
            # Отключаем SMB шару
            if mount_path:
                self.unmount_smb_share(mount_path)
    
    def run_automation_local(self, source_path: str, sd_card_path: str):
        """
        Запускает автоматизацию с локальными папками
        
        Args:
            source_path: Путь к исходной папке
            sd_card_path: Путь к SD карте SP-404 MKII
        """
        logger.info("Запуск автоматизации Roland SP-404 MKII (локальная версия)")
        
        try:
            # Проверяем существование исходной папки
            source = Path(source_path)
            if not source.exists():
                logger.error(f"Исходная папка не существует: {source_path}")
                return False
            
            if not source.is_dir():
                logger.error(f"Указанный путь не является папкой: {source_path}")
                return False
            
            # Создаем целевую папку
            target = Path(sd_card_path)
            target.mkdir(parents=True, exist_ok=True)
            
            # Обрабатываем исходную папку
            self.process_directory(source, target)
            
            logger.info("Автоматизация завершена успешно!")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка во время автоматизации: {e}")
            return False


def main():
    """Основная функция"""
    print("Roland SP-404 MKII macOS File Automation")
    print("=" * 45)
    print()
    print("Выберите режим работы:")
    print("1. Подключение к SMB шаре (автоматическое)")
    print("2. Работа с локальными папками")
    print("3. Работа с уже подключенной сетевой папкой")
    print()
    
    choice = input("Введите номер режима (1-3): ").strip()
    
    automation = RolandSP404MacOSAutomation()
    success = False
    
    if choice == "1":
        # Режим с автоматическим подключением к SMB
        print("\n=== Режим SMB подключения ===")
        server = input("IP адрес SMB сервера [192.168.2.81]: ").strip() or "192.168.2.81"
        share = input("Имя SMB шары [4Music]: ").strip() or "4Music"
        username = input("Имя пользователя (или Enter для гостевого доступа): ").strip()
        password = input("Пароль (или Enter если не нужен): ").strip()
        source_path = input("Путь к исходной папке на сервере [Music_Projects/Roland/]: ").strip() or "Music_Projects/Roland/"
        sd_card_path = input("Путь к папке IMPORT на SD карте SP-404 MKII: ").strip()
        
        if not sd_card_path:
            print("Ошибка: Не указан путь к SD карте")
            return
        
        success = automation.run_automation_with_smb(
            server, share, source_path, sd_card_path, username, password
        )
        
    elif choice == "2":
        # Режим с локальными папками
        print("\n=== Режим локальных папок ===")
        source_path = input("Путь к исходной папке с семплами: ").strip()
        sd_card_path = input("Путь к папке IMPORT на SD карте SP-404 MKII: ").strip()
        
        if not source_path or not sd_card_path:
            print("Ошибка: Не указаны необходимые пути")
            return
        
        success = automation.run_automation_local(source_path, sd_card_path)
        
    elif choice == "3":
        # Режим с уже подключенной сетевой папкой
        print("\n=== Режим подключенной сетевой папки ===")
        print("Убедитесь, что сетевая папка уже подключена через Finder")
        print("Обычно она находится в /Volumes/")
        source_path = input("Путь к подключенной сетевой папке: ").strip()
        sd_card_path = input("Путь к папке IMPORT на SD карте SP-404 MKII: ").strip()
        
        if not source_path or not sd_card_path:
            print("Ошибка: Не указаны необходимые пути")
            return
        
        success = automation.run_automation_local(source_path, sd_card_path)
        
    else:
        print("Ошибка: Неверный выбор режима")
        return
    
    if success:
        print("\n✅ Автоматизация завершена успешно!")
        print("Проверьте папку IMPORT на SD карте SP-404 MKII")
    else:
        print("\n❌ Автоматизация завершилась с ошибками")
        print("Проверьте лог файл roland_macos_automation.log для подробностей")


if __name__ == "__main__":
    main()

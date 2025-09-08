#!/usr/bin/env python3
"""
Roland SP-404 MKII Local File Automation Script

Альтернативная версия скрипта для работы с локальными папками или 
сетевыми папками, подключенными через macOS Finder.

Этот скрипт автоматизирует процесс подготовки файлов для Roland SP-404 MKII:
1. Создает структуру папок на SD карте в папке IMPORT
2. Нормализует названия папок и файлов (только латиница, цифры, подчеркивания)
3. Конвертирует WAV файлы в нужный формат (16-bit/24-bit, 44.1/48 kHz)
4. Копирует только WAV файлы в новую структуру

Требования:
- Python 3.7+
- soundfile, scipy, numpy (для конвертации аудио)
- pathlib, os, re (стандартные библиотеки)
"""

import os
import re
import shutil
import logging
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
        logging.FileHandler('roland_local_automation.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class RolandSP404LocalAutomation:
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
    
    def run_automation(self, source_path: str, sd_card_path: str):
        """
        Запускает полную автоматизацию
        
        Args:
            source_path: Путь к исходной папке
            sd_card_path: Путь к SD карте SP-404 MKII (папка IMPORT)
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
    print("Roland SP-404 MKII Local File Automation")
    print("=" * 45)
    print()
    print("Эта версия работает с локальными папками или сетевыми папками,")
    print("подключенными через macOS Finder.")
    print()
    print("Для работы с сетевой папкой:")
    print("1. Откройте Finder")
    print("2. Нажмите Cmd+K")
    print("3. Введите: smb://192.168.2.81/4Music")
    print("4. Подключитесь к папке")
    print("5. Укажите путь к подключенной папке ниже")
    print()
    
    # Пути
    source_path = input("Введите путь к исходной папке с семплами: ").strip()
    if not source_path:
        print("Ошибка: Не указан путь к исходной папке")
        return
    
    sd_card_path = input("Введите путь к папке IMPORT на SD карте SP-404 MKII: ").strip()
    if not sd_card_path:
        print("Ошибка: Не указан путь к SD карте")
        return
    
    # Создаем экземпляр класса и запускаем автоматизацию
    automation = RolandSP404LocalAutomation()
    success = automation.run_automation(source_path, sd_card_path)
    
    if success:
        print("\n✅ Автоматизация завершена успешно!")
        print("Проверьте папку IMPORT на SD карте SP-404 MKII")
    else:
        print("\n❌ Автоматизация завершилась с ошибками")
        print("Проверьте лог файл roland_local_automation.log для подробностей")


if __name__ == "__main__":
    main()

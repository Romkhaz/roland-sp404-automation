#!/usr/bin/env python3
"""
Roland SP-404 MKII File Automation Script

Этот скрипт автоматизирует процесс подготовки файлов для Roland SP-404 MKII:
1. Создает структуру папок на SD карте в папке IMPORT
2. Нормализует названия папок и файлов (только латиница, цифры, подчеркивания)
3. Конвертирует WAV файлы в нужный формат (16-bit/24-bit, 44.1/48 kHz)
4. Копирует только WAV файлы в новую структуру

Требования:
- Python 3.7+
- pysmb (для работы с SMB)
- pydub (для конвертации аудио)
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
    from smb.SMBConnection import SMBConnection
    from smb.smb_structs import OperationFailure
except ImportError:
    print("Ошибка: Не установлен pysmb. Установите: pip install pysmb")
    exit(1)

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
        logging.FileHandler('roland_automation.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class RolandSP404Automation:
    def __init__(self, smb_server: str, smb_share: str, smb_username: str = "", smb_password: str = ""):
        """
        Инициализация класса для автоматизации Roland SP-404 MKII
        
        Args:
            smb_server: IP адрес SMB сервера
            smb_share: Имя SMB шары
            smb_username: Имя пользователя (опционально)
            smb_password: Пароль (опционально)
        """
        self.smb_server = smb_server
        self.smb_share = smb_share
        self.smb_username = smb_username
        self.smb_password = smb_password
        self.conn = None
        
        # Поддерживаемые форматы для SP-404 MKII
        self.supported_sample_rates = [44100, 48000]
        self.supported_bit_depths = [16, 24]
        
    def normalize_name(self, name: str) -> str:
        """
        Нормализует название файла или папки для SP-404 MKII
        
        Args:
            name: Исходное название
            
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
        
        # Если название стало пустым, используем дефолтное
        if not normalized:
            normalized = "unnamed"
            
        return normalized + extension
    
    def connect_smb(self) -> bool:
        """
        Подключается к SMB серверу
        
        Returns:
            True если подключение успешно, False иначе
        """
        try:
            self.conn = SMBConnection(
                self.smb_username, 
                self.smb_password, 
                "roland_automation", 
                "server", 
                use_ntlm_v2=True
            )
            
            result = self.conn.connect(self.smb_server, 445)
            if result:
                logger.info(f"Успешно подключились к SMB серверу {self.smb_server}")
                return True
            else:
                logger.error(f"Не удалось подключиться к SMB серверу {self.smb_server}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка подключения к SMB: {e}")
            return False
    
    def disconnect_smb(self):
        """Отключается от SMB сервера"""
        if self.conn:
            self.conn.close()
            logger.info("Отключились от SMB сервера")
    
    def get_smb_file_list(self, remote_path: str) -> List[Tuple[str, bool]]:
        """
        Получает список файлов и папок с SMB сервера
        
        Args:
            remote_path: Путь на SMB сервере
            
        Returns:
            Список кортежей (имя, является_файлом)
        """
        try:
            files = []
            for file_info in self.conn.listPath(self.smb_share, remote_path):
                if file_info.filename not in ['.', '..']:
                    files.append((file_info.filename, not file_info.isDirectory))
            return files
        except Exception as e:
            logger.error(f"Ошибка получения списка файлов из {remote_path}: {e}")
            return []
    
    def download_smb_file(self, remote_path: str, local_path: str) -> bool:
        """
        Скачивает файл с SMB сервера
        
        Args:
            remote_path: Путь к файлу на SMB сервере
            local_path: Локальный путь для сохранения
            
        Returns:
            True если скачивание успешно, False иначе
        """
        try:
            with open(local_path, 'wb') as local_file:
                self.conn.retrieveFile(self.smb_share, remote_path, local_file)
            logger.info(f"Скачан файл: {remote_path} -> {local_path}")
            return True
        except Exception as e:
            logger.error(f"Ошибка скачивания файла {remote_path}: {e}")
            return False
    
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
            
            # Приводим к моно, если нужно (SP-404 MKII лучше работает с моно)
            if current_channels > 1:
                data = np.mean(data, axis=1)
                logger.info("Конвертировано в моно")
            
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
    
    def process_directory(self, remote_path: str, local_base_path: str, sd_card_path: str):
        """
        Обрабатывает директорию рекурсивно
        
        Args:
            remote_path: Путь на SMB сервере
            local_base_path: Базовый локальный путь для временных файлов
            sd_card_path: Путь к SD карте SP-404 MKII
        """
        logger.info(f"Обрабатываем директорию: {remote_path}")
        
        # Получаем список файлов и папок
        items = self.get_smb_file_list(remote_path)
        
        for name, is_file in items:
            normalized_name = self.normalize_name(name)
            
            if is_file:
                # Обрабатываем файл
                if name.lower().endswith('.wav'):
                    logger.info(f"Обрабатываем WAV файл: {name}")
                    
                    # Создаем временный файл
                    temp_file = local_base_path / "temp" / name
                    temp_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Скачиваем файл
                    if self.download_smb_file(f"{remote_path}/{name}", str(temp_file)):
                        # Создаем выходной файл
                        output_file = sd_card_path / normalized_name
                        
                        # Конвертируем файл
                        if self.convert_audio_file(str(temp_file), str(output_file)):
                            logger.info(f"Успешно обработан: {name} -> {normalized_name}")
                        else:
                            logger.error(f"Ошибка конвертации: {name}")
                        
                        # Удаляем временный файл
                        temp_file.unlink(missing_ok=True)
                    else:
                        logger.error(f"Ошибка скачивания: {name}")
                else:
                    logger.info(f"Пропускаем не-WAV файл: {name}")
            else:
                # Обрабатываем папку
                logger.info(f"Обрабатываем папку: {name}")
                
                # Создаем нормализованную папку
                normalized_folder = sd_card_path / normalized_name
                normalized_folder.mkdir(parents=True, exist_ok=True)
                
                # Рекурсивно обрабатываем содержимое папки
                self.process_directory(
                    f"{remote_path}/{name}",
                    local_base_path,
                    normalized_folder
                )
    
    def run_automation(self, source_path: str, sd_card_path: str):
        """
        Запускает полную автоматизацию
        
        Args:
            source_path: Путь к исходной папке на SMB сервере
            sd_card_path: Путь к SD карте SP-404 MKII (папка IMPORT)
        """
        logger.info("Запуск автоматизации Roland SP-404 MKII")
        
        # Подключаемся к SMB
        if not self.connect_smb():
            logger.error("Не удалось подключиться к SMB серверу")
            return False
        
        try:
            # Создаем базовую структуру
            sd_path = Path(sd_card_path)
            sd_path.mkdir(parents=True, exist_ok=True)
            
            local_temp_path = Path("temp_roland_processing")
            local_temp_path.mkdir(parents=True, exist_ok=True)
            
            # Обрабатываем исходную папку
            self.process_directory(source_path, local_temp_path, sd_path)
            
            logger.info("Автоматизация завершена успешно!")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка во время автоматизации: {e}")
            return False
        finally:
            # Отключаемся от SMB
            self.disconnect_smb()
            
            # Очищаем временные файлы
            temp_path = Path("temp_roland_processing")
            if temp_path.exists():
                shutil.rmtree(temp_path)
                logger.info("Временные файлы очищены")


def main():
    """Основная функция"""
    print("Roland SP-404 MKII File Automation")
    print("=" * 40)
    
    # Параметры подключения к SMB
    smb_server = "192.168.2.81"
    smb_share = "4Music"
    smb_username = input("Введите имя пользователя SMB (или Enter для гостевого доступа): ").strip()
    smb_password = input("Введите пароль SMB (или Enter если не нужен): ").strip()
    
    # Пути
    source_path = "Music_Projects/Roland/"  # Путь на SMB сервере
    sd_card_path = input("Введите путь к папке IMPORT на SD карте SP-404 MKII: ").strip()
    
    if not sd_card_path:
        print("Ошибка: Не указан путь к SD карте")
        return
    
    # Создаем экземпляр класса и запускаем автоматизацию
    automation = RolandSP404Automation(smb_server, smb_share, smb_username, smb_password)
    success = automation.run_automation(source_path, sd_card_path)
    
    if success:
        print("\n✅ Автоматизация завершена успешно!")
        print("Проверьте папку IMPORT на SD карте SP-404 MKII")
    else:
        print("\n❌ Автоматизация завершилась с ошибками")
        print("Проверьте лог файл roland_automation.log для подробностей")


if __name__ == "__main__":
    main()

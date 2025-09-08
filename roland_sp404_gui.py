#!/usr/bin/env python3
"""
Roland SP-404 MKII GUI Automation

Простой графический интерфейс для автоматизации подготовки файлов
для Roland SP-404 MKII с возможностью выбора папок через диалоги.

Требования:
- Python 3.7+
- tkinter (входит в стандартную библиотеку)
- soundfile, scipy, numpy (для конвертации аудио)
"""

import os
import re
import shutil
import logging
import threading
from pathlib import Path
from typing import List, Tuple, Optional
import unicodedata
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

try:
    import soundfile as sf
    import numpy as np
    from scipy import signal
except ImportError:
    messagebox.showerror("Ошибка", "Не установлены soundfile и scipy.\nУстановите: pip install soundfile scipy")
    exit(1)

class RolandSP404GUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Roland SP-404 MKII File Automation")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        
        # Переменные
        self.source_path = tk.StringVar()
        self.target_path = tk.StringVar()
        self.is_processing = False
        
        # Настройка логирования
        self.setup_logging()
        
        # Создание интерфейса
        self.create_widgets()
        
        # Поддерживаемые форматы для SP-404 MKII
        self.supported_sample_rates = [44100, 48000]
        self.supported_bit_depths = [16, 24]
    
    def setup_logging(self):
        """Настройка логирования"""
        # Создаем логгер
        self.logger = logging.getLogger('roland_gui')
        self.logger.setLevel(logging.INFO)
        
        # Очищаем существующие обработчики
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Создаем обработчик для GUI
        self.log_handler = logging.StreamHandler()
        self.log_handler.setLevel(logging.INFO)
        
        # Создаем форматтер
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        self.log_handler.setFormatter(formatter)
        
        # Добавляем обработчик
        self.logger.addHandler(self.log_handler)
    
    def create_widgets(self):
        """Создание элементов интерфейса"""
        # Главный фрейм
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Настройка сетки
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Заголовок
        title_label = ttk.Label(main_frame, text="Roland SP-404 MKII File Automation", 
                               font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Выбор исходной папки
        ttk.Label(main_frame, text="Исходная папка с семплами:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.source_path, width=50).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 5), pady=5)
        ttk.Button(main_frame, text="Выбрать", command=self.select_source_folder).grid(row=1, column=2, pady=5)
        
        # Выбор целевой папки
        ttk.Label(main_frame, text="Папка IMPORT на SD карте:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.target_path, width=50).grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(5, 5), pady=5)
        ttk.Button(main_frame, text="Выбрать", command=self.select_target_folder).grid(row=2, column=2, pady=5)
        
        # Кнопки управления
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=20)
        
        self.start_button = ttk.Button(button_frame, text="Начать обработку", 
                                      command=self.start_processing, style='Accent.TButton')
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(button_frame, text="Остановить", 
                                     command=self.stop_processing, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Очистить лог", command=self.clear_log).pack(side=tk.LEFT, padx=5)
        
        # Прогресс бар
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        # Лог
        ttk.Label(main_frame, text="Лог обработки:").grid(row=5, column=0, sticky=tk.W, pady=(10, 5))
        
        # Создаем текстовое поле с прокруткой для лога
        log_frame = ttk.Frame(main_frame)
        log_frame.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, width=80)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Настройка весов для растягивания
        main_frame.rowconfigure(6, weight=1)
        
        # Статус бар
        self.status_var = tk.StringVar()
        self.status_var.set("Готов к работе")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=7, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        
        # Информация о поддерживаемых форматах
        info_frame = ttk.LabelFrame(main_frame, text="Поддерживаемые форматы", padding="5")
        info_frame.grid(row=8, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        
        info_text = """• Входные файлы: WAV любого формата
• Выходные файлы: 16-bit WAV PCM, 44.1/48 kHz, моно/стерео
• Названия файлов: только латиница, цифры, подчеркивания
• Структура папок: сохраняется с нормализованными названиями"""
        
        ttk.Label(info_frame, text=info_text, justify=tk.LEFT).pack(anchor=tk.W)
    
    def select_source_folder(self):
        """Выбор исходной папки"""
        folder = filedialog.askdirectory(title="Выберите папку с семплами")
        if folder:
            self.source_path.set(folder)
            self.log_message(f"Выбрана исходная папка: {folder}")
    
    def select_target_folder(self):
        """Выбор целевой папки"""
        folder = filedialog.askdirectory(title="Выберите папку IMPORT на SD карте SP-404 MKII")
        if folder:
            self.target_path.set(folder)
            self.log_message(f"Выбрана целевая папка: {folder}")
    
    def log_message(self, message):
        """Добавление сообщения в лог"""
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def clear_log(self):
        """Очистка лога"""
        self.log_text.delete(1.0, tk.END)
    
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
            
            self.log_message(f"Исходный файл: {current_sample_rate}Hz, {current_channels}ch")
            
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
                self.log_message(f"Изменена частота дискретизации: {current_sample_rate} -> {target_sample_rate}")
            
            # Сохраняем стерео, если исходный файл стерео (SP-404 MKII поддерживает стерео)
            if current_channels > 1:
                self.log_message(f"Сохраняем стерео ({current_channels} каналов)")
            
            # Нормализуем данные для 16-bit
            if np.max(np.abs(data)) > 0:
                data = data / np.max(np.abs(data)) * 0.95  # Оставляем небольшой запас
            
            # Конвертируем в 16-bit
            data_16bit = (data * 32767).astype(np.int16)
            
            # Сохраняем как WAV файл с правильным количеством каналов
            sf.write(output_path, data_16bit, target_sample_rate, subtype='PCM_16')
            self.log_message(f"Файл конвертирован: {output_path}")
            return True
            
        except Exception as e:
            self.log_message(f"Ошибка конвертации файла {input_path}: {e}")
            return False
    
    def process_directory(self, source_path: Path, target_path: Path):
        """
        Обрабатывает директорию рекурсивно
        
        Args:
            source_path: Путь к исходной папке
            target_path: Путь к целевой папке на SD карте
        """
        if not self.is_processing:
            return
            
        self.log_message(f"Обрабатываем директорию: {source_path}")
        
        # Создаем целевую папку если не существует
        target_path.mkdir(parents=True, exist_ok=True)
        
        try:
            # Получаем список элементов в папке
            items = list(source_path.iterdir())
            
            # Счетчик для уникальности имен файлов
            file_counter = 0
            
            for item in items:
                if not self.is_processing:
                    break
                    
                if item.is_file():
                    # Обрабатываем файл
                    if item.suffix.lower() == '.wav':
                        self.log_message(f"Обрабатываем WAV файл: {item.name}")
                        
                        # Создаем нормализованное имя файла с уникальным номером
                        normalized_name = self.normalize_name(item.name, file_counter)
                        output_file = target_path / normalized_name
                        
                        # Конвертируем файл
                        if self.convert_audio_file(str(item), str(output_file)):
                            self.log_message(f"Успешно обработан: {item.name} -> {normalized_name}")
                            file_counter += 1
                        else:
                            self.log_message(f"Ошибка конвертации: {item.name}")
                    else:
                        self.log_message(f"Пропускаем не-WAV файл: {item.name}")
                        
                elif item.is_dir():
                    # Обрабатываем папку
                    self.log_message(f"Обрабатываем папку: {item.name}")
                    
                    # Создаем нормализованную папку
                    normalized_folder_name = self.normalize_name(item.name)
                    normalized_folder = target_path / normalized_folder_name
                    
                    # Рекурсивно обрабатываем содержимое папки
                    self.process_directory(item, normalized_folder)
                    
        except PermissionError as e:
            self.log_message(f"Ошибка доступа к папке {source_path}: {e}")
        except Exception as e:
            self.log_message(f"Ошибка обработки папки {source_path}: {e}")
    
    def start_processing(self):
        """Запуск обработки в отдельном потоке"""
        if not self.source_path.get() or not self.target_path.get():
            messagebox.showerror("Ошибка", "Выберите исходную и целевую папки")
            return
        
        if not Path(self.source_path.get()).exists():
            messagebox.showerror("Ошибка", "Исходная папка не существует")
            return
        
        # Блокируем интерфейс
        self.is_processing = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.progress.start()
        self.status_var.set("Обработка...")
        
        # Запускаем обработку в отдельном потоке
        thread = threading.Thread(target=self.run_processing)
        thread.daemon = True
        thread.start()
    
    def stop_processing(self):
        """Остановка обработки"""
        self.is_processing = False
        self.log_message("Остановка обработки...")
        self.status_var.set("Остановка...")
    
    def run_processing(self):
        """Основная функция обработки"""
        try:
            self.log_message("Запуск автоматизации Roland SP-404 MKII")
            
            # Проверяем существование исходной папки
            source = Path(self.source_path.get())
            if not source.exists():
                self.log_message(f"Ошибка: Исходная папка не существует: {source}")
                return
            
            if not source.is_dir():
                self.log_message(f"Ошибка: Указанный путь не является папкой: {source}")
                return
            
            # Создаем целевую папку
            target = Path(self.target_path.get())
            target.mkdir(parents=True, exist_ok=True)
            
            # Обрабатываем исходную папку
            self.process_directory(source, target)
            
            if self.is_processing:
                self.log_message("Автоматизация завершена успешно!")
                self.root.after(0, lambda: messagebox.showinfo("Успех", "Обработка завершена успешно!"))
            else:
                self.log_message("Обработка остановлена пользователем")
                
        except Exception as e:
            self.log_message(f"Ошибка во время автоматизации: {e}")
            self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Ошибка обработки: {e}"))
        finally:
            # Разблокируем интерфейс
            self.root.after(0, self.processing_finished)
    
    def processing_finished(self):
        """Завершение обработки"""
        self.is_processing = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.progress.stop()
        self.status_var.set("Готов к работе")


def main():
    """Основная функция"""
    root = tk.Tk()
    
    # Настройка стиля
    style = ttk.Style()
    style.theme_use('clam')
    
    # Создание приложения
    app = RolandSP404GUI(root)
    
    # Запуск главного цикла
    root.mainloop()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Создает тестовые WAV файлы для демонстрации работы скрипта
"""

import numpy as np
import soundfile as sf
from pathlib import Path

def create_test_wav(filename: str, sample_rate: int = 48000, duration: float = 1.0, channels: int = 1):
    """Создает тестовый WAV файл с синусоидальным сигналом"""
    # Генерируем синусоидальный сигнал 440 Hz (нота A)
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    frequency = 440.0  # Hz
    signal = np.sin(2 * np.pi * frequency * t)
    
    # Добавляем небольшой шум для реалистичности
    noise = np.random.normal(0, 0.1, signal.shape)
    signal = signal + noise
    
    # Нормализуем
    signal = signal / np.max(np.abs(signal)) * 0.8
    
    # Создаем стерео, если нужно
    if channels == 2:
        # Левый канал - 440 Hz, правый канал - 880 Hz
        left_channel = signal
        right_channel = np.sin(2 * np.pi * 880.0 * t)  # Октава выше
        right_channel = right_channel / np.max(np.abs(right_channel)) * 0.8
        signal = np.column_stack((left_channel, right_channel))
    
    # Сохраняем как WAV
    sf.write(filename, signal, sample_rate, subtype='PCM_16')
    print(f"Создан тестовый файл: {filename} ({channels} канал(ов))")

def main():
    # Создаем тестовые файлы с разными параметрами
    test_files = [
        ("test_samples/Test_Folder_1/Кириллица_файл.wav", 44100, 0.5, 1),
        ("test_samples/Test_Folder_1/File with spaces.wav", 48000, 1.0, 2),  # стерео
        ("test_samples/Test_Folder_1/файл_с_символами!@#.wav", 44100, 0.8, 1),
        ("test_samples/Test_Folder_2/Test_File_1.wav", 48000, 1.2, 2),  # стерео
        ("test_samples/Test_Folder_2/Test_File_2.wav", 44100, 0.6, 1),
        ("test_samples/Test_Folder_3/Another_Test.wav", 48000, 0.9, 2),  # стерео
    ]
    
    for filename, sample_rate, duration, channels in test_files:
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        create_test_wav(filename, sample_rate, duration, channels)
    
    print("\nВсе тестовые файлы созданы!")

if __name__ == "__main__":
    main()

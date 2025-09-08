@echo off
echo Roland SP-404 MKII GUI Automation
echo ====================================
echo.

REM Проверяем наличие Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Ошибка: Python не найден. Установите Python 3.7 или выше.
    pause
    exit /b 1
)

REM Проверяем зависимости
python -c "import soundfile, scipy, numpy, tkinter" >nul 2>&1
if errorlevel 1 (
    echo Установка зависимостей...
    pip install soundfile scipy
    if errorlevel 1 (
        echo Ошибка установки зависимостей.
        pause
        exit /b 1
    )
)

REM Запускаем GUI
echo Запуск GUI приложения...
python roland_sp404_gui.py

pause

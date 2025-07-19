# Путь к виртуальному окружению
$venvPath = "D:\LunchBOT\venv"

# Активация окружения
& "$venvPath\Scripts\Activate.ps1"

# Явный путь к интерпретатору из venv
$pythonPath = "$venvPath\Scripts\python.exe"

# Запуск watchmedo с авто-перезапуском run_all.py
python -m watchdog.watchmedo auto-restart `
    --pattern="*.py" `
    --recursive `
    --signal=SIGTERM `
    -- "$pythonPath" run_all.py

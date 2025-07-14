import subprocess
import sys
import time

processes = []

try:
    # Запуск Telegram-бота
    bot_proc = subprocess.Popen([sys.executable, 'main.py'])
    processes.append(bot_proc)

    # Запуск админ-панели через streamlit
    admin_proc = subprocess.Popen([
        'streamlit', 'run', 'admin_panel/streamlit_app.py', '--server.port', '8000'
    ])
    processes.append(admin_proc)

    print('Бот и админ-панель (Streamlit) запущены. Для остановки нажмите Ctrl+C.')
    while True:
        time.sleep(1)
        # Проверяем, не завершился ли какой-либо процесс
        for proc in processes:
            if proc.poll() is not None:
                raise KeyboardInterrupt
except KeyboardInterrupt:
    print('\nОстановка всех процессов...')
    for proc in processes:
        proc.terminate()
    for proc in processes:
        proc.wait()
    print('Все процессы остановлены.') 
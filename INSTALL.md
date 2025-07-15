     # 🚀 Инструкция по установке LunchBOT

## Быстрая установка

### 1. Подготовка
```bash
# Убедитесь, что у вас установлен Python 3.8+
python3 --version

# Создайте виртуальное окружение (рекомендуется)
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows
```

### 2. Установка зависимостей
```bash
pip install -r requirements.txt
```

**Если возникают проблемы с зависимостями:**
```bash
# Запустите скрипт исправления
python3 fix_dependencies.py

# Или вручную:
pip uninstall numpy pandas streamlit -y
pip install -r requirements.txt
```

### 3. Настройка бота
1. Создайте бота через [@BotFather](https://t.me/BotFather)
2. Получите токен бота
3. Установите переменную окружения:
```bash
export BOT_TOKEN="your_bot_token_here"
```

### 4. Запуск
```bash
python3 run_all.py
```

## Что произойдет после запуска

1. **База данных**: Автоматически создастся файл `lunchbot.db`
2. **Telegram бот**: Запустится и будет ожидать сообщений
3. **Админ-панель**: Будет доступна по адресу http://localhost:8501

## Первые шаги

1. Откройте админ-панель: http://localhost:8501
2. Перейдите в "Ссылки активации"
3. Создайте ссылку для каждого участника команды
4. Отправьте ссылки участникам или команды `/activate <token>`

## Структура команд

### Для участников:
- `/start` - Главное меню
- `/new_debt` - Создать долг
- `/my_debts` - Мои долги
- `/activate <token>` - Активация

### Админ-панель:
- **Обзор**: Статистика системы
- **Долги**: Управление долгами
- **Пользователи**: Управление участниками
- **Ссылки активации**: Создание ссылок
- **Настройки**: Конфигурация системы

## Устранение неполадок

### Ошибка совместимости numpy/pandas
```bash
# Автоматическое исправление
python3 fix_dependencies.py

# Или вручную
pip uninstall numpy pandas streamlit -y
pip cache purge
pip install -r requirements.txt
```

### Ошибка "Token not found"
```bash
export BOT_TOKEN="your_actual_bot_token"
```

### Ошибка "Module not found"
```bash
pip install -r requirements.txt
```

### Порт занят
Измените порт в `run_all.py` (строка с `--server.port`)

## Готово!

Теперь ваша система учёта долгов готова к работе! 🎉 
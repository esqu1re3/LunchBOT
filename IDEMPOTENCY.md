# 🔄 Идемпотентность в LunchBOT

## Что такое идемпотентность?

**Идемпотентность** — это свойство системы, при котором повторное выполнение одного и того же действия не приводит к нежелательным побочным эффектам (например, дублированию данных, повторным уведомлениям, ошибкам).

## Реализованные механизмы идемпотентности

### 1. 💰 Создание долгов

- **Проблема**: Пользователь может случайно создать одинаковый долг несколько раз
- **Решение**: Проверка дублирования долгов в течение 5-минутного окна
- **Критерии дублирования**: 
  - Одинаковые должник и кредитор
  - Одинаковая сумма
  - Одинаковое описание (или оба пустые)
  - Создано менее 5 минут назад

```python
# Пример: повторное создание долга вернет ID существующего
debt_id1 = db.create_debt(debtor_id=1, creditor_id=2, amount=100.0, description="Обед")
debt_id2 = db.create_debt(debtor_id=1, creditor_id=2, amount=100.0, description="Обед")
# debt_id1 == debt_id2 (дублирование предотвращено)
```

### 2. 💳 Создание платежей

- **Проблема**: Должник может отправить чек несколько раз для одного долга
- **Решение**: Один активный платеж на долг от должника
- **Критерии дублирования**:
  - Один и тот же долг
  - Один и тот же должник
  - Статус платежа: 'Pending' или 'Confirmed'

```python
# Пример: повторная отправка чека вернет ID существующего платежа
payment_id1 = db.create_payment(debt_id=1, debtor_id=1, creditor_id=2, file_id="file123")
payment_id2 = db.create_payment(debt_id=1, debtor_id=1, creditor_id=2, file_id="file456")
# payment_id1 == payment_id2 (дублирование предотвращено)
```

### 3. ✅ Подтверждение платежей

- **Проблема**: Кредитор может случайно подтвердить платеж несколько раз
- **Решение**: Проверка статуса платежа и хэширование операции
- **Поведение**: Повторное подтверждение уже подтвержденного платежа возвращает `True`

```python
# Пример: повторное подтверждение безопасно
result1 = db.confirm_payment(payment_id)  # True (подтверждено)
result2 = db.confirm_payment(payment_id)  # True (уже подтверждено)
```

### 4. 🔄 Callback-запросы

- **Проблема**: Пользователь может быстро нажать кнопку несколько раз
- **Решение**: Кэширование обработанных callback-запросов
- **Механизм**:
  - Создание уникального ключа: `{user_id}:{callback_data}`
  - Кэширование на 1 минуту
  - Автоматическая очистка устаревших записей

```python
# Пример: повторный callback игнорируется
if self.is_callback_processed(call.id, user_id, data):
    self.safe_answer_callback_query(call.id, "Операция уже выполнена")
    return
```

### 5. 📢 Уведомления

- **Проблема**: Пользователь может получить дублирующие уведомления
- **Решение**: Хэширование уведомлений и проверка отправки
- **Типы уведомлений**:
  - Уведомления о новых долгах
  - Запросы на подтверждение платежей
  - Запросы на подтверждение множественных платежей

```python
# Пример: дублирующие уведомления не отправляются
notification_hash = db.create_operation_hash('debt_notification', debtor_id, debt_id=debt_id)
if db.check_operation_processed(notification_hash):
    return  # Уведомление уже отправлено
```

## Архитектура системы идемпотентности

### Таблица `processed_operations`

```sql
CREATE TABLE processed_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_hash TEXT UNIQUE NOT NULL,      -- Хэш операции
    operation_type TEXT NOT NULL,             -- Тип операции
    user_id INTEGER NOT NULL,                 -- ID пользователя
    operation_data TEXT,                      -- JSON с данными
    result_id INTEGER,                        -- ID результата
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP                      -- Время истечения
);
```

### Создание хэшей операций

```python
def create_operation_hash(self, operation_type: str, user_id: int, **kwargs) -> str:
    hash_data = {
        'operation_type': operation_type,
        'user_id': user_id,
        **kwargs
    }
    sorted_data = json.dumps(hash_data, sort_keys=True)
    return hashlib.sha256(sorted_data.encode('utf-8')).hexdigest()
```

### Автоматическая очистка

- **Планировщик**: Каждые 30 минут
- **Метод**: `cleanup_expired_operations()`
- **Критерий**: `datetime(expires_at) <= datetime('now')`

## Временные окна

| Операция | Время жизни | Описание |
|----------|-------------|----------|
| Создание долга | 5 минут | Проверка дублирования |
| Операции в БД | 5 минут | Хэши операций |
| Callback-запросы | 1 минута | Кэш в памяти |
| Уведомления | 5 минут | Предотвращение дублирования |

## Обработка ошибок

### Timeout callback-запросов

```python
def safe_answer_callback_query(self, callback_id: str, text: str = None):
    try:
        self.bot.answer_callback_query(callback_id, text)
    except Exception as e:
        if "query is too old" in str(e).lower():
            logger.warning(f"Callback query устарел: {callback_id}")
        else:
            logger.error(f"Ошибка ответа на callback query: {e}")
```

### Восстановление после ошибок

```python
except Exception as e:
    logger.error(f"Ошибка обработки callback {data}: {e}")
    # Удаляем из кэша, чтобы можно было повторить
    callback_key = f"{user_id}:{data}"
    if callback_key in self.processed_callbacks:
        del self.processed_callbacks[callback_key]
```

## Преимущества реализации

1. **🛡️ Защита от дублирования**: Предотвращает создание дублирующих долгов, платежей и уведомлений
2. **⚡ Быстрая работа**: Callback-запросы обрабатываются мгновенно без таймаутов
3. **🔄 Надежность**: Повторные операции безопасны и предсказуемы
4. **🧹 Самоочистка**: Автоматическое удаление устаревших записей
5. **📊 Прозрачность**: Логирование всех операций для отладки

## Тестирование

Система идемпотентности покрыта комплексными тестами:

- ✅ Создание дублирующих долгов
- ✅ Создание дублирующих платежей  
- ✅ Повторное подтверждение платежей
- ✅ Консистентность хэшей операций
- ✅ Истечение операций
- ✅ Временные окна дублирования
- ✅ Разные пользователи и операции

## Мониторинг

Для мониторинга идемпотентности используются логи:

```python
logger.info(f"Найден дублирующий долг {existing_debt_id}, возвращаем его")
logger.info(f"Операция создания долга уже обработана: {processed['result_id']}")
logger.info(f"Callback {callback_key} уже обработан")
logger.info(f"Уведомление о долге {debt_id} уже отправлено должнику {debtor_id}")
```

---

**Результат**: LunchBOT теперь полностью идемпотентен и защищен от всех видов дублирования операций и уведомлений. 
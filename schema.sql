-- Схема базы данных для LunchBOT

-- Таблица пользователей
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE NOT NULL,  -- Telegram user ID
    username TEXT,                    -- Telegram username
    first_name TEXT,                  -- Имя пользователя
    last_name TEXT,                   -- Фамилия пользователя
    is_active BOOLEAN DEFAULT 1,      -- Активен ли пользователь
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    activated_at TIMESTAMP            -- Когда активирован
);

-- Таблица ссылок активации
CREATE TABLE IF NOT EXISTS activation_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT UNIQUE NOT NULL,       -- Уникальный токен для активации
    user_id INTEGER,                  -- Telegram user ID (если уже использован)
    name TEXT NOT NULL,               -- Имя участника
    is_used BOOLEAN DEFAULT 0,        -- Использована ли ссылка
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    used_at TIMESTAMP                 -- Когда использована
);

-- Таблица долгов
CREATE TABLE IF NOT EXISTS debts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    debtor_id INTEGER NOT NULL,       -- Кто должен (user_id)
    creditor_id INTEGER NOT NULL,     -- Кому должен (user_id)
    amount REAL NOT NULL,             -- Сумма долга
    description TEXT,                 -- Описание (например, "сэндвич")
    status TEXT DEFAULT 'Open',       -- Статус: Open, Closed, Disputed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP,              -- Дата закрытия долга
    reminder_frequency INTEGER DEFAULT 1,  -- Частота напоминаний в днях
    last_reminder TIMESTAMP,          -- Последнее напоминание
    FOREIGN KEY (debtor_id) REFERENCES users (user_id),
    FOREIGN KEY (creditor_id) REFERENCES users (user_id)
);

-- Таблица платежей/подтверждений
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    debt_id INTEGER NOT NULL,         -- ID долга
    debtor_id INTEGER NOT NULL,       -- Кто оплатил
    creditor_id INTEGER NOT NULL,     -- Кто подтверждает
    file_id TEXT,                     -- ID файла чека в Telegram
    status TEXT DEFAULT 'Pending',    -- Статус: Pending, Confirmed, Cancelled
    cancel_reason TEXT,               -- Причина отмены подтверждения
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMP,           -- Дата подтверждения
    FOREIGN KEY (debt_id) REFERENCES debts (id),
    FOREIGN KEY (debtor_id) REFERENCES users (user_id),
    FOREIGN KEY (creditor_id) REFERENCES users (user_id)
);

-- Таблица настроек
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,         -- Ключ настройки
    value TEXT NOT NULL,              -- Значение настройки
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Вставляем значения настроек по умолчанию
INSERT OR IGNORE INTO settings (key, value) VALUES ('reminder_frequency', '1');
INSERT OR IGNORE INTO settings (key, value) VALUES ('reminder_time', '17:30');
INSERT OR IGNORE INTO settings (key, value) VALUES ('bot_token', '');
INSERT OR IGNORE INTO settings (key, value) VALUES ('admin_chat_id', '');

-- Индексы для оптимизации запросов
CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id);
CREATE INDEX IF NOT EXISTS idx_debts_debtor ON debts(debtor_id);
CREATE INDEX IF NOT EXISTS idx_debts_creditor ON debts(creditor_id);
CREATE INDEX IF NOT EXISTS idx_debts_status ON debts(status);
CREATE INDEX IF NOT EXISTS idx_payments_debt_id ON payments(debt_id);
CREATE INDEX IF NOT EXISTS idx_activation_token ON activation_links(token); 
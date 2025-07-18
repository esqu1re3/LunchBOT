from datetime import datetime

def format_debt_list(debts):
    """
    Форматирует список долгов для отображения
    
    Args:
        debts: Список долгов
        
    Returns:
        Отформатированная строка
    """
    if not debts:
        return "Нет активных долгов"
    lines = []
    for d in debts:
        debtor = d.get('debtor_name') or d.get('debtor_username') or f"User {d.get('debtor_id')}"
        description = d.get('description') or "без описания"
        created = format_datetime(d.get('created_at'))
        lines.append(f"• {debtor}: {d['amount']:.2f} сом ({description})\n  📅 {created}")
    return '\n'.join(lines)

def format_datetime(dt_string):
    try:
        dt = datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return dt_string

def debt_created_message(debtor_name, amount, description, date):
    return f"""
✅ Долг создан успешно!

Должник: {debtor_name}
Сумма: {amount:.2f} сом
Описание: {description}
Дата: {date}
"""

def new_debt_message(creditor_name, amount, description, created_at):
    """
    Сообщение о новом долге для должника
    
    Args:
        creditor_name: Имя кредитора
        amount: Сумма долга
        description: Описание долга
        created_at: Дата создания
        
    Returns:
        Отформатированное сообщение
    """
    return f"""
💰 У вас новый долг!

Вы должны {creditor_name} {amount:.2f} сом
Описание: {description}
Дата создания: {created_at}

Пожалуйста, погасите долг и подтвердите оплату.
"""

def payment_confirmed_message(amount):
    return f"✅ Оплата подтверждена! Долг на сумму {amount:.2f} сом закрыт. Спасибо!"

def debt_reminder_message(creditor_name, amount, description, created_at):
    """
    Сообщение-напоминание о долге (для автоматических напоминаний)
    
    Args:
        creditor_name: Имя кредитора
        amount: Сумма долга
        description: Описание долга
        created_at: Дата создания
        
    Returns:
        Отформатированное сообщение
    """
    return f"""
⏰ Напоминание о долге

Вы должны {creditor_name} {amount:.2f} сом
Описание: {description}
Дата создания: {created_at}

Пожалуйста, погасите долг и подтвердите оплату.
"""

def error_message(text):
    return f"❌ {text}" 
"""
Админ-панель на Streamlit для управления системой долгов
"""
import streamlit as st
import pandas as pd
import os
import sys
from datetime import datetime
from typing import List, Dict, Any

# Добавляем родительскую директорию в путь для импорта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.db import DatabaseManager

# Настройка страницы
st.set_page_config(
    page_title="LunchBOT - Админ-панель",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Инициализация базы данных
@st.cache_resource
def get_db():
    """Получить экземпляр базы данных"""
    return DatabaseManager()

def format_datetime(dt_string: str) -> str:
    """Форматировать дату и время для отображения"""
    try:
        if not dt_string:
            return "Не указано"
        dt = datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
        return dt.strftime("%d.%m.%Y %H:%M")
    except:
        return dt_string

def format_status(status: str) -> str:
    """Форматировать статус для отображения"""
    status_map = {
        'Open': '🔴 Открыт',
        'Closed': '✅ Закрыт',
        'Disputed': '⚠️ Спорный',
        'Pending': '⏳ В ожидании',
        'Confirmed': '✅ Подтвержден'
    }
    return status_map.get(status, status)

def main():
    """Главная функция админ-панели"""
    st.title("🍽️ LunchBOT - Админ-панель")
    st.markdown("---")
    
    # Получаем базу данных
    db = get_db()
    
    # Сайдбар с навигацией
    st.sidebar.title("📋 Навигация")
    
    pages = {
        "Обзор": "overview",
        "Долги": "debts",
        "Пользователи": "users",
        "Настройки": "settings"
    }
    
    selected_page = st.sidebar.selectbox("Выберите страницу", list(pages.keys()))
    
    # Отображаем выбранную страницу
    if selected_page == "Обзор":
        show_overview(db)
    elif selected_page == "Долги":
        show_debts(db)
    elif selected_page == "Пользователи":
        show_users(db)
    elif selected_page == "Настройки":
        show_settings(db)

def show_overview(db: DatabaseManager):
    """Показать обзор системы"""
    st.header("📊 Обзор системы")
    
    # Получаем статистику
    users = db.get_all_users()
    debts = db.get_open_debts()
    
    # Метрики
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Пользователи", len(users))
    
    with col2:
        st.metric("Активные долги", len(debts))
    
    with col3:
        total_amount = sum(debt['amount'] for debt in debts)
        st.metric("Общая сумма долгов", f"{total_amount:.2f} сом.")
    
    with col4:
        avg_amount = total_amount / len(debts) if debts else 0
        st.metric("Средний долг", f"{avg_amount:.2f} сом.")
    
    # Таблица последних долгов
    st.subheader("📋 Последние долги")
    
    if debts:
        # Преобразуем в DataFrame для отображения
        debts_df = pd.DataFrame(debts)
        
        # Выбираем только нужные колонки
        display_columns = [
            'debtor_name', 'creditor_name', 'amount', 
            'description', 'created_at', 'status'
        ]
        
        if all(col in debts_df.columns for col in display_columns):
            debts_display = debts_df[display_columns].copy()
            debts_display.columns = [
                'Должник', 'Кредитор', 'Сумма', 
                'Описание', 'Дата создания', 'Статус'
            ]
            
            # Форматируем данные
            debts_display['Сумма'] = debts_display['Сумма'].apply(lambda x: f"{x:.2f} сом.")
            debts_display['Дата создания'] = debts_display['Дата создания'].apply(format_datetime)
            debts_display['Статус'] = debts_display['Статус'].apply(format_status)
            
            st.dataframe(debts_display, use_container_width=True)
        else:
            st.warning("Нет данных для отображения")
    else:
        st.info("Нет активных долгов")

def show_debts(db: DatabaseManager):
    """Показать управление долгами"""
    st.header("💰 Управление долгами")
    
    # Вкладки
    tab1, tab2 = st.tabs(["Активные долги", "Создать долг"])
    
    with tab1:
        st.subheader("📋 Активные долги")
        
        debts = db.get_open_debts()
        
        if debts:
            # Фильтры
            col1, col2 = st.columns(2)
            
            with col1:
                # Фильтр по должнику
                debtors = list(set(debt['debtor_name'] for debt in debts))
                selected_debtor = st.selectbox(
                    "Фильтр по должнику", 
                    ["Все"] + debtors,
                    key="debtor_filter"
                )
            
            with col2:
                # Фильтр по кредитору
                creditors = list(set(debt['creditor_name'] for debt in debts))
                selected_creditor = st.selectbox(
                    "Фильтр по кредитору", 
                    ["Все"] + creditors,
                    key="creditor_filter"
                )
            
            # Применяем фильтры
            filtered_debts = debts
            if selected_debtor != "Все":
                filtered_debts = [d for d in filtered_debts if d['debtor_name'] == selected_debtor]
            if selected_creditor != "Все":
                filtered_debts = [d for d in filtered_debts if d['creditor_name'] == selected_creditor]
            
            # Отображаем долги
            for debt in filtered_debts:
                with st.expander(f"💰 {debt['debtor_name']} → {debt['creditor_name']}: {debt['amount']} сом."):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Должник:** {debt['debtor_name']}")
                        st.write(f"**Кредитор:** {debt['creditor_name']}")
                        st.write(f"**Сумма:** {debt['amount']} сом.")
                        st.write(f"**Описание:** {debt['description'] or 'Не указано'}")
                    
                    with col2:
                        st.write(f"**Дата создания:** {format_datetime(debt['created_at'])}")
                        st.write(f"**Статус:** {format_status(debt['status'])}")
                        st.write(f"**Последнее напоминание:** {format_datetime(debt['last_reminder'])}")
                    
                    # Кнопки действий
                    col_btn1, col_btn2 = st.columns(2)
                    
                    with col_btn1:
                        if st.button(f"Закрыть долг", key=f"close_{debt['id']}"):
                            if db.close_debt(debt['id']):
                                st.success("Долг закрыт!")
                                st.rerun()
                            else:
                                st.error("Ошибка при закрытии долга")
                    
                    with col_btn2:
                        if st.button(f"Оспорить долг", key=f"dispute_{debt['id']}"):
                            if db.dispute_debt(debt['id']):
                                st.success("Долг оспорен!")
                                st.rerun()
                            else:
                                st.error("Ошибка при оспаривании долга")
        else:
            st.info("Нет активных долгов")
    
    with tab2:
        st.subheader("➕ Создать новый долг")
        
        users = db.get_all_users()
        
        if len(users) >= 2:
            # Форма создания долга
            with st.form("create_debt_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    # Выбор должника
                    debtor_options = {f"{user['first_name']} (@{user['username']})": user['user_id'] 
                                    for user in users}
                    selected_debtor = st.selectbox("Должник", list(debtor_options.keys()))
                    debtor_id = debtor_options[selected_debtor]
                    
                    # Сумма
                    amount = st.number_input("Сумма долга", min_value=0.01, value=100.0, step=0.01)
                
                with col2:
                    # Выбор кредитора
                    creditor_options = {f"{user['first_name']} (@{user['username']})": user['user_id'] 
                                      for user in users if user['user_id'] != debtor_id}
                    selected_creditor = st.selectbox("Кредитор", list(creditor_options.keys()))
                    creditor_id = creditor_options[selected_creditor]
                    
                    # Описание
                    description = st.text_input("Описание (необязательно)")
                
                # Кнопка создания
                if st.form_submit_button("Создать долг"):
                    if debtor_id == creditor_id:
                        st.error("Должник и кредитор не могут быть одним лицом!")
                    else:
                        debt_id = db.create_debt(debtor_id, creditor_id, amount, description)
                        if debt_id:
                            st.success(f"Долг создан! ID: {debt_id}")
                            st.rerun()
                        else:
                            st.error("Ошибка при создании долга")
        else:
            st.warning("Для создания долга нужно минимум 2 пользователя")

def show_users(db: DatabaseManager):
    """Показать управление пользователями"""
    st.header("👥 Управление пользователями")
    
    users = db.get_all_users()
    
    if users:
        # Статистика пользователей
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 Статистика по должникам")
            
            # Группируем долги по должникам
            debts = db.get_open_debts()
            debtor_stats = {}
            
            for debt in debts:
                debtor_name = debt['debtor_name']
                if debtor_name not in debtor_stats:
                    debtor_stats[debtor_name] = {'count': 0, 'amount': 0}
                debtor_stats[debtor_name]['count'] += 1
                debtor_stats[debtor_name]['amount'] += debt['amount']
            
            if debtor_stats:
                for debtor, stats in debtor_stats.items():
                    st.write(f"**{debtor}**: {stats['count']} долгов на сумму {stats['amount']:.2f} сом.")
            else:
                st.info("Нет долгов")
        
        with col2:
            st.subheader("📊 Статистика по кредиторам")
            
            # Группируем долги по кредиторам
            creditor_stats = {}
            
            for debt in debts:
                creditor_name = debt['creditor_name']
                if creditor_name not in creditor_stats:
                    creditor_stats[creditor_name] = {'count': 0, 'amount': 0}
                creditor_stats[creditor_name]['count'] += 1
                creditor_stats[creditor_name]['amount'] += debt['amount']
            
            if creditor_stats:
                for creditor, stats in creditor_stats.items():
                    st.write(f"**{creditor}**: {stats['count']} долгов на сумму {stats['amount']:.2f} сом.")
            else:
                st.info("Нет долгов")
        
        # Таблица пользователей
        st.subheader("📋 Список пользователей")
        
        # Показываем пользователей в expandable блоках
        for user in users:
            display_name = user['first_name'] or user['username'] or f"User {user['user_id']}"
            
            with st.expander(f"👤 {display_name} (@{user['username'] or 'нет username'})"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**User ID:** {user['user_id']}")
                    st.write(f"**Username:** @{user['username'] or 'нет'}")
                    st.write(f"**Активен:** {'✅' if user['is_active'] else '❌'}")
                    st.write(f"**Создан:** {format_datetime(user['created_at'])}")
                    st.write(f"**Активирован:** {format_datetime(user['activated_at'])}")
                    # Toggle для активации/деактивации
                    active = st.toggle("Активен (можно назначать долги)", value=bool(user['is_active']), key=f"toggle_active_{user['user_id']}")
                    if active != bool(user['is_active']):
                        if db.set_user_active(user['user_id'], int(active)):
                            st.success("Статус пользователя обновлён!")
                            st.rerun()
                        else:
                            st.error("Ошибка при обновлении статуса пользователя")
                    # Кнопка для каскадного удаления
                    if st.button(f"Удалить пользователя и все данные", key=f"delete_user_{user['user_id']}"):
                        if db.delete_user_cascade(user['user_id']):
                            st.success("Пользователь и все связанные данные удалены!")
                            st.rerun()
                        else:
                            st.error("Ошибка при удалении пользователя")
                
                with col2:
                    # Форма для переименования
                    with st.form(f"rename_user_{user['user_id']}"):
                        st.write("**Изменить имя:**")
                        new_first_name = st.text_input(
                            "Имя", 
                            value=user['first_name'] or '', 
                            key=f"first_name_{user['user_id']}"
                        )
                        new_last_name = st.text_input(
                            "Фамилия", 
                            value=user['last_name'] or '', 
                            key=f"last_name_{user['user_id']}"
                        )
                        
                        if st.form_submit_button("Сохранить"):
                            if new_first_name.strip():
                                if db.update_user_name(user['user_id'], new_first_name.strip(), new_last_name.strip() or None):
                                    st.success("Имя обновлено!")
                                    st.rerun()
                                else:
                                    st.error("Ошибка при обновлении имени")
                            else:
                                st.error("Имя не может быть пустым")
    else:
        st.info("Нет зарегистрированных пользователей")



def show_settings(db: DatabaseManager):
    """Показать настройки системы"""
    st.header("⚙️ Настройки системы")
    
    # Настройки напоминаний
    st.subheader("⏰ Настройки напоминаний")
    
    current_frequency = int(db.get_setting('reminder_frequency') or 1)
    current_time = db.get_setting('reminder_time') or '17:30'
    
    with st.form("reminder_settings"):
        col1, col2 = st.columns(2)
        
        with col1:
            frequency_options = {
                "Каждый день": 1,
                "Каждые 2 дня": 2,
                "Каждые 3 дня": 3,
                "Еженедельно": 7,
                "Каждые 2 недели": 14
            }
            
            # Находим текущий вариант
            current_option = None
            for option, value in frequency_options.items():
                if value == current_frequency:
                    current_option = option
                    break
            
            if not current_option:
                current_option = f"Каждые {current_frequency} дней"
                frequency_options[current_option] = current_frequency
            
            selected_frequency = st.selectbox(
                "Частота напоминаний о долгах",
                list(frequency_options.keys()),
                index=list(frequency_options.keys()).index(current_option)
            )
        
        with col2:
            # Парсим время
            try:
                time_obj = datetime.strptime(current_time, '%H:%M').time()
            except:
                time_obj = datetime.strptime('17:30', '%H:%M').time()
            
            reminder_time = st.time_input(
                "Время напоминаний",
                value=time_obj
            )
        
        if st.form_submit_button("Сохранить настройки"):
            new_frequency = frequency_options[selected_frequency]
            new_time = reminder_time.strftime('%H:%M')
            
            success = True
            if not db.set_setting('reminder_frequency', str(new_frequency)):
                success = False
            if not db.set_setting('reminder_time', new_time):
                success = False
            
            if success:
                st.success(f"Настройки сохранены: {selected_frequency} в {new_time}")
                st.rerun()
            else:
                st.error("Ошибка при сохранении настроек")
    
    # Настройки бота
    st.subheader("🤖 Информация о боте")
    
    admin_chat_id = db.get_setting('admin_chat_id') or "Не установлен"
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info(f"**ID чата администратора:** {admin_chat_id}")
    
    with col2:
        st.info("**Токен бота:** Настраивается в файле .env")
    
    st.warning("ℹ️ Для изменения токена бота и админ ID отредактируйте файл .env и перезапустите систему.")
    
    # Ссылка на бота
    st.subheader("🔗 Подключение к боту")
    
    bot_url = "https://t.me/MealLunchBot"
    
    st.info(f"**Ссылка на бота:** {bot_url}")
    st.write("Отправьте эту ссылку участникам команды. При переходе по ссылке и нажатии /start пользователи автоматически подключатся к боту.")
    
    # Кнопка для копирования
    st.code(bot_url, language="text")
    
    # Информация о системе
    st.subheader("📊 Информация о системе")
    
    # Статистика базы данных
    users_count = len(db.get_all_users())
    debts_count = len(db.get_open_debts())
    links_count = len(db.get_activation_links())
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Пользователи", users_count)
    
    with col2:
        st.metric("Активные долги", debts_count)
    
    with col3:
        st.metric("Ссылки активации", links_count)

if __name__ == "__main__":
    main() 
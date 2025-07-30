"""
Асинхронная админ-панель на Streamlit для управления системой долгов
"""
import streamlit as st
import pandas as pd
import os
import sys
import asyncio
import requests
import io
from datetime import datetime
from typing import List, Dict, Any
from dotenv import load_dotenv
from st_cookies_manager import EncryptedCookieManager
import pytz
import logging
from PIL import Image

# Загрузка переменных окружения
load_dotenv()

# Добавляем родительскую директорию в путь для импорта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.async_db import AsyncDatabaseManager

# Настройка страницы
st.set_page_config(
    page_title="LunchBOT - Асинхронная админ-панель",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Инициализация асинхронной базы данных
@st.cache_resource
def get_async_db():
    """Получить экземпляр асинхронной базы данных"""
    return AsyncDatabaseManager()

def load_telegram_image(file_id: str, bot_token: str):
    """Загрузить изображение из Telegram по file_id"""
    try:
        # Получаем информацию о файле
        file_info_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
        response = requests.get(file_info_url)
        if response.status_code != 200:
            return None
        
        file_info = response.json()
        if not file_info.get('ok'):
            return None
        
        file_path = file_info['result']['file_path']
        
        # Загружаем файл
        file_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
        image_response = requests.get(file_url)
        if image_response.status_code != 200:
            return None
        
        # Конвертируем в PIL Image
        image = Image.open(io.BytesIO(image_response.content))
        return image
        
    except Exception as e:
        st.error(f"Ошибка загрузки изображения: {e}")
        return None

async def get_db_data():
    """Получить данные из асинхронной БД"""
    db = get_async_db()
    users = await db.get_all_users()
    debts = await db.get_open_debts()
    return users, debts

def format_datetime(dt_string: str) -> str:
    """Форматировать дату и время для отображения в UTC+6 (Asia/Bishkek)"""
    try:
        if not dt_string:
            return "Не указано"
        dt = datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
        # Приводим к UTC+6
        tz = pytz.timezone('Asia/Bishkek')
        if dt.tzinfo is None:
            dt = pytz.utc.localize(dt)
        dt = dt.astimezone(tz)
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return dt_string

def format_status(status: str) -> str:
    """Форматировать статус для отображения"""
    status_map = {
        'Open': '🔴 Открыт',
        'Closed': '✅ Закрыт',
        'Cancelled': '❌ Отменён',
        'Pending': '⏳ В ожидании',
        'Confirmed': '✅ Подтвержден'
    }
    return status_map.get(status, status)

# === ПРОСТАЯ АВТОРИЗАЦИЯ ПО ПАРОЛЮ С COOKIE ===
cookies_secret = os.getenv('COOKIES_SECRET', 'default_secret')
cookie_manager = EncryptedCookieManager(prefix="lunchbot_admin_", password=cookies_secret)
cookie_manager.ready()

def check_password():
    """Проверка пароля для входа в админ-панель (cookie-based)"""
    if not cookie_manager.ready():
        st.warning("Cookie manager не готов. Перезагрузите страницу.")
        st.stop()
    # Проверяем cookie
    if cookie_manager.get("admin_authenticated") == "1":
        st.session_state['admin_authenticated'] = True
        return True
    if 'admin_authenticated' not in st.session_state:
        st.session_state['admin_authenticated'] = False
    if st.session_state['admin_authenticated']:
        cookie_manager["admin_authenticated"] = "1"
        return True
    correct_password = os.getenv('ADMIN_PANEL_PASSWORD')
    st.title('🔒 Вход в асинхронную админ-панель')
    password = st.text_input('Введите пароль', type='password')
    if st.button('Войти'):
        if password == correct_password and password:
            st.session_state['admin_authenticated'] = True
            cookie_manager["admin_authenticated"] = "1"
            st.success('Доступ разрешён!')
            st.experimental_rerun()
        else:
            st.error('Неверный пароль!')
    return False

async def main():
    """Главная функция асинхронной админ-панели"""
    if not check_password():
        st.stop()
    st.title("🍽️ LunchBOT - Асинхронная админ-панель")
    st.markdown("---")
    
    # Получаем данные из асинхронной БД
    users, debts = await get_db_data()
    
    # Сайдбар с навигацией
    st.sidebar.title("📋 Навигация")
    
    pages = {
        "Обзор": "overview",
        "Долги": "debts",
        "Пользователи": "users",
        "QR-коды": "qr_codes",
        "Настройки": "settings"
    }
    page_names = list(pages.keys())
    # Получаем query-параметры
    query_params = st.experimental_get_query_params()
    default_page = query_params.get("page", [page_names[0]])[0]
    if default_page not in page_names:
        default_page = page_names[0]
    # Выбор страницы с сохранением в query-параметрах
    selected_page = st.sidebar.selectbox(
        "Выберите страницу",
        page_names,
        index=page_names.index(default_page),
        key="page_select"
    )
    # Сохраняем выбор в query-параметрах
    st.experimental_set_query_params(page=selected_page)
    # Отображаем выбранную страницу
    if selected_page == "Обзор":
        await show_overview(users, debts)
    elif selected_page == "Долги":
        await show_debts(users, debts)
    elif selected_page == "Пользователи":
        await show_users(users, debts)
    elif selected_page == "QR-коды":
        await show_qr_codes(users)
    elif selected_page == "Настройки":
        await show_settings()

async def show_overview(users: List[Dict], debts: List[Dict]):
    """Показать обзор системы"""
    st.header("📊 Обзор системы")
    
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

async def show_debts(users: List[Dict], debts: List[Dict]):
    """Показать управление долгами"""
    st.header("💰 Управление долгами")
    
    # Вкладки
    tab1, tab2 = st.tabs(["Активные долги", "Создать долг"])
    
    with tab1:
        st.subheader("📋 Активные долги")
        
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
                with st.expander(f"💰 {debt['debtor_name']} → {debt['creditor_name']}: {debt['amount']:.2f} сом."):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Должник:** {debt['debtor_name']}")
                        st.write(f"**Кредитор:** {debt['creditor_name']}")
                        st.write(f"**Сумма:** {debt['amount']:.2f} сом.")
                        st.write(f"**Описание:** {debt['description'] or 'Не указано'}")
                    
                    with col2:
                        st.write(f"**Дата создания:** {format_datetime(debt['created_at'])}")
                        st.write(f"**Статус:** {format_status(debt['status'])}")
                        st.write(f"**Последнее напоминание:** {format_datetime(debt['last_reminder'])}")
                    
                    # Кнопки действий
                    col_btn1, col_btn2 = st.columns(2)
                    
                    with col_btn1:
                        if st.button(f"Закрыть долг", key=f"close_{debt['id']}"):
                            db = get_async_db()
                            if await db.close_debt(debt['id']):
                                st.success("Долг закрыт!")
                                st.rerun()
                            else:
                                st.error("Ошибка при закрытии долга")
        else:
            st.info("Нет активных долгов")
    
    with tab2:
        st.subheader("➕ Создать новый долг")
        
        if len(users) >= 2:
            with st.form("create_debt_form"):
                user_options = {f"{user['first_name']} (@{user['username']})": user['user_id'] for user in users}
                user_names = list(user_options.keys())
                # Инициализация session_state
                if 'selected_debtor' not in st.session_state or st.session_state['selected_debtor'] not in user_names:
                    st.session_state['selected_debtor'] = user_names[0]
                if ('selected_creditor' not in st.session_state or 
                    st.session_state['selected_creditor'] not in user_names):
                    st.session_state['selected_creditor'] = user_names[1] if len(user_names) > 1 else user_names[0]
                col1, col2 = st.columns(2)
                with col1:
                    selected_debtor = st.selectbox(
                        "Должник",
                        user_names,
                        key="debtor_select",
                        index=(user_names.index(st.session_state['selected_debtor']) 
                               if st.session_state['selected_debtor'] in user_names else 0)
                    )
                    st.session_state['selected_debtor'] = selected_debtor
                    debtor_id = user_options[selected_debtor]
                with col2:
                    selected_creditor = st.selectbox(
                        "Кредитор",
                        user_names,
                        key="creditor_select",
                        index=(user_names.index(st.session_state['selected_creditor']) 
                               if st.session_state['selected_creditor'] in user_names else 0)
                    )
                    st.session_state['selected_creditor'] = selected_creditor
                    creditor_id = user_options[selected_creditor]
                amount = st.number_input("Сумма долга", min_value=0.01, value=100.0, step=0.01)
                description = st.text_input("Описание (необязательно)")
                if st.form_submit_button("Создать долг"):
                    if debtor_id == creditor_id:
                        st.error("Должник и кредитор не могут быть одним лицом!")
                    else:
                        db = get_async_db()
                        debt_id = await db.create_debt(debtor_id, creditor_id, amount, description)
                        if debt_id:
                            st.success(f"Долг создан! ID: {debt_id}")
                            st.rerun()
                        else:
                            st.error("Ошибка при создании долга")
        else:
            st.warning("Для создания долга нужно минимум 2 пользователя")

async def show_users(users: List[Dict], debts: List[Dict]):
    """Показать управление пользователями"""
    st.header("👥 Управление пользователями")
    
    if users:
        # Статистика пользователей
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 Статистика по должникам")
            
            # Группируем долги по должникам
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
                    active = st.toggle(
                        "Активен (можно назначать долги)", 
                        value=bool(user['is_active']), 
                        key=f"toggle_active_{user['user_id']}"
                    )
                    if active != bool(user['is_active']):
                        db = get_async_db()
                        if await db.set_user_active(user['user_id'], int(active)):
                            st.success("Статус пользователя обновлён!")
                            st.rerun()
                        else:
                            st.error("Ошибка при обновлении статуса пользователя")
                    # Кнопка для каскадного удаления
                    if st.button(f"Удалить пользователя и все данные", key=f"delete_user_{user['user_id']}"):
                        db = get_async_db()
                        if await db.delete_user_cascade(user['user_id']):
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
                                db = get_async_db()
                                if await db.update_user_name(
                                    user['user_id'], 
                                    new_first_name.strip(), 
                                    new_last_name.strip() or None
                                ):
                                    st.success("Имя обновлено!")
                                    st.rerun()
                                else:
                                    st.error("Ошибка при обновлении имени")
                            else:
                                st.error("Имя не может быть пустым")
    else:
        st.info("Нет зарегистрированных пользователей")

async def show_qr_codes(users: List[Dict]):
    """Показать управление QR-кодами"""
    st.header("📱 Управление QR-кодами")
    
    db = get_async_db()
    
    # Получаем всех пользователей с QR-кодами
    users_with_qr = await db.get_users_with_qr_codes()
    
    if users_with_qr:
        st.subheader("📋 Пользователи с QR-кодами")
        
        # Показываем пользователей с QR-кодами
        for user in users_with_qr:
            display_name = user['first_name'] or user['username'] or f"User {user['user_id']}"
            description = user['qr_code_description'] or "Без описания"
            
            with st.expander(f"📱 {display_name} - {description}"):
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    st.write(f"**User ID:** {user['user_id']}")
                    st.write(f"**Username:** @{user['username'] or 'нет'}")
                    st.write(f"**Описание:** {description}")
                
                with col2:
                    # Показываем QR-код
                    st.subheader("🖼️ QR-код")
                    try:
                        # Получаем токен бота из переменных окружения
                        bot_token = os.getenv('BOT_TOKEN')
                        if bot_token:
                            # Загружаем реальное изображение из Telegram
                            image = load_telegram_image(user['qr_code_file_id'], bot_token)
                            if image:
                                st.image(image, caption=f"QR-код {display_name}", width=200)
                                st.success("✅ QR-код загружен из Telegram")
                            else:
                                # Fallback на placeholder
                                st.image(
                                    "https://via.placeholder.com/200x200/FFFFFF/000000?text=QR+Code",
                                    caption=f"QR-код {display_name} (не удалось загрузить)",
                                    width=200
                                )
                                st.warning("⚠️ Не удалось загрузить QR-код из Telegram")
                        else:
                            st.error("❌ Токен бота не найден")
                    except Exception as e:
                        st.error(f"❌ Ошибка загрузки QR-кода: {e}")
                
                with col3:
                    if st.button(f"Удалить QR-код", key=f"remove_qr_{user['user_id']}"):
                        if await db.remove_user_qr_code(user['user_id']):
                            st.success("QR-код удален!")
                            st.rerun()
                        else:
                            st.error("Ошибка при удалении QR-кода")
    else:
        st.info("Пока никто не добавил QR-коды банков")
    
    st.subheader("ℹ️ Информация о QR-кодах")
    st.write("""
    **Как работают QR-коды в LunchBOT:**
    
    1. **Добавление QR-кода**: Пользователи могут добавить QR-код своего банка через бота
    2. **Просмотр своего QR-кода**: Пользователи могут посмотреть свой QR-код с фото
    3. **Оплата долгов**: При оплате долга должник может получить QR-код кредитора
    4. **Управление**: Пользователи могут удалить или изменить свой QR-код
    5. **Админ-панель**: Администратор может просматривать все QR-коды пользователей
    
    **Поддерживаемые форматы:** JPG, JPEG, PNG
    """)
    
    # Статистика
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Пользователей с QR-кодами", len(users_with_qr))
    
    with col2:
        total_users = len(users)
        qr_coverage = (len(users_with_qr) / total_users * 100) if total_users > 0 else 0
        st.metric("Покрытие QR-кодами", f"{qr_coverage:.1f}%")

async def show_settings():
    """Показать настройки системы"""
    st.header("⚙️ Настройки системы")
    
    db = get_async_db()
    
    # Настройки напоминаний
    st.subheader("⏰ Настройки напоминаний")
    
    current_frequency = int(await db.get_setting('reminder_frequency') or 1)
    current_time = await db.get_setting('reminder_time') or '17:30'
    
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
            except ValueError:
                time_obj = datetime.strptime('17:30', '%H:%M').time()
            
            reminder_time = st.time_input(
                "Время напоминаний",
                value=time_obj
            )
        
        if st.form_submit_button("Сохранить настройки"):
            new_frequency = frequency_options[selected_frequency]
            new_time = reminder_time.strftime('%H:%M')
            
            success = True
            if not await db.set_setting('reminder_frequency', str(new_frequency)):
                success = False
            if not await db.set_setting('reminder_time', new_time):
                success = False
            
            if success:
                st.success(f"Настройки сохранены: {selected_frequency} в {new_time}")
                st.rerun()
            else:
                st.error("Ошибка при сохранении настроек")
    
    # Настройки бота
    st.subheader("🤖 Информация о боте")
    
    admin_chat_id = await db.get_setting('admin_chat_id') or "Не установлен"
    
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
    st.write("Отправьте эту ссылку участникам команды. При переходе по ссылке и нажатии /start "
             "пользователи автоматически подключатся к боту.")
    
    # Кнопка для копирования
    st.code(bot_url, language="text")
    
    # Информация о системе
    st.subheader("📊 Информация о системе")
    
    # Статистика базы данных
    users, debts = await get_db_data()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Пользователи", len(users))
    
    with col2:
        st.metric("Активные долги", len(debts))
    
    with col3:
        st.metric("Асинхронная БД", "✅ Активна")

# Запуск асинхронной админ-панели
if __name__ == "__main__":
    asyncio.run(main()) 
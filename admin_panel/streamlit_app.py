import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
from sqlalchemy.orm import sessionmaker
from db.database import engine
from models.user import User
from models.expense import Expense
from models.transaction import Transaction
from datetime import datetime

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

st.set_page_config(page_title="Lunch Ledger Admin Panel", layout="wide")
st.title("🍽️ Lunch Ledger — Админ-панель")

menu = ["Пользователи", "Расходы", "Транзакции", "Добавить расход", "Назначить дежурного"]
choice = st.sidebar.selectbox("Меню", menu)

with SessionLocal() as db:
    if choice == "Пользователи":
        st.header("👥 Пользователи")
        if st.button("Обновить"): st.rerun()
        users = db.query(User).all()
        st.table([
            {
                "ID": u.id,
                "Telegram ID": u.telegram_id,
                "Username": u.username,
                "Админ": "✅" if u.is_admin else "❌",
                "Дежурный": "✅" if u.is_duty else "❌"
            } for u in users
        ])

    elif choice == "Расходы":
        st.header("💸 Расходы")
        if st.button("Обновить"): st.rerun()
        expenses = db.query(Expense).order_by(Expense.created_at.desc()).all()
        st.table([
            {
                "ID": e.id,
                "Сумма": f"{e.amount:.2f}",
                "Описание": e.description,
                "Дата": e.created_at.strftime("%Y-%m-%d %H:%M"),
                "Дежурный": e.duty_user.username if e.duty_user else "-"
            } for e in expenses
        ])

    elif choice == "Транзакции":
        st.header("🔄 Транзакции")
        if st.button("Обновить"): st.rerun()
        transactions = db.query(Transaction).order_by(Transaction.created_at.desc()).all()
        st.table([
            {
                "ID": t.id,
                "От": t.from_user.username if t.from_user else t.from_user_id,
                "Кому": t.to_user.username if t.to_user else t.to_user_id,
                "Сумма": f"{t.amount:.2f}",
                "Дата": t.created_at.strftime("%Y-%m-%d %H:%M")
            } for t in transactions
        ])

    elif choice == "Добавить расход":
        st.header("➕ Добавить расход")
        if st.button("Обновить"): st.rerun()
        users = db.query(User).all()
        description = st.text_input("Описание")
        amount = st.number_input("Сумма", min_value=0.0, step=0.01)
        duty_user = st.selectbox("Дежурный", users, format_func=lambda u: u.username or str(u.telegram_id))
        if st.button("Добавить"):
            if amount > 0 and description:
                expense = Expense(amount=amount, description=description, duty_user_id=duty_user.id, created_at=datetime.utcnow())
                db.add(expense)
                db.commit()
                st.success("Расход добавлен!")
            else:
                st.error("Заполните все поля!")

    elif choice == "Назначить дежурного":
        st.header("🧑‍🍳 Назначить дежурного")
        if st.button("Обновить"): st.rerun()
        users = db.query(User).all()
        current_duty = db.query(User).filter_by(is_duty=True).first()
        st.write(f"Текущий дежурный: {current_duty.username if current_duty else 'Нет'}")
        new_duty = st.selectbox("Выбрать нового дежурного", users, format_func=lambda u: u.username or str(u.telegram_id))
        if st.button("Назначить"):
            for u in users:
                u.is_duty = (u.id == new_duty.id)
            db.commit()
            st.success(f"{new_duty.username or new_duty.telegram_id} теперь дежурный!") 
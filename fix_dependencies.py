#!/usr/bin/env python3
"""
Скрипт для исправления проблем с зависимостями numpy и pandas
"""
import subprocess
import sys
import os

def run_command(cmd):
    """Выполнить команду и вывести результат"""
    print(f"Выполняется: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.stdout:
        print(f"Вывод: {result.stdout}")
    if result.stderr:
        print(f"Ошибки: {result.stderr}")
    
    return result.returncode == 0

def main():
    """Основная функция для исправления зависимостей"""
    print("🔧 Исправление проблем с зависимостями...")
    print("=" * 50)
    
    # Проверяем виртуальное окружение
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("⚠️  Рекомендуется использовать виртуальное окружение!")
        print("   Создайте его: python3 -m venv venv")
        print("   Активируйте: source venv/bin/activate")
        print()
    
    # Шаг 1: Удаляем проблемные пакеты
    print("1. Удаление проблемных пакетов...")
    packages_to_remove = ['numpy', 'pandas', 'streamlit']
    
    for package in packages_to_remove:
        if not run_command(f"pip uninstall {package} -y"):
            print(f"Не удалось удалить {package} (возможно, он не установлен)")
    
    # Шаг 2: Очищаем кэш pip
    print("\n2. Очистка кэша pip...")
    run_command("pip cache purge")
    
    # Шаг 3: Устанавливаем зависимости из requirements.txt
    print("\n3. Установка зависимостей из requirements.txt...")
    if not run_command("pip install -r requirements.txt"):
        print("❌ Ошибка при установке зависимостей!")
        return False
    
    # Шаг 4: Проверяем установку
    print("\n4. Проверка установки...")
    try:
        import numpy
        import pandas
        import streamlit
        import telebot
        import apscheduler
        
        print("✅ Все основные пакеты установлены успешно!")
        print(f"   NumPy: {numpy.__version__}")
        print(f"   Pandas: {pandas.__version__}")
        print(f"   Streamlit: {streamlit.__version__}")
        print(f"   PyTelegramBotAPI: {telebot.__version__}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        return False

if __name__ == "__main__":
    success = main()
    
    if success:
        print("\n🎉 Зависимости исправлены!")
        print("   Теперь можете запустить: python3 run_all.py")
    else:
        print("\n💥 Не удалось исправить зависимости")
        print("   Попробуйте вручную:")
        print("   1. pip uninstall numpy pandas streamlit -y")
        print("   2. pip install -r requirements.txt")
        
    sys.exit(0 if success else 1) 
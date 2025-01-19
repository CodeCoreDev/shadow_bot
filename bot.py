import json
import asyncio
from zeroconf import ServiceBrowser, Zeroconf, ServiceListener
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Класс для обработки обнаруженных устройств
class MyListener(ServiceListener):
    def __init__(self):
        self.discovered_devices = []

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        if info and name.startswith("eShader_"):
            device = {
                "Hostname": info.name,
                "IPAddress": info.parsed_addresses()[0],
                "Services": info.properties,
                "Id": info.name
            }
            self.discovered_devices.append(device)
            print(f"Discovered device: {device}")

    def remove_service(self, zeroconf, type, name):
        pass

    def update_service(self, zeroconf, type, name):
        pass

# Функция для чтения Telegram токена из config.json
def read_telegram_token():
    try:
        with open('config.json', 'r') as file:
            config = json.load(file)
            return config.get('telegram_token')
    except Exception as ex:
        print(f"Error reading config file: {ex}")
        return None

# Синхронная функция для сканирования устройств
def discover_devices():
    zeroconf = Zeroconf()
    listener = MyListener()
    browser = ServiceBrowser(zeroconf, "_http._tcp.local.", listener)

    try:
        # Сканируем сеть в течение 20 секунд (можно увеличить)
        import time
        time.sleep(20)
    finally:
        zeroconf.close()

    return listener.discovered_devices

# Обработчик команды /scan
async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Сканирование сети началось...")

    # Запуск синхронной функции discover_devices в отдельном потоке
    devices = await asyncio.to_thread(discover_devices)

    if devices:
        response = "Найденные устройства:\n"
        for device in devices:
            response += f"Hostname: {device['Hostname']}, IP: {device['IPAddress']}\n"
    else:
        response = "Устройства не найдены."

    await update.message.reply_text(response)

# Основная функция для запуска бота
def main():
    # Чтение токена из config.json
    telegram_token = read_telegram_token()
    if not telegram_token:
        print("Telegram token not found in config.json.")
        return

    # Создание приложения Telegram бота
    application = Application.builder().token(telegram_token).build()

    # Регистрация обработчика команды /scan
    application.add_handler(CommandHandler("scan", scan_command))

    # Запуск бота
    print("Бот запущен...")
    application.run_polling()

if __name__ == "__main__":
    main()
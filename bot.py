import json
import asyncio
from zeroconf import ServiceBrowser, Zeroconf, ServiceListener
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import paho.mqtt.client as mqtt

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

# Функция для чтения конфигурации из config.json
def read_config():
    try:
        with open('config.json', 'r') as file:
            config = json.load(file)
            return config
    except Exception as ex:
        print(f"Error reading config file: {ex}")
        return None

# Функция для сканирования устройств
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

# Функция для преобразования байтовых строк в обычные строки
def convert_bytes_to_str(data):
    if isinstance(data, bytes):
        return data.decode("utf-8")
    elif isinstance(data, dict):
        return {convert_bytes_to_str(key): convert_bytes_to_str(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [convert_bytes_to_str(item) for item in data]
    else:
        return data

# Функция для подключения к MQTT брокеру
def connect_to_mqtt(config):
    try:
        client = mqtt.Client()

        # Установка имени пользователя и пароля (если они есть)
        if config.get("mqtt_user") and config.get("mqtt_password"):
            client.username_pw_set(config["mqtt_user"], config["mqtt_password"])

        # Подключение к брокеру
        client.connect(config["mqtt_server"], config["mqtt_port"], 60)
        print(f"Connected to MQTT broker at {config['mqtt_server']}:{config['mqtt_port']}")
        return client
    except Exception as ex:
        print(f"Failed to connect to MQTT broker: {ex}")
        return None

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

    # Публикация списка устройств в MQTT
    config = read_config()
    if config:
        mqtt_client = connect_to_mqtt(config)
        if mqtt_client:
            try:
                # Преобразуем байтовые строки в обычные строки
                devices_cleaned = [convert_bytes_to_str(device) for device in devices]
                mqtt_client.publish("devices/found", json.dumps(devices_cleaned))
                print("Список устройств отправлен в MQTT.")
            except Exception as ex:
                print(f"Failed to publish to MQTT: {ex}")
            finally:
                mqtt_client.disconnect()
        else:
            await update.message.reply_text("Ошибка подключения к MQTT брокеру.")

# Основная функция для запуска бота
def main():
    # Чтение конфигурации из config.json
    config = read_config()
    if not config:
        print("Ошибка: Не удалось загрузить конфигурацию из config.json.")
        return

    # Создание приложения Telegram бота
    application = Application.builder().token(config["telegram_token"]).build()

    # Регистрация обработчика команды /scan
    application.add_handler(CommandHandler("scan", scan_command))

    # Запуск бота
    print("Бот запущен...")
    application.run_polling()

if __name__ == "__main__":
    main()
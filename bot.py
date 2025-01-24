import json
import asyncio
from zeroconf import ServiceBrowser, Zeroconf, ServiceListener
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import paho.mqtt.client as mqtt
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MyListener(ServiceListener):
    def __init__(self):
        self.discovered_devices = []

    def add_service(self, zeroconf, type, name):
        logger.info(f"Service {name} of type {type} added")
        info = zeroconf.get_service_info(type, name)
        if info and name.startswith("eShader_"):
            device = {
                "Hostname": info.name,
                "IPAddress": info.parsed_addresses()[0],
                "Services": info.properties,
                "Id": info.name
            }
            self.discovered_devices.append(device)
            logger.info(f"Discovered device: {device}")

    def remove_service(self, zeroconf, type, name):
        pass

    def update_service(self, zeroconf, type, name):
        pass

def read_config():
    try:
        with open('config.json', 'r') as file:
            config = json.load(file)
            # Проверка обязательных ключей
            required_keys = ["telegram_token", "mqtt_server", "mqtt_port"]
            for key in required_keys:
                if key not in config:
                    raise ValueError(f"Missing required key in config: {key}")
            return config
    except Exception as ex:
        logger.error(f"Error reading config file: {ex}")
        return None

async def discover_devices():
    zeroconf = Zeroconf()
    listener = MyListener()
    browser = ServiceBrowser(zeroconf, "_http._tcp.local.", listener)
    try:
        await asyncio.sleep(20)  # Сканирование сети в течение 20 секунд
    finally:
        zeroconf.close()
    return listener.discovered_devices

def convert_bytes_to_str(data):
    if isinstance(data, bytes):
        return data.decode("utf-8")
    elif isinstance(data, dict):
        return {convert_bytes_to_str(key): convert_bytes_to_str(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [convert_bytes_to_str(item) for item in data]
    else:
        return data

def connect_to_mqtt(config):
    try:
        client = mqtt.Client()
        if config.get("mqtt_user") and config.get("mqtt_password"):
            client.username_pw_set(config["mqtt_user"], config["mqtt_password"])
        client.connect(config["mqtt_server"], config["mqtt_port"], 60)
        logger.info(f"Connected to MQTT broker at {config['mqtt_server']}:{config['mqtt_port']}")
        return client
    except Exception as ex:
        logger.error(f"Failed to connect to MQTT broker: {ex}")
        return None

async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Сканирование сети началось...")
    devices = await discover_devices()
    if devices:
        response = "Найденные устройства:\n"
        for device in devices:
            response += f"Hostname: {device['Hostname']}, IP: {device['IPAddress']}\n"
    else:
        response = "Устройства не найдены."
    await update.message.reply_text(response)

    config = read_config()
    if config:
        mqtt_client = connect_to_mqtt(config)
        if mqtt_client:
            try:
                devices_cleaned = [convert_bytes_to_str(device) for device in devices]
                mqtt_client.publish("devices/found", json.dumps(devices_cleaned))
                logger.info("Список устройств отправлен в MQTT.")
            except Exception as ex:
                logger.error(f"Failed to publish to MQTT: {ex}")
            finally:
                mqtt_client.disconnect()
        else:
            await update.message.reply_text("Ошибка подключения к MQTT брокеру.")

def main():
    config = read_config()
    if not config:
        logger.error("Ошибка: Не удалось загрузить конфигурацию из config.json.")
        return

    try:
        application = Application.builder().token(config["telegram_token"]).build()
        application.add_handler(CommandHandler("scan", scan_command))

        async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
            logger.error(msg="Exception while handling an update:", exc_info=context.error)

        application.add_error_handler(error_handler)

        logger.info("Бот запущен...")
        application.run_polling()
    except Exception as e:
        logger.error(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
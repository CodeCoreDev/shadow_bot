import json
import asyncio
from zeroconf import ServiceBrowser, Zeroconf, ServiceListener
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, ExtBot
import paho.mqtt.client as mqtt
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MyListener(ServiceListener):
    def __init__(self):
        self.discovered_devices = []

    def add_service(self, zeroconf, type, name):
        
        """""
        Метод add_service вызывается, когда zeroconf обнаруживает новый сервис.
        Он получает информацию о сервисе, если она доступна,
        и, если сервис начинается с "eShader_", то добавляет его в список
        обнаруженных устройств.
        """

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
    
    """
    Читает конфигурационный файл config.json и возвращает его содержимое в виде словаря.
    Если файл не существует или содержит ошибки, то возвращает None.
    """
    try:
        with open('config.json', 'r') as file:
            config = json.load(file)
            return config
    except Exception as ex:
        logger.error(f"Error reading config file: {ex}")
        return None

def discover_devices():

    """
    Сканирует сеть на предмет обнаружения устройств, опубликовавших сервис "_http._tcp.local.".
    Возвращает список обнаруженных устройств, каждый из которых является словарем,
    содержащим hostname, IP-адрес, список сервисов, предложенных устройством,
    и его идентификатор.
    """
    
    zeroconf = Zeroconf()
    listener = MyListener()
    browser = ServiceBrowser(zeroconf, "_http._tcp.local.", listener)
    try:
        import time
        time.sleep(20)  # Сканирование сети в течение 20 секунд
    finally:
        zeroconf.close()
    return listener.discovered_devices

def convert_bytes_to_str(data):

    """
    Конвертирует байтовые строки, словари и списки, содержащие байтовые строки,
    в строки, раскодированные в utf-8. Если аргумент не является байтами, словарем или списком,
    то возвращает аргумент без изменений.
    """
    
    if isinstance(data, bytes):
        return data.decode("utf-8")
    elif isinstance(data, dict):
        return {convert_bytes_to_str(key): convert_bytes_to_str(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [convert_bytes_to_str(item) for item in data]
    else:
        return data

def connect_to_mqtt(config):

    """
    Подключается к MQTT брокеру, используя параметры, указанные в config.
    Если подключение успешно, то возвращает клиент MQTT. Иначе возвращает None.
    """
    
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
    
    """
    Обработчик команды /scan. Сканирует сеть на предмет обнаружения устройств,
    опубликовавших сервис "_http._tcp.local.". Если устройства найдены,
    то отправляет список устройств в MQTTtopic "devices/found".
    """
    
    await update.message.reply_text("Сканирование сети началось...")
    devices = await asyncio.to_thread(discover_devices)
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

    """
    Главная функция программы. Читает конфигурационный файл config.json,
    создает экземпляр бота и добавляет к нему обработчик команды /scan.
    Если конфигурация не загружена, то выводит ошибку и завершает работу.
    """
    
    config = read_config()
    if not config:
        logger.error("Ошибка: Не удалось загрузить конфигурацию из config.json.")
        return

    try:
        application = Application.builder().token(config["telegram_token"]).build()
        application.add_handler(CommandHandler("scan", scan_command))

        # Добавление обработчиков ошибок
        async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
            logger.error(msg="Exception while handling an update:", exc_info=context.error)

        application.add_error_handler(error_handler)

        logger.info("Бот запущен...")
        application.run_polling()
    except Exception as e:
        logger.error(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
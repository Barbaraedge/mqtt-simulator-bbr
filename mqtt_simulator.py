import json
import logging
import math
import os
import random
import time
from datetime import datetime

import paho.mqtt.client as mqtt

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
LOG_FILE = os.path.join(LOG_DIR, "logs.txt")
os.makedirs(LOG_DIR, exist_ok=True)

log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

file_handler = logging.FileHandler(LOG_FILE)
file_handler.setFormatter(log_formatter)

logging.basicConfig(level=logging.INFO, handlers=[console_handler, file_handler])
logger = logging.getLogger("barbara-mqtt-simulator")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "config.json")

MQTT_URL = os.environ.get("MQTT_SIM_URL", "")
MQTT_PORT = os.environ.get("MQTT_SIM_PORT", "")
MQTT_USER = os.environ.get("MQTT_SIM_USER", "")
MQTT_PASSWORD = os.environ.get("MQTT_SIM_PASSWORD", "")

DEFAULT_TOPIC = "api/v1/barbara/reads"

REQUIRED_ENV_VARS = {
    "MQTT_SIM_URL": MQTT_URL,
    "MQTT_SIM_PORT": MQTT_PORT,
    "MQTT_SIM_USER": MQTT_USER,
    "MQTT_SIM_PASSWORD": MQTT_PASSWORD,
}


def check_env_vars():
    missing = [name for name, value in REQUIRED_ENV_VARS.items() if value == ""]
    for name in missing:
        logger.error("Missing environment variable %s", name)
    return len(missing) == 0


def load_config():
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Could not load configuration file '%s': %s", CONFIG_PATH, exc)
        return None


def validate_fields(config):
    valid_fields = []
    for index, field in enumerate(config.get("fields", [])):
        if "name" not in field or "type" not in field:
            logger.error("Field at position %d is missing 'name' and/or 'type', it will be ignored: %s", index, field)
            continue
        valid_fields.append(field)
    config["fields"] = valid_fields


def get_config_mtime():
    try:
        return os.path.getmtime(CONFIG_PATH)
    except OSError as exc:
        logger.error("Could not check configuration file '%s': %s", CONFIG_PATH, exc)
        return None


def reload_config_if_changed(config, last_mtime):
    current_mtime = get_config_mtime()
    if current_mtime is None or current_mtime == last_mtime:
        return config, last_mtime

    new_config = load_config()
    if new_config is None:
        return config, last_mtime

    validate_fields(new_config)
    apply_log_level(new_config)
    logger.info("Detected a change in '%s', new values have been applied: %s", CONFIG_PATH, new_config)
    return new_config, current_mtime


def apply_log_level(config):
    level_name = config.get("log_level", "INFO")
    level = getattr(logging, level_name.upper(), None)
    if not isinstance(level, int):
        logger.warning("Invalid log level '%s', defaulting to INFO", level_name)
        level = logging.INFO
    logging.getLogger().setLevel(level)


def generate_field_value(field, elapsed_seconds):
    field_type = field.get("type")

    if field_type == "random":
        min_value = field.get("min", 0)
        max_value = field.get("max", 1)
        return random.uniform(min_value, max_value)

    if field_type == "boolean":
        return random.choice([True, False])

    if field_type == "string":
        values = field.get("values", [])
        if not values:
            logger.warning("Field '%s' of type 'string' has no values defined", field.get("name"))
            return ""
        return random.choice(values)

    if field_type == "sine_wave":
        min_value = field.get("min", 0)
        max_value = field.get("max", 1)
        period_seconds = field.get("period_ms", 60000) / 1000.0
        amplitude = (max_value - min_value) / 2
        offset = (max_value + min_value) / 2
        return offset + amplitude * math.sin(2 * math.pi * elapsed_seconds / period_seconds)

    if field_type == "ramp":
        min_value = field.get("min", 0)
        max_value = field.get("max", 1)
        period_seconds = field.get("period_ms", 60000) / 1000.0
        progress = (elapsed_seconds % period_seconds) / period_seconds
        return min_value + (max_value - min_value) * progress

    if field_type == "square_wave":
        min_value = field.get("min", 0)
        max_value = field.get("max", 1)
        period_seconds = field.get("period_ms", 60000) / 1000.0
        duty_cycle = field.get("duty_cycle", 0.5)
        progress = (elapsed_seconds % period_seconds) / period_seconds
        return max_value if progress < duty_cycle else min_value

    logger.warning("Unknown field type '%s' for field '%s'", field_type, field.get("name"))
    return None


def build_message(config, elapsed_seconds):
    data = {}
    for field in config.get("fields", []):
        data[field["name"]] = generate_field_value(field, elapsed_seconds)

    return {
        "data": data,
        "deviceDisplayName": config.get("device_display_name", "barbara-mqtt-simulator"),
        "error": False,
        "errorDescription": "",
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("Successfully connected to the MQTT broker")
    else:
        logger.error("Failed to connect to the MQTT broker (code %s)", rc)


def on_disconnect(client, userdata, rc):
    if rc == 0:
        logger.info("Cleanly disconnected from the MQTT broker")
    else:
        logger.warning("Unexpected disconnection from the MQTT broker (code %s)", rc)


def main():
    config = load_config()
    if config is None:
        return
    apply_log_level(config)
    validate_fields(config)

    if not check_env_vars():
        logger.error("Cannot continue, required environment variables are missing")
        return

    client = mqtt.Client()
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    try:
        client.connect(MQTT_URL, int(MQTT_PORT))
    except (ValueError, OSError) as exc:
        logger.error("Could not connect to the MQTT broker: %s", exc)
        return

    client.loop_start()
    time.sleep(1)

    last_mtime = get_config_mtime()
    start_time = time.time()

    try:
        while True:
            config, last_mtime = reload_config_if_changed(config, last_mtime)

            topic = config.get("topic", DEFAULT_TOPIC)
            elapsed_seconds = time.time() - start_time
            message = build_message(config, elapsed_seconds)
            client.publish(topic, json.dumps(message))
            logger.info("Message published to topic '%s': %s", topic, message)

            interval_seconds = config.get("publish_interval_ms", 5000) / 1000.0
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        logger.info("Simulation stopped by the user")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()

# Barbara MQTT Simulator

A lightweight simulator of an IoT device that connects to an MQTT broker and
periodically publishes status messages to a fixed topic. Payload values are
configurable (random numbers, booleans, strings, or periodic signals such as
sine wave, ramp, or square wave) via a configuration file that is hot-reloaded
at runtime, with no need to restart the service.

> This repository is also used for the **Barbara Certification, Level 2
> (Application Development)** practice. See
> [`Barbara Certification Practice. Level 2.md`](./Barbara%20Certification%20Practice.%20Level%202.md)
> for the step-by-step exercise.

## How it works

1. On startup, the script:
   - Loads `config/config.json`.
   - Applies the log level specified in the configuration.
   - Validates the configured fields (fields missing `name` and/or `type` are
     discarded).
   - Checks that the required connection environment variables are set.
   - Connects to the MQTT broker.
2. Every `publish_interval_ms` milliseconds:
   - Checks whether `config/config.json` has changed (based on its
     modification time) and, if so, hot-reloads the configuration and logs
     the change.
   - Builds a message using the fields defined in `fields`.
   - Publishes the message to the topic defined by `topic`.
3. The process runs in an infinite loop until it is stopped (`Ctrl+C` or
   container shutdown), at which point it disconnects from the broker
   gracefully.

### Published message format

```json
{
  "data": {
    "pollution_particles": 0.337,
    "alert": false,
    "status": "OK",
    "temperature": 21.3,
    "tank_level": 42.0,
    "pump_state": 1
  },
  "deviceDisplayName": "barbara-mqtt-simulator",
  "error": false,
  "errorDescription": "",
  "timestamp": "2026-07-16T12:01:52"
}
```

The contents of `data` depend on the fields defined in the configuration. The
remaining payload fields (`deviceDisplayName`, `error`, `errorDescription`,
`timestamp`) are fixed, except for `deviceDisplayName`, which is also
configurable.

## Environment variables

Required for connecting to the MQTT broker. All default to an empty string;
if any is missing, the script logs it and does not start.

| Variable            | Description                  |
|----------------------|-------------------------------|
| `MQTT_SIM_URL`       | MQTT broker host/URL          |
| `MQTT_SIM_PORT`      | Broker connection port         |
| `MQTT_SIM_USER`      | Connection username             |
| `MQTT_SIM_PASSWORD`  | Connection password             |

The `secrets.txt` file contains a template with these variables to fill in
locally (used by `docker-compose-local.yml` as an `env_file`).

## Configuration (`config/config.json`)

| Field                 | Type    | Description                                                  |
|-----------------------|---------|----------------------------------------------------------------|
| `log_level`           | string  | Minimum log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, ...)   |
| `device_display_name` | string  | Value of the payload's `deviceDisplayName` field               |
| `topic`               | string  | MQTT topic the messages are published to                        |
| `publish_interval_ms` | number  | Publishing interval, in milliseconds                            |
| `fields`              | array   | List of fields to include in `data` (see below)                 |

Each entry in `fields` requires at least `name` and `type`. Fields missing
either attribute are ignored (an error is logged). Supported types:

| `type`            | Additional parameters                            | Behavior                                                                |
|-------------------|----------------------------------------------------|---------------------------------------------------------------------------|
| `random`          | `min`, `max`                                        | Uniform random number between `min` and `max`                            |
| `boolean`         | —                                                    | Random `true`/`false`                                                    |
| `string`          | `values` (list)                                     | Randomly picks one of the given values                                   |
| `sine_wave`       | `min`, `max`, `period_ms`                           | Sine wave between `min` and `max` with period `period_ms`                |
| `ramp`            | `min`, `max`, `period_ms`                           | Sawtooth wave: rises from `min` to `max` over `period_ms`, then resets   |
| `square_wave`     | `min`, `max`, `period_ms`, `duty_cycle` (default 0.5) | Alternates between `max` and `min`; `duty_cycle` is the fraction of the cycle spent at `max` |

Periodic signals (`sine_wave`, `ramp`, `square_wave`) are computed based on
elapsed time since the script started, not on the number of messages sent.

Example configuration:

```json
{
  "log_level": "INFO",
  "device_display_name": "barbara-mqtt-simulator",
  "topic": "api/v1/barbara/reads",
  "publish_interval_ms": 5000,
  "fields": [
    { "name": "pollution_particles", "type": "random", "min": 0, "max": 1 },
    { "name": "alert", "type": "boolean" },
    { "name": "status", "type": "string", "values": ["OK", "WARNING", "ERROR"] },
    { "name": "temperature", "type": "sine_wave", "min": 15, "max": 25, "period_ms": 60000 },
    { "name": "tank_level", "type": "ramp", "min": 0, "max": 100, "period_ms": 30000 },
    { "name": "pump_state", "type": "square_wave", "min": 0, "max": 1, "period_ms": 10000, "duty_cycle": 0.5 }
  ]
}
```

### Hot reload

On every publishing cycle, the script checks whether `config/config.json` has
changed (based on its modification time). If a valid change is detected, all
parameters (log level, `device_display_name`, `topic`, `publish_interval_ms`,
`fields`) are reloaded with no need to restart the process, and a log entry indicates
that new values have been applied. If the modified file contains invalid
JSON, the previous configuration is kept and the reload is retried on the
next cycle.

## Logs

Logs are printed to the console and also written to `logs/logs.txt` (the
directory is created automatically if it does not exist). The minimum level
shown is controlled by `log_level` in `config/config.json`.

## Running locally (without Docker)

Requirements: Python 3.x and the `paho-mqtt` library.

```bash
pip install -r requirements.txt

export MQTT_SIM_URL=broker.example.com
export MQTT_SIM_PORT=1883
export MQTT_SIM_USER=user
export MQTT_SIM_PASSWORD=password

python mqtt_simulator.py
```

## Running with Docker Compose (recommended for local use)

1. Copy `secrets.txt.example` to `secrets.txt` and fill it in with the actual
   connection values:

   ```bash
   cp secrets.txt.example secrets.txt
   ```

   ```
   MQTT_SIM_URL=broker.example.com
   MQTT_SIM_PORT=1883
   MQTT_SIM_USER=user
   MQTT_SIM_PASSWORD=password
   ```

2. Start the service:

   ```bash
   docker compose -f docker-compose-local.yml up --build
   ```

`docker-compose-local.yml` mounts `config/` and `logs/` as volumes, so you can
edit `config/config.json` while the container is running (changes are
hot-reloaded, see above) and inspect `logs/logs.txt` from the host without
entering the container.

To stop the service:

```bash
docker compose -f docker-compose-local.yml down
```

> **Security note:** `secrets.txt` will contain real credentials once filled
> in and is listed in `.gitignore`, so it is never committed. Only
> `secrets.txt.example` (with empty placeholder values) is tracked in the
> repository.

## Project structure

```
.
├── mqtt_simulator.py          # Main script
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Docker image (python:3.12-alpine)
├── docker-compose-local.yml   # Local startup via docker compose
├── secrets.txt.example        # Template for local environment variables
├── secrets.txt                # Local credentials (gitignored, not tracked)
├── config/
│   └── config.json            # Simulation configuration
└── logs/
    └── logs.txt                # Logs generated at runtime (gitignored, not tracked)
```

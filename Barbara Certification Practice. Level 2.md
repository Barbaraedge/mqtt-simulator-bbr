# Barbara Certification Practice — Level 2 (Application Development)

This practice walks you through taking the **Barbara MQTT Simulator** — a
Docker app that already runs locally — and turning it into a proper Barbara
Edge app: reading its configuration from **App Config**, its credentials from
**Global Secrets**, talking to other Marketplace apps over the node's
internal network, and running under explicit resource limits/reservations.

By the end of the practice you will have:

- Adapted the simulator's code to read the Barbara App Config and Global
  Secrets mechanisms instead of local files/env files.
- Written an edge-ready `docker-compose.yaml`, evolving it step by step
  (named volume, network, resource limits, resource reservations).
- Deployed an MQTT Broker and a Web File Browser from the Barbara
  Marketplace, and wired the simulator to both.
- Verified end-to-end delivery of messages with MQTT Explorer and verified
  the log file is visible through Web File Browser.

## Prerequisites

- Access to a **Barbara Panel** account with a licensed, online Edge Node.
- [MQTT Explorer](http://mqtt-explorer.com/) installed on your workstation.
- `git` installed locally.
- This repository cloned (see Step 1) and a text editor.

## Key Barbara concepts used in this practice

| Concept | What it is | How it reaches the container |
|---|---|---|
| **App Config** | Non-sensitive, workload-scoped configuration, edited in the *Config* segment of the workload card. Live-reloaded: a new value pushed from Panel is picked up the next time the app re-reads the file, no restart needed. | Written by the platform as `/appconfig/appconfig.json` inside the container, once the compose file bind-mounts `./appconfig/:/appconfig/`. |
| **Global Config** | Same idea as App Config, but shared by every workload on the node. | `/appconfig/global.json`, same mount. |
| **Global Secrets** | Sensitive, node-wide values (credentials, hosts, ports) configured once from the *Secrets* card on the Node Details page. | Automatically exposed as environment variables with the same name in every container that loads the `.barbara_env` file via `env_file` in the compose. No `${...}` interpolation needed. |
| **`barbaraServices` network** | A pre-existing bridge network on every node that lets Marketplace apps reach each other by service name instead of by IP. | Joined by declaring an external-style network named `barbaraServices` in the compose file. |
| **External volumes** | Named Docker volumes that outlive a single app and can be mounted by more than one independent compose stack — the mechanism used to share data (e.g. our log file) between two unrelated apps. | Declared `external: true` in the compose and pre-created on the node before deployment. |

With that in mind, here are the steps.

---

## Step 1 — Clone the repository

```bash
git clone git@github.com:Barbaraedge/mqtt-simulator-bbr.git
cd mqtt-simulator-bbr
```

This gives you the working local version of the simulator (`mqtt_simulator.py`,
`config/config.json`, `Dockerfile`, `docker-compose-local.yml`, `secrets.txt.example`)
as documented in `README.md`. The rest of this practice adapts it for the Edge Node.

---

## Step 2 — Adapt the code to use App Config and Global Secrets

**Global Secrets require no code change.** The app already reads its
connection parameters from environment variables:

```python
MQTT_URL = os.environ.get("MQTT_SIM_URL", "")
MQTT_PORT = os.environ.get("MQTT_SIM_PORT", "")
MQTT_USER = os.environ.get("MQTT_SIM_USER", "")
MQTT_PASSWORD = os.environ.get("MQTT_SIM_PASSWORD", "")
```

Since Barbara injects every Global Secret as an environment variable with the
exact same name, all you need to do later (Step 7) is define four Global
Secrets on the node called `MQTT_SIM_URL`, `MQTT_SIM_PORT`, `MQTT_SIM_USER`
and `MQTT_SIM_PASSWORD`.

**App Config does require a small change.** Today the app always reads its
configuration from a file bundled in the repo:

```python
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "config.json")
```

On the Edge Node, this configuration must instead come from
`/appconfig/appconfig.json`, the path where Barbara surfaces the App Config
you edit from the workload card. Change `mqtt_simulator.py` to read the path
from an environment variable, defaulting to the App Config location, so the
same image can still be pointed at the bundled file for local testing if
needed:

```python
CONFIG_PATH = os.environ.get(
    "BARBARA_APPCONFIG_PATH",
    "/appconfig/appconfig.json",
)
```

No other change is required: `load_config`, `validate_fields`,
`get_config_mtime` and `reload_config_if_changed` already poll the file's
modification time and reload it in place, which is exactly how Barbara's
"live reload" of App Config works — a new value pushed from Panel changes the
file on disk, and the existing hot-reload loop in `mqtt_simulator.py` picks
it up on its own, with no extra code needed.

---

## Step 3 — Create a docker-compose for the edge node

Barbara packages a Docker app as a zip containing, at minimum, a
`docker-compose.yaml` at its root. Bind mounts are only accepted when the
host-side path starts with `./persist/`, `./appconfig` or `./sys/` — root
paths and `..` are rejected. Create `docker-compose.yaml` with the minimum
needed to receive App Config and Global Secrets:

```yaml
version: "3.3"
services:
  mqtt-simulator:
    build: .
    volumes:
      - "./appconfig/:/appconfig/"
      - "./persist/:/persist/"
    env_file:
      - .barbara_env
```

`./appconfig/:/appconfig/` is what makes `/appconfig/appconfig.json` (Step 2)
appear inside the container, and `env_file: .barbara_env` is what makes the
Global Secrets defined on the node (Step 7) appear as environment variables.

---

## Step 4 — Add a named volume for the log file

The app writes `logs/logs.txt` relative to its working directory, which is
`/app` inside the image (see the `Dockerfile`), i.e. `/app/logs/logs.txt`.
To make that file visible to another, independent app later (Web File
Browser, Step 9), back it with an **external** named volume instead of a
plain bind mount:

```yaml
services:
  mqtt-simulator:
    build: .
    volumes:
      - "./appconfig/:/appconfig/"
      - "./persist/:/persist/"
      - "mqtt-simulator-data:/app/logs"
    env_file:
      - .barbara_env

volumes:
  mqtt-simulator-data:
    external: true
```

`external: true` tells Compose the volume already exists and must not be
created automatically — so before deploying, create it once from the
**Docker Volumes** card on the Node Details page (name it exactly
`mqtt-simulator-data`). This is what lets Web File Browser mount the very
same volume in Step 9 and read the log file the simulator writes.

---

## Step 5 — Configure the network so the app can reach other Marketplace apps

Join the pre-existing `barbaraServices` bridge network, which every
Marketplace app on the node is attached to. This lets the simulator reach the
MQTT broker you'll deploy in Step 6 by its service name, instead of an IP
address:

```yaml
services:
  mqtt-simulator:
    build: .
    volumes:
      - "./appconfig/:/appconfig/"
      - "./persist/:/persist/"
      - "mqtt-simulator-data:/app/logs"
    env_file:
      - .barbara_env
    networks:
      - barbaraServices

volumes:
  mqtt-simulator-data:
    external: true

networks:
  barbaraServices:
    driver: bridge
    name: barbaraServices
```

---

## Step 6 — Deploy an MQTT broker on the edge node

From Barbara Panel, open the target Edge Node, go to the **Marketplace**,
search for the **MQTT Broker** app, and deploy it with a few clicks. Once the
workload reports `Running`, note down from its workload card:

- Its **service name** on `barbaraServices` (this is the hostname the
  simulator will use, e.g. `mqttbbr`).
- The **port** it listens on.
- The **username/password** it was configured with, if authentication is
  enabled.

You will use these four values in the next step.

---

## Step 7 — Configure Global Secrets and App Config, then deploy the simulator

1. **Global Secrets** — On the Node Details page, open the **Secrets** card
   and add four Global Secrets matching the environment variables the app
   already reads:

   | Secret name | Value |
   |---|---|
   | `MQTT_SIM_URL` | Broker service name from Step 6 (e.g. `mqttbbr`) |
   | `MQTT_SIM_PORT` | Broker port from Step 6 |
   | `MQTT_SIM_USER` | Broker username from Step 6 |
   | `MQTT_SIM_PASSWORD` | Broker password from Step 6 |

   These become environment variables in every container on the node —
   including `mqtt-simulator`, via the `.barbara_env` file wired in Step 3 —
   with no further compose changes needed.

2. **App Config** — Zip the repository (with `docker-compose.yaml` at its
   root) and upload it to the App Library, then deploy it onto the node like
   any other app. On its workload card, open the **Config** segment and
   paste the same JSON structure documented in `README.md`
   (`log_level`, `device_display_name`, `topic`, `publish_interval_ms`,
   `fields`). This is exactly the payload `mqtt_simulator.py` will read from
   `/appconfig/appconfig.json` after the Step 2 code change.

3. Save, deploy (or redeploy) the `mqtt-simulator` workload, and check its
   logs panel for `Successfully connected to the MQTT broker`.

---

## Step 8 — Verify delivery with MQTT Explorer

Open MQTT Explorer and connect to the broker deployed in Step 6, using the
same host/port/credentials you configured as Global Secrets. Subscribe to the
topic configured in App Config (`api/v1/barbara/reads` by default) and
confirm that a new JSON message arrives every `publish_interval_ms`
milliseconds, matching the format documented in `README.md`.

---

## Step 9 — Deploy Web File Browser and inspect the logs

1. From the Marketplace, deploy the **Web File Browser** app onto the same
   node.
2. Configure it to mount the `mqtt-simulator-data` external volume created in
   Step 4 (the same way the simulator does, e.g. mapped to `/srv` inside the
   Web File Browser container).
3. Open the Web File Browser UI, navigate to `logs.txt`, and confirm it
   contains the same log lines the simulator is writing (connection status,
   published messages, any App Config reload notifications).

---

## Step 10 — Add resource limits

Edit `docker-compose.yaml` again and cap how much CPU and RAM the workload
may use: **70% of one CPU core** and **512 MB of RAM**. `cpus` is expressed
as a fraction of a single core, and `memory` uses Docker's `M`/`G` suffixes:

```yaml
services:
  mqtt-simulator:
    build: .
    volumes:
      - "./appconfig/:/appconfig/"
      - "./persist/:/persist/"
      - "mqtt-simulator-data:/app/logs"
    env_file:
      - .barbara_env
    networks:
      - barbaraServices
    deploy:
      resources:
        limits:
          cpus: "0.7"
          memory: "512M"

volumes:
  mqtt-simulator-data:
    external: true

networks:
  barbaraServices:
    driver: bridge
    name: barbaraServices
```

A limit is a hard ceiling: the container is throttled at 70% of a core, and
killed by the kernel if it tries to use more than 512 MB of RAM.

---

## Step 11 — Add resource reservations

Edit `docker-compose.yaml` once more and add reservations of **40% of one CPU
core** and **256 MB of RAM** — the soft floor the scheduler guarantees the
workload even when the node is busy:

```yaml
    deploy:
      resources:
        limits:
          cpus: "0.7"
          memory: "512M"
        reservations:
          cpus: "0.4"
          memory: "256M"
```

---

## Final `docker-compose.yaml`

For reference, this is what the file should look like after all the steps
above:

```yaml
version: "3.3"
services:
  mqtt-simulator:
    build: .
    volumes:
      - "./appconfig/:/appconfig/"
      - "./persist/:/persist/"
      - "mqtt-simulator-data:/app/logs"
    env_file:
      - .barbara_env
    networks:
      - barbaraServices
    deploy:
      resources:
        limits:
          cpus: "0.7"
          memory: "512M"
        reservations:
          cpus: "0.4"
          memory: "256M"

volumes:
  mqtt-simulator-data:
    external: true

networks:
  barbaraServices:
    driver: bridge
    name: barbaraServices
```

## Checklist

- [ ] Repository cloned.
- [ ] `CONFIG_PATH` reads from `/appconfig/appconfig.json` by default.
- [ ] `docker-compose.yaml` created, mounting `./appconfig/` and `./persist/`,
      loading `.barbara_env`.
- [ ] `mqtt-simulator-data` external volume created on the node and mounted
      at `/app/logs`.
- [ ] `mqtt-simulator` joined to the `barbaraServices` network.
- [ ] MQTT Broker deployed from the Marketplace.
- [ ] Global Secrets (`MQTT_SIM_URL`, `MQTT_SIM_PORT`, `MQTT_SIM_USER`,
      `MQTT_SIM_PASSWORD`) and App Config configured; `mqtt-simulator`
      deployed and connected.
- [ ] Messages observed arriving at the broker via MQTT Explorer.
- [ ] Web File Browser deployed, mounted on `mqtt-simulator-data`, and
      `logs.txt` inspected successfully.
- [ ] Resource limits (`0.7` CPU / `512M` RAM) added.
- [ ] Resource reservations (`0.4` CPU / `256M` RAM) added.

# Barbara Certification Practice — Level 2 (Application Development)

This practice takes the **Barbara MQTT Simulator**, which currently runs
only as a local Docker app, and turns it into a real Barbara Edge app:
configured through App Config and Global Secrets, deployed on an Edge Node
alongside other Marketplace apps, and running under explicit resource
constraints.

## Prerequisites

- Access to a **Barbara Panel** account with a licensed, online Edge Node.
- [MQTT Explorer](http://mqtt-explorer.com/) installed on your workstation.
- `git` installed locally.

## Steps

1. **Clone the repository**: `git@github.com:Barbaraedge/mqtt-simulator-bbr.git`.

2. **Adapt the Python code** so that it reads its configuration from the
   node's **App Config** and its connection credentials from **Global
   Secrets**, instead of the local `config.json` file and `secrets.txt` used
   so far.

3. **Create a `docker-compose.yaml`** to deploy the app on the Edge Node.

4. **Add a named volume** called `mqtt-simulator-data` to the compose, to
   persist the app's log file.

5. **Configure the service's network** in the compose so the app can communicate with other Marketplace apps on the node.

6. **Deploy an MQTT broker** on the Edge Node from the Marketplace.

7. **Configure the Global Secrets and App Config and deploy the simulator** correctly so it connects to the broker from Step 6.

8. **Verify with MQTT Explorer** that messages are correctly arriving at the
   broker.

9. **Deploy the "Web File Browser"** Marketplace app and configure it to
   access the `mqtt-simulator-data` volume. Open its interface, locate
   `logs.txt`, and confirm the app's logs are being stored there.

10. **Add resource limits** to the app in the compose: **CPU: 70%**,
    **RAM: 512 MB**.

11. **Add resource reservations** to the app in the compose: **CPU: 40%**,
    **RAM: 256 MB**.

## Definition of done

- The simulator runs as a Marketplace-style app on the Edge Node, reading
  its configuration exclusively from App Config and Global Secrets.
- It exchanges messages with a broker also deployed on the node, confirmed
  via MQTT Explorer.
- Its log file persists in a named volume and is readable from Web File
  Browser.
- The compose enforces the specified CPU/RAM limits and reservations.

## Evidence of Completion

To validate this practice, send the following artifacts to
**certifications@barbara.tech**:

- The final `docker-compose.yaml` used to deploy the app on the Edge Node.
- The `logs.txt` file, downloaded from the Web File Browser interface.

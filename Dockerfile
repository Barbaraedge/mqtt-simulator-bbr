FROM python:3.12-alpine

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mqtt_simulator.py .
COPY config ./config

CMD ["python", "mqtt_simulator.py"]

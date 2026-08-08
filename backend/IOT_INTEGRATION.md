# IoT Integration Guide: MQTT Sensor Telemetry

This guide explains how field engineers can configure physical sensors (e.g., LoRaWAN gateways, NB-IoT nodes) to stream telemetry data directly into the Su-AI backend via MQTT.

## 1. Connection Details
The backend listens for sensor data using an MQTT broker.
By default (local development), the details are:
- **Host**: `localhost` (or your server's IP address)
- **Port**: `1883`

> [!IMPORTANT]
> **Production Security Note**: For production deployments, you MUST configure your Mosquitto broker to use TLS (Port 8883) and require Username/Password authentication. Never transmit unencrypted sensor data over the public internet.

## 2. Topic Structure
Sensors must publish their data to the following topic pattern:
`su-ai/stations/{station_id}/measurements`

Replace `{station_id}` with the numeric ID of the station in the database.
Example: `su-ai/stations/1/measurements`

## 3. Payload Schema
The payload must be a valid JSON object.

### Fields
- `station_id` (Integer, Required): Must match the `{station_id}` in the topic.
- `pH` (Float, Optional): 0.0 to 14.0.
- `chlorine` (Float, Optional): Free chlorine in mg/L.
- `turbidity` (Float, Optional): Turbidity in NTU.
- `conductivity` (Float, Optional): Conductivity in µS/cm.
- `temperature` (Float, Optional): Water temperature in °C.
- `timestamp` (String, Optional): ISO-8601 formatted timestamp. If omitted, the server time is used.

### Example JSON Payload
```json
{
  "station_id": 1,
  "pH": 7.4,
  "chlorine": 0.8,
  "turbidity": 0.4,
  "conductivity": 350.5,
  "temperature": 18.2,
  "timestamp": "2026-08-08T10:00:00Z"
}
```

## 4. How the Data is Processed
When a sensor publishes to this topic, the backend immediately:
1. Validates the JSON schema.
2. Cross-references the `station_id` with the internal database.
3. Inserts the measurement into the `su_olcumleri` table with the note: `[MQTT] Otomatik sensör verisi`.
4. Runs the rule engine to determine the `risk_seviyesi` (NORMAL, DÜŞÜK, ORTA, KRİTİK).
5. Triggers the asynchronous LLM analysis pipeline to evaluate anomalies and provide technical recommendations.

## 5. Testing with the Built-in Simulator
You can test the MQTT ingestion pipeline without physical hardware using the backend's built-in simulator.

Send a POST request to the API:
```bash
curl -X POST "http://localhost:8000/api/sim/tetikle?istasyon_id=1&mod=karisik&use_mqtt=true" \
     -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```
By appending `use_mqtt=true`, the simulator will generate a fake JSON payload and publish it to the broker instead of directly inserting it into the database, allowing you to load-test the MQTT flow.

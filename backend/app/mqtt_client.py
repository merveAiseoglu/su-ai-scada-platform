import asyncio
import json
import logging
import os

import paho.mqtt.client as mqtt
from pydantic import ValidationError
from sqlalchemy.future import select

from app.database import SessionLocal
from app.engine import hesapla_anomali_durumu
from app.llm_service import arka_planda_analiz_et
from app.metrics import mqtt_message_counter
from app.models import Istasyon, SuOlcumu
from app.schemas import MqttPayload

logger = logging.getLogger(__name__)


async def process_mqtt_payload(payload: MqttPayload):
    """Async pipeline for processing the validated MQTT payload."""
    async with SessionLocal() as db:
        # 1. Validate station
        result = await db.execute(select(Istasyon).filter(Istasyon.id == payload.station_id))
        istasyon = result.scalars().first()
        if not istasyon:
            logger.warning(f"[MQTT] Station {payload.station_id} not found in DB. Dropping message.")
            return

        # 2. Insert SuOlcumu
        db_olcum = SuOlcumu(
            istasyon_id=payload.station_id,
            ph=payload.pH,
            serbest_klor=payload.chlorine,
            bulaniklik=payload.turbidity,
            iletkenlik=payload.conductivity,
            sicaklik=payload.temperature,
            personel_notu="[MQTT] Otomatik sensör verisi",
        )
        db.add(db_olcum)
        await db.commit()
        await db.refresh(db_olcum)

        # 3. Rule Engine
        analiz_girdisi = {
            "ph": db_olcum.ph,
            "serbest_klor": db_olcum.serbest_klor,
            "bulaniklik": db_olcum.bulaniklik,
            "iletkenlik": db_olcum.iletkenlik,
            "sicaklik": db_olcum.sicaklik,
        }
        kural_motoru_sonucu = await hesapla_anomali_durumu(db, analiz_girdisi)

        db_olcum.risk_seviyesi = kural_motoru_sonucu.get("en_yuksek_risk_seviyesi", "NORMAL")
        await db.commit()
        await db.refresh(db_olcum)

        olcum_id = db_olcum.id

        # Alert Notifications
        if db_olcum.risk_seviyesi == "KRİTİK":
            from app.notification_service import dispatch_critical_alerts

            asyncio.create_task(dispatch_critical_alerts(olcum_id, SessionLocal))

    # 4. Trigger LLM Analysis Background Task
    # We await it here since we are inside a dedicated asyncio.run() loop for this message.
    # We close the previous db session so arka_planda_analiz_et can open its own cleanly.
    await arka_planda_analiz_et(olcum_id, SessionLocal)


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("[MQTT] Connected to broker successfully.")
        client.subscribe("su-ai/stations/+/measurements")
    else:
        logger.error(f"[MQTT] Failed to connect, return code {rc}")


def on_message(client, userdata, msg):
    try:
        raw_data = json.loads(msg.payload.decode("utf-8"))
        payload = MqttPayload(**raw_data)
        logger.info(f"[MQTT] Received valid payload for station {payload.station_id}")
        mqtt_message_counter.labels(status="valid").inc()

        # Bridge to async FastAPI world
        asyncio.run(process_mqtt_payload(payload))

    except json.JSONDecodeError:
        mqtt_message_counter.labels(status="malformed").inc()
        logger.error(f"[MQTT] Malformed JSON received on {msg.topic}: {msg.payload}")
    except ValidationError as e:
        mqtt_message_counter.labels(status="malformed").inc()
        logger.error(f"[MQTT] Validation error for payload on {msg.topic}: {e.errors()}")
    except Exception as e:
        mqtt_message_counter.labels(status="malformed").inc()
        logger.error(f"[MQTT] Unexpected error processing message on {msg.topic}: {e}")


def get_mqtt_client():
    host = os.getenv("MQTT_BROKER_HOST", "localhost")
    port = int(os.getenv("MQTT_BROKER_PORT", "1883"))

    client = mqtt.Client(client_id="su-ai-backend")
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(host, port, 60)
        return client
    except Exception as e:
        logger.warning(f"[MQTT] Could not connect to broker at {host}:{port}: {e}")
        return None

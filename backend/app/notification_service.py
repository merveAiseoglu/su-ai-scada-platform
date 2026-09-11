import asyncio
import logging
import os
from email.message import EmailMessage

import aiosmtplib
import firebase_admin
from firebase_admin import credentials, messaging
from sqlalchemy.future import select

from app.models import Istasyon, Kullanici, SuOlcumu

logger = logging.getLogger(__name__)

# Initialize Firebase (Graceful failure)
firebase_cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "")
firebase_app = None

if firebase_cred_path and os.path.exists(firebase_cred_path):
    try:
        cred = credentials.Certificate(firebase_cred_path)
        firebase_app = firebase_admin.initialize_app(cred)
        logger.info("[NOTIFICATION] Firebase Admin initialized successfully.")
    except Exception as e:
        logger.error(f"[NOTIFICATION] Failed to initialize Firebase: {e}")
else:
    logger.warning("[NOTIFICATION] Firebase credentials not found. Push notifications will be skipped.")


async def send_push_notification(user_tokens: list[str], title: str, body: str):
    if not firebase_app:
        logger.warning("[NOTIFICATION] Skipping push notification; Firebase not initialized.")
        return

    if not user_tokens:
        return

    try:
        # We can send multicasts in Firebase
        # Note: messaging.send_multicast is synchronous, so we run it in a thread
        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            tokens=user_tokens,
        )
        response = await asyncio.to_thread(messaging.send_multicast, message)
        logger.info(f"[NOTIFICATION] Successfully sent push to {response.success_count} devices.")
        if response.failure_count > 0:
            logger.warning(f"[NOTIFICATION] Failed to send push to {response.failure_count} devices.")
    except Exception as e:
        logger.error(f"[NOTIFICATION] Push notification failed: {e}")


async def send_email_alert(recipients: list[str], subject: str, body: str):
    if not recipients:
        return

    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if not smtp_host or not smtp_user or not smtp_password:
        logger.warning("[NOTIFICATION] SMTP settings missing. Skipping email alert.")
        return

    message = EmailMessage()
    message["From"] = smtp_user
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    message.set_content(body)

    try:
        await aiosmtplib.send(
            message,
            hostname=smtp_host,
            port=smtp_port,
            start_tls=True,
            username=smtp_user,
            password=smtp_password,
        )
        logger.info(f"[NOTIFICATION] Successfully sent email to {len(recipients)} recipients.")
    except Exception as e:
        logger.error(f"[NOTIFICATION] Email sending failed: {e}")


async def dispatch_critical_alerts(olcum_id: int, db_factory):
    """
    Background worker that fetches admins and sends them push/email
    alerts regarding a CRITICAL anomaly.
    """
    try:
        async with db_factory() as db:
            # Get Measurement and Station
            result = await db.execute(select(SuOlcumu).filter(SuOlcumu.id == olcum_id))
            olcum = result.scalars().first()
            if not olcum:
                return

            ist_result = await db.execute(select(Istasyon).filter(Istasyon.id == olcum.istasyon_id))
            istasyon = ist_result.scalars().first()
            istasyon_adi = istasyon.ad if istasyon else f"ID:{olcum.istasyon_id}"

            # Get Admins of the same organization
            admins_result = await db.execute(
                select(Kullanici).filter(
                    Kullanici.rol == "yonetici",
                    Kullanici.aktif_mi.is_(True),
                    Kullanici.organization_id == istasyon.organization_id,
                )
            )
            admins = admins_result.scalars().all()

            push_tokens = []
            email_recipients = []

            for admin in admins:
                if admin.notify_push and admin.push_token:
                    push_tokens.append(admin.push_token)
                if admin.notify_email and admin.email:
                    email_recipients.append(admin.email)

            # Environment override for emails
            env_emails = os.getenv("ALERT_EMAIL_RECIPIENTS", "")
            if env_emails:
                for email in env_emails.split(","):
                    email = email.strip()
                    if email and email not in email_recipients:
                        email_recipients.append(email)

            title = f"🚨 KRİTİK ANOMALİ: {istasyon_adi}"
            body = f"İstasyon: {istasyon_adi}\npH: {olcum.ph}, Klor: {olcum.serbest_klor}, Bulanıklık: {olcum.bulaniklik}\nLütfen derhal sistemi kontrol edin."

        # Send asynchronously OUTSIDE the DB block to avoid holding connection during network I/O
        tasks = []
        if push_tokens:
            tasks.append(send_push_notification(push_tokens, title, body))
        if email_recipients:
            tasks.append(send_email_alert(email_recipients, title, body))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        logger.error(f"[NOTIFICATION] Error in alert dispatcher: {e}")

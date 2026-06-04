# Next‑Gen Infrastructure Setup (Kafka + Celery + WhatsApp Gateway + FastAPI)

This repo remains a Django monolith, but now includes optional **Kafka event bus** + **FastAPI read APIs** to support high‑scale automation.

## 1) Docker (Recommended)

Run everything:

```bash
docker compose up --build
```

Services:
- Django: `http://localhost:8000`
- WhatsApp Gateway (WPPConnect): `http://localhost:3100`
- FastAPI service: `http://localhost:9000/health`
- Redpanda (Kafka): `localhost:9092`

## 2) Kafka Event Bus

The system uses an **Outbox table** and Celery Beat flush:
- Model: `event_bus.EventOutbox`
- Task: `event_bus.tasks.flush_outbox` (runs every minute via `CELERY_BEAT_SCHEDULE`)

Topics used:
- `billing.events`
  - `invoice.created`
  - `payment.received`

## 3) WhatsApp Media Automation

Gateway sends small media payloads (base64) in webhooks so Django can:
- run OCR (supplier invoice photo → purchase + stock)
- run voice transcription (OpenAI Whisper) and then route commands normally

Control:
- `.env` `WA_MEDIA_MAX_BYTES` (default 3MB)

## 4) OCR / Voice Requirements

### OCR (no key mode)
If `OPENAI_API_KEY` is empty, OCR can still work **offline** using Tesseract:
- Install Tesseract on Windows
- `pip install pytesseract`
- Set `TESSERACT_CMD` in `.env` if needed

### Voice
Voice transcription uses OpenAI Whisper:
- Set `OPENAI_API_KEY`
- Model: `WHATSAPP_AUDIO_MODEL` (default `whisper-1`)


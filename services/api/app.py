import hmac
import hashlib
import os
import json
from typing import Optional
from fastapi import FastAPI, Request, Header, HTTPException
from aiokafka import AIOKafkaProducer
from services.common.db import SessionLocal, init_db
from services.common.models import Base, Delivery
from sqlalchemy.ext.asyncio import AsyncSession

app = FastAPI()
producer: Optional[AIOKafkaProducer] = None

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "broker:29092")
TOPIC_REVIEW = os.getenv("KAFKA_TOPIC_REVIEW", "review.pr")
WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "").encode()


@app.on_event("startup")
async def startup() -> None:
    """Initialize database and Kafka producer on startup."""
    global producer
    await init_db()
    
    async with SessionLocal() as s:
        async with s.begin():
            await s.run_sync(Base.metadata.create_all)
    
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        linger_ms=50
    )
    await producer.start()


@app.on_event("shutdown")
async def shutdown() -> None:
    """Clean up resources on shutdown."""
    if producer:
        await producer.stop()


def verify_signature(body: bytes, sig: Optional[str]) -> None:
    """Verify GitHub webhook signature."""
    if not sig:
        raise HTTPException(400, "Missing signature")
    
    mac = hmac.new(
        WEBHOOK_SECRET,
        msg=body,
        digestmod=hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(f"sha256={mac}", sig):
        raise HTTPException(401, "Bad signature")


@app.post("/webhook")
async def webhook(
    request: Request,
    x_github_event: str = Header(...),
    x_github_delivery: str = Header(...),
    x_hub_signature_256: Optional[str] = Header(None)
) -> dict:
    """Handle GitHub webhook events."""
    body = await request.body()
    verify_signature(body, x_hub_signature_256)
    
    payload = await request.json()
    
    async with SessionLocal() as s:
        d = Delivery(
            guid=x_github_delivery,
            event=x_github_event,
            payload=payload
        )
        s.add(d)
        await s.commit()
    
    if (x_github_event == "pull_request" and 
        payload.get("action") in {"opened", "synchronize", "reopened", "ready_for_review"}):
        
        msg = {
            "repo": payload["repository"]["full_name"],
            "pr_number": payload["number"],
            "head_sha": payload["pull_request"]["head"]["sha"],
            "installation_id": payload.get("installation", {}).get("id"),
        }
        
        if producer:
            await producer.send_and_wait(
                TOPIC_REVIEW,
                json.dumps(msg).encode()
            )
    
    return {"ok": True}

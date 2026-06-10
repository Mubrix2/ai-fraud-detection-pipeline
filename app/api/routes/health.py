# app/api/routes/health.py
from fastapi import APIRouter
from app.streaming.consumer import get_consumer_stats
from app.core.audit_logger import get_stats as get_audit_stats
from app.config import APP_ENV

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    consumer = get_consumer_stats()
    audit    = get_audit_stats()
    return {
        "status":  "healthy",
        "env":     APP_ENV,
        "consumer": {
            "running":          consumer["consumer_running"],
            "messages_consumed": consumer["consumed"],
            "messages_flagged":  consumer["flagged"],
        },
        "audit": {
            "total_decisions": audit.get("total", 0),
            "blocked":         audit.get("blocked", 0),
        },
    }
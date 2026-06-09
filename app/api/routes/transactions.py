# app/api/routes/transactions.py
"""
Transaction API routes.

POST /submit:
  1. Validate with Pydantic (extra=forbid, enum serialisation)
  2. Score synchronously via assess_transaction() → store in _results_store
  3. Publish to Kafka for consumer thread (demonstrates streaming)
  4. Return 202 Accepted immediately

Why score synchronously AND publish to Kafka?
  The dashboard needs results immediately after submission.
  The consumer thread will also process it, but that's asynchronous.
  Synchronous scoring ensures the GET /results/{id} endpoint works
  without polling delays.

GET /recent:
  Returns sorted results from the in-memory store.
  Polled by the React dashboard every 3 seconds.

GET /stats:
  Derived from the in-memory store — always accurate,
  no dependency on consumer thread memory.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from app.api.schemas import (
    FraudResultResponse,
    InvestigateRequest,
    SubmitResponse,
    TransactionRequest,
)
from app.core.audit_logger import get_stats as audit_stats
from app.services.detection_service import assess_transaction
from app.streaming.consumer import (
    get_all_results,
    get_result,
    store_result,
)
from app.streaming.producer import publish_transaction

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post(
    "/submit",
    response_model=SubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a transaction for fraud screening",
)
async def submit_transaction(request: TransactionRequest):
    # mode='json' ensures TransactionType.TRANSFER → "TRANSFER" (not the enum object)
    data = request.model_dump(mode="json")

    # Synchronous scoring — result available immediately
    assessment = assess_transaction(
        transaction_id   = data["transaction_id"],
        transaction_data = data,
    )
    store_result(data["transaction_id"], assessment)

    # Async Kafka publish — demonstrates streaming pipeline
    publish_transaction(data)

    decision = assessment.get("decision", "APPROVE")
    logger.info(
        f"Submitted {data['transaction_id']} | "
        f"decision={decision}"
    )

    return SubmitResponse(
        transaction_id = data["transaction_id"],
        status         = "accepted",
        message        = f"Transaction received. Decision: {decision}",
    )


@router.get(
    "/results/{transaction_id}",
    response_model=FraudResultResponse,
    summary="Get scoring result for a transaction",
)
async def get_transaction_result(transaction_id: str):
    result = get_result(transaction_id)
    if result is None:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail      = f"No result found for {transaction_id}",
        )
    return FraudResultResponse(**result)


@router.get(
    "/recent",
    summary="Get recent transaction results for dashboard",
)
async def get_recent(limit: int = 100):
    results = get_all_results()[:limit]
    return {
        "transactions": results,
        "total":        len(results),
    }


@router.get(
    "/stats",
    summary="System statistics for the dashboard stats bar",
)
async def get_stats():
    all_results  = get_all_results()
    total        = len(all_results)
    blocked      = sum(1 for r in all_results if r.get("decision") == "BLOCK")
    reviewed     = sum(1 for r in all_results if r.get("decision") == "REVIEW")
    sar_required = sum(1 for r in all_results if r.get("requires_sar"))

    avg_ms = 0.0
    if total > 0:
        times  = [r.get("processing_ms", 0) for r in all_results]
        avg_ms = round(sum(times) / len(times), 2)

    return {
        "total_processed": total,
        "blocked":         blocked,
        "reviewed":        reviewed,
        "approved":        total - blocked - reviewed,
        "sar_required":    sar_required,
        "fraud_rate":      round((blocked + reviewed) / total, 4) if total > 0 else 0.0,
        "avg_processing_ms": avg_ms,
    }


@router.post(
    "/investigate",
    summary="AI investigation agent for fraud analysts",
)
async def investigate(request: InvestigateRequest):
    """
    Ask the LangGraph investigation agent about flagged transactions.

    Examples:
        "Why was TXN-001 flagged?"
        "Show me the velocity pattern for customer C1234567890"
        "Generate an investigation report for TXN-001"
    """
    try:
        from app.core.investigation_agent import investigate as run_agent
        answer = run_agent(
            question   = request.question,
            session_id = request.session_id,
        )
        return {"answer": answer, "session_id": request.session_id}
    except Exception as e:
        logger.error(f"Investigation agent error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
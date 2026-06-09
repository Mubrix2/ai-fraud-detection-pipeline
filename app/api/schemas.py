# app/api/schemas.py
"""
Pydantic v2 request and response schemas.

extra='forbid' on the request schema:
  Rejects any field not declared in the model.
  A client cannot probe the system by adding unexpected fields.
  Unknown fields return HTTP 422 before reaching any business logic.

mode='json' in model_dump():
  Serialises enum members to their string values.
  Without this: TransactionType.TRANSFER → "TransactionType.TRANSFER"
  With this:    TransactionType.TRANSFER → "TRANSFER"
  The type guard comparison requires the plain string.
"""
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TransactionType(str, Enum):
    TRANSFER  = "TRANSFER"
    CASH_OUT  = "CASH_OUT"
    PAYMENT   = "PAYMENT"
    CASH_IN   = "CASH_IN"
    DEBIT     = "DEBIT"


class TransactionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: str           = Field(..., min_length=1, max_length=64)
    step:           int           = Field(..., ge=0)
    type:           TransactionType
    amount:         float         = Field(..., gt=0)
    name_orig:      str           = Field(..., min_length=1)
    oldbalance_org: float         = Field(..., ge=0)
    newbalance_orig: float        = Field(..., ge=0)
    name_dest:      str           = Field(..., min_length=1)
    oldbalance_dest: float        = Field(..., ge=0)
    newbalance_dest: float        = Field(..., ge=0)


class SubmitResponse(BaseModel):
    transaction_id: str
    status:         str = "accepted"
    message:        str


class FraudResultResponse(BaseModel):
    transaction_id:    str
    decision:          str
    risk_level:        str
    fraud_probability: float
    is_flagged:        bool
    anomaly_label:     str
    aml_flag_count:    int
    requires_sar:      bool
    requires_ctr:      bool
    triggered_rules:   list
    top_reasons:       list
    explanation_text:  str
    velocity:          dict
    scored_at:         str
    processing_ms:     float
    note:              Optional[str] = None


class InvestigateRequest(BaseModel):
    question:   str = Field(..., min_length=3)
    session_id: str = Field(default="analyst-1")
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

TripStatus = Literal["running", "awaiting_review", "completed", "blocked", "failed"]


class TripCreateRequest(BaseModel):
    query: str = Field(
        min_length=5,
        max_length=2000,
        examples=["Plan a 4 day trip to Dubai for next month from Kolkata, budget 80000 INR"],
    )
    thread_id: UUID | None = None
    origin: str | None = None
    destination: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    adults: int = Field(default=1, ge=1)
    children: int = Field(default=0, ge=0)
    budget: float | None = None
    currency: str = Field(default="INR")
    food_preference: str | None = None  # veg, non-veg, vegan, jain, halal, etc.


class ReviewRequest(BaseModel):
    action: Literal["approve", "request_changes"]
    feedback: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def feedback_required_for_changes(self):
        if self.action == "request_changes" and not self.feedback:
            raise ValueError("feedback is required when requesting changes")
        return self


class TripHistoryItem(BaseModel):
    thread_id: UUID
    title: str | None = None
    destination: str | None = None
    user_query: str
    status: TripStatus
    has_pdf: bool = False
    created_at: datetime


class TripResponse(BaseModel):
    thread_id: UUID
    status: TripStatus
    title: str | None = None
    destination: str | None = None
    has_pdf: bool = False
    message: str | None = None  # final plan or blocked reason
    review_payload: dict[str, Any] | None = None  # itinerary awaiting approval

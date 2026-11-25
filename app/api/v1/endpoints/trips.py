from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import get_current_user, get_trip_service
from app.core.exceptions import TripNotAwaitingReview, TripNotFound
from app.models.user import User
from app.schemas.trip import ReviewRequest, TripCreateRequest, TripHistoryItem, TripResponse
from app.services.trip_service import TripService

router = APIRouter(prefix="/trips", tags=["trips"])


@router.post("", response_model=TripResponse, status_code=status.HTTP_201_CREATED)
async def create_trip(
    body: TripCreateRequest,
    svc: TripService = Depends(get_trip_service),
    current_user: User = Depends(get_current_user),
):
    return await svc.create_trip(body, user_id=current_user.id)


@router.get("", response_model=list[TripHistoryItem])
async def list_trips(
    svc: TripService = Depends(get_trip_service),
    current_user: User = Depends(get_current_user),
):
    """Retrieve all past trip planning conversations for the authenticated user."""
    return await svc.list_user_trips(current_user.id)


@router.post("/{thread_id}/review", response_model=TripResponse)
async def review_trip(
    thread_id: UUID,
    body: ReviewRequest,
    svc: TripService = Depends(get_trip_service),
):
    try:
        return await svc.review(thread_id, body)
    except TripNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TripNotAwaitingReview as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{thread_id}", response_model=TripResponse)
async def get_trip(
    thread_id: UUID,
    svc: TripService = Depends(get_trip_service),
):
    try:
        return await svc.get_trip(thread_id)
    except TripNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{thread_id}/preview-pdf")
async def preview_trip_pdf(
    thread_id: UUID,
    svc: TripService = Depends(get_trip_service),
):
    """Returns an ephemeral in-memory preview PDF of the draft plan for human review."""
    try:
        pdf_bytes = await svc.preview_pdf(thread_id)
        filename = f"Draft_Trip_Preview_{str(thread_id)[:8]}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )
    except TripNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{thread_id}/pdf")
async def download_trip_pdf(
    thread_id: UUID,
    svc: TripService = Depends(get_trip_service),
):
    """Streams the official finalized PDF binary directly from PostgreSQL."""
    try:
        pdf_bytes, filename = await svc.get_pdf(thread_id)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except TripNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trip(
    thread_id: UUID,
    svc: TripService = Depends(get_trip_service),
    current_user: User = Depends(get_current_user),
):
    """Deletes a journey conversation and any associated stored files."""
    deleted = await svc.delete_trip(thread_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Journey not found or unauthorized")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

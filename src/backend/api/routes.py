"""
Routes API router — /api/routes/*

Endpoints
---------
GET /api/routes              List all routes
GET /api/routes/{route_id}   Get one route

Pure database reads — no engine computation.

Note: RouteResponse.model_validate(route_orm) works correctly because the
field_validator fix in schemas/route.py deserialises the JSON-text highways,
waypoints, and cold_storage_depots columns to Python lists before Pydantic's
type coercion runs.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.backend.db.database import get_db
from src.backend.models.route import Route
from src.backend.schemas.route import RouteResponse

router = APIRouter()


@router.get("/", response_model=list[RouteResponse])
def list_routes(db: Session = Depends(get_db)):
    """Return all routes from the database."""
    routes = db.query(Route).all()
    return [RouteResponse.model_validate(r) for r in routes]


@router.get("/{route_id}", response_model=RouteResponse)
def get_route(route_id: str, db: Session = Depends(get_db)):
    """
    Return a single route by ID.  404 if not found.

    route_id maps to Route.route_id (the primary key), e.g. "RT-SEA-DEN-01".
    """
    route = db.get(Route, route_id)
    if route is None:
        raise HTTPException(
            status_code=404,
            detail=f"Route {route_id!r} not found",
        )
    return RouteResponse.model_validate(route)

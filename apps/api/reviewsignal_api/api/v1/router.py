"""Aggregates the v1 routers. New endpoint groups are mounted here."""

from fastapi import APIRouter

from reviewsignal_api.api.v1 import google, system

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(google.router)

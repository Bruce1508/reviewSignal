"""Aggregates the v1 routers. New endpoint groups are mounted here.

Every route under `/api/v1` requires a session except `/health`, which stays open for
container health checks (`docs/api-spec.md` §15). The guard is applied at mount time
rather than per route, so forgetting it on a new group is a visible omission here
rather than an invisible one spread across handlers.
"""

from fastapi import APIRouter, Depends

from reviewsignal_api.api.deps import require_session
from reviewsignal_api.api.v1 import auth, google, system

GUARDED = [Depends(require_session)]

api_router = APIRouter()
api_router.include_router(system.public_router)
api_router.include_router(auth.router)
api_router.include_router(system.router, dependencies=GUARDED)
api_router.include_router(google.router, dependencies=GUARDED)

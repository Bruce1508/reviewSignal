"""Google ingestion job handlers (`docs/architecture.md` §7, `docs/PRD.md` §6.1).

Backfill and incremental sync are the same pipeline with different stop conditions,
so both handlers are thin wrappers over `IngestionService`.
"""

import logging

from reviewsignal_api.integrations.base import SourceNotConnectedError
from reviewsignal_api.integrations.google.adapter import GoogleReviewSourceAdapter
from reviewsignal_api.integrations.google.client import GoogleReviewsClient
from reviewsignal_api.services.google_token import load_credential, resolve_access_token
from reviewsignal_api.services.ingestion import IngestionService
from reviewsignal_worker.db import session_scope

logger = logging.getLogger(__name__)

SOURCE = "google"


def google_backfill(payload: dict) -> None:
    """One-time historical backfill (`docs/PRD.md` §4.1)."""
    _ingest(mode="backfill")


def google_sync(payload: dict) -> None:
    """Daily incremental sync (`docs/PRD.md` §4.2)."""
    _ingest(mode="incremental")


def _ingest(mode: str) -> None:
    with session_scope() as session:
        credential = load_credential(session, SOURCE)
        if credential.account_id is None or credential.location_id is None:
            # Without both, there is no URL to call. Failing loudly here beats issuing a
            # request to a malformed path and reporting it as a Google outage.
            raise SourceNotConnectedError(
                "The Google connection has no account/location selected yet."
            )

        access_token = resolve_access_token(session, credential)
        adapter = GoogleReviewSourceAdapter(
            GoogleReviewsClient(
                access_token=access_token,
                account_id=credential.account_id,
                location_id=credential.location_id,
            )
        )

        service = IngestionService(session, adapter)
        outcome = service.backfill() if mode == "backfill" else service.incremental()

    logger.info(
        "Google %s finished: fetched=%s created=%s updated=%s unchanged=%s unmappable=%s",
        mode, outcome.fetched, outcome.created, outcome.updated,
        outcome.unchanged, outcome.unmappable,
    )

"""The async-job acceptance contract (`docs/api-spec.md` §12).

Every endpoint that queues work answers with this shape, so it belongs to no single
source module.
"""

import uuid

from pydantic import BaseModel


class JobAcceptedPayload(BaseModel):
    job_id: uuid.UUID
    status: str
    job_type: str

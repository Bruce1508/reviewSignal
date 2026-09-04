"""Constants shared between the API and the worker."""

API_V1_PREFIX = "/api/v1"

# RQ queue name. The worker listens here; the API reports its depth.
DEFAULT_QUEUE_NAME = "reviewsignal"

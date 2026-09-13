"""Queue one taxonomy generation run (`docs/taxonomy-pipeline.md` §3, the first pass).

A script rather than an endpoint. This slice stores a `candidate` version and activates
nothing, so there is no product action for the dashboard to offer yet; `POST
/taxonomy/generate` belongs with automatic acceptance (`taxonomy-pipeline.md` §6).
"""

import argparse

from reviewsignal_worker.jobs.taxonomy import DEFAULT_SAMPLE_SIZE, TAXONOMY_JOB_TYPE
from reviewsignal_worker.queue import enqueue


def main() -> None:
    parser = argparse.ArgumentParser(description="Queue a taxonomy generation run.")
    parser.add_argument(
        "--sample-size",
        type=int,
        default=DEFAULT_SAMPLE_SIZE,
        help="Newest reviews with text to send in the prompt.",
    )
    arguments = parser.parse_args()
    job_id = enqueue(TAXONOMY_JOB_TYPE, {"sample_size": arguments.sample_size})
    print(f"Queued {TAXONOMY_JOB_TYPE} job {job_id}")


if __name__ == "__main__":
    main()

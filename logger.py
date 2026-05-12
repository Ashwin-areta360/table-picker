import json
import sys
import traceback
from datetime import datetime


def log(
    level="info",
    service="table-picker",
    event=None,
    org_id=None,
    trace_id=None,
    duration_ms=None,
    error=None,
    **rest
):

    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": level,
        "service": service,
        "event": event,
    }

    if org_id:
        entry["org_id"] = org_id

    if trace_id:
        entry["trace_id"] = trace_id

    if duration_ms is not None:
        entry["duration_ms"] = duration_ms

    if error:
        if isinstance(error, Exception):
            entry["error"] = {
                "message": str(error),
                "stack": traceback.format_exc()
            }
        else:
            entry["error"] = error

    entry.update(rest)

    sys.stdout.write(json.dumps(entry) + "\n")
    sys.stdout.flush()
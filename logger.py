import threading, time, json
from datetime import datetime
from typing import Any

class LogBus:
    def __init__(self, sink=None):
        self._lock = threading.Lock()
        self._sink = sink
        self._lines = []

    def log(self, msg):
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        with self._lock:
            self._lines.append(line)
        if self._sink:
            self._sink(line)
        else:
            print(line)

    def dump(self):
        with self._lock:
            return list(self._lines)

def _instrumentation_payload(instrumentation: Any):
    if instrumentation is None:
        return {"detected": False}
    if hasattr(instrumentation, "to_report_dict"):
        return instrumentation.to_report_dict()
    if isinstance(instrumentation, dict):
        return instrumentation
    return {"detected": bool(instrumentation)}


class Report:
    def __init__(self, engine_path, instrumentation=None):
        self.data = {
            "engine": engine_path,
            "started": datetime.now().isoformat(timespec="seconds"),
            "finished": None,
            "tests": [],
            "notes": [],
            "instrumentation": _instrumentation_payload(instrumentation),
        }

    def add_test(self, name, **params):
        self.data["tests"].append({"name": name, **params})

    def finish(self):
        self.data["finished"] = datetime.now().isoformat(timespec="seconds")

    def to_json(self):
        return json.dumps(self.data, indent=2)

    def set_instrumentation(self, instrumentation):
        self.data["instrumentation"] = _instrumentation_payload(instrumentation)

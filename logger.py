import threading, time, json
from datetime import datetime

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

class Report:
    def __init__(self, engine_path):
        self.data = {
            "engine": engine_path,
            "started": datetime.now().isoformat(timespec="seconds"),
            "finished": None,
            "tests": [],
            "notes": []
        }

    def add_test(self, name, **params):
        self.data["tests"].append({"name": name, **params})

    def finish(self):
        self.data["finished"] = datetime.now().isoformat(timespec="seconds")

    def to_json(self):
        return json.dumps(self.data, indent=2)

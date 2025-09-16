import os, time, random
import chess, chess.engine
from typing import Optional, TYPE_CHECKING
try:
    import psutil
except Exception:
    psutil = None

if TYPE_CHECKING:  # pragma: no cover - typing helper
    from instrumentation import InstrumentationProfile

def clamp(x, lo, hi): return max(lo, min(hi, x))
def now(): return time.time()

def random_legal_fen(max_plies=12):
    b = chess.Board()
    for _ in range(random.randint(0, max_plies)):
        if b.is_game_over(): break
        b.push(random.choice(list(b.legal_moves)))
    return b.fen()

class EngineRunner:
    """Context manager: UCI engine aç, configure et, analyse/play yap."""

    def __init__(
        self,
        path,
        threads: int = 1,
        hash_mb: int = 128,
        multipv: int = 1,
        uci_options: Optional[dict] = None,
        instrumentation: Optional["InstrumentationProfile"] = None,
    ):
        self.path = path
        self.threads = int(threads)
        self.hash_mb = int(hash_mb)
        self.multipv = int(multipv)
        self.uci_options = dict(uci_options or {})
        self.instrumentation = instrumentation
        self.engine = None
        self.proc = None

    def __enter__(self):
        self.engine = chess.engine.SimpleEngine.popen_uci(self.path)
        opts = {"Threads": self.threads, "Hash": self.hash_mb, "MultiPV": self.multipv}
        opts.update(self.uci_options)
        if self.instrumentation:
            opts.update(self.instrumentation.uci_options)
        try:
            self.engine.configure(opts)
        except Exception:
            pass
        if self.instrumentation:
            try:
                self.instrumentation.activate(self)
            except Exception:
                pass
        # process handle
        try:
            self.proc = psutil.Process(self.engine.process.pid) if psutil else None
        except Exception:
            self.proc = None
        return self

    def __exit__(self, *exc):
        try:
            if self.engine: self.engine.quit()
        except Exception:
            pass

    def analyse_cp(self, fen, movetime=None, depth=None):
        board = chess.Board(fen)
        limit = chess.engine.Limit(time=movetime) if movetime is not None else chess.engine.Limit(depth=depth or 10)
        info = self.engine.analyse(board, limit)
        s = info.get("score")
        cp = s.white().score(mate_score=100000) if s else 0
        return clamp(cp, -2000, 2000), info

    def cpu_mem_snapshot(self):
        if not self.proc: return None
        with self.proc.oneshot():
            return {
                "cpu_percent": self.proc.cpu_percent(interval=None),
                "rss": self.proc.memory_info().rss
            }

    # Instrumentation helpers -------------------------------------------------
    def send_command(self, line: str) -> bool:
        if not self.engine:
            raise RuntimeError("engine not running")
        proto = getattr(self.engine, "protocol", None)
        if proto:
            sender = getattr(proto, "send_line", None) or getattr(proto, "write_line", None)
            if sender:
                sender(line)
                return True
        proc = getattr(self.engine, "process", None)
        try:
            stdin = getattr(proc, "stdin", None)
        except Exception:
            stdin = None
        if stdin:
            try:
                stdin.write(line + "\n")
                stdin.flush()
                return True
            except Exception:
                return False
        return False

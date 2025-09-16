import os, time, random
import chess, chess.engine
try:
    import psutil
except Exception:
    psutil = None

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
    def __init__(self, path, threads=1, hash_mb=128, multipv=1, uci_options=None):
        self.path = path
        self.threads = int(threads)
        self.hash_mb = int(hash_mb)
        self.multipv = int(multipv)
        self.uci_options = dict(uci_options or {})
        self.engine = None
        self.proc = None

    def __enter__(self):
        self.engine = chess.engine.SimpleEngine.popen_uci(self.path)
        opts = {"Threads": self.threads, "Hash": self.hash_mb, "MultiPV": self.multipv}
        opts.update(self.uci_options)
        try:
            self.engine.configure(opts)
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

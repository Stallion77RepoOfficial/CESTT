import time
from core import EngineRunner, random_legal_fen

def run(logger, report, path, duration_s=60, movetime=0.1):
    report.add_test("endurance", duration_s=duration_s, movetime=movetime)
    t0 = time.time()
    iters = 0
    cpu_peak, rss_peak = 0.0, 0
    with EngineRunner(path) as er:
        while time.time() - t0 < duration_s:
            fen = random_legal_fen(14)
            cp, _ = er.analyse_cp(fen, movetime=movetime)
            iters += 1
            snap = er.cpu_mem_snapshot()
            if snap:
                cpu_peak = max(cpu_peak, snap["cpu_percent"])
                rss_peak = max(rss_peak, snap["rss"])
            if iters % 10 == 0:
                logger.log(f"[Endurance] it={iters} cp={cp}")
    logger.log(f"[Endurance] OK {iters} iters | cpu_peak={cpu_peak:.1f}% | rss_peak={rss_peak/1e6:.1f}MB")

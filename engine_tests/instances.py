import threading, queue, time
from core import EngineRunner, random_legal_fen

def _worker(idx, path, movetime, per_instance, q):
    try:
        with EngineRunner(path) as er:
            for i in range(per_instance):
                fen = random_legal_fen(8)
                cp,_ = er.analyse_cp(fen, movetime=movetime)
                if i % 10 == 0:
                    q.put(f"[Inst#{idx}] {i}/{per_instance} cp={cp}")
        q.put(f"[Inst#{idx}] done")
    except Exception as e:
        q.put(f"[Inst#{idx}] ERROR: {e!r}")

def run(logger, report, path, instances=4, per_instance=50, movetime=0.1):
    report.add_test("multi_instance", instances=instances, per_instance=per_instance, movetime=movetime)
    q = queue.Queue()
    threads = []
    for k in range(instances):
        t = threading.Thread(target=_worker, args=(k, path, movetime, per_instance, q), daemon=True)
        t.start(); threads.append(t)

    alive = instances; t0 = time.time()
    while alive:
        try:
            msg = q.get(timeout=0.5)
            logger.log(msg)
            if msg.endswith("done"): alive -= 1
        except queue.Empty:
            pass
    logger.log(f"[MultiInstance] {instances} instances finished in {time.time()-t0:.1f}s")

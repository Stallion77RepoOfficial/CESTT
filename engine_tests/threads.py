from core import EngineRunner
import chess, time


def run(logger, report, path, movetime=0.2, max_threads=8, instrumentation=None):
    report.add_test("threads_scaling", movetime=movetime, max_threads=max_threads)
    results = []
    for th in [1,2,4,8]:
        if th > max_threads: break
        t0 = time.time()
        with EngineRunner(path, threads=th, instrumentation=instrumentation) as er:
            cp, info = er.analyse_cp(chess.STARTING_FEN, movetime=movetime)
            nodes = int(info.get("nodes", 0))
            dt = time.time()-t0
            nps = nodes / max(dt, 1e-6)
            results.append((th, nodes, dt, nps))
            logger.log(f"[Threads] T={th} cp={cp} nodes={nodes} time={dt:.3f}s nps={int(nps)}")

    if results:
        base = results[0][3] or 1.0
        for th,_,__,nps in results:
            logger.log(f"[Threads] scale(T={th})={nps/base:.2f}x")

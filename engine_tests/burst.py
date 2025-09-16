from core import EngineRunner, random_legal_fen

def run(logger, report, path, count=200, movetime=0.02):
    report.add_test("burst", count=count, movetime=movetime)
    with EngineRunner(path) as er:
        nodes_total = 0
        for i in range(count):
            fen = random_legal_fen(10)
            cp, info = er.analyse_cp(fen, movetime=movetime)
            nodes_total += int(info.get("nodes", 0))
            if i % max(1, count//10) == 0:
                logger.log(f"[Burst {i+1}/{count}] cp={cp} nodes={info.get('nodes',0)}")
        logger.log(f"[Burst] Done {count} pos | total_nodes={nodes_total} | avg={nodes_total/max(1,count):.0f}")

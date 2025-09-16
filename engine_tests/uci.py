from core import EngineRunner
import chess

def run(logger, report, path, movetime=0.05):
    report.add_test("uci_handshake", movetime=movetime)
    with EngineRunner(path) as er:
        cp, _ = er.analyse_cp(chess.STARTING_FEN, movetime=movetime)
        logger.log(f"[UCI] startpos movetime={int(movetime*1000)}ms → cp={cp}")

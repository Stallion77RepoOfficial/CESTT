from core import EngineRunner
import chess

def run(logger, report, path, movetime=0.25, multipv=4):
    report.add_test("multipv", movetime=movetime, multipv=multipv)
    with EngineRunner(path, multipv=multipv) as er:
        cp, info = er.analyse_cp(chess.STARTING_FEN, movetime=movetime)
        logger.log(f"[MultiPV] cp={cp} info_keys={list(info.keys())}")

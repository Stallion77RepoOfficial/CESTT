import chess, chess.pgn, glob, os
from core import EngineRunner

def _stream_games(paths):
    for p in paths:
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            while True:
                g = chess.pgn.read_game(f)
                if not g: break
                yield p, g

def run(logger, report, path, pgn_dir, movetime=0.05, max_games=200, instrumentation=None):
    files = glob.glob(os.path.join(pgn_dir, "*.pgn"))
    report.add_test("pgn_replay", dir=pgn_dir, movetime=movetime, max_games=max_games, files=len(files))
    if not files:
        logger.log("[PGN] no files found"); return
    count = 0
    with EngineRunner(path, instrumentation=instrumentation) as er:
        for fpath, game in _stream_games(files):
            board = game.board()
            for mv in game.mainline_moves():
                fen = board.fen()
                cp, _ = er.analyse_cp(fen, movetime=movetime)
                # seyrek log
                if count % 200 == 0:
                    logger.log(f"[PGN] {os.path.basename(fpath)} cp={cp}")
                board.push(mv)
            count += 1
            if count >= max_games: break
    logger.log(f"[PGN] replayed {count} games.")

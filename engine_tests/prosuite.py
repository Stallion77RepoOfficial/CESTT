import chess
from core import EngineRunner, random_legal_fen
from instrumentation import InstrumentationProfile


DEFAULT_TACTICAL_SUITE = [
    {
        "label": "King's Gambit Pressure",
        "fen": "rnbqkbnr/pppp1ppp/8/4p3/2B1P3/8/PPPP1PPP/RNBQK1NR b KQkq - 1 2",
        "movetime": 0.6,
    },
    {
        "label": "Closed centre grind",
        "fen": "rnbq1rk1/ppp2ppp/3bpn2/3p4/3P4/2N1PN2/PP3PPP/R1BQKB1R w KQ - 0 8",
        "movetime": 0.6,
    },
    {
        "label": "Technical rook ending",
        "fen": "8/5pk1/5np1/1p6/pP3P2/P1P2K1P/6P1/8 w - - 0 1",
        "movetime": 0.6,
    },
]

DEFAULT_STABILITY = {
    "samples": 6,
    "movetime": 0.35,
    "max_cp_delta": 45,
    "max_plies": 18,
}


def _load_suite(definition, fallback):
    if not definition:
        return list(fallback), {}
    if isinstance(definition, dict):
        positions = definition.get("positions")
        if not isinstance(positions, list):
            positions = fallback
        opts = {k: v for k, v in definition.items() if k != "positions"}
        return list(positions), opts
    if isinstance(definition, list):
        return list(definition), {}
    return list(fallback), {}


def _normalise_entry(entry):
    if isinstance(entry, str):
        return {"fen": entry}
    if isinstance(entry, dict):
        return dict(entry)
    return {}


def _expected_moves(entry, board: chess.Board):
    moves = []
    candidates = []
    for key in ("best", "expected_move", "expected_moves"):
        value = entry.get(key)
        if isinstance(value, (list, tuple, set)):
            candidates.extend(value)
        elif value is not None:
            candidates.append(value)
    result = []
    for item in candidates:
        if item is None:
            continue
        text = str(item).strip()
        if not text:
            continue
        try:
            move = board.parse_san(text)
            result.append(move.uci())
            continue
        except Exception:
            pass
        if len(text) in (4, 5) and text[0].isalpha():
            result.append(text)
    return result


def run(logger, report, path, movetime=0.4, instrumentation: InstrumentationProfile = None):
    manifest_path = None
    if instrumentation and instrumentation.manifest_path:
        manifest_path = str(instrumentation.manifest_path)

    raw_suite, suite_opts = _load_suite(
        instrumentation.get_suite("tactical") if instrumentation else None,
        DEFAULT_TACTICAL_SUITE,
    )
    tactical_entries = []
    for item in raw_suite:
        norm = _normalise_entry(item)
        if norm.get("fen"):
            tactical_entries.append(norm)
    if not tactical_entries:
        for item in DEFAULT_TACTICAL_SUITE:
            norm = _normalise_entry(item)
            if norm.get("fen"):
                tactical_entries.append(norm)

    stability_conf = dict(DEFAULT_STABILITY)
    if instrumentation:
        stability_def = instrumentation.get_suite("stability")
        if isinstance(stability_def, dict):
            stability_conf.update(stability_def)

    samples = int(max(1, stability_conf.get("samples", DEFAULT_STABILITY["samples"])))

    report.add_test(
        "professional_suite",
        movetime=movetime,
        manifest=manifest_path,
        tactical_positions=len(tactical_entries),
        stability_samples=samples,
    )

    if not instrumentation or not instrumentation.supports_professional_suite():
        logger.log("[PRO] instrumentation package missing — professional suite locked")
        if instrumentation and instrumentation.error:
            report.data.setdefault("notes", []).append(f"professional suite manifest error: {instrumentation.error}")
        return

    analysis_threads = int(suite_opts.get("threads", 1)) if suite_opts else 1
    analysis_hash = int(suite_opts.get("hash", 256)) if suite_opts else 256
    analysis_multipv = int(suite_opts.get("multipv", 3)) if suite_opts else 3
    base_movetime = float(suite_opts.get("movetime", movetime)) if suite_opts else float(movetime)

    try:
        with EngineRunner(
            path,
            threads=max(1, analysis_threads),
            hash_mb=max(32, analysis_hash),
            multipv=max(1, analysis_multipv),
            instrumentation=instrumentation,
        ) as er:
            instrumentation.activate(er, logger=logger)

            passed = 0
            for idx, entry in enumerate(tactical_entries, 1):
                fen = entry.get("fen")
                if not fen:
                    continue
                board = chess.Board(fen)
                label = entry.get("label") or entry.get("name") or f"pos#{idx}"
                entry_movetime = float(entry.get("movetime", base_movetime))
                depth = entry.get("depth")
                cp, info = er.analyse_cp(fen, movetime=entry_movetime, depth=depth)
                pv = info.get("pv") or []
                pv_moves = []
                try:
                    pv_moves = [mv.uci() if hasattr(mv, "uci") else str(mv) for mv in pv]
                except Exception:
                    pv_moves = [str(mv) for mv in pv]
                best_move = pv_moves[0] if pv_moves else None
                nodes = info.get("nodes")
                speed = None
                if nodes and entry_movetime > 0:
                    speed = int(nodes / max(entry_movetime, 1e-6))
                logger.log(
                    f"[PRO] tactical {label}: cp={cp} nodes={nodes} nps={speed} pv={pv_moves[:3]}"
                )

                expected_candidates = _expected_moves(entry, board)
                success = True
                if expected_candidates:
                    if best_move in expected_candidates:
                        logger.log(f"[PRO] ✓ {label} expected move matched ({best_move})")
                    else:
                        logger.log(
                            f"[PRO] ✗ {label} expected {expected_candidates} got {best_move}"
                        )
                        success = False

                cp_range = entry.get("cp_range") or entry.get("expected_cp_range")
                if cp_range and isinstance(cp_range, (list, tuple)) and len(cp_range) == 2:
                    low, high = float(cp_range[0]), float(cp_range[1])
                    if not (low <= cp <= high):
                        logger.log(
                            f"[PRO] ✗ {label} eval {cp} outside range [{low}, {high}]"
                        )
                        success = False

                if success:
                    passed += 1
                else:
                    report.data.setdefault("notes", []).append(f"tactical miss: {label}")

            if tactical_entries:
                logger.log(
                    f"[PRO] tactical summary: {passed}/{len(tactical_entries)} matched expectations"
                )

            stability_failures = 0
            stability_movetime = float(stability_conf.get("movetime", base_movetime))
            max_cp_delta = float(stability_conf.get("max_cp_delta", DEFAULT_STABILITY["max_cp_delta"]))
            max_plies = int(stability_conf.get("max_plies", DEFAULT_STABILITY["max_plies"]))

            for i in range(samples):
                fen = random_legal_fen(max(4, max_plies))
                cp1, _ = er.analyse_cp(fen, movetime=stability_movetime)
                cp2, _ = er.analyse_cp(fen, movetime=stability_movetime)
                delta = abs(cp1 - cp2)
                logger.log(
                    f"[PRO] stability {i+1}/{samples}: Δcp={delta} cp1={cp1} cp2={cp2}"
                )
                if delta > max_cp_delta:
                    stability_failures += 1
            if stability_failures:
                report.data.setdefault("notes", []).append(
                    f"stability drift: {stability_failures}/{samples} over threshold"
                )
            logger.log(
                f"[PRO] stability summary: {samples - stability_failures}/{samples} within Δcp≤{max_cp_delta}"
            )

    except Exception as exc:
        logger.log(f"[PRO] professional suite failed: {exc!r}")
        report.data.setdefault("notes", []).append(f"professional suite error: {exc!r}")
        return

    for warning in instrumentation.warnings:
        logger.log(f"[PRO] warning: {warning}")

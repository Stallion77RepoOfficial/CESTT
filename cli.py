import argparse
from logger import LogBus, Report
from engine_tests import uci, burst, endurance, threads, multipv, instances, fuzz, pgnreplay

def main():
    ap = argparse.ArgumentParser(description="CESTT — CLI")
    ap.add_argument("--engine", required=True)
    ap.add_argument("--movetime", type=float, default=0.1)
    ap.add_argument("--duration", type=int, default=60)
    ap.add_argument("--burst", type=int, default=200)
    ap.add_argument("--threads-max", type=int, default=8)
    ap.add_argument("--instances", type=int, default=4)
    ap.add_argument("--per-instance", type=int, default=50)
    ap.add_argument("--pgn-dir", default="")
    ap.add_argument("--tests", default="uci,burst,threads,multipv", help="comma list: uci,burst,endurance,threads,multipv,instances,fuzz,pgn")
    args = ap.parse_args()

    bus = LogBus()
    rep = Report(args.engine)
    selected = {t.strip() for t in args.tests.split(",") if t.strip()}

    if "uci"       in selected: uci.run(bus, rep, args.engine, movetime=args.movetime)
    if "burst"     in selected: burst.run(bus, rep, args.engine, count=args.burst, movetime=args.movetime)
    if "endurance" in selected: endurance.run(bus, rep, args.engine, duration_s=args.duration, movetime=args.movetime)
    if "threads"   in selected: threads.run(bus, rep, args.engine, movetime=args.movetime, max_threads=args.threads_max)
    if "multipv"   in selected: multipv.run(bus, rep, args.engine, movetime=args.movetime, multipv=4)
    if "instances" in selected: instances.run(bus, rep, args.engine, instances=args.instances, per_instance=args.per_instance, movetime=args.movetime)
    if "fuzz"      in selected: fuzz.run(bus, rep, args.engine, seconds=10)
    if "pgn"       in selected and args.pgn_dir: pgnreplay.run(bus, rep, args.engine, pgn_dir=args.pgn_dir, movetime=args.movetime, max_games=200)

    rep.finish()
    print(rep.to_json())

import argparse
from logger import LogBus, Report
from engine_tests import (
    uci,
    burst,
    endurance,
    threads,
    multipv,
    instances,
    fuzz,
    pgnreplay,
    asmdebug,
    prosuite,
)
from instrumentation import detect

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
    default_tests = "uci,burst,threads,multipv"
    ap.add_argument(
        "--tests",
        default=default_tests,
        help="comma list: uci,burst,endurance,threads,multipv,instances,fuzz,pgn,asm,pro (use 'auto' for defaults)",
    )
    args = ap.parse_args()

    bus = LogBus()
    profile = detect(args.engine)
    if profile.manifest:
        bus.log(f"[instrumentation] detected {profile.describe()}")
    elif profile.error:
        bus.log(f"[instrumentation] manifest error: {profile.error}")
    else:
        bus.log("[instrumentation] no instrumentation manifest found")

    rep = Report(args.engine, instrumentation=profile)

    raw_tests = args.tests.strip()
    if raw_tests.lower() == "auto":
        selected = set(default_tests.split(","))
    else:
        selected = {t.strip() for t in raw_tests.split(",") if t.strip()}

    if profile.supports_assembly_debug() and (raw_tests.lower() == "auto" or raw_tests == default_tests):
        bus.log("[instrumentation] enabling assembly diagnostics")
        selected.add("asm")
    if profile.supports_professional_suite() and (raw_tests.lower() == "auto" or raw_tests == default_tests):
        bus.log("[instrumentation] enabling professional suite")
        selected.add("pro")

    if "uci"       in selected: uci.run(bus, rep, args.engine, movetime=args.movetime, instrumentation=profile)
    if "burst"     in selected: burst.run(bus, rep, args.engine, count=args.burst, movetime=args.movetime, instrumentation=profile)
    if "endurance" in selected: endurance.run(bus, rep, args.engine, duration_s=args.duration, movetime=args.movetime, instrumentation=profile)
    if "threads"   in selected: threads.run(bus, rep, args.engine, movetime=args.movetime, max_threads=args.threads_max, instrumentation=profile)
    if "multipv"   in selected: multipv.run(bus, rep, args.engine, movetime=args.movetime, multipv=4, instrumentation=profile)
    if "instances" in selected: instances.run(bus, rep, args.engine, instances=args.instances, per_instance=args.per_instance, movetime=args.movetime, instrumentation=profile)
    if "fuzz"      in selected: fuzz.run(bus, rep, args.engine, seconds=10, instrumentation=profile)
    if "pgn"       in selected and args.pgn_dir: pgnreplay.run(bus, rep, args.engine, pgn_dir=args.pgn_dir, movetime=args.movetime, max_games=200, instrumentation=profile)
    if "asm"       in selected: asmdebug.run(bus, rep, args.engine, instrumentation=profile)
    if "pro"       in selected: prosuite.run(bus, rep, args.engine, movetime=args.movetime, instrumentation=profile)

    rep.finish()
    print(rep.to_json())

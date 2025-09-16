import time
from core import EngineRunner
from instrumentation import InstrumentationProfile


def run(logger, report, path, instrumentation: InstrumentationProfile = None, capture_seconds: float = 1.5):
    manifest_path = None
    if instrumentation and instrumentation.manifest_path:
        manifest_path = str(instrumentation.manifest_path)
    report.add_test("assembly_debug", capture_seconds=capture_seconds, manifest=manifest_path)

    if not instrumentation or not instrumentation.supports_assembly_debug():
        logger.log("[ASM] instrumentation package not detected — skipping assembly diagnostics")
        if instrumentation and instrumentation.error:
            report.data.setdefault("notes", []).append(f"asm_debug manifest error: {instrumentation.error}")
        return

    logger.log(f"[ASM] instrumentation → {instrumentation.describe()}")
    if instrumentation.assembly_map:
        preview = instrumentation.assembly_map[:5]
        for entry in preview:
            sym = entry.get("symbol") or entry.get("name") or "?"
            addr = entry.get("address") or entry.get("offset") or "?"
            size = entry.get("size") or entry.get("bytes")
            logger.log(f"[ASM] breakpoint {sym} @ {addr} size={size}")
        if len(instrumentation.assembly_map) > len(preview):
            logger.log(f"[ASM] … {len(instrumentation.assembly_map) - len(preview)} more entries")

    try:
        with EngineRunner(path, instrumentation=instrumentation) as er:
            # Re-issue commands with logging to show activity.
            instrumentation.activate(er, logger=logger)
            probe_cmd = instrumentation.probes.get("asm_state") if instrumentation.probes else None
            if probe_cmd:
                try:
                    logger.log(f"[ASM] requesting probe: {probe_cmd}")
                    er.send_command(probe_cmd)
                except Exception as exc:  # pragma: no cover - defensive
                    logger.log(f"[ASM] probe command failed: {exc!r}")
            time.sleep(min(0.5, capture_seconds))
    except Exception as exc:
        logger.log(f"[ASM] engine session failed: {exc!r}")
        report.data.setdefault("notes", []).append(f"asm_debug error: {exc!r}")
        return

    trace = instrumentation.capture_trace_preview()
    if trace:
        lines = [ln for ln in trace.splitlines() if ln.strip()][:6]
        if lines:
            logger.log("[ASM] trace preview:")
            for line in lines:
                logger.log(f"[ASM] | {line}")
        else:
            logger.log("[ASM] trace file contained no printable lines")
    else:
        logger.log("[ASM] no trace data available")

    for warning in instrumentation.warnings:
        logger.log(f"[ASM] warning: {warning}")

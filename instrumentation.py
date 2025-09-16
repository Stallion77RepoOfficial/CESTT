"""Instrumentation detection and activation helpers for CESTT.

This module enables the toolkit to detect whether it was built alongside a
dedicated instrumentation package when the target chess engine was compiled.
If such a package is found a manifest file will describe the additional
capabilities that can be unlocked (assembly debug hooks, professional stress
suites, trace capture, ...).  The GUI/CLI will leverage this information to
expose advanced tests automatically.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def _iter_candidates(engine_path: Optional[str]) -> Iterable[Path]:
    """Yield possible manifest locations for *engine_path*.

    The instrumentation bundle may drop the manifest using different naming
    schemes.  We also honour the ``CESTT_MANIFEST`` environment variable for
    custom setups.
    """

    env_path = os.getenv("CESTT_MANIFEST")
    if env_path:
        p = Path(env_path).expanduser()
        if p.is_file():
            yield p

    if not engine_path:
        return

    engine = Path(engine_path)
    # Same directory with additional suffixes.
    yield engine.with_suffix(engine.suffix + ".cestt.json")
    yield engine.with_suffix(engine.suffix + ".cestt")
    # Same name with JSON extension.
    yield engine.parent / f"{engine.name}.cestt.json"
    yield engine.parent / f"{engine.stem}.cestt.json"
    # Generic manifests inside the directory.
    yield engine.parent / "cestt_manifest.json"
    yield engine.parent / "cestt-instrumentation.json"


def _load_manifest(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("manifest root must be an object")
        return data
    except json.JSONDecodeError:
        # Support a very small "key=value" manifest for ease of integration.
        data: Dict[str, Any] = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith(("#", ";")):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                data[key.strip()] = value.strip()
        if data:
            return data
        raise


@dataclass
class InstrumentationProfile:
    """Metadata describing the detected instrumentation package."""

    manifest_path: Optional[Path] = None
    manifest: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        caps = self.manifest.get("capabilities", {})
        if not isinstance(caps, dict):
            caps = {}
        self.capabilities: Dict[str, Any] = dict(caps)

        handshake = self.manifest.get("handshake", {})
        if not isinstance(handshake, dict):
            handshake = {}
        self.handshake_options: Dict[str, Any] = dict(handshake.get("options", {}))
        self.handshake_commands: List[str] = list(handshake.get("commands", []))

        token = handshake.get("token") or self.manifest.get("token")
        if token and "token" not in self.handshake_options:
            # Expose token both in meta and as an option helper.
            self.handshake_options.setdefault("CESTT Instrumentation Token", token)
        self.token = token

        self.probes: Dict[str, str] = dict(self.manifest.get("probes", {}))
        self.assembly_map: List[Dict[str, Any]] = list(self.manifest.get("assembly_map", []))
        suites = self.manifest.get("pro_tests", {})
        if isinstance(suites, list):
            suites = {name: {} for name in suites}
        if not isinstance(suites, dict):
            suites = {}
        self.pro_suites: Dict[str, Any] = suites

        self.trace_pipe: Optional[str] = self.manifest.get("trace_pipe")
        self.trace_preview_bytes: int = int(self.manifest.get("trace_preview_bytes", 4096))

        self.package = self.manifest.get("package")
        self.version = self.manifest.get("version")

        self.available: bool = bool(
            self.capabilities.get("assembly_debug")
            or self.capabilities.get("professional")
            or self.capabilities.get("pro_tests")
            or self.pro_suites
        )

    # ------------------------------------------------------------------ helpers
    def describe(self) -> str:
        if not self.manifest:
            return "no instrumentation"
        base = self.package or "unnamed package"
        if self.version:
            base = f"{base} v{self.version}"
        if self.token:
            base = f"{base} (token={self.token})"
        return base

    def to_report_dict(self) -> Dict[str, Any]:
        return {
            "detected": bool(self.manifest),
            "available": self.available,
            "manifest": str(self.manifest_path) if self.manifest_path else None,
            "package": self.package,
            "version": self.version,
            "capabilities": self.capabilities,
            "pro_suites": list(self.pro_suites.keys()),
            "warnings": list(self.warnings),
            "error": self.error,
        }

    # Capabilities ------------------------------------------------------------
    def supports_assembly_debug(self) -> bool:
        return bool(self.capabilities.get("assembly_debug"))

    def supports_professional_suite(self) -> bool:
        return bool(self.capabilities.get("professional") or self.pro_suites)

    @property
    def uci_options(self) -> Dict[str, Any]:
        return dict(self.handshake_options)

    def activate(self, runner: Any, logger: Optional[Any] = None) -> None:
        """Send handshake commands to an already running :class:`EngineRunner`.

        The runner is expected to expose a ``send_command`` method.  Any errors
        are captured inside ``self.warnings`` so the caller can surface them to
        the user.
        """

        for cmd in self.handshake_commands:
            try:
                runner.send_command(cmd)
                if logger:
                    logger.log(f"[instrumentation] → {cmd}")
            except Exception as exc:  # pragma: no cover - defensive
                msg = f"handshake command '{cmd}' failed: {exc!r}"
                self.warnings.append(msg)
                if logger:
                    logger.log(f"[instrumentation] {msg}")

    # Trace utilities --------------------------------------------------------
    def capture_trace_preview(self) -> str:
        if not self.trace_pipe:
            return ""
        path = Path(self.trace_pipe)
        if not path.exists() or not path.is_file():
            self.warnings.append(f"trace pipe '{path}' not found")
            return ""
        try:
            data = path.read_bytes()
        except Exception as exc:  # pragma: no cover - filesystem race
            self.warnings.append(f"trace read failed: {exc!r}")
            return ""
        if not data:
            return ""
        if len(data) > self.trace_preview_bytes:
            data = data[-self.trace_preview_bytes :]
        return data.decode("utf-8", errors="replace")

    def get_suite(self, name: str, default: Any = None) -> Any:
        return self.pro_suites.get(name, default)


def detect(engine_path: Optional[str]) -> InstrumentationProfile:
    last_error: Optional[str] = None
    for candidate in _iter_candidates(engine_path):
        if not candidate.exists():
            continue
        try:
            manifest = _load_manifest(candidate)
        except Exception as exc:  # pragma: no cover - malformed manifest
            last_error = f"failed to load {candidate}: {exc}"
            continue
        return InstrumentationProfile(candidate, manifest)

    if os.getenv("CESTT_ADVANCED", "").strip():
        manifest = {
            "package": "environment override",
            "version": "env",
            "capabilities": {"assembly_debug": True, "professional": True},
        }
        profile = InstrumentationProfile(None, manifest)
        profile.warnings.append("CESTT_ADVANCED environment flag forced enable")
        return profile

    profile = InstrumentationProfile(None, {})
    profile.error = last_error
    return profile


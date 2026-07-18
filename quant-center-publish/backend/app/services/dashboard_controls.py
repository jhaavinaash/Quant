"""Dashboard control actions from dashboard/app_ai.py header buttons."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

from app.core.config import settings
from app.schemas.dashboard import ControlResult
from app.services.dashboard_service import clear_live_price_cache

_last_engine_result: ControlResult | None = None


def get_last_engine_result() -> ControlResult | None:
    return _last_engine_result


def _set_engine_result(result: ControlResult) -> ControlResult:
    global _last_engine_result
    _last_engine_result = result
    return result


def _app_root() -> Path:
    return Path(settings.QUANT_BASE_DIR)


def _run_env() -> dict[str, str]:
    return {**os.environ, "PYTHONIOENCODING": "utf-8"}


def _append_engine_log(app_root: Path, header: str, body: str) -> None:
    try:
        log_path = app_root / "signals" / "engine_run.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        ts = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n{'=' * 60}\n{header}: {ts}\n{'=' * 60}\n{body}\n")
    except Exception:
        pass


def _dispatch_signal_alerts(app_root: Path) -> tuple[bool, bool, bool, int, str]:
    sa = app_root / "core" / "signal_alerts.py"
    if not sa.exists():
        return False, False, False, 0, "signal_alerts.py not found"

    try:
        spec = importlib.util.spec_from_file_location("signal_alerts", str(sa))
        if spec is None or spec.loader is None:
            return False, False, False, 0, "could not load signal_alerts"
        module = importlib.util.module_from_spec(spec)
        if str(app_root) not in sys.path:
            sys.path.insert(0, str(app_root))
        if str(sa.parent) not in sys.path:
            sys.path.insert(0, str(sa.parent))
        spec.loader.exec_module(module)
        result = module.dispatch_signals()
        tg_ok = bool(result.get("telegram", False))
        em_ok = bool(result.get("email", False))
        no_sigs = result.get("signals", 1) == 0
        log = f"signals={result.get('signals', 0)} tg={tg_ok} email={em_ok}"
        return tg_ok, em_ok, no_sigs, int(result.get("signals", 0)), log
    except Exception as exc:
        return False, False, False, 0, f"dispatch_signals() exception: {exc}"


class DashboardControlsService:
    @classmethod
    def refresh_data(cls) -> ControlResult:
        clear_live_price_cache()
        return _set_engine_result(ControlResult(kind="success", main="Data refreshed", hint=""))

    @classmethod
    def run_engines(cls) -> ControlResult:
        app_root = _app_root()
        run_env = _run_env()
        cleared = 0

        try:
            if str(app_root) not in sys.path:
                sys.path.insert(0, str(app_root))
            from Signals.pending_order_queue import PendingOrderQueue

            cleared = PendingOrderQueue().clear_pending_for_new_scan()
        except Exception as exc:
            return _set_engine_result(
                ControlResult(
                    kind="warning",
                    main=f"Signal Layer unavailable at scan start: {type(exc).__name__}: {exc}",
                    hint="",
                )
            )

        orch = None
        for candidate in [
            app_root / "core" / "orchestrator.py",
            app_root / "orchestrator.py",
        ]:
            if candidate.exists():
                orch = candidate
                break

        if orch is None:
            return _set_engine_result(
                ControlResult(
                    kind="error",
                    main="orchestrator.py not found — expected at project_root/core/ or project_root/",
                    hint="",
                )
            )

        rc_updater = None
        for candidate in [
            app_root / "core" / "result_calendar_updater.py",
            app_root / "result_calendar_updater.py",
            orch.parent / "result_calendar_updater.py",
        ]:
            if candidate.exists():
                rc_updater = candidate
                break

        if rc_updater:
            subprocess.run(
                [sys.executable, str(rc_updater)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                cwd=str(rc_updater.parent),
                timeout=60,
                env=run_env,
            )

        result = subprocess.run(
            [sys.executable, str(orch)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=str(orch.parent),
            timeout=600,
            env=run_env,
        )

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        full_log = (stdout + ("\n" + stderr if stderr else "")).strip()
        _append_engine_log(app_root, "Run", full_log)

        failed = [e for e in ["E1", "E2", "E3", "E4", "E5", "E6"] if f"{e} FAILED" in stdout]
        done = [e for e in ["E1", "E2", "E3", "E4", "E5", "E6"] if f"{e} completed" in stdout]
        empty = [
            e
            for e in ["E1", "E2", "E3", "E4", "E5", "E6"]
            if e not in failed
            and e not in done
            and f"Running {e}" in stdout
        ]

        tg_ok = em_ok = alert_run = no_sigs = False
        sa_log = ""
        if done:
            tg_ok, em_ok, no_sigs, _, sa_log = _dispatch_signal_alerts(app_root)
            alert_run = True
            _append_engine_log(app_root, "[ALERTS]", sa_log)

        pending_after = 0
        try:
            from Signals.pending_order_queue import PendingOrderQueue

            pending_after = PendingOrderQueue().stats().get("pending", 0)
        except Exception:
            pass

        dispatch_lines = []
        for line in stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith("Signal Layer dispatch:"):
                continue
            if "→ {" in stripped and stripped[:2] in (
                "E1",
                "E2",
                "E3",
                "E4",
                "E5",
                "E6",
                "F1",
                "G1",
                "R1",
                "S1",
            ):
                dispatch_lines.append(stripped)

        queue_line = (
            f"Signal Layer: cleared {cleared} · dispatched into {pending_after} pending"
        )
        if dispatch_lines:
            queue_line += " · " + " | ".join(dispatch_lines[:6])

        eng_line = f"{len(done)} ok · {len(empty)} empty · {len(failed)} failed"
        alert_line = ""
        if alert_run and not no_sigs:
            alert_line = ("TG ok" if tg_ok else "TG fail") + " · " + ("Email ok" if em_ok else "Email fail")

        main_msg = eng_line
        if alert_line:
            main_msg += f" · {alert_line}"
        main_msg += f"\n\n{queue_line}"
        if not failed:
            main_msg += " · click Refresh Data to load signals"
        else:
            main_msg += " · see signals/engine_run.log"

        hint = ""
        if alert_run and not tg_ok and not em_ok and not no_sigs:
            hint = (
                "Alerts not sent — check TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, "
                "EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER in config.py"
            )

        return _set_engine_result(
            ControlResult(
                kind="warning" if failed else "success",
                main=main_msg,
                hint=hint,
            )
        )

    @classmethod
    def run_s1(cls) -> ControlResult:
        app_root = _app_root()
        run_env = _run_env()
        claude1 = app_root / "engines" / "claude_system1_live.py"

        try:
            if str(app_root) not in sys.path:
                sys.path.insert(0, str(app_root))
            from Signals.pending_order_queue import PendingOrderQueue

            PendingOrderQueue().clear_pending_for_new_scan()
        except Exception:
            pass

        if not claude1.exists():
            return _set_engine_result(
                ControlResult(
                    kind="error",
                    main=f"claude_system1_live.py not found at {claude1}",
                    hint="Copy Claude1 files into engines/ folder.",
                )
            )

        s1_res = subprocess.run(
            [sys.executable, str(claude1)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=str(claude1.parent),
            timeout=900,
            env=run_env,
        )

        s1_out = (s1_res.stdout or "").strip()
        s1_err = (s1_res.stderr or "").strip()
        s1_full = (s1_out + ("\n" + s1_err if s1_err else "")).strip()
        s1_ok = (s1_res.returncode == 0) and ("Pipeline complete" in s1_out)
        _append_engine_log(app_root, "S1 Run", s1_full)

        s1_count = 0
        for line in s1_out.splitlines():
            if "S1 signals in master queue" in line or "Appended" in line:
                for token in line.split():
                    if token.isdigit():
                        s1_count = int(token)
                        break
                if s1_count:
                    break

        tg_ok = em_ok = alert_run = False
        if s1_ok and s1_count > 0:
            tg_ok, em_ok, _, _, sa_log = _dispatch_signal_alerts(app_root)
            alert_run = True
            _append_engine_log(app_root, "[S1 ALERTS]", sa_log)

        if not s1_ok:
            return _set_engine_result(
                ControlResult(
                    kind="error",
                    main="S1 pipeline failed — see signals/engine_run.log",
                    hint="",
                )
            )
        if s1_count == 0:
            return _set_engine_result(
                ControlResult(
                    kind="warning",
                    main="S1 pipeline ok · 0 signals today · nothing appended",
                    hint="",
                )
            )

        main_msg = f"S1 ok · {s1_count} signal(s) appended"
        if alert_run:
            main_msg += " · " + ("TG ok" if tg_ok else "TG fail")
            main_msg += " " + ("Email ok" if em_ok else "Email fail")
        main_msg += " · click Refresh data to see in queue"

        return _set_engine_result(ControlResult(kind="success", main=main_msg, hint=""))

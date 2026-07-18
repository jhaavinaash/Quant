"""Open-position alert classification from dashboard/app_ai.py (trades_log local view).

Source: dashboard/app_ai.py — TAB 2 OPEN POSITIONS, _alert() + SL_Gap%/TP_Gap% formulas.
Logic copied exactly; do not modify thresholds or labels here.
"""


def sl_gap_pct(current_price: float, stop_loss: float) -> float:
    return (current_price - stop_loss) / current_price * 100


def tp_gap_pct(target: float, current_price: float) -> float:
    return (target - current_price) / current_price * 100


def classify_position_alert(
    *,
    current_price: float | None,
    stop_loss: float | None,
    target: float | None,
    live_pnl: float,
) -> str:
    """Return the dashboard Alert label for one open position."""
    try:
        if current_price is None or stop_loss is None or target is None:
            raise ValueError("missing price inputs")
        sl = sl_gap_pct(current_price, stop_loss)
        tp = tp_gap_pct(target, current_price)
        if sl <= 0:
            return "🚨 SL BREACHED"
        if sl <= 2:
            return "🔴 Near SL"
        if sl <= 5:
            return "🟡 Watch SL"
        if tp <= 2:
            return "🎯 Near Target"
        if float(live_pnl) > 0:
            return "🟢 Profit"
    except Exception:
        pass
    return "⚪ Hold"

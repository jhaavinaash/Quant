"""F1 Basket — preview, deployment, live management (Phase 1–3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from app.schemas.f1_basket import (
    BasketActionResult,
    BasketConstituentRow,
    BasketDeployConfirmation,
    BasketDeploymentProgress,
    BasketEligibility,
    BasketExitProgress,
    BasketPreviewSummary,
    BasketStrategyParams,
    F1BasketSnapshot,
    F1BuyCandidateRow,
)
from app.services.f1_basket.allocation import allocate_controlled_entry
from app.services.f1_basket.controlled_entry import (
    SlotSelection,
    deploy_selected_slots,
)
from app.services.f1_basket.holdings import load_broker_holdings
from app.services.f1_basket.constants import (
    BASKET_SIZE,
    BUY_COST_PCT,
    FILL_PENDING,
    HARD_STOP_PCT,
    INITIAL_CAPITAL,
    PROFIT_TARGET_PCT,
    SELL_COST_PCT,
    STATUS_ACTIVE,
    STATUS_CLOSED,
    STATUS_DEPLOYING,
    STATUS_EXITING,
    STATUS_EXIT_PENDING,
    STATUS_NOT_READY,
    STATUS_READY,
    STRATEGY_NAME,
    TERMINAL_FAILURE_STATUSES,
    EXIT_REASON_MANUAL,
    EXIT_REASON_STOP,
    EXIT_REASON_TARGET,
    SELL_TERMINAL_FAILURE,
)
from app.services.f1_basket.deployment import check_deploy_gate, deploy_basket_orders
from app.services.f1_basket.exit import (
    exit_progress,
    initiate_manual_exit,
    mark_exit_trigger,
    submit_basket_exits,
    sync_basket_exits,
)
from app.services.f1_basket.live_valuation import value_active_basket
from app.services.f1_basket.reconciliation import deployment_progress, sync_basket_fills
from app.services.f1_basket.selection import (
    eligibility_from_candidates,
    extract_buy_candidates,
    load_f1_decisions_df,
    select_top_n,
)
from app.services.f1_basket.store import get_basket_store
from app.services.f1_basket.valuation import value_basket


class F1BasketService:
    @staticmethod
    def _strategy_header() -> BasketStrategyParams:
        return BasketStrategyParams(
            strategyName=STRATEGY_NAME,
            basketSize=BASKET_SIZE,
            initialCapital=INITIAL_CAPITAL,
            profitTargetPct=PROFIT_TARGET_PCT * 100,
            hardStopPct=HARD_STOP_PCT * 100,
            buyCostPct=BUY_COST_PCT * 100,
            sellCostPct=SELL_COST_PCT * 100,
            weighting="equal",
        )

    @staticmethod
    def _candidate_rows(candidates: list) -> list[F1BuyCandidateRow]:
        return [
            F1BuyCandidateRow(
                ticker=c.ticker,
                portfolioRank=c.portfolio_rank,
                action=c.action,
                technicalState=c.technical_state,
                sectorState=c.sector_state,
                businessGate=c.business_gate,
                sector=c.sector,
                referencePrice=c.reference_price,
                heldGlobally=c.held_globally,
                heldConflict=c.held_conflict,
            )
            for c in candidates
        ]

    @classmethod
    def get_eligibility(
        cls,
        *,
        decisions_path: Path | None = None,
    ) -> BasketEligibility:
        df = load_f1_decisions_df(decisions_path)
        candidates, ts, total = extract_buy_candidates(df)
        el = eligibility_from_candidates(candidates, ts, total)
        return BasketEligibility(
            f1DecisionTimestamp=el["f1_decision_timestamp"],
            totalDecisions=el["total_decisions"],
            buyCandidateCount=el["buy_candidate_count"],
            requiredConstituents=el["required_constituents"],
            availableCandidates=el["available_candidates"],
            missingCandidates=el["missing_candidates"],
            ready=el["ready"],
            status=el["status"],
            topCandidates=cls._candidate_rows(el["top_candidates"]),
        )

    @classmethod
    def get_snapshot(cls) -> F1BasketSnapshot:
        elig = cls.get_eligibility()
        store = get_basket_store()
        basket_raw = store.get_current_operational_basket()
        preview = None
        msg = ""
        if not elig.ready and not basket_raw:
            msg = (
                f"NOT READY — {elig.availableCandidates}/{elig.requiredConstituents} "
                f"F1 BUY candidates ({elig.missingCandidates} more required)."
            )
        if basket_raw:
            preview = cls._build_basket_summary(basket_raw, elig.f1DecisionTimestamp)
            if basket_raw.get("status") == STATUS_DEPLOYING and preview.deploymentIncomplete:
                msg = "DEPLOYMENT INCOMPLETE — review constituent statuses."
            elif basket_raw.get("status") == STATUS_ACTIVE:
                msg = "Basket ACTIVE — monitored every 5 min during market hours."
            elif basket_raw.get("status") in (STATUS_EXIT_PENDING, STATUS_EXITING):
                msg = preview.deployBlockReason or "Basket exit in progress."
            elif basket_raw.get("status") == STATUS_CLOSED:
                msg = f"Basket CLOSED — {preview.exitReason or 'completed'}."
            elif basket_raw.get("status") == STATUS_READY and not preview.deployAllowed:
                msg = preview.deployBlockReason or msg
        return F1BasketSnapshot(
            strategy=cls._strategy_header(),
            eligibility=elig,
            preview=preview,
            message=msg,
        )

    @classmethod
    def get_deploy_confirmation(cls, basket_id: str) -> BasketDeployConfirmation | None:
        store = get_basket_store()
        basket = store.get_basket(basket_id)
        if not basket:
            return None
        elig = cls.get_eligibility()
        stale = (
            bool(basket.get("f1_snapshot_timestamp"))
            and bool(elig.f1DecisionTimestamp)
            and basket["f1_snapshot_timestamp"] != elig.f1DecisionTimestamp
        )
        gate = check_deploy_gate(basket, current_f1_timestamp=elig.f1DecisionTimestamp, stale=stale)
        if not gate.allowed:
            return None
        cons = cls._constituent_rows_from_raw(basket.get("constituents") or [], {})
        return BasketDeployConfirmation(
            basketId=basket_id,
            capital=float(basket["initial_capital"]),
            stockCount=BASKET_SIZE,
            totalEstimatedInvestment=float(basket["allocated_capital"]),
            estimatedBuyCost=sum(c.buyCost for c in cons),
            cashRemaining=float(basket["cash_remaining"]),
            broker="Zerodha",
            constituents=cons,
        )

    @classmethod
    def deploy_basket(cls, basket_id: str) -> BasketActionResult:
        elig = cls.get_eligibility()
        result = deploy_basket_orders(
            basket_id,
            current_f1_timestamp=elig.f1DecisionTimestamp,
        )
        snap = cls.get_snapshot()
        return BasketActionResult(
            success=result.submitted > 0 or result.skipped > 0,
            message=result.message,
            snapshot=snap,
        )

    @classmethod
    def sync_valuation(cls, basket_id: str) -> BasketActionResult:
        store = get_basket_store()
        basket = store.get_basket(basket_id)
        if not basket:
            return BasketActionResult(success=False, message="Basket not found.", snapshot=cls.get_snapshot())
        st = basket.get("status")
        if st == STATUS_DEPLOYING:
            sync = sync_basket_fills(basket_id)
            msg = sync.message
        elif st in (STATUS_ACTIVE, STATUS_EXIT_PENDING):
            result = value_active_basket(basket_id)
            msg = result.message if result else "valuation failed"
            if result and result.trigger in ("TARGET", "STOP") and st == STATUS_ACTIVE:
                reason = EXIT_REASON_TARGET if result.trigger == "TARGET" else EXIT_REASON_STOP
                if mark_exit_trigger(
                    basket_id, trigger=result.trigger, reason=reason,
                    trigger_value=result.valuation.gross_market_value,
                ):
                    submit_basket_exits(basket_id)
                    msg += f" · {result.trigger} exit initiated"
        elif st == STATUS_EXITING:
            sync = sync_basket_exits(basket_id)
            msg = sync.message
        else:
            msg = f"No valuation sync for status {st}"
        return BasketActionResult(success=True, message=msg, snapshot=cls.get_snapshot())

    @classmethod
    def manual_exit_basket(cls, basket_id: str) -> BasketActionResult:
        result = initiate_manual_exit(basket_id)
        return BasketActionResult(
            success=result.submitted > 0 or result.skipped > 0,
            message=result.message,
            snapshot=cls.get_snapshot(),
        )

    @classmethod
    def retry_failed_exits(cls, basket_id: str) -> BasketActionResult:
        result = submit_basket_exits(basket_id, retry_failed_only=True)
        return BasketActionResult(
            success=result.submitted > 0,
            message=result.message,
            snapshot=cls.get_snapshot(),
        )

    @classmethod
    def sync_basket(cls, basket_id: str) -> BasketActionResult:
        sync = sync_basket_fills(basket_id)
        snap = cls.get_snapshot()
        return BasketActionResult(
            success=True,
            message=sync.message,
            snapshot=snap,
        )

    @classmethod
    def retry_failed_orders(cls, basket_id: str) -> BasketActionResult:
        elig = cls.get_eligibility()
        result = deploy_basket_orders(
            basket_id,
            current_f1_timestamp=elig.f1DecisionTimestamp,
            retry_failed_only=True,
        )
        snap = cls.get_snapshot()
        return BasketActionResult(
            success=result.submitted > 0,
            message=result.message,
            snapshot=snap,
        )

    @staticmethod
    def _constituent_rows_from_raw(
        cons_raw: list[dict], cv_map: dict
    ) -> list[BasketConstituentRow]:
        rows = []
        for c in cons_raw:
            cv = cv_map.get(c["ticker"])
            rows.append(
                BasketConstituentRow(
                    selectionOrder=int(c["selection_order"]),
                    ticker=c["ticker"],
                    portfolioRank=float(c["portfolio_rank"] or 0),
                    targetWeight=float(c["target_weight"]),
                    referencePrice=float(c["reference_price"]),
                    quantity=float(c["quantity"]),
                    grossAllocation=float(c["gross_buy_value"]),
                    buyCost=float(c["estimated_buy_cost"]),
                    totalEntryCost=float(c["estimated_total_entry_cost"]),
                    currentPrice=cv.current_price if cv else float(c.get("current_price") or c["reference_price"]),
                    currentValue=cv.current_market_value if cv else float(c.get("current_market_value") or c["gross_buy_value"]),
                    pnl=cv.constituent_pnl if cv else float(c.get("constituent_pnl") or 0),
                    returnPct=cv.constituent_return_pct if cv else float(c.get("constituent_return_pct") or 0),
                    heldGloballyAtSelection=bool(c.get("held_globally_at_selection")),
                    f1ActionAtSelection=str(c.get("f1_action_at_selection") or ""),
                    technicalStateAtSelection=str(c.get("technical_state_at_selection") or ""),
                    sectorStateAtSelection=str(c.get("sector_state_at_selection") or ""),
                    businessGateAtSelection=str(c.get("business_gate_at_selection") or ""),
                    sectorAtSelection=str(c.get("sector_at_selection") or ""),
                    brokerOrderId=str(c.get("broker_order_id") or ""),
                    fillStatus=str(c.get("fill_status") or FILL_PENDING),
                    filledQty=float(c.get("filled_qty") or 0),
                    averageFillPrice=float(c.get("average_fill_price") or 0),
                    lastError=str(c.get("last_error") or ""),
                    avgBuyPrice=float(c.get("average_fill_price") or c.get("reference_price") or 0),
                    sellBrokerOrderId=str(c.get("sell_broker_order_id") or ""),
                    sellStatus=str(c.get("sell_status") or ""),
                    sellFilledQty=float(c.get("sell_filled_qty") or 0),
                    averageSellFillPrice=float(c.get("average_sell_fill_price") or 0),
                    sellLastError=str(c.get("sell_last_error") or ""),
                    targetSlotExposure=float(c.get("target_slot_exposure") or c.get("allocated_amount") or 0),
                    currentBrokerQty=float(c.get("current_broker_qty") or 0),
                    currentExposure=float(c.get("current_exposure") or 0),
                    exposureGap=float(c.get("exposure_gap") or 0),
                    recommendedBuyQty=float(c.get("recommended_buy_qty") or c.get("quantity") or 0),
                    recommendedBuyValue=float(c.get("recommended_buy_value") or c.get("gross_buy_value") or 0),
                    adoptedExistingQty=float(c.get("adopted_existing_qty") or 0),
                    basketBoughtQty=float(c.get("basket_bought_qty") or 0),
                    basketAttributedQty=float(c.get("basket_attributed_qty") or 0),
                    slotResolved=bool(int(c.get("slot_resolved") or 0)),
                    slotSkipped=bool(int(c.get("slot_skipped") or 0)),
                    attributionPrice=float(c.get("attribution_price") or 0),
                )
            )
        return rows

    @classmethod
    def _build_basket_summary(
        cls, basket: dict, current_f1_ts: str
    ) -> BasketPreviewSummary:
        cons_raw = basket.get("constituents") or []
        cons_for_val = []
        for c in cons_raw:
            qty = float(c.get("basket_attributed_qty") or 0)
            if qty <= 0 and basket.get("status") in (STATUS_READY, STATUS_DEPLOYING):
                adopted_preview = float(c.get("current_exposure") or 0)
                rec_buy = float(c.get("recommended_buy_value") or 0)
                gross = min(float(c.get("target_slot_exposure") or c.get("allocated_amount") or 0), adopted_preview + rec_buy)
                qty = float(c.get("recommended_buy_qty") or c.get("quantity") or 0)
            else:
                gross = float(c.get("gross_buy_value") or 0)
            if qty <= 0 and gross <= 0:
                qty = float(c.get("quantity") or 0)
                gross = float(c.get("gross_buy_value") or 0)
            cons_for_val.append(
                {
                    "ticker": c["ticker"],
                    "quantity": qty if float(c.get("basket_attributed_qty") or 0) <= 0 else float(c.get("basket_attributed_qty") or 0),
                    "gross_buy_value": gross,
                    "reference_price": c["reference_price"],
                    "current_price": c.get("current_price") or c["reference_price"],
                }
            )
        val = value_basket(
            basket_start_value=float(basket["basket_start_value"]),
            target_value=float(basket["target_value"]),
            stop_value=float(basket["stop_value"]),
            profit_target_pct=PROFIT_TARGET_PCT,
            hard_stop_pct=HARD_STOP_PCT,
            sell_cost_pct=SELL_COST_PCT,
            constituents=cons_for_val,
        )
        cv_map = {cv.ticker: cv for cv in val.constituents}
        held_conflicts = [
            c["ticker"] for c in cons_raw if c.get("held_globally_at_selection")
        ]
        stale = (
            bool(basket.get("f1_snapshot_timestamp"))
            and bool(current_f1_ts)
            and basket["f1_snapshot_timestamp"] != current_f1_ts
            and basket.get("status") == STATUS_READY
        )
        rows = cls._constituent_rows_from_raw(cons_raw, cv_map)
        progress_raw = deployment_progress(cons_raw)
        progress = BasketDeploymentProgress(**progress_raw) if cons_raw else None
        resolved_slots = sum(1 for c in cons_raw if int(c.get("slot_resolved") or 0) == 1)
        gate = check_deploy_gate(basket, current_f1_timestamp=current_f1_ts, stale=stale)
        can_deploy_selected = (
            basket.get("status") in (STATUS_READY, STATUS_DEPLOYING)
            and resolved_slots < BASKET_SIZE
            and not stale
            and (gate.allowed if basket.get("status") == STATUS_READY else True)
        )
        can_retry = basket.get("status") == STATUS_DEPLOYING and any(
            str(c.get("fill_status") or "").upper() in TERMINAL_FAILURE_STATUSES
            for c in cons_raw
        )
        deployment_incomplete = basket.get("status") == STATUS_DEPLOYING and resolved_slots < BASKET_SIZE and (
            progress_raw.get("failed", 0) > 0
            or progress_raw.get("partial", 0) > 0
        )
        exit_prog_raw = exit_progress(cons_raw) if basket.get("status") in (STATUS_EXIT_PENDING, STATUS_EXITING, STATUS_CLOSED) else None
        exit_progress_model = BasketExitProgress(**exit_prog_raw) if exit_prog_raw else None
        can_retry_exits = basket.get("status") == STATUS_EXITING and any(
            str(c.get("sell_status") or "").upper() in SELL_TERMINAL_FAILURE for c in cons_raw
        )
        return BasketPreviewSummary(
            basketId=basket["basket_id"],
            status=basket["status"],
            createdAt=basket["created_at"],
            selectionSnapshotTimestamp=basket["f1_snapshot_timestamp"],
            currentF1DecisionTimestamp=current_f1_ts,
            previewStale=stale,
            capital=float(basket["initial_capital"]),
            allocated=float(basket["allocated_capital"]),
            cashRemaining=float(basket["cash_remaining"]),
            basketStartValue=float(basket["basket_start_value"]),
            targetValue=float(basket["target_value"]),
            stopValue=float(basket["stop_value"]),
            estimatedBuyCost=sum(float(c["estimated_buy_cost"]) for c in cons_raw),
            estimatedExitCost=val.estimated_exit_cost,
            grossMarketValue=val.gross_market_value,
            netLiquidationValue=val.net_liquidation_value,
            grossPnl=val.gross_pnl,
            netPnl=val.net_pnl,
            basketReturnPct=val.return_pct,
            distanceToTargetPct=val.distance_to_target_pct,
            distanceToStopPct=val.distance_to_stop_pct,
            currentTrigger=val.trigger,
            heldConflicts=held_conflicts,
            constituents=rows,
            deploymentProgress=progress,
            deployAllowed=gate.allowed and basket.get("status") == STATUS_READY,
            deployBlockReason="" if gate.allowed else gate.reason,
            canRetryFailed=can_retry,
            deploymentIncomplete=deployment_incomplete or (
                basket.get("status") == STATUS_DEPLOYING and resolved_slots < BASKET_SIZE
            ),
            resolvedSlots=resolved_slots,
            maxSlots=BASKET_SIZE,
            canDeploySelected=can_deploy_selected,
            broker="Zerodha",
            startedAt=str(basket.get("started_at") or ""),
            completedAt=str(basket.get("completed_at") or ""),
            exitTrigger=str(basket.get("exit_trigger") or ""),
            exitReason=str(basket.get("exit_reason") or ""),
            triggeredAt=str(basket.get("triggered_at") or ""),
            lastValuedAt=str(basket.get("last_valued_at") or ""),
            canManualExit=basket.get("status") == STATUS_ACTIVE,
            canRetryFailedExits=can_retry_exits,
            exitIncomplete=basket.get("status") == STATUS_EXITING and (exit_prog_raw or {}).get("complete", 0) < BASKET_SIZE,
            exitProgress=exit_progress_model,
        )

    @classmethod
    def create_preview(cls, capital: float = INITIAL_CAPITAL) -> F1BasketSnapshot:
        df = load_f1_decisions_df()
        candidates, ts, total = extract_buy_candidates(df)
        el = eligibility_from_candidates(candidates, ts, total)
        if not el["ready"]:
            return F1BasketSnapshot(
                strategy=cls._strategy_header(),
                eligibility=cls.get_eligibility(),
                preview=None,
                message=(
                    f"Cannot create preview: NOT_READY "
                    f"({el['available_candidates']}/{el['required_constituents']} BUY candidates)."
                ),
            )
        selected = select_top_n(el["top_candidates"])
        holdings = load_broker_holdings()
        alloc = allocate_controlled_entry(
            selected,
            capital,
            holdings,
            basket_size=BASKET_SIZE,
            profit_target_pct=PROFIT_TARGET_PCT,
            hard_stop_pct=HARD_STOP_PCT,
        )
        store = get_basket_store()
        store.delete_preview_baskets()
        basket_id = store.create_preview_basket(
            allocation=alloc,
            f1_timestamp=ts,
            status=STATUS_READY,
        )
        basket = store.get_basket(basket_id)
        assert basket
        preview = cls._build_basket_summary(basket, ts)
        return F1BasketSnapshot(
            strategy=cls._strategy_header(),
            eligibility=cls.get_eligibility(),
            preview=preview,
            message="Basket preview created (READY).",
        )

    @classmethod
    def deploy_selected(cls, basket_id: str, selections: list[dict]) -> BasketActionResult:
        elig = cls.get_eligibility()
        slot_sels = [
            SlotSelection(
                ticker=s["ticker"],
                execute=bool(s.get("execute", False)),
                adopt_existing_qty=int(s.get("adoptExistingQty") or s.get("adopt_existing_qty") or 0),
            )
            for s in selections
        ]
        result = deploy_selected_slots(
            basket_id,
            slot_sels,
            current_f1_timestamp=elig.f1DecisionTimestamp,
        )
        snap = cls.get_snapshot()
        return BasketActionResult(
            success=result.submitted > 0 or result.resolved > 0,
            message=result.message,
            snapshot=snap,
        )

    @classmethod
    def rebuild_preview(cls, capital: float = INITIAL_CAPITAL) -> F1BasketSnapshot:
        return cls.create_preview(capital=capital)

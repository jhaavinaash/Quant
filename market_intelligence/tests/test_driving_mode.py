"""Tests for deterministic Driving Mode selection."""

from __future__ import annotations

import itertools
import unittest
from datetime import datetime

from market_intelligence import (
    ConfidenceLevel,
    DrivingMode,
    DrivingModeEngine,
    DrivingModeName,
    DrivingModeRules,
    LeadershipCondition,
    LeadershipResult,
    LeadershipState,
    MarketConditions,
    ParticipationCondition,
    ParticipationResult,
    ParticipationState,
    StressCondition,
    StressResult,
    StressState,
    TrendCondition,
    TrendResult,
    TrendState,
    determine_driving_mode,
)

AS_OF = datetime(2026, 6, 16)


def _trend_condition(state: TrendState) -> TrendCondition:
    raw = TrendResult(
        as_of=AS_OF,
        constituent_count=100,
        universe_level=1.0,
        medium_average=1.0,
        long_average=1.0,
        distance_from_medium=0.0,
        distance_from_long=0.0,
    )
    return TrendCondition(raw=raw, state=state, explanation="Trend explanation.")


def _participation_condition(
    state: ParticipationState,
) -> ParticipationCondition:
    raw = ParticipationResult(
        as_of=AS_OF,
        constituent_count=100,
        medium_coverage=100,
        long_coverage=100,
        above_medium_count=50,
        above_long_count=50,
        above_medium_share=0.5,
        above_long_share=0.5,
        medium_breadth_change=0.0,
        change_window=5,
    )
    return ParticipationCondition(
        raw=raw,
        state=state,
        explanation="Participation explanation.",
    )


def _leadership_condition(state: LeadershipState) -> LeadershipCondition:
    raw = LeadershipResult(
        as_of=AS_OF,
        lookback=20,
        eligible_constituent_count=100,
        positive_constituent_count=50,
        positive_return_share=0.5,
        leadership_concentration=0.02,
        effective_leader_count=50.0,
        sector_count=10,
        positive_sector_share=0.5,
    )
    return LeadershipCondition(
        raw=raw,
        state=state,
        explanation="Leadership explanation.",
    )


def _stress_condition(state: StressState) -> StressCondition:
    raw = StressResult(
        as_of=AS_OF,
        constituent_count=100,
        universe_drawdown=0.0,
        new_low_count=0,
        new_low_coverage=100,
        new_low_share=0.0,
        persistent_breadth_change=0.0,
        breadth_declining_days=0,
        breadth_change_observations=20,
        downside_deviation=0.0,
    )
    return StressCondition(
        raw=raw,
        state=state,
        explanation="Stress explanation.",
    )


def _conditions(
    trend: TrendState,
    participation: ParticipationState,
    leadership: LeadershipState,
    stress: StressState,
) -> MarketConditions:
    return MarketConditions(
        as_of=AS_OF,
        trend=_trend_condition(trend),
        participation=_participation_condition(participation),
        leadership=_leadership_condition(leadership),
        stress=_stress_condition(stress),
    )


class DrivingModeSelectionTests(unittest.TestCase):
    def test_aggressive_requires_full_opportunity_and_low_stress(self) -> None:
        result = determine_driving_mode(
            _conditions(
                TrendState.STRONG,
                ParticipationState.BROAD,
                LeadershipState.BROAD,
                StressState.LOW,
            )
        )

        self.assertEqual(result.mode, DrivingModeName.AGGRESSIVE)
        self.assertEqual(result.confidence, ConfidenceLevel.HIGH)

    def test_normal_has_no_trigger_but_is_not_fully_favorable(self) -> None:
        result = determine_driving_mode(
            _conditions(
                TrendState.NEUTRAL,
                ParticipationState.AVERAGE,
                LeadershipState.BROAD,
                StressState.LOW,
            )
        )

        self.assertEqual(result.mode, DrivingModeName.NORMAL)

    def test_cautious_for_elevated_stress(self) -> None:
        result = determine_driving_mode(
            _conditions(
                TrendState.STRONG,
                ParticipationState.BROAD,
                LeadershipState.BROAD,
                StressState.ELEVATED,
            )
        )

        self.assertEqual(result.mode, DrivingModeName.CAUTIOUS)
        self.assertIn("Stress is Elevated", result.reason)

    def test_cautious_for_concentrated_leadership(self) -> None:
        result = determine_driving_mode(
            _conditions(
                TrendState.STRONG,
                ParticipationState.BROAD,
                LeadershipState.CONCENTRATED,
                StressState.LOW,
            )
        )

        self.assertEqual(result.mode, DrivingModeName.CAUTIOUS)
        self.assertIn("Concentrated", result.reason)

    def test_cautious_for_one_adverse_opportunity_dimension(self) -> None:
        result = determine_driving_mode(
            _conditions(
                TrendState.WEAK,
                ParticipationState.BROAD,
                LeadershipState.BROAD,
                StressState.LOW,
            )
        )

        self.assertEqual(result.mode, DrivingModeName.CAUTIOUS)
        self.assertIn("Trend is Weak", result.reason)

    def test_defensive_for_high_stress_even_with_strong_opportunity(self) -> None:
        result = determine_driving_mode(
            _conditions(
                TrendState.STRONG,
                ParticipationState.BROAD,
                LeadershipState.BROAD,
                StressState.HIGH,
            )
        )

        self.assertEqual(result.mode, DrivingModeName.DEFENSIVE)
        self.assertIn("defensive override", result.reason)
        self.assertEqual(result.confidence, ConfidenceLevel.MEDIUM)

    def test_defensive_for_multiple_adverse_opportunity_dimensions(self) -> None:
        result = determine_driving_mode(
            _conditions(
                TrendState.WEAK,
                ParticipationState.NARROW,
                LeadershipState.BROAD,
                StressState.LOW,
            )
        )

        self.assertEqual(result.mode, DrivingModeName.DEFENSIVE)
        self.assertIn("2 opportunity dimensions", result.reason)

    def test_unavailable_condition_is_cautious_with_low_confidence(self) -> None:
        result = determine_driving_mode(
            _conditions(
                TrendState.UNAVAILABLE,
                ParticipationState.BROAD,
                LeadershipState.BROAD,
                StressState.LOW,
            )
        )

        self.assertEqual(result.mode, DrivingModeName.CAUTIOUS)
        self.assertEqual(result.confidence, ConfidenceLevel.LOW)
        self.assertIn("unavailable", result.reason)


class DrivingModeRuleTests(unittest.TestCase):
    def test_rule_configuration_changes_only_declared_behavior(self) -> None:
        conditions = _conditions(
            TrendState.WEAK,
            ParticipationState.NARROW,
            LeadershipState.BROAD,
            StressState.LOW,
        )

        default = determine_driving_mode(conditions)
        configured = determine_driving_mode(
            conditions,
            DrivingModeRules(
                defensive_adverse_dimensions_required=3,
            ),
        )

        self.assertEqual(default.mode, DrivingModeName.DEFENSIVE)
        self.assertEqual(configured.mode, DrivingModeName.CAUTIOUS)

    def test_high_stress_override_can_be_configured(self) -> None:
        conditions = _conditions(
            TrendState.STRONG,
            ParticipationState.BROAD,
            LeadershipState.BROAD,
            StressState.HIGH,
        )
        result = determine_driving_mode(
            conditions,
            DrivingModeRules(defensive_on_high_stress=False),
        )

        self.assertEqual(result.mode, DrivingModeName.CAUTIOUS)

    def test_invalid_rule_order_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            DrivingModeRules(
                defensive_adverse_dimensions_required=1,
                normal_adverse_dimensions_allowed=1,
            )


class DrivingModeCompletenessTests(unittest.TestCase):
    def test_all_state_combinations_are_deterministic_and_explainable(self) -> None:
        combinations = itertools.product(
            list(TrendState),
            list(ParticipationState),
            list(LeadershipState),
            list(StressState),
        )
        checked = 0
        for trend, participation, leadership, stress in combinations:
            conditions = _conditions(
                trend,
                participation,
                leadership,
                stress,
            )
            first = DrivingModeEngine().determine(conditions)
            second = DrivingModeEngine().determine(conditions)

            self.assertEqual(first, second)
            self.assertIsInstance(first, DrivingMode)
            self.assertIn(first.mode, list(DrivingModeName))
            self.assertTrue(first.reason)
            self.assertTrue(first.dimensions.trend)
            self.assertTrue(first.dimensions.participation)
            self.assertTrue(first.dimensions.leadership)
            self.assertTrue(first.dimensions.stress)
            checked += 1

        self.assertEqual(checked, 256)

    def test_output_contains_no_raw_metrics_or_decision_controls(self) -> None:
        result = determine_driving_mode(
            _conditions(
                TrendState.STRONG,
                ParticipationState.BROAD,
                LeadershipState.BROAD,
                StressState.LOW,
            )
        ).as_dict()

        self.assertEqual(
            set(result),
            {"as_of", "mode", "reason", "dimensions", "confidence"},
        )
        self.assertNotIn("raw", result)
        self.assertNotIn("risk_o_meter", result)
        self.assertNotIn("f1", result)


if __name__ == "__main__":
    unittest.main()

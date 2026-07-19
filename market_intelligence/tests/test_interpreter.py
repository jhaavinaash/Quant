"""Comprehensive tests for independent metric interpretation."""

from __future__ import annotations

import unittest
from datetime import datetime

from market_intelligence import (
    InterpretationConfig,
    LeadershipInterpretationThresholds,
    LeadershipResult,
    LeadershipState,
    MarketConditions,
    MarketIntelligence,
    MarketIntelligenceInterpreter,
    ParticipationInterpretationThresholds,
    ParticipationResult,
    ParticipationState,
    StressInterpretationThresholds,
    StressResult,
    StressState,
    TrendInterpretationThresholds,
    TrendResult,
    TrendState,
    interpret_leadership,
    interpret_participation,
    interpret_stress,
    interpret_trend,
)

AS_OF = datetime(2026, 6, 16)


def _trend(medium: float | None, long: float | None) -> TrendResult:
    return TrendResult(
        as_of=AS_OF,
        constituent_count=100,
        universe_level=1.0,
        medium_average=1.0,
        long_average=1.0,
        distance_from_medium=medium,
        distance_from_long=long,
    )


def _participation(
    medium: float | None,
    long: float | None,
) -> ParticipationResult:
    return ParticipationResult(
        as_of=AS_OF,
        constituent_count=100,
        medium_coverage=100,
        long_coverage=100,
        above_medium_count=0 if medium is None else round(medium * 100),
        above_long_count=0 if long is None else round(long * 100),
        above_medium_share=medium,
        above_long_share=long,
        medium_breadth_change=0.0,
        change_window=5,
    )


def _leadership(
    positive_share: float | None,
    effective_count: float | None,
    sector_share: float | None,
) -> LeadershipResult:
    return LeadershipResult(
        as_of=AS_OF,
        lookback=20,
        eligible_constituent_count=100,
        positive_constituent_count=(
            0 if positive_share is None else round(positive_share * 100)
        ),
        positive_return_share=positive_share,
        leadership_concentration=(
            None if effective_count in (None, 0) else 1.0 / effective_count
        ),
        effective_leader_count=effective_count,
        sector_count=10 if sector_share is not None else 0,
        positive_sector_share=sector_share,
    )


def _stress(
    *,
    drawdown: float | None = 0.01,
    new_low_share: float | None = 0.01,
    breadth_change: float | None = -0.01,
    declining_days: int = 5,
    observations: int = 20,
    downside_deviation: float | None = 0.10,
) -> StressResult:
    return StressResult(
        as_of=AS_OF,
        constituent_count=100,
        universe_drawdown=drawdown,
        new_low_count=0 if new_low_share is None else round(new_low_share * 100),
        new_low_coverage=100 if new_low_share is not None else 0,
        new_low_share=new_low_share,
        persistent_breadth_change=breadth_change,
        breadth_declining_days=declining_days,
        breadth_change_observations=observations,
        downside_deviation=downside_deviation,
    )


class TrendInterpretationTests(unittest.TestCase):
    def test_all_trend_states(self) -> None:
        thresholds = TrendInterpretationThresholds()
        cases = [
            (_trend(0.03, 0.05), TrendState.STRONG),
            (_trend(0.01, 0.03), TrendState.NEUTRAL),
            (_trend(-0.03, -0.05), TrendState.WEAK),
            (_trend(None, None), TrendState.UNAVAILABLE),
        ]

        for raw, expected in cases:
            with self.subTest(expected=expected):
                condition = interpret_trend(raw, thresholds)
                self.assertEqual(condition.state, expected)
                self.assertIs(condition.raw, raw)
                self.assertTrue(condition.explanation)


class ParticipationInterpretationTests(unittest.TestCase):
    def test_all_participation_states(self) -> None:
        thresholds = ParticipationInterpretationThresholds()
        cases = [
            (_participation(0.70, 0.65), ParticipationState.BROAD),
            (_participation(0.55, 0.45), ParticipationState.AVERAGE),
            (_participation(0.30, 0.35), ParticipationState.NARROW),
            (_participation(None, None), ParticipationState.UNAVAILABLE),
        ]

        for raw, expected in cases:
            with self.subTest(expected=expected):
                condition = interpret_participation(raw, thresholds)
                self.assertEqual(condition.state, expected)
                self.assertIs(condition.raw, raw)
                self.assertTrue(condition.explanation)


class LeadershipInterpretationTests(unittest.TestCase):
    def test_all_leadership_states(self) -> None:
        thresholds = LeadershipInterpretationThresholds()
        cases = [
            (_leadership(0.70, 50.0, 0.70), LeadershipState.BROAD),
            (
                _leadership(0.70, 10.0, 0.70),
                LeadershipState.CONCENTRATED,
            ),
            (_leadership(0.30, 20.0, 0.30), LeadershipState.WEAK),
            (_leadership(None, None, None), LeadershipState.UNAVAILABLE),
        ]

        for raw, expected in cases:
            with self.subTest(expected=expected):
                condition = interpret_leadership(raw, thresholds)
                self.assertEqual(condition.state, expected)
                self.assertIs(condition.raw, raw)
                self.assertTrue(condition.explanation)


class StressInterpretationTests(unittest.TestCase):
    def test_all_stress_states(self) -> None:
        thresholds = StressInterpretationThresholds()
        cases = [
            (_stress(), StressState.LOW),
            (_stress(drawdown=0.06), StressState.ELEVATED),
            (_stress(downside_deviation=0.40), StressState.HIGH),
            (
                _stress(
                    drawdown=None,
                    new_low_share=None,
                    breadth_change=None,
                    declining_days=0,
                    observations=0,
                    downside_deviation=None,
                ),
                StressState.UNAVAILABLE,
            ),
        ]

        for raw, expected in cases:
            with self.subTest(expected=expected):
                condition = interpret_stress(raw, thresholds)
                self.assertEqual(condition.state, expected)
                self.assertIs(condition.raw, raw)
                self.assertTrue(condition.explanation)

    def test_each_stress_family_can_raise_state_independently(self) -> None:
        thresholds = StressInterpretationThresholds()
        elevated_cases = [
            _stress(drawdown=0.06),
            _stress(new_low_share=0.06),
            _stress(breadth_change=-0.11),
            _stress(declining_days=13),
            _stress(downside_deviation=0.21),
        ]
        for raw in elevated_cases:
            with self.subTest(raw=raw):
                self.assertEqual(
                    interpret_stress(raw, thresholds).state,
                    StressState.ELEVATED,
                )


class InterpreterIntegrationTests(unittest.TestCase):
    def test_market_conditions_preserve_raw_dimensions(self) -> None:
        intelligence = MarketIntelligence(
            as_of=AS_OF,
            universe_size=100,
            trend=_trend(0.03, 0.05),
            participation=_participation(0.70, 0.65),
            leadership=_leadership(0.70, 50.0, 0.70),
            stress=_stress(),
        )

        conditions = MarketIntelligenceInterpreter().interpret(intelligence)

        self.assertIsInstance(conditions, MarketConditions)
        self.assertIs(conditions.trend.raw, intelligence.trend)
        self.assertIs(conditions.participation.raw, intelligence.participation)
        self.assertIs(conditions.leadership.raw, intelligence.leadership)
        self.assertIs(conditions.stress.raw, intelligence.stress)
        serialized = conditions.as_dict()
        self.assertNotIn("driving_mode", serialized)
        self.assertNotIn("score", serialized)

    def test_custom_thresholds_change_only_the_target_dimension(self) -> None:
        intelligence = MarketIntelligence(
            as_of=AS_OF,
            universe_size=100,
            trend=_trend(0.03, 0.03),
            participation=_participation(0.70, 0.70),
            leadership=_leadership(0.70, 50.0, 0.70),
            stress=_stress(),
        )
        default = MarketIntelligenceInterpreter().interpret(intelligence)
        custom = MarketIntelligenceInterpreter(
            InterpretationConfig(
                trend=TrendInterpretationThresholds(
                    strong_distance=0.05,
                    weak_distance=-0.05,
                )
            )
        ).interpret(intelligence)

        self.assertEqual(default.trend.state, TrendState.STRONG)
        self.assertEqual(custom.trend.state, TrendState.NEUTRAL)
        self.assertEqual(default.participation.state, custom.participation.state)
        self.assertEqual(default.leadership.state, custom.leadership.state)
        self.assertEqual(default.stress.state, custom.stress.state)


if __name__ == "__main__":
    unittest.main()

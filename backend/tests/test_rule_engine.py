"""Genel kural değerlendirici (RuleEngine) testleri."""

from __future__ import annotations

from backend.domain.rule_engine.engine import RuleDefinitionData, RuleEngine
from backend.domain.shared.enums import RuleEffect
from backend.tests.factories import make_snapshot


def _rule(code, effect, points, predicate, priority=1) -> RuleDefinitionData:
    return RuleDefinitionData(
        code=code,
        priority=priority,
        effect=effect,
        points=points,
        message=f"{code} tetiklendi.",
        predicate=predicate,
    )


def test_no_rules_match_gives_zero_score_and_no_blockers():
    engine = RuleEngine("TEST", [_rule("NEVER", RuleEffect.ADD_SCORE, 10, lambda c: False)])
    result = engine.evaluate(make_snapshot())

    assert result.score == 0
    assert result.blockers == ()
    assert result.warnings == ()
    assert result.approved is True


def test_add_score_rules_accumulate():
    rules = [
        _rule("A", RuleEffect.ADD_SCORE, 10, lambda c: True, priority=1),
        _rule("B", RuleEffect.ADD_SCORE, 15, lambda c: True, priority=2),
    ]
    result = RuleEngine("TEST", rules).evaluate(make_snapshot())

    assert result.score == 25
    assert [o.code for o in result.outcomes] == ["A", "B"]


def test_block_rule_sets_approved_false_but_does_not_add_score():
    rules = [_rule("BLOCK_ME", RuleEffect.BLOCK, 999, lambda c: True)]
    result = RuleEngine("TEST", rules).evaluate(make_snapshot())

    assert result.score == 0
    assert result.approved is False
    assert result.blockers == ("BLOCK_ME tetiklendi.",)


def test_warn_rule_adds_warning_not_score():
    rules = [_rule("WARN_ME", RuleEffect.WARN, 5, lambda c: True)]
    result = RuleEngine("TEST", rules).evaluate(make_snapshot())

    assert result.score == 0
    assert result.warnings == ("WARN_ME tetiklendi.",)


def test_rules_evaluate_in_priority_order():
    seen = []
    rules = [
        _rule("SECOND", RuleEffect.ADD_SCORE, 1, lambda c: seen.append("SECOND") or True, priority=2),
        _rule("FIRST", RuleEffect.ADD_SCORE, 1, lambda c: seen.append("FIRST") or True, priority=1),
    ]
    RuleEngine("TEST", rules).evaluate(make_snapshot())

    assert seen == ["FIRST", "SECOND"]

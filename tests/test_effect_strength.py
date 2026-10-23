import unittest

from app.grounding_validation import _validate_effect_strength


class EffectStrengthTests(unittest.TestCase):
    def test_rescue_failure_cannot_become_absence_of_effect(self) -> None:
        for claim in [
            "PPID had no effect on expression.",
            "Treatment caused no changes in expression.",
            "Expression was unchanged.",
            "Expression was unaffected.",
            "PPID did not alter expression.",
        ]:
            with (
                self.subTest(claim=claim),
                self.assertRaisesRegex(ValueError, "absence of effect"),
            ):
                _validate_effect_strength(
                    claim, ["PPID downregulation did not exert any rescue effect."]
                )

    def test_rescue_cannot_become_complete_restoration(self) -> None:
        for claim in [
            "VDAC1 fully rescued expression.",
            "VDAC1 completely restored expression.",
            "VDAC1 gave a complete rescue.",
        ]:
            with (
                self.subTest(claim=claim),
                self.assertRaisesRegex(ValueError, "complete restoration"),
            ):
                _validate_effect_strength(claim, ["VDAC1 rescued expression."])

    def test_explicit_strength_and_faithful_rescue_wording_are_allowed(self) -> None:
        for claim, quote in [
            (
                "PPID did not rescue expression.",
                "PPID did not exert any rescue effect.",
            ),
            ("Expression was unchanged.", "We observed no change in expression."),
            ("Expression was unchanged.", "Expression was un- changed."),
            ("The treatment had no effect.", "Expression was unaffected by treatment."),
            (
                "VDAC1 fully rescued expression.",
                "Complete restoration of expression was observed.",
            ),
            ("VDAC1 rescued expression.", "Expression was partially rescued."),
        ]:
            with self.subTest(claim=claim):
                _validate_effect_strength(claim, [quote])

    def test_negated_strength_is_not_positive_support(self) -> None:
        for quote in [
            "Expression was not fully restored.",
            "Expression was not\n\n fully restored.",
            "Expression wasn't fully restored.",
            "Expression wasn’t fully restored.",
        ]:
            with self.subTest(quote=quote), self.assertRaises(ValueError):
                _validate_effect_strength("Expression was fully restored.", [quote])
        _validate_effect_strength(
            "Expression was not fully restored.", ["Partial rescue."]
        )

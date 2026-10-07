import unittest

from app.grounding_durations import validate_duration_evidence


class DurationEvidenceTests(unittest.TestCase):
    def test_cardinal_numbers_and_time_units_match_semantically(self) -> None:
        cases = [
            ("The observation lasted zero seconds.", "The observation lasted 0 second."),
            ("The delay lasted five minutes.", "The delay lasted 5 minute."),
            ("The fast lasted twelve hours.", "The fast lasted 12 hours."),
            ("Follow-up continued for twenty-one days.", "Follow-up continued for 21 day."),
            ("The intervention lasted ninety-nine weeks.", "The intervention lasted 99 weeks."),
            ("The cohort was followed for 3 months.", "The cohort was followed for three month."),
            ("The protocol lasted forty years.", "The protocol lasted 40 year."),
        ]
        for claim, quote in cases:
            with self.subTest(claim=claim):
                validate_duration_evidence(claim, [quote])

    def test_hyphenated_and_unicode_numeric_ranges_match_exact_bounds(self) -> None:
        validate_duration_evidence(
            "Animals were monitored for 16–18 days.",
            ["Animals were monitored for sixteen to eighteen days."],
        )
        with self.assertRaisesRegex(ValueError, "duration"):
            validate_duration_evidence("Animals were monitored for 16–18 days.", ["Animals were monitored for 16 days and 18 days."])

    def test_fixed_week_day_conversion_is_allowed_but_month_day_conversion_is_not(self) -> None:
        validate_duration_evidence("The washout lasted one week.", ["The washout lasted 7 days."])
        validate_duration_evidence("The delay lasted two minutes.", ["The delay lasted 120 seconds."])
        with self.assertRaisesRegex(ValueError, "duration"):
            validate_duration_evidence("The follow-up lasted one month.", ["The follow-up lasted 30 days."])

    def test_duration_quantities_must_be_supported_by_the_union_of_quotes(self) -> None:
        validate_duration_evidence(
            "The animals were fasted for six hours and observed for two days.",
            ["Animals were fasted for 6 hours.", "Animals were observed for 48 hours."],
        )
        with self.assertRaisesRegex(ValueError, "duration"):
            validate_duration_evidence(
                "The animals were fasted for six hours and observed for three days.",
                ["Animals were fasted for 6 hours.", "Animals were observed for 2 days."],
            )

    def test_fold_multipliers_are_not_durations(self) -> None:
        validate_duration_evidence("The response was 6-fold versus 3-fold.", ["The response was six-fold versus three-fold."])

    def test_signed_grouped_and_fractional_quantities_are_not_read_as_suffixes(self) -> None:
        mismatches = [
            ("The protocol lasted -3 days.", ["The protocol lasted 3 days."]),
            ("The protocol lasted 1,003 days.", ["The protocol lasted 3 days."]),
            ("The protocol lasted 1/3 days.", ["The protocol lasted 3 days."]),
            ("The protocol lasted 500 days.", ["The protocol lasted 1,500 days."]),
            ("The protocol lasted 2 days.", ["The protocol lasted 1/2 days."]),
            ("The protocol lasted 3 days.", ["The protocol lasted -3 days."]),
        ]
        for claim, quotes in mismatches:
            with self.subTest(claim=claim), self.assertRaisesRegex(ValueError, "duration"):
                validate_duration_evidence(claim, quotes)

        exact_matches = [
            ("The protocol lasted -3 days.", ["The protocol lasted -3 days."]),
            ("The protocol lasted 1,003 days.", ["The protocol lasted 1,003 days."]),
            ("The protocol lasted 1/3 days.", ["The protocol lasted 1/3 days."]),
            ("The delay lasted 1/2 day.", ["The delay lasted 12 hours."]),
        ]
        for claim, quotes in exact_matches:
            with self.subTest(claim=claim):
                validate_duration_evidence(claim, quotes)

    def test_missing_duration_evidence_raises_a_duration_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "duration"):
            validate_duration_evidence("The cohort lasted three days.", ["The cohort was followed throughout."])

    def test_and_ranges_preserve_both_bounds_in_claims_and_quotes(self) -> None:
        for expression in ("between 16 and 18 days", "16 and 18 days"):
            with self.subTest(expression=expression):
                validate_duration_evidence(expression, ["16–18 days"])
                validate_duration_evidence("16–18 days", [expression])
                for scalar in ("16 days", "18 days"):
                    with self.assertRaisesRegex(ValueError, "duration"):
                        validate_duration_evidence(expression, [scalar])
                    with self.assertRaisesRegex(ValueError, "duration"):
                        validate_duration_evidence(scalar, [expression])

    def test_spaced_fractions_preserve_the_complete_value(self) -> None:
        for expression in ("1 / 2 days", "1/ 2 days", "1 /2 days"):
            with self.subTest(expression=expression):
                validate_duration_evidence(expression, ["12 hours"])
                validate_duration_evidence("1/2 days", [expression])
                with self.assertRaisesRegex(ValueError, "duration"):
                    validate_duration_evidence(expression, ["2 days"])
                with self.assertRaisesRegex(ValueError, "duration"):
                    validate_duration_evidence("2 days", [expression])


if __name__ == "__main__":
    unittest.main()

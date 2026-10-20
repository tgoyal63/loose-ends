import unittest

from loose_ends.extraction import InvalidModelOutput, parse_proposals, validate_proposals


def proposal(title="send the draft", quote="Priya will send the draft on Friday.", **extra):
    return {"title": title, "quote": quote, "owner": "Priya", "due": "Friday", "condition": None, **extra}


class ExtractionTests(unittest.TestCase):
    def test_keeps_exact_attributed_action(self):
        note = "Priya will send the draft on Friday."
        tasks, rejected = validate_proposals(note, [proposal()])
        self.assertEqual(rejected, 0)
        self.assertEqual(tasks[0]["title"], "send the draft")
        self.assertEqual(tasks[0]["due"], "Friday")
        self.assertEqual(tasks[0]["quote"], note)

    def test_unknown_owner_and_date_stay_unknown(self):
        note = "Check the broken link."
        tasks, _ = validate_proposals(note, [proposal(title=note, quote=note, owner=None, due=None)])
        self.assertIsNone(tasks[0]["owner"])
        self.assertIsNone(tasks[0]["due"])

    def test_rejects_fabricated_title_quote_owner_or_date(self):
        note = "Priya will send the draft on Friday."
        variants = [
            proposal(title="publish the final release"),
            proposal(quote="Priya will approve the payment."),
            proposal(owner="Sam"),
            proposal(due="2026-10-23"),
        ]
        self.assertEqual(validate_proposals(note, variants), ([], 4))

    def test_cannot_crop_away_a_condition(self):
        note = "If legal approves, Priya will send the draft on Friday."
        self.assertEqual(validate_proposals(note, [proposal()]), ([], 1))

    def test_conditional_commitment_requires_its_condition(self):
        note = "If legal approves, Priya will send the draft on Friday."
        tasks, rejected = validate_proposals(
            note,
            [proposal(quote=note), proposal(quote=note, condition="If legal approves")],
        )
        self.assertEqual(rejected, 1)
        self.assertEqual(tasks[0]["condition"], note)

    def test_shortened_condition_cannot_drop_an_additional_prerequisite(self):
        note = "If legal approves and security signs off, Priya will send the draft on Friday."
        for condition in ("If", "If legal approves"):
            with self.subTest(condition=condition):
                tasks, rejected = validate_proposals(note, [proposal(quote=note, condition=condition)])
                self.assertEqual(rejected, 0)
                self.assertEqual(tasks[0]["condition"], note)

    def test_unpaired_unicode_cannot_reach_task_id_encoding(self):
        note = "Priya will send the draft on Friday.\ud800"
        self.assertEqual(validate_proposals(note, [proposal(quote=note)]), ([], 1))

    def test_rejects_cross_line_attribution(self):
        note = "Priya will send the draft.\nSam will review it on Friday."
        self.assertEqual(
            validate_proposals(note, [proposal(quote="Priya will send the draft.", due="Friday")]),
            ([], 1),
        )

    def test_rejects_negative_speculative_completed_or_question_lines(self):
        lines = [
            "Do not send the draft.",
            "Maybe send the draft.",
            "We already sent the draft.",
            "Send the draft?",
            "The draft is completed.",
        ]
        for note in lines:
            with self.subTest(note=note):
                item = proposal(title=note, quote=note, owner=None, due=None)
                self.assertEqual(validate_proposals(note, [item]), ([], 1))

    def test_rejects_truncated_prohibition_quote(self):
        note = "Do not send the draft on Friday."
        item = proposal(title="send the draft", quote="send the draft on Friday.", owner=None)
        self.assertEqual(validate_proposals(note, [item]), ([], 1))

    def test_deduplicates_and_uses_stable_ids(self):
        note = "Priya will send the draft on Friday."
        first = validate_proposals(note, [proposal(), proposal()])
        self.assertEqual(first[1], 1)
        self.assertEqual(first[0][0]["id"], validate_proposals(note, [proposal()])[0][0]["id"])

    def test_empty_input_proposals_are_legitimate(self):
        self.assertEqual(validate_proposals("Nothing to do.", []), ([], 0))

    def test_malformed_fields_rejected_without_crashing(self):
        items = [None, 1, {}, {"title": [], "quote": {}}, proposal(owner=[])]
        self.assertEqual(validate_proposals("Priya will send the draft on Friday.", items), ([], len(items)))

    def test_json_or_single_fence_accepted(self):
        self.assertEqual(parse_proposals('{"tasks":[]}'), [])
        self.assertEqual(parse_proposals('```json\n{"tasks":[]}\n```'), [])

    def test_invalid_json_is_not_an_empty_success(self):
        for text in ["I cannot answer", '{"tasks":', '{"tasks":{}}', "[]", '```json\n{"tasks":[]}']:
            with self.subTest(text=text), self.assertRaises(InvalidModelOutput):
                parse_proposals(text)

    def test_oversized_json_integer_is_a_documented_model_error(self):
        import sys
        if not hasattr(sys, "set_int_max_str_digits"):
            self.skipTest("Python without the integer-string conversion limit.")
        prior = sys.get_int_max_str_digits()
        try:
            sys.set_int_max_str_digits(4300)
            with self.assertRaises(InvalidModelOutput):
                parse_proposals('{"tasks":[],"unused":' + "9" * 5000 + "}")
        finally:
            sys.set_int_max_str_digits(prior)

    def test_task_limit_bounds_output(self):
        lines = [f"Send item {n}." for n in range(25)]
        items = [proposal(title=line, quote=line, owner=None, due=None) for line in lines]
        tasks, rejected = validate_proposals("\n".join(lines), items)
        self.assertEqual((len(tasks), rejected), (20, 5))


if __name__ == "__main__":
    unittest.main()

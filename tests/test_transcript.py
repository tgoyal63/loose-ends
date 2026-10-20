from pathlib import Path
import unittest

from loose_ends.extraction import validate_proposals
from loose_ends.transcript import parse_turns


FIXTURE = Path(__file__).parent / "fixtures" / "meeting_transcript.txt"


def proposal(turn_id="turn-1", title="send the sample", **fields):
    return {"turn_id": turn_id, "title": title, "owner": None, "due": None, "condition": None, **fields}


class TranscriptRegressionTests(unittest.TestCase):
    def test_multiline_first_person_commitment_keeps_speaker_and_context(self):
        notes = FIXTURE.read_text()
        tasks, rejected = validate_proposals(notes, [{
            "turn_id": "turn-3",
            "title": "create the sample listing",
            "owner": "Mira Shah",
            "due": "Friday",
            "condition": None,
        }])
        self.assertEqual(rejected, 0)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["owner"], "Mira Shah")
        self.assertIn("I will\ncreate the sample listing", tasks[0]["quote"])
        self.assertIn("Only after finance approves", tasks[0]["source"]["context"])

    def test_source_context_is_exact_contiguous_original_text(self):
        notes = FIXTURE.read_text()
        tasks, _ = validate_proposals(notes, [proposal("turn-3", "create the sample listing", owner="Mira Shah")])
        task = tasks[0]
        self.assertIn(task["quote"], task["source"]["context"])
        self.assertIn(task["source"]["context"], notes)
        self.assertEqual(task["source"]["speaker"], "Mira Shah")
        self.assertEqual(task["source"]["timestamp"], "09:10:25")
        self.assertIn("Once account access works and the sample is ready", task["source"]["context"])
        self.assertIn("Only after finance approves the test.", task["source"]["context"])

    def test_crlf_sources_and_multiline_title_are_preserved(self):
        note = "Mira Shah 09:10:00\r\nI will\r\nsend the sample on Friday.\r\n"
        tasks, rejected = validate_proposals(note, [proposal(title="I will send the sample", owner="Mira Shah")])
        self.assertEqual(rejected, 0)
        self.assertEqual(tasks[0]["quote"], note.rstrip("\r\n"))
        self.assertIn("\r\n", tasks[0]["source"]["context"])

    def test_whitespace_normalization_does_not_allow_rewriting(self):
        note = "Mira Shah 09:10:00\nI will send  the\nsample."
        self.assertEqual(len(validate_proposals(note, [proposal()])[0]), 1)
        self.assertEqual(validate_proposals(note, [proposal(title="publish the sample")]), ([], 1))
        self.assertEqual(validate_proposals(note, [proposal(title="Send the sample")]), ([], 1))

    def test_header_ids_are_stable_without_merging_similar_names(self):
        notes = FIXTURE.read_text()
        turns = parse_turns(notes)
        self.assertEqual([turn.id for turn in turns], [f"turn-{i}" for i in range(1, 9)])
        self.assertEqual(turns[-2].speaker, "Lee Park")
        self.assertEqual(turns[-1].speaker, "Lee Patel")
        proposals = [
            proposal("turn-7", "review the sample", owner="Lee Park", due="Monday"),
            proposal("turn-8", "review the sample", owner="Lee Patel", due="Monday"),
        ]
        tasks, rejected = validate_proposals(notes, proposals)
        self.assertEqual(rejected, 0)
        self.assertEqual(len({task["id"] for task in tasks}), 2)
        self.assertEqual(tasks, validate_proposals(notes, proposals)[0])

    def test_no_owner_leaks_from_nearby_turn_or_similar_name(self):
        note = "Lee Park 09:10:00\nI will send the sample.\nLee Patel 09:11:00\nI will review it."
        for owner in ("Lee Patel", "Lee", "Chris", "I"):
            with self.subTest(owner=owner):
                self.assertEqual(validate_proposals(note, [proposal(owner=owner)]), ([], 1))

    def test_ambiguous_group_and_addressed_person_remain_unassigned(self):
        for utterance in ("We will send the sample.", "You will send the sample."):
            note = f"Mira Shah 09:10:00\n{utterance}"
            tasks, rejected = validate_proposals(note, [proposal()])
            self.assertEqual(rejected, 0)
            self.assertIsNone(tasks[0]["owner"])
            self.assertEqual(validate_proposals(note, [proposal(owner="Mira Shah")]), ([], 1))

    def test_unknown_speaker_is_not_a_person(self):
        note = "Unknown speaker 09:10:00\nI will send the sample."
        self.assertIsNone(validate_proposals(note, [proposal()])[0][0]["owner"])
        self.assertEqual(validate_proposals(note, [proposal(owner="Unknown speaker")]), ([], 1))

    def test_first_person_commitment_forms_support_exact_speaker(self):
        for words in ("I will", "I'll", "I’ll", "I am going to", "I'm going to", "I’m going to"):
            note = f"Mira Shah 09:10:00\n{words} send the sample."
            with self.subTest(words=words):
                self.assertEqual(validate_proposals(note, [proposal(owner="Mira Shah")])[1], 0)

    def test_named_owner_requires_explicit_clause_provenance(self):
        note = "Mira Shah 09:10:00\nLee Park will send the sample."
        self.assertEqual(validate_proposals(note, [proposal(owner="Lee Park")])[1], 0)
        self.assertEqual(validate_proposals(note, [proposal(owner="Mira Shah")]), ([], 1))

    def test_ownership_cannot_leak_from_another_action_in_same_sentence(self):
        note = "Mira Shah 09:10:00\nI will review the invoice and Jordan will send the sample on Friday."
        self.assertEqual(validate_proposals(note, [proposal(owner="Mira Shah")]), ([], 1))
        self.assertEqual(validate_proposals(note, [proposal(owner="Jordan")])[1], 0)

    def test_quoted_first_person_is_not_the_speaker(self):
        for quote in ('"I will send the sample on Friday."', "“I will send the sample on Friday.”"):
            note = f"Mira Shah 09:10:00\nJordan said, {quote}"
            self.assertEqual(validate_proposals(note, [proposal(owner="Mira Shah")]), ([], 1))

    def test_multisentence_quotation_cannot_lose_owner_context(self):
        note = 'Mira Shah 09:10:00\nJordan said, "I will send the sample. The report is separate."'
        self.assertEqual(validate_proposals(note, [proposal(owner="Mira Shah")]), ([], 1))

    def test_delegated_action_does_not_become_speakers_own_action(self):
        note = "Mira Shah 09:10:00\nI will ask Jordan to send the sample."
        self.assertEqual(validate_proposals(note, [proposal(owner="Mira Shah")]), ([], 1))
        self.assertEqual(validate_proposals(note, [proposal(title="ask Jordan to send the sample", owner="Mira Shah")])[1], 0)

    def test_bare_infinitive_delegation_cannot_assign_delegate_action_to_speaker(self):
        for verb in ("have", "let"):
            note = f"Mira Shah 09:10:00\nI will {verb} Jordan send the sample."
            self.assertEqual(validate_proposals(note, [proposal(owner="Mira Shah")]), ([], 1))
            self.assertEqual(validate_proposals(note, [proposal(
                title=f"{verb} Jordan send the sample", owner="Mira Shah",
            )])[1], 0)

    def test_forged_ids_quotes_dates_or_fields_are_rejected(self):
        note = "Mira Shah 09:10:00\nI will send the sample on Friday.\nLee Park 09:10:30\nLet's discuss Monday."
        variants = [
            proposal("turn-99"), proposal(turn_id=[]),
            proposal(quote="I will send the sample on Friday."),
            proposal(due="Monday"), proposal(due="2026-10-23"),
            proposal(condition="If legal approves"), proposal(owner=[]),
            proposal(title="send the sample\x00"), proposal(condition={}),
            None, 1, {}, {"turn_id": "turn-1", "title": []},
        ]
        self.assertEqual(validate_proposals(note, variants), ([], len(variants)))

    def test_literal_optional_null_sentinels_canonicalize_to_unknown(self):
        note = "Mira Shah 09:10:00\nI will send the sample."
        expected = validate_proposals(note, [proposal()])
        for sentinel in ("null", "NULL", " null "):
            with self.subTest(sentinel=sentinel):
                self.assertEqual(validate_proposals(note, [proposal(
                    owner=sentinel, due=sentinel, condition=sentinel,
                )]), expected)
        # This recovery applies only to missing optional fields.
        self.assertEqual(validate_proposals(note, [proposal(title="null")]), ([], 1))
        self.assertEqual(validate_proposals(note, [proposal(turn_id="null")]), ([], 1))
        self.assertEqual(validate_proposals(note, [proposal(owner="Another Person")]), ([], 1))
        self.assertEqual(validate_proposals(note, [proposal(due="Tuesday")]), ([], 1))

    def test_completed_nearby_work_is_not_a_prerequisite(self):
        note = "Mira Shah 09:10:00\nI already sent the checklist. I will send the sample."
        self.assertEqual(validate_proposals(note, [proposal(condition="I already sent the checklist")]), ([], 1))

    def test_compound_condition_is_not_lost_by_title_or_shortened_condition(self):
        note = "Mira Shah 09:10:00\nIf access works and finance approves,\nI will send the sample."
        for condition in (None, "If", "If access works"):
            task = validate_proposals(note, [proposal(owner="Mira Shah", condition=condition)])[0][0]
            self.assertEqual(task["condition"], note)

    def test_standalone_prerequisite_cannot_become_an_action(self):
        for prerequisite in (
            "Only after finance approves the test.",
            "Once account access works and the sample is ready.",
            "If legal approves and security signs off.",
        ):
            note = f"Lee Park 09:10:00\n{prerequisite}"
            self.assertEqual(validate_proposals(note, [proposal(title=prerequisite)]), ([], 1))

    def test_cropped_prerequisite_is_not_the_committed_action(self):
        note = "Mira Shah 09:10:00\nAfter finance approves the test, I will notify Lee."
        self.assertEqual(validate_proposals(note, [proposal(title="After finance approves the test")]), ([], 1))
        self.assertEqual(validate_proposals(note, [proposal(
            title="After finance approves the test, I will notify Lee", owner="Mira Shah",
        )])[1], 0)

    def test_cross_turn_condition_keeps_complete_surrounding_context(self):
        notes = FIXTURE.read_text()
        task = validate_proposals(notes, [proposal(
            "turn-3", "create the sample listing", owner="Mira Shah",
            condition="Once account access works",
        )])[0][0]
        self.assertIn("and the sample is ready", task["condition"])
        self.assertIn("Only after finance approves", task["condition"])
        self.assertEqual(task["condition"], task["source"]["context"])

    def test_server_retains_conditions_when_model_omits_condition_field(self):
        notes = FIXTURE.read_text()
        proposals = [
            {"turn_id": "turn-3", "title": "create the sample listing", "owner": "Mira Shah", "due": "Friday"},
            {"turn_id": "turn-5", "title": "notify Lee", "owner": "Mira Shah", "due": None},
        ]
        tasks, rejected = validate_proposals(notes, proposals)
        self.assertEqual(rejected, 0)
        self.assertIn("Only after finance approves the test.", tasks[0]["source"]["context"])
        self.assertIn("Once account access works and the sample is ready", tasks[0]["source"]["context"])
        self.assertEqual(tasks[1]["condition"], tasks[1]["quote"])
        self.assertIn("after finance approves the test", tasks[1]["condition"])

    def test_unsafe_other_sentences_do_not_hide_real_commitment(self):
        note = "Mira Shah 09:10:00\nMaybe the UI needs a redesign. I already sent the checklist.\nI will send the sample."
        tasks, rejected = validate_proposals(note, [proposal(owner="Mira Shah")])
        self.assertEqual(rejected, 0)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["quote"], note)

    def test_cropped_speculative_prohibited_completed_actions_are_rejected(self):
        utterances = [
            "Do not send the sample.", "I won't send the sample.", "I will not send the sample.",
            "I'm not going to send the sample.", "Maybe I will send the sample.",
            "Perhaps I will send the sample.", "I could send the sample.",
            "I already sent the sample.", "I have sent the sample.",
            "I’ve sent the sample.", "We finished the sample.", "Send the sample?",
            "For example, I will send the sample.", "Let's say I will send the sample.",
            "I will\nnot\nsend the sample.",
        ]
        for utterance in utterances:
            note = f"Mira Shah 09:10:00\n{utterance}"
            title = "sent the sample" if "sent the sample" in utterance else "send the sample"
            with self.subTest(utterance=utterance):
                self.assertEqual(validate_proposals(note, [proposal(title=title)]), ([], 1))

    def test_dates_from_another_sentence_cannot_attach_to_action(self):
        note = "Mira Shah 09:10:00\nWe met on Friday. I will send the sample."
        self.assertEqual(validate_proposals(note, [proposal(due="Friday")]), ([], 1))

    def test_same_turn_duplicate_proposals_are_deduplicated(self):
        note = "Mira Shah 09:10:00\nI will send the sample."
        tasks, rejected = validate_proposals(note, [proposal(), proposal()])
        self.assertEqual((len(tasks), rejected), (1, 1))

    def test_task_limit_is_retained(self):
        note = "\n".join(f"Speaker Name 09:10:{i:02}\nI will send item {i}." for i in range(25))
        items = [proposal(f"turn-{i + 1}", f"send item {i}") for i in range(25)]
        tasks, rejected = validate_proposals(note, items)
        self.assertEqual((len(tasks), rejected), (20, 5))

    def test_unpaired_unicode_in_original_source_rejected_without_crash(self):
        note = "Mira Shah 09:10:00\nI will send the sample.\ud800"
        self.assertEqual(validate_proposals(note, [proposal()]), ([], 1))

    def test_ordinary_multiline_notes_still_require_complete_source_lines(self):
        note = "Mira will send the sample.\nLee will review it on Friday."
        self.assertEqual(parse_turns(note), [])
        self.assertEqual(validate_proposals(note, [{
            "title": "send the sample", "quote": "Mira will send the sample.",
            "owner": "Mira", "due": "Friday", "condition": None,
        }]), ([], 1))

    def test_parser_preserves_preamble_and_empty_turn_boundaries(self):
        note = "Meeting notes\nMira Shah 09:10:00\n\nLee Park 09:10:20\nI will send the sample.\n"
        turns = parse_turns(note)
        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0].id, "turn-2")
        self.assertEqual(turns[0].quote, "Lee Park 09:10:20\nI will send the sample.")
        self.assertEqual(note[turns[0].start:turns[0].end], turns[0].quote)


if __name__ == "__main__":
    unittest.main()

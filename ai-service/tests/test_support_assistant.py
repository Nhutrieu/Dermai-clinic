import pytest

from app.support_assistant import classify_support_request, rag_disease_key


def test_cancel_request_requires_receptionist_handoff():
    decision = classify_support_request("Tôi muốn hủy lịch khám ngày mai")

    assert decision.category == "CANCEL_APPOINTMENT"
    assert decision.requires_handoff is True
    assert "chỉ thay đổi khi hệ thống xác nhận" in decision.answer


def test_how_to_cancel_is_answered_before_an_operational_handoff():
    decision = classify_support_request("Làm sao để hủy lịch khám?")

    assert decision.category == "APPOINTMENT_CHANGE_GUIDE"
    assert decision.requires_handoff is False


@pytest.mark.parametrize(
    "message",
    [
        "Đặt lịch sao á bạn",
        "Mình đặt lịch ở đâu?",
        "Làm thế nào để đặt lịch?",
    ],
)
def test_natural_booking_guide_variants_are_answered_without_handoff(message: str):
    decision = classify_support_request(message)

    assert decision.category == "BOOKING_GUIDE"
    assert decision.requires_handoff is False


def test_receptionist_booking_request_still_requires_handoff():
    decision = classify_support_request("Lễ tân đặt hộ tôi")

    assert decision.category == "BOOKING_ASSISTANCE"
    assert decision.requires_handoff is True


def test_patient_can_explicitly_request_a_human():
    decision = classify_support_request("Tôi muốn gặp người thật")

    assert decision.category == "HUMAN_REQUEST"
    assert decision.requires_handoff is False
    assert decision.needs_clarification is True


def test_price_question_is_answered_without_handoff():
    decision = classify_support_request("Giá khám bao nhiêu vậy?")

    assert decision.category == "CONSULTATION_FEE"
    assert decision.requires_handoff is False
    assert "thanh toán trực tiếp" in decision.answer


def test_unknown_request_fails_safe_to_receptionist():
    decision = classify_support_request("Tôi có một việc khác cần giải quyết")

    assert decision.category == "OTHER"
    assert decision.requires_handoff is True


@pytest.mark.parametrize("message", ["Bạn ơi", "Xin chào", "Alo"])
def test_greeting_and_call_phrases_do_not_escalate(message: str):
    decision = classify_support_request(message)

    assert decision.category == "GREETING"
    assert decision.requires_handoff is False
    assert decision.needs_clarification is False


@pytest.mark.parametrize("message", ["OK", "Oke", "Cảm ơn", "Vâng"])
def test_short_acknowledgements_do_not_escalate_to_receptionist(message: str):
    decision = classify_support_request(message)

    assert decision.category == "ACKNOWLEDGEMENT"
    assert decision.requires_handoff is False

def test_stacked_conversation_openers_alone_are_a_greeting():
    decision = classify_support_request("Bạn ơi cho mình hỏi")

    assert decision.category == "GREETING"
    assert decision.requires_handoff is False


def test_stacked_conversation_openers_keep_booking_guide_intent():
    decision = classify_support_request("Bạn ơi, cho mình hỏi, đặt lịch sao á?")

    assert decision.category == "BOOKING_GUIDE"
    assert decision.requires_handoff is False


def test_stacked_conversation_openers_keep_cancel_intent():
    decision = classify_support_request("Bạn ơi cho mình hỏi hủy lịch")

    assert decision.category == "CANCEL_APPOINTMENT"
    assert decision.requires_handoff is True


def test_conversation_opener_does_not_hide_cancel_request():
    decision = classify_support_request("Bạn ơi, tôi muốn hủy lịch ngày mai")

    assert decision.category == "CANCEL_APPOINTMENT"
    assert decision.requires_handoff is True


def test_conversation_opener_keeps_doctor_availability_request():
    decision = classify_support_request("Bạn ơi, xem lịch bác sĩ Bình ngày mai")

    assert decision.category == "DOCTOR_AVAILABILITY"
    assert decision.doctor_name == "Bình"
    assert decision.requires_handoff is False


def test_ai_result_explanation_is_safe_reference_content():
    decision = classify_support_request("Top 3 và Grad-CAM trong kết quả AI là gì?")

    assert decision.category == "AI_RESULT_EXPLANATION"
    assert decision.requires_handoff is False


def test_general_dermatology_question_is_routed_to_rag():
    decision = classify_support_request("Vảy nến là gì?")

    assert decision.category == "DERMATOLOGY_GENERAL"
    assert decision.requires_handoff is False
    assert rag_disease_key("Vảy nến là gì?") == "Psoriasis"


@pytest.mark.parametrize(
    "message",
    [
        "Làm sao để mình biết được mình nên đi khám lúc nào",
        "Khi nào cần đi khám da liễu",
    ],
)
def test_when_to_see_a_dermatologist_is_safe_guidance_without_handoff(message: str):
    decision = classify_support_request(message)

    assert decision.category == "DERMATOLOGY_VISIT_GUIDE"
    assert decision.requires_handoff is False
    assert decision.needs_clarification is False


def test_explicit_urgent_symptoms_take_priority_over_dermatology_visit_guidance():
    decision = classify_support_request(
        "Khi nào cần đi khám da liễu? Tôi đang khó thở và tổn thương lan nhanh."
    )

    assert decision.category == "URGENT"
    assert decision.requires_handoff is True
    assert "115" in decision.answer


def test_explicit_urgent_symptoms_take_priority_over_availability_lookup():
    decision = classify_support_request(
        "Tôi đang khó thở, lịch bác sĩ Bình ngày mai còn không?"
    )

    assert decision.category == "URGENT"
    assert decision.requires_handoff is True
    assert "115" in decision.answer


def test_doctor_availability_extracts_read_only_lookup_entities():
    decision = classify_support_request("Tôi muốn biết lịch bác sĩ Minh ngày mai")

    assert decision.category == "DOCTOR_AVAILABILITY"
    assert decision.intent_confidence >= 0.8
    assert decision.doctor_name == "Minh"
    assert decision.requested_date is not None


def test_doctor_availability_accepts_doctor_leave_question():
    decision = classify_support_request("Bác sĩ Bình nghỉ ngày mai không?")

    assert decision.category == "DOCTOR_AVAILABILITY"
    assert decision.doctor_name == "Bình"
    assert decision.requested_date is not None


def test_doctor_leave_schedule_question_without_a_date_is_supported():
    decision = classify_support_request("Bác sĩ Bình có nghỉ ngày nào không?")

    assert decision.category == "DOCTOR_LEAVE_SCHEDULE"
    assert decision.doctor_name == "Bình"
    assert decision.requires_handoff is False
    assert decision.needs_clarification is False


def test_clinic_closure_question_extracts_the_requested_date():
    decision = classify_support_request("Phòng khám có nghỉ ngày 2/9 không?")

    assert decision.category == "CLINIC_CLOSURE"
    assert decision.requires_handoff is False
    assert decision.needs_clarification is False
    assert decision.requested_date is not None
    assert decision.requested_date.endswith("-09-02")


def test_clinic_closure_question_without_a_date_asks_for_one():
    decision = classify_support_request("Phòng khám hôm nào nghỉ vậy?")

    assert decision.category == "CLINIC_CLOSURE"
    assert decision.requires_handoff is False
    assert decision.needs_clarification is True
    assert "ngày nào" in decision.answer


def test_doctor_information_treats_any_doctor_wording_as_generic():
    decision = classify_support_request("Cho tôi xem thông tin bác sĩ nào cũng được ngày 2/9")

    assert decision.category == "DOCTOR_INFORMATION"
    assert decision.doctor_name is None
    assert decision.requested_date is not None


def test_doctor_availability_accepts_short_doctor_prefix():
    decision = classify_support_request("Lịch BS. Bình ngày mai")

    assert decision.category == "DOCTOR_AVAILABILITY"
    assert decision.doctor_name == "Bình"
    assert decision.requested_date is not None


def test_doctor_availability_accepts_accentless_date_words():
    decision = classify_support_request("Lich BS. Binh ngay mai")

    assert decision.category == "DOCTOR_AVAILABILITY"
    assert decision.doctor_name == "Binh"
    assert decision.requested_date is not None


def test_doctor_availability_understands_doctor_mentioned_after_date_and_time():
    decision = classify_support_request("Xem lịch bác sĩ ngày 14/8 vào lúc 9h bác sĩ Bình")

    assert decision.category == "DOCTOR_AVAILABILITY"
    assert decision.doctor_name == "Bình"
    assert decision.requested_date.endswith("-08-14")
    assert decision.requested_time == "09:00"
    assert decision.needs_clarification is False


def test_doctor_availability_extracts_half_hour_time():
    decision = classify_support_request("Kiểm tra lịch ngày 14/8 lúc 9h30 của BS. Bình")

    assert decision.category == "DOCTOR_AVAILABILITY"
    assert decision.doctor_name == "Bình"
    assert decision.requested_time == "09:30"


def test_doctor_availability_accepts_doctor_before_natural_question():
    decision = classify_support_request("Bác sĩ Bình có lịch lúc 09:00 ngày 14/8 không?")

    assert decision.category == "DOCTOR_AVAILABILITY"
    assert decision.doctor_name == "Bình"
    assert decision.requested_time == "09:00"


def test_doctor_availability_does_not_include_open_word_in_doctor_name():
    decision = classify_support_request("Tôi muốn biết lịch bác sĩ Bình trống vào ngày 14/8 không")

    assert decision.category == "DOCTOR_AVAILABILITY"
    assert decision.doctor_name == "Bình"
    assert decision.requested_date.endswith("-08-14")
    assert decision.needs_clarification is False


def test_doctor_availability_accepts_free_and_available_wording():
    free_decision = classify_support_request("Bác sĩ Bình còn trống ngày 14/8 không?")
    available_decision = classify_support_request("Lịch BS. Bình rảnh ngày 14/8 không?")

    assert free_decision.category == "DOCTOR_AVAILABILITY"
    assert free_decision.doctor_name == "Bình"
    assert available_decision.category == "DOCTOR_AVAILABILITY"
    assert available_decision.doctor_name == "Bình"


def test_doctor_availability_removes_conversational_particle_from_clarified_name():
    decision = classify_support_request(
        "Tôi muốn biết lịch bác sĩ Bình trống vào ngày 14/8 không\n"
        "Ý mình là bác sĩ Bình á"
    )

    assert decision.category == "DOCTOR_AVAILABILITY"
    assert decision.doctor_name == "Bình"
    assert decision.requested_date.endswith("-08-14")


def test_doctor_availability_removes_polite_suffixes_from_name():
    polite = classify_support_request("Xem lịch bác sĩ Linh ạ ngày 14/8")
    friendly = classify_support_request("Xem lịch bác sĩ Vương nha ngày 14/8")

    assert polite.doctor_name == "Linh"
    assert friendly.doctor_name == "Vương"


def test_general_doctor_information_request_stays_with_assistant():
    decision = classify_support_request("Cho tôi thông tin về bác sĩ")

    assert decision.category == "DOCTOR_INFORMATION"
    assert decision.requires_handoff is False
    assert decision.doctor_name is None


def test_specific_doctor_information_extracts_doctor_name():
    decision = classify_support_request("Cho tôi thông tin về bác sĩ Bình")

    assert decision.category == "DOCTOR_INFORMATION"
    assert decision.requires_handoff is False
    assert decision.doctor_name == "Bình"


def test_condition_based_doctor_question_is_not_mistaken_for_booking_guide():
    decision = classify_support_request("Tôi đang bị nấm da thì nên chọn bác sĩ nào phù hợp")

    assert decision.category == "DOCTOR_RECOMMENDATION"
    assert decision.requires_handoff is False
    assert decision.needs_clarification is False


def test_acne_doctor_recommendation_stays_with_assistant():
    decision = classify_support_request("Mình bị mụn viêm, bác sĩ nào phù hợp?")

    assert decision.category == "DOCTOR_RECOMMENDATION"
    assert decision.requires_handoff is False


def test_dissatisfaction_escalates_without_another_prompt():
    decision = classify_support_request("Tôi đã nói rồi, sao vẫn không được?")

    assert decision.category == "DISSATISFACTION"
    assert decision.requires_handoff is True


def test_emergency_wording_does_not_tell_patient_to_wait_for_chat():
    decision = classify_support_request("Tôi đang khó thở và đau dữ dội")

    assert decision.category == "URGENT"
    assert decision.requires_handoff is True
    assert "đừng chờ" in decision.answer
    assert "115" in decision.answer


@pytest.mark.parametrize("message", [
    "Lịch của tôi khi nào?", "Lịch khám của mình vào ngày nào?", "Tôi có lịch khám không?",
    "Xem lịch đã đặt", "Trạng thái lịch của tôi", "Lịch hẹn của tui khi nào?",
    "Lịch của tôi với bác sĩ Bình ngày mai", "Bác sĩ Bình còn lịch ngày mai không?\nLịch của tôi khi nào?",
])
def test_own_appointments_are_looked_up_without_handoff(message):
    decision = classify_support_request(message)
    assert decision.category == "APPOINTMENT_STATUS"
    assert decision.requires_handoff is False
    assert decision.needs_clarification is False


def test_cancel_own_appointment_still_goes_to_reception():
    decision = classify_support_request("Tôi muốn hủy lịch khám của tôi")
    assert decision.category == "CANCEL_APPOINTMENT"
    assert decision.requires_handoff is True



def lookup_context(decision):
    return {"intent": decision.category, "doctor_name": decision.doctor_name,
            "requested_date": decision.requested_date, "requested_time": decision.requested_time}


def test_doctor_and_time_without_date_asks_for_date_without_handoff():
    decision = classify_support_request("Bác sĩ Bình vào lúc 8 giờ")
    assert decision.category == "DOCTOR_AVAILABILITY"
    assert decision.doctor_name == "Bình"
    assert decision.requested_time == "08:00"
    assert decision.requested_date is None
    assert decision.needs_clarification is True
    assert decision.requires_handoff is False


def test_separate_name_time_and_date_replies_keep_all_lookup_fields():
    first = classify_support_request("Tôi muốn biết lịch bác sĩ")
    assert first.needs_clarification is True
    name = classify_support_request("Bình á", lookup_context(first))
    assert name.doctor_name == "Bình"
    time = classify_support_request("8 giờ", lookup_context(name))
    assert time.doctor_name == "Bình"
    assert time.requested_time == "08:00"
    assert time.needs_clarification is True
    date = classify_support_request("Ngày mai", lookup_context(time))
    assert date.category == "DOCTOR_AVAILABILITY"
    assert date.doctor_name == "Bình"
    assert date.requested_time == "08:00"
    assert date.requested_date is not None
    assert date.needs_clarification is False
    assert date.requires_handoff is False


@pytest.mark.parametrize("question, expected", [
    ("Tôi muốn hủy lịch", "CANCEL_APPOINTMENT"),
    ("Lịch của tôi khi nào?", "APPOINTMENT_STATUS"),
    ("Tôi đang khó thở", "URGENT"),
    ("Thông tin bác sĩ Linh", "DOCTOR_INFORMATION"),
    ("Cảm ơn", "ACKNOWLEDGEMENT"),
    ("Tôi muốn đổi lịch", "RESCHEDULE_APPOINTMENT"),
])
def test_explicit_new_intent_wins_over_previous_lookup(question, expected):
    context = {"intent": "DOCTOR_AVAILABILITY", "doctor_name": "Bình", "requested_date": "2026-11-21", "requested_time": "08:00"}
    decision = classify_support_request(question, context)
    assert decision.category == expected


def test_new_doctor_date_and_time_override_the_old_lookup_fields():
    context = {"intent": "DOCTOR_AVAILABILITY", "doctor_name": "Bình", "requested_date": "2026-11-21", "requested_time": "08:00"}
    decision = classify_support_request("Bác sĩ Linh ngày 22/11/2026 lúc 9h30", context)
    assert decision.doctor_name == "Linh"
    assert decision.requested_date == "2026-11-22"
    assert decision.requested_time == "09:30"


def test_date_followup_for_leave_schedule_checks_doctor_availability():
    context = {"intent": "DOCTOR_LEAVE_SCHEDULE", "doctor_name": "Bình", "requested_date": None, "requested_time": None}
    decision = classify_support_request("Ngày mai", context)
    assert decision.category == "DOCTOR_AVAILABILITY"
    assert decision.doctor_name == "Bình"
    assert decision.needs_clarification is False


def test_clinic_date_reply_does_not_require_a_doctor():
    context = {"intent": "CLINIC_CLOSURE", "doctor_name": None, "requested_date": None, "requested_time": None}
    decision = classify_support_request("Ngày 22/11/2026", context)
    assert decision.category == "CLINIC_CLOSURE"
    assert decision.requested_date == "2026-11-22"
    assert decision.doctor_name is None
    assert decision.needs_clarification is False


@pytest.fixture
def clinic_today(monkeypatch):
    from datetime import datetime
    import app.support_assistant as assistant

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 20, 10, 0, tzinfo=tz)

    monkeypatch.setattr(assistant, "datetime", FixedDateTime)


@pytest.mark.parametrize("message", ["ngày 21", "ngay21", "21", "21 nha", "Ngày 21 nhé"])
def test_day_only_reply_uses_current_month_when_it_is_not_past(message, clinic_today):
    context = {"intent": "DOCTOR_AVAILABILITY", "doctor_name": "Bình", "requested_date": None, "requested_time": "08:00"}
    decision = classify_support_request(message, context)
    assert decision.category == "DOCTOR_AVAILABILITY"
    assert decision.doctor_name == "Bình"
    assert decision.requested_date == "2026-11-21"
    assert decision.requested_time == "08:00"
    assert decision.needs_clarification is False
    assert decision.requires_handoff is False


@pytest.mark.parametrize("message", ["ngày 5", "5", "ngày 31", "ngày 32", "ngày 0"])
def test_unclear_or_invalid_day_asks_for_full_date_without_handoff(message, clinic_today):
    context = {"intent": "DOCTOR_AVAILABILITY", "doctor_name": "Bình", "requested_date": "2026-11-21", "requested_time": "08:00"}
    decision = classify_support_request(message, context)
    assert decision.category == "DOCTOR_AVAILABILITY"
    assert decision.requested_date is None
    assert decision.doctor_name == "Bình"
    assert decision.requested_time == "08:00"
    assert decision.needs_clarification is True
    assert decision.requires_handoff is False
    assert "ngày/tháng" in decision.answer


@pytest.mark.parametrize("message", ["Bác sĩ Bình ngày 21", "Bác sĩ Bình ngày 21 tháng 11", "Lịch bác sĩ Bình ngày 21 tháng 12 năm 2026 lúc 8 giờ"])
def test_written_vietnamese_date_is_understood_in_a_direct_lookup(message, clinic_today):
    decision = classify_support_request(message)
    assert decision.category == "DOCTOR_AVAILABILITY"
    assert decision.requested_date in {"2026-11-21", "2026-12-21"}
    assert decision.needs_clarification is False
    assert decision.requires_handoff is False


def test_bare_day_is_not_treated_as_booking_without_lookup_context(clinic_today):
    decision = classify_support_request("21")
    assert decision.category != "DOCTOR_AVAILABILITY"


def test_full_date_can_resolve_an_unclear_short_day(clinic_today):
    context = {"intent": "DOCTOR_AVAILABILITY", "doctor_name": "Bình", "requested_date": None, "requested_time": "08:00"}
    decision = classify_support_request("Ngày 5/12", context)
    assert decision.requested_date == "2026-12-05"
    assert decision.requested_time == "08:00"
    assert decision.needs_clarification is False
    assert decision.requires_handoff is False


def test_short_day_also_answers_a_clinic_closure_question(clinic_today):
    context = {"intent": "CLINIC_CLOSURE", "doctor_name": None, "requested_date": None, "requested_time": None}
    decision = classify_support_request("ngày 21", context)
    assert decision.category == "CLINIC_CLOSURE"
    assert decision.requested_date == "2026-11-21"
    assert decision.needs_clarification is False

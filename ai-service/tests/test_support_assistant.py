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

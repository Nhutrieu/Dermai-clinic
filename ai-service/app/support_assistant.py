from dataclasses import dataclass
from datetime import datetime, timedelta
import re
import unicodedata
from zoneinfo import ZoneInfo

import httpx


HOTLINE = "0352 790 904"


@dataclass(frozen=True)
class SupportDecision:
    category: str
    answer: str
    requires_handoff: bool
    handoff_summary: str
    intent_confidence: float = 0.9
    needs_clarification: bool = False
    doctor_name: str | None = None
    requested_date: str | None = None
    requested_time: str | None = None


def _normalize(value: str) -> str:
    """Normalize Vietnamese text only for intent matching; never persist this copy."""
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn").replace("đ", "d")


def _contains(text: str, phrases: tuple[str, ...]) -> bool:
    # Word boundaries avoid false positives such as "ai" inside "giải" or
    # "giá" inside "giải quyết" after accent normalization.
    return any(re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) for phrase in phrases)


def _without_conversation_opener(text: str) -> tuple[str, bool]:
    """Remove consecutive Vietnamese call-to-attention phrases safely."""
    # Keep this anchored to the start. A phrase such as "bạn ơi, hủy lịch"
    # must still be classified from the meaningful text that follows it. Looping
    # handles natural combinations such as "bạn ơi, cho mình hỏi".
    opener = re.compile(
        r"^\s*(?:ban\s+oi|ad\s+oi|le\s+tan\s+oi|cho\s+minh\s+hoi|"
        r"minh\s+hoi\s+(?:chut|mot\s+chut))(?=$|[\s,!?.:;\-])[\s,!?.:;\-]*"
    )
    remaining = text
    removed = False
    while match := opener.match(remaining):
        removed = True
        remaining = remaining[match.end():].strip()
    return remaining, removed


def rag_disease_key(question: str) -> str | None:
    """Map a general question to one of the reviewed RAG guidance groups."""
    normalized = _normalize(question)
    disease_terms = (
        ("SkinCancer", ("ung thu da",)),
        ("Psoriasis", ("vay nen", "psoriasis")),
        ("Candidiasis", ("candida", "candidiasis")),
        ("Eczema", ("cham", "eczema", "viem da co dia")),
        ("Tinea", ("nam da", "tinea")),
        ("Warts", ("mun coc", "hat com", "warts")),
        ("Lupus", ("lupus",)),
        ("Acne", ("mun", "trung ca", "acne")),
    )
    return next((key for key, terms in disease_terms if _contains(normalized, terms)), None)


def _appointment_entities(question: str) -> tuple[str | None, str | None, str | None]:
    """Extract routing entities only; Appointment Service remains the scheduling source of truth."""
    doctor_matches = re.finditer(
        r"(?:bác\s*sĩ|bs\.?)[\s:]+(.+?)(?=\s+(?:ngày|ngay|hôm|hom|vào|vao|còn|con|có|co|lúc|luc|thứ|thu|trống|trong|rảnh|ranh|làm|lam)\b|[?!,.]|$)",
        question,
        re.IGNORECASE,
    )
    # A patient may say "bác sĩ ngày 14/8 ... bác sĩ Bình". Ignore the
    # temporal fragment after the first mention and keep the last valid name.
    invalid_name_prefixes = ("ngay", "hom", "vao", "luc", "thu", "ca", "khung", "gio")
    conversational_suffixes = {
        "a", "nha", "nhe", "vay", "do", "nhi", "hen", "ma", "giup", "minh", "toi", "voi"
    }
    doctor_candidates = []
    for match in doctor_matches:
        candidate = match.group(1).strip(" -:")
        # Patients commonly end a clarification with particles such as
        # "Bình á", "Linh ạ" or "Vương nha"; these are not part of a name.
        name_parts = candidate.split()
        while len(name_parts) > 1 and _normalize(name_parts[-1].strip("?!,.")) in conversational_suffixes:
            name_parts.pop()
        candidate = " ".join(name_parts).strip(" -:?!,.")
        folded = _normalize(candidate)
        if candidate and not folded.startswith(invalid_name_prefixes):
            doctor_candidates.append(candidate)
    doctor_name = doctor_candidates[-1] if doctor_candidates else None
    today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
    normalized = _normalize(question)
    requested_date = None
    requested_time = None
    date_candidates: list[tuple[int, object]] = []
    for relative_match in re.finditer(r"(?<!\w)(ngay mai|hom nay)(?!\w)", normalized):
        relative_date = today + timedelta(days=1) if relative_match.group(1) == "ngay mai" else today
        date_candidates.append((relative_match.start(), relative_date))
    for date_match in re.finditer(r"(?<!\d)(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}))?(?!\d)", question):
        day, month = int(date_match.group(1)), int(date_match.group(2))
        year = int(date_match.group(3) or today.year)
        try:
            parsed = today.replace(year=year, month=month, day=day)
            if date_match.group(3) is None and parsed < today:
                parsed = parsed.replace(year=year + 1)
            date_candidates.append((date_match.start(), parsed))
        except ValueError:
            continue
    if date_candidates:
        requested_date = max(date_candidates, key=lambda item: item[0])[1]

    # Accept the common Vietnamese time formats used in chat: 9h, 9h30,
    # 9 giờ and 09:00. The scheduling service validates whether it is a slot.
    time_matches = list(re.finditer(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)", question))
    time_matches.extend(re.finditer(
        r"(?<!\d)([01]?\d|2[0-3])\s*(?:h|giờ|gio)(?:\s*([0-5]?\d))?(?!\d)",
        question,
        re.IGNORECASE,
    ))
    if time_matches:
        time_match = max(time_matches, key=lambda item: item.start())
        requested_time = f"{int(time_match.group(1)):02d}:{int(time_match.group(2) or 0):02d}"

    return doctor_name, requested_date.isoformat() if requested_date else None, requested_time


def classify_support_request(question: str) -> SupportDecision:
    """Keep operational decisions deterministic; generative AI may only polish safe FAQ wording."""
    clean = question.strip()
    normalized = _normalize(clean)
    normalized, has_conversation_opener = _without_conversation_opener(normalized)
    doctor_name, requested_date, requested_time = _appointment_entities(clean)

    if has_conversation_opener and not normalized:
        return SupportDecision(
            "GREETING",
            "Mình đây. Bạn cần hỗ trợ gì về lịch khám, bác sĩ, giá khám hoặc tài khoản?",
            False,
            "Bệnh nhân mở đầu cuộc trò chuyện.",
            0.96,
        )

    if _contains(normalized, ("ban khong hieu", "toi da noi roi", "sao van khong duoc", "van khong duoc", "tra loi sai")):
        return SupportDecision(
            "DISSATISFACTION",
            "Mình chưa thể xử lý chính xác trường hợp này. Mình sẽ chuyển cuộc trò chuyện cho bộ phận lễ tân hỗ trợ tiếp.",
            True,
            "Bệnh nhân cho biết hướng dẫn tự động chưa giải quyết được vấn đề.",
            0.98,
        )

    # Safety must win over operational intents. A patient mentioning an
    # emergency sign and a doctor's schedule needs urgent guidance first.
    if _contains(normalized, ("kho tho", "kho nuot", "ngat", "sot cao", "dau du doi", "cap cuu", "lan nhanh", "soc phan ve", "sung moi", "sung mat")):
        return SupportDecision(
            "URGENT",
            "Nếu bạn đang khó thở, khó nuốt, ngất, sốt cao, đau dữ dội, sưng môi hoặc mắt, hay tổn thương lan nhanh, đừng chờ phản hồi trong chat. Hãy gọi 115 hoặc đến cơ sở cấp cứu gần nhất. Tôi có thể chuyển yêu cầu hành chính cho lễ tân sau khi bạn đã bảo đảm an toàn.",
            True,
            "Bệnh nhân mô tả dấu hiệu cần ưu tiên an toàn; không xử lý y khoa qua chat.",
        )

    # A request to choose a suitable doctor is different from asking how to
    # operate the booking form. The appointment service will compare the care
    # topic with real specialty and biography data from doctor-service.
    doctor_recommendation = _contains(normalized, (
        "nen chon bac si", "chon bac si nao", "bac si nao phu hop",
        "goi y bac si", "tu van bac si", "nen kham bac si nao",
    ))
    dermatology_topic = _contains(normalized, (
        "nam da", "nam", "mun", "trung ca", "viem da", "di ung",
        "me day", "vay nen", "eczema", "cham", "sac to", "toc", "mong",
    ))
    if doctor_recommendation and dermatology_topic:
        return SupportDecision(
            "DOCTOR_RECOMMENDATION",
            "Mình đang đối chiếu nhu cầu của bạn với chuyên môn và mô tả hồ sơ bác sĩ tại phòng khám.",
            False,
            "Gợi ý bác sĩ dựa trên hồ sơ chuyên môn đang hoạt động tại phòng khám.",
            0.95,
        )

    personal_appointment = _contains(normalized, ("lich cua toi", "toi co lich", "lich da dat", "trang thai lich"))
    doctor_reference = re.search(r"(?<!\w)(?:bac si|bs\.?)\b", normalized) is not None
    availability_wording = _contains(normalized, (
        "lich bac si", "lich bs", "gio trong bac si", "gio trong bs",
        "bac si con lich", "bac si co lich", "xem lich", "kiem tra lich",
        "con lich", "co lich", "con trong", "co trong", "gio trong",
        "gio nao trong", "bac si ranh", "bs ranh", "bac si lam", "bs lam",
    ))
    natural_availability = requested_date is not None and _contains(
        normalized, ("lich", "trong", "ranh", "gio", "lam")
    )
    if (availability_wording or natural_availability) and doctor_reference and not personal_appointment:
        missing = []
        if not doctor_name:
            missing.append("tên bác sĩ")
        if not requested_date:
            missing.append("ngày muốn khám")
        if missing:
            return SupportDecision(
                "DOCTOR_AVAILABILITY",
                f"Bạn cho mình biết {' và '.join(missing)} để mình kiểm tra khung giờ trống trên hệ thống nhé.",
                False,
                "Chưa đủ thông tin để tra cứu lịch bác sĩ.",
                0.68,
                True,
                doctor_name,
                requested_date,
                requested_time,
            )
        return SupportDecision(
            "DOCTOR_AVAILABILITY",
            "Mình đang kiểm tra khung giờ trống từ hệ thống đặt lịch.",
            False,
            "Tra cứu khung giờ trống của bác sĩ.",
            0.94,
            False,
            doctor_name,
            requested_date,
            requested_time,
        )

    visit_action = re.search(r"\b(?:nen|can|phai)\s+(?:di\s+)?kham\b", normalized) is not None
    visit_timing = re.search(r"\b(?:khi nao|luc nao|bao gio|truong hop nao|dau hieu nao)\b", normalized) is not None
    visit_decision = re.search(r"\bco\s+(?:can|nen)\s+(?:di\s+)?kham(?:\s+khong)?\b", normalized) is not None
    if (visit_action and visit_timing) or visit_decision or _contains(normalized, ("dau hieu can di kham",)):
        return SupportDecision(
            "DERMATOLOGY_VISIT_GUIDE",
            "Bạn nên đặt khám da liễu khi vấn đề da kéo dài, tái phát, nặng dần; gây đau hoặc ngứa ảnh hưởng sinh hoạt; phát ban lan rộng, phồng rộp, có vết loét; hoặc có dấu hiệu nhiễm trùng như sưng nóng, mủ hay sốt. Nếu khó thở, khó nuốt, sưng môi hoặc mắt, hay phát ban lan nhanh kèm sốt hoặc đau nhiều, hãy gọi 115 hoặc đến cơ sở cấp cứu. Trợ lý không thể chẩn đoán qua chat.",
            False,
            "Hỏi dấu hiệu và thời điểm nên đi khám da liễu.",
            0.94,
        )

    if _contains(normalized, ("gap le tan", "gap nguoi that", "gap nhan vien", "ket noi le tan", "noi chuyen voi le tan")):
        return SupportDecision(
            "HUMAN_REQUEST",
            "Mình có thể hỗ trợ bạn trước. Bạn đang gặp vấn đề gì với lịch khám hoặc tài khoản?",
            False,
            "Bệnh nhân yêu cầu gặp lễ tân nhưng chưa mô tả vấn đề.",
            0.95,
            True,
        )

    if _contains(normalized, (
        "cach huy lich", "huy lich nhu the nao", "lam sao de huy lich", "quy dinh huy lich",
        "cach doi lich", "doi lich nhu the nao", "lam sao de doi lich", "quy dinh doi lich",
    )):
        return SupportDecision(
            "APPOINTMENT_CHANGE_GUIDE",
            "Bạn có thể tự đổi hoặc hủy khi lịch còn trong thời hạn cho phép. Khi lịch đã được lễ tân xác nhận hoặc không còn quyền tự thao tác, hãy chọn Liên hệ hỗ trợ để lễ tân kiểm tra. Lịch chỉ thay đổi sau khi hệ thống xác nhận.",
            False,
            "Hỏi cách đổi hoặc hủy lịch.",
        )

    if _contains(normalized, ("bao loi", "loi he thong", "khong doi duoc", "khong huy duoc", "thong tin khong dung")):
        return SupportDecision(
            "APPOINTMENT_TECHNICAL_ISSUE",
            "Bạn hãy tải lại trang, mở mục Lịch khám và kiểm tra trạng thái lịch. Nếu lịch đã được xác nhận hoặc đã quá thời hạn tự thao tác thì hệ thống sẽ yêu cầu lễ tân hỗ trợ. Nếu bạn đã thử nhưng vẫn lỗi, hãy mô tả thông báo đang thấy để mình kiểm tra tiếp.",
            False,
            "Bệnh nhân gặp lỗi khi thao tác lịch; AI đã hướng dẫn kiểm tra trạng thái và tải lại trang.",
            0.82,
            True,
        )

    if _contains(normalized, ("huy lich", "khong di duoc", "khong den duoc")):
        return SupportDecision(
            "CANCEL_APPOINTMENT",
            "Tôi chưa thể xử lý yêu cầu hủy lịch trực tiếp. Lễ tân cần kiểm tra đúng lịch và trạng thái hiện tại; lịch chỉ thay đổi khi hệ thống xác nhận.",
            True,
            "Bệnh nhân yêu cầu hỗ trợ hủy lịch.",
        )

    if _contains(normalized, ("doi lich", "doi gio", "doi ngay", "chuyen lich", "hen lai")):
        return SupportDecision(
            "RESCHEDULE_APPOINTMENT",
            "Tôi chưa thể xử lý yêu cầu đổi lịch trực tiếp. Lễ tân cần kiểm tra khung giờ còn trống; lịch cũ vẫn giữ nguyên cho đến khi hệ thống xác nhận lịch mới.",
            True,
            "Bệnh nhân yêu cầu hỗ trợ đổi lịch.",
        )

    booking_howto = re.search(
        r"\b(?:cach|lam sao(?: de)?|lam the nao(?: de)?|huong dan)\s+dat lich\b"
        r"|\bdat lich\s+(?:nhu the nao|lam sao|sao|o dau|bang cach nao)\b",
        normalized,
    ) is not None
    if booking_howto or _contains(normalized, ("chon bac si",)):
        return SupportDecision(
            "BOOKING_GUIDE",
            "Bạn mở mục Lịch khám, lần lượt chọn bác sĩ, ngày, khung giờ, nhập lý do khám, xem lại thông tin rồi xác nhận. Khung giờ được giữ trong 5 phút khi bạn hoàn tất đặt lịch.",
            False,
            "Hỏi cách tự đặt lịch trên web.",
            0.96,
        )

    if _contains(normalized, ("dat ho", "dat lich giup", "le tan dat", "muon dat lich", "can dat lich")):
        return SupportDecision(
            "BOOKING_ASSISTANCE",
            "Tôi chưa thể tự tạo lịch thay bạn. Lễ tân có thể kiểm tra bác sĩ, ngày và khung giờ rồi gửi đề nghị để bạn xác nhận.",
            True,
            "Bệnh nhân cần lễ tân hỗ trợ đặt lịch.",
        )

    if _contains(normalized, ("lich cua toi", "lich da dat", "da xac nhan", "trang thai lich", "kiem tra lich")):
        return SupportDecision(
            "APPOINTMENT_STATUS",
            "Thông tin trạng thái lịch là dữ liệu cá nhân. Vui lòng mở mục Lịch khám; nếu thông tin chưa rõ, tôi sẽ chuyển bạn sang lễ tân để kiểm tra đúng hồ sơ.",
            True,
            "Bệnh nhân cần kiểm tra trạng thái lịch cá nhân.",
        )

    if _contains(normalized, ("quen mat khau", "khong dang nhap", "khoa tai khoan", "email", "otp", "tai khoan")):
        return SupportDecision(
            "ACCOUNT_SUPPORT",
            "Bạn có thể dùng chức năng Quên mật khẩu tại màn hình đăng nhập. Nếu email, OTP hoặc tài khoản vẫn gặp lỗi, lễ tân sẽ ghi nhận và chuyển quản trị viên kiểm tra.",
            True,
            "Bệnh nhân cần hỗ trợ tài khoản hoặc xác minh email.",
        )

    if _contains(normalized, ("khieu nai", "phan anh", "khong hai long", "thai do")):
        return SupportDecision(
            "FEEDBACK",
            "Tôi sẽ chuyển phản ánh này cho lễ tân tiếp nhận. Bạn không cần gửi thông tin nhạy cảm trong chat; nhân viên sẽ xác minh đúng hồ sơ khi cần.",
            True,
            "Bệnh nhân gửi phản ánh cần nhân viên tiếp nhận.",
        )

    if _contains(normalized, ("ket qua ai", "top 3", "grad cam", "gradcam", "do tin cay", "phan tram ai", "ai noi")):
        return SupportDecision(
            "AI_RESULT_EXPLANATION",
            "Kết quả AI là thông tin tham khảo từ hình ảnh: Top-3 là ba nhóm mô hình thấy tương đồng nhất, phần trăm thể hiện mức tin cậy tương đối và Grad-CAM đánh dấu vùng ảnh ảnh hưởng đến dự đoán. Kết quả không phải chẩn đoán; bác sĩ cần đối chiếu triệu chứng và thăm khám trực tiếp.",
            False,
            "Hỏi cách hiểu kết quả kiểm tra da bằng AI.",
        )

    if _contains(normalized, ("thuoc", "lieu", "ke don", "chan doan cho toi", "toi bi", "benh cua toi", "anh cua toi", "benh gi")):
        return SupportDecision(
            "MEDICAL_QUESTION",
            "Hộp hỗ trợ không chẩn đoán hoặc kê thuốc. Bạn có thể dùng mục Kiểm tra da AI để tham khảo sơ bộ, nhưng kết luận và điều trị phải do bác sĩ thực hiện. Tôi có thể chuyển lễ tân nếu bạn cần đặt lịch.",
            True,
            "Bệnh nhân có câu hỏi chuyên môn; cần hướng dẫn đặt khám thay vì chẩn đoán qua chat.",
        )

    if _contains(normalized, ("hotline", "so dien thoai", "goi phong kham", "lien he")):
        return SupportDecision(
            "HOTLINE",
            f"Hotline phòng khám là {HOTLINE}. Bạn cũng có thể tiếp tục nhắn tại đây; yêu cầu cần thao tác lịch sẽ được chuyển sang lễ tân.",
            False,
            "Hỏi số hotline phòng khám.",
        )

    if _contains(normalized, ("gia kham", "muc gia", "phi kham", "bao nhieu", "chi phi")):
        return SupportDecision(
            "CONSULTATION_FEE",
            "Giá khám cơ bản được hiển thị theo từng bác sĩ ở danh sách và phần xem lại trước khi xác nhận. Giá được chốt tại thời điểm đặt và thanh toán trực tiếp tại phòng khám.",
            False,
            "Hỏi về giá khám cơ bản.",
        )

    if _contains(normalized, (
        "thong tin bac si", "thong tin ve bac si", "gioi thieu bac si",
        "ho so bac si", "cho toi thong tin bac si", "cho toi thong tin ve bac si",
    )):
        return SupportDecision(
            "DOCTOR_INFORMATION",
            "Mình đang tra cứu hồ sơ bác sĩ đang hoạt động tại phòng khám.",
            False,
            "Hỏi thông tin hồ sơ bác sĩ.",
            0.96,
            False,
            doctor_name,
        )

    if _contains(normalized, ("tim bac si", "bac si nao", "xem bac si", "danh sach bac si", "chuyen mon bac si")):
        return SupportDecision(
            "DOCTOR_GUIDE",
            "Bạn mở mục Lịch khám để xem danh sách bác sĩ. Mỗi hồ sơ có chuyên môn, kinh nghiệm, mô tả và giá khám; hãy chọn bác sĩ phù hợp rồi xem ngày và khung giờ còn trống.",
            False,
            "Hỏi cách tìm bác sĩ phù hợp.",
        )

    if _contains(normalized, ("gio lam", "lam viec", "mo cua", "thu may")):
        return SupportDecision(
            "WORKING_HOURS",
            "Lịch làm phụ thuộc từng bác sĩ và ngày nghỉ của phòng khám. Bạn chọn bác sĩ và ngày trong mục Lịch khám để xem các khung giờ đang thực sự còn trống.",
            False,
            "Hỏi giờ làm việc hoặc lịch trống.",
        )

    if _contains(normalized, ("ai", "kiem tra da", "tai anh", "hinh anh")):
        return SupportDecision(
            "AI_GUIDE",
            "Mục Kiểm tra da AI cho phép tải JPEG, PNG hoặc WebP để xem Top-3 nhóm tham khảo. Kết quả không thay thế bác sĩ; bạn có thể chủ động chia sẻ ảnh với đúng bác sĩ phụ trách khi đặt lịch.",
            False,
            "Hỏi cách sử dụng kiểm tra da AI.",
        )

    if _contains(normalized, (
        "da lieu", "cham soc da", "mun", "trung ca", "vay nen", "nam da", "eczema",
        "viem da", "me day", "mun coc", "hat com", "lupus", "candida", "ung thu da", "dieu tri",
    )):
        return SupportDecision(
            "DERMATOLOGY_GENERAL",
            "Tôi sẽ tra cứu tài liệu da liễu của hệ thống để cung cấp thông tin tham khảo chung.",
            False,
            "Hỏi kiến thức da liễu chung trong phạm vi tài liệu RAG.",
        )

    if re.search(r"\b(chao|hello|hi|alo)\b", normalized):
        return SupportDecision(
            "GREETING",
            "Xin chào! Tôi là trợ lý hỗ trợ tự động của DermAI Clinic. Tôi có thể hướng dẫn đặt lịch, giá khám, lịch làm việc, hotline hoặc chuyển bạn sang lễ tân.",
            False,
            "Bệnh nhân bắt đầu cuộc trò chuyện.",
        )

    return SupportDecision(
        "OTHER",
        "Tôi chưa thể xử lý yêu cầu này trực tiếp. Tôi có thể chuyển nội dung bạn vừa nhập sang lễ tân để nhân viên tiếp tục hỗ trợ trong cuộc trò chuyện này.",
        True,
        "Yêu cầu chưa thuộc nhóm hướng dẫn tự động; cần lễ tân tiếp nhận.",
        0.3,
    )


async def polish_safe_answer(decision: SupportDecision, api_key: str, preferred_model: str) -> str:
    """Send only a policy-approved category and template to Gemini, never the patient's message."""
    if not api_key or decision.requires_handoff:
        return decision.answer

    system_instruction = (
        "Bạn biên tập câu trả lời thủ tục của DermAI Clinic bằng tiếng Việt. "
        "Giữ nguyên toàn bộ dữ kiện, tối đa 80 từ, giọng bình tĩnh và chuyên nghiệp. "
        "Không thêm dữ kiện, không chẩn đoán, không kê đơn và không tuyên bố đã thao tác lịch. "
        "Chỉ trả về câu trả lời hoàn chỉnh, không thêm tiêu đề."
    )
    prompt = f"Nhóm yêu cầu: {decision.category}\nNội dung được phép: {decision.answer}"
    models = [preferred_model, "gemini-flash-latest", "gemini-2.5-flash", "gemini-2.0-flash"]
    models = list(dict.fromkeys(model for model in models if model))
    payload = {
        "system_instruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.15, "maxOutputTokens": 256},
    }

    async with httpx.AsyncClient(timeout=12.0) as client:
        for model in models:
            try:
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    headers={"x-goog-api-key": api_key},
                    json=payload,
                )
                response.raise_for_status()
                parts = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
                answer = "".join(part.get("text", "") for part in parts).strip()
                # Reject clipped generations and keep the reviewed deterministic
                # response instead of showing an incomplete administrative answer.
                if len(answer) >= 50 and answer.endswith((".", "!", "?")):
                    return answer
            except (httpx.HTTPStatusError, httpx.RequestError, KeyError, IndexError, TypeError):
                # Support remains available with the reviewed local response when Gemini is unavailable.
                continue
    return decision.answer

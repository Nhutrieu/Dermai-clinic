import { type ReactNode, useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  BrainCircuit,
  CalendarDays,
  Check,
  ChevronDown,
  CircleDollarSign,
  HeartPulse,
  MapPin,
  Menu,
  MessageCircle,
  PhoneCall,
  ShieldCheck,
  Star,
  Stethoscope,
  UserRound,
  X,
} from "lucide-react";
import { request } from "../../core/api";
import { formatVnd } from "../../core/currency";
import type { ClinicReview, Doctor } from "../../core/types";
import AccessibleDialog from "../../components/AccessibleDialog";
import AppFooter from "../../components/AppFooter";
import HomeFeatureCarousel from "../../components/HomeFeatureCarousel";

type HomePageProps = {
  openAuth: () => void;
  chat?: ReactNode;
};

const NAV_ITEMS = [
  { href: "#about", label: "Về chúng tôi" },
  { href: "#services", label: "Dịch vụ" },
  { href: "#doctors", label: "Bác sĩ" },
  { href: "#reviews", label: "Đánh giá" },
  { href: "#process", label: "Quy trình" },
];

const TREATMENT_GROUPS = [
  {
    title: "Mụn và thâm sau mụn",
    description: "Thăm khám mụn viêm, mụn ẩn, thâm và xây dựng kế hoạch chăm sóc phù hợp với tình trạng da.",
  },
  {
    title: "Viêm da và dị ứng",
    description: "Đánh giá tình trạng ngứa, mẩn đỏ, viêm da tiếp xúc, mề đay và các biểu hiện da nhạy cảm.",
  },
  {
    title: "Nấm da và rối loạn sắc tố",
    description: "Khám các biểu hiện nghi ngờ nấm da, tăng hoặc giảm sắc tố và những thay đổi màu sắc trên da.",
  },
  {
    title: "Theo dõi bệnh da tái phát",
    description: "Theo dõi đáp ứng, lịch tái khám và hướng dẫn chăm sóc giữa các lần gặp bác sĩ.",
  },
];

const FAQ_ITEMS = [
  {
    question: "Tôi có thể chọn bác sĩ và giờ khám không?",
    answer: "Có. Sau khi đăng nhập, bạn chọn bác sĩ, ngày khám và khung giờ còn trống được cập nhật trực tiếp từ lịch làm việc.",
  },
  {
    question: "Khi không thể đổi hoặc hủy lịch, tôi cần làm gì?",
    answer: "Bạn mở hộp thư hỗ trợ để trao đổi với lễ tân. Lễ tân sẽ kiểm tra trạng thái lịch và hỗ trợ theo quy định của phòng khám.",
  },
  {
    question: "Kết quả kiểm tra da bằng AI có phải chẩn đoán không?",
    answer: "Không. Kết quả chỉ hỗ trợ tham khảo từ hình ảnh. Bác sĩ da liễu là người đánh giá triệu chứng và đưa ra kết luận chuyên môn.",
  },
  {
    question: "Tôi có thể đặt lịch qua điện thoại không?",
    answer: "Có. Gọi hotline 0352 790 904 để lễ tân tìm hồ sơ, kiểm tra giờ trống và đặt lịch hộ khi cần.",
  },
];

function initials(name: string) {
  return name
    .trim()
    .split(/\s+/)
    .slice(-2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function DoctorPhoto({ doctor }: { doctor: Doctor }) {
  if (doctor.avatarUrl) {
    return <img src={doctor.avatarUrl} alt={`Bác sĩ ${doctor.fullName}`} loading="lazy" />;
  }

  return <span aria-hidden="true">{initials(doctor.fullName)}</span>;
}

function DoctorDetails({ doctor }: { doctor: Doctor }) {
  return (
    <>
      <p className="clinic-home-doctor-specialty">{doctor.specialtyCode}</p>
      <h3>BS. {doctor.fullName}</h3>
      <p className="clinic-home-doctor-meta">
        {doctor.experienceYears} năm kinh nghiệm
        {doctor.certificateNo ? `, chứng chỉ ${doctor.certificateNo}` : ""}
      </p>
      <p className="clinic-home-doctor-fee">
        Giá khám <strong>{formatVnd(doctor.consultationFee)}</strong>
      </p>
      <p className="clinic-home-doctor-bio">
        {doctor.bio?.trim() || "Bác sĩ đang cập nhật phần giới thiệu chuyên môn."}
      </p>
    </>
  );
}

export default function HomePage({ openAuth, chat }: HomePageProps) {
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [reviews, setReviews] = useState<ClinicReview[]>([]);
  const [doctorState, setDoctorState] = useState<"loading" | "ready" | "error">("loading");
  const [menuOpen, setMenuOpen] = useState(false);
  const [reviewsOpen, setReviewsOpen] = useState(false);
  const homeRef = useRef<HTMLDivElement>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const navigationRef = useRef<HTMLElement>(null);

  // Keep the existing public data endpoints and doctor-profile realtime refresh intact.
  async function loadDoctors() {
    const list = await request<Doctor[]>("/doctors");
    setDoctors(list.filter((doctor) => doctor.fullName?.trim()));
    setDoctorState("ready");
  }

  useEffect(() => {
    void loadDoctors().catch(() => setDoctorState("error"));
    void request<ClinicReview[]>("/appointments/reviews/public")
      .then(setReviews)
      .catch(() => setReviews([]));
  }, []);

  useEffect(() => {
    const refresh = () => void loadDoctors().catch(() => undefined);
    window.addEventListener("doctor-profiles-changed", refresh);
    return () => window.removeEventListener("doctor-profiles-changed", refresh);
  }, []);

  // Mobile navigation locks background scroll, traps focus and restores the trigger on close.
  useEffect(() => {
    if (!menuOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    navigationRef.current?.querySelector<HTMLElement>("a[href],button:not([disabled])")?.focus();
    const handleKeyboard = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMenuOpen(false);
        window.requestAnimationFrame(() => menuButtonRef.current?.focus());
        return;
      }
      if (event.key !== "Tab" || !navigationRef.current) return;
      const items = Array.from(navigationRef.current.querySelectorAll<HTMLElement>("a[href],button:not([disabled])"));
      const first = items[0];
      const last = items.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    window.addEventListener("keydown", handleKeyboard);
    return () => {
      window.removeEventListener("keydown", handleKeyboard);
      document.body.style.overflow = previousOverflow;
    };
  }, [menuOpen]);

  // One observer coordinates section reveals without running work on every scroll frame.
  useEffect(() => {
    const root = homeRef.current;
    if (!root) return;

    const sections = Array.from(root.querySelectorAll<HTMLElement>("[data-home-reveal]"));
    const showAll = () => sections.forEach((section) => section.classList.add("is-visible"));
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (reduceMotion || !("IntersectionObserver" in window)) {
      showAll();
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        });
      },
      { rootMargin: "0px 0px -8%", threshold: 0.16 },
    );

    sections.forEach((section) => observer.observe(section));
    return () => observer.disconnect();
  }, []);

  const closeMenu = () => setMenuOpen(false);
  const featuredReview = reviews[0];
  // Keep the homepage concise; the dialog carries the complete approved review list.
  const supportingReviews = reviews.slice(1, 2);
  const validConsultationFees = doctors
    .map((doctor) => Number(doctor.consultationFee))
    .filter((fee) => Number.isFinite(fee) && fee > 0);
  const minimumConsultationFee = validConsultationFees.length > 0
    ? Math.min(...validConsultationFees)
    : null;

  return (
    <div ref={homeRef} className="clinic-home home-page">
      <a className="clinic-home-skip-link" href="#home-content">Đi đến nội dung chính</a>

      <header className="clinic-home-header">
        <div className="clinic-home-header-inner">
          <a className="clinic-home-brand" href="#top" aria-label="Derm Clinic, về đầu trang">
            <span className="clinic-home-brand-mark" aria-hidden="true"><Activity /></span>
            <span><strong>Derm Clinic</strong><small>Phòng khám da liễu</small></span>
          </a>

          <nav
            ref={navigationRef}
            id="clinic-home-navigation"
            className={`clinic-home-nav-links ${menuOpen ? "is-open" : ""}`}
            aria-label="Điều hướng trang chủ"
          >
            {NAV_ITEMS.map((item) => (
              <a key={item.href} href={item.href} onClick={closeMenu}>{item.label}</a>
            ))}
          </nav>

          <div className="clinic-home-header-actions">
          <a className="clinic-home-header-phone" href="tel:0352790904" aria-label="Gọi hotline Derm Clinic 0352 790 904">
              <PhoneCall aria-hidden="true" /><span>0352 790 904</span>
            </a>
            <button type="button" className="clinic-home-login" onClick={openAuth}>Đăng nhập</button>
            <button type="button" className="clinic-home-button clinic-home-header-book" onClick={openAuth}>
              Đặt lịch khám
            </button>
            <button
              ref={menuButtonRef}
              type="button"
              className="clinic-home-menu-button"
              aria-label={menuOpen ? "Đóng menu" : "Mở menu"}
              aria-expanded={menuOpen}
              aria-controls="clinic-home-navigation"
              onClick={() => setMenuOpen((value) => !value)}
            >
              {menuOpen ? <X /> : <Menu />}
            </button>
          </div>
        </div>
      </header>

      <main id="home-content" className="clinic-home-main">
        <section className="clinic-home-hero" id="top" aria-labelledby="home-hero-title">
          <div className="clinic-home-container clinic-home-hero-layout">
            <div className="clinic-home-hero-copy">
              <span className="clinic-home-skin-mark" aria-hidden="true">
                <span />
                <span />
                <span />
              </span>
              <h1 id="home-hero-title">Đặt lịch da liễu, gặp đúng bác sĩ.</h1>
              <p>Chọn bác sĩ, xem giờ trống và theo dõi lịch hẹn. Lễ tân hỗ trợ qua hotline khi cần.</p>
              <div className="clinic-home-hero-actions">
                <button type="button" className="clinic-home-button" onClick={openAuth}>
                  Đặt lịch khám <ArrowRight aria-hidden="true" />
                </button>
                <a className="clinic-home-text-link" href="#doctors">Xem bác sĩ đang nhận lịch</a>
              </div>
            </div>

            <HomeFeatureCarousel />
          </div>
        </section>

        <section className="clinic-home-access" aria-label="Thông tin đặt lịch nhanh">
          <div className="clinic-home-container clinic-home-access-grid">
            <button type="button" className="clinic-home-access-action" onClick={openAuth}>
              <CalendarDays aria-hidden="true" />
              <span><small>Đặt lịch trực tuyến</small><strong>Chọn bác sĩ và giờ còn trống</strong></span>
              <ArrowRight aria-hidden="true" />
            </button>
            <div className="clinic-home-access-item">
              <CircleDollarSign aria-hidden="true" />
              <span><small>Giá khám cơ bản</small><strong>{minimumConsultationFee ? `Từ ${formatVnd(minimumConsultationFee)}` : "Theo từng bác sĩ"}</strong></span>
            </div>
            <a className="clinic-home-access-item" href="https://maps.google.com/?q=32%2F2+Th%E1%BB%91ng+Nh%E1%BA%A5t+G%C3%B2+V%E1%BA%A5p" target="_blank" rel="noreferrer">
              <MapPin aria-hidden="true" />
              <span><small>Địa chỉ phòng khám</small><strong>32/2 Thống Nhất, Gò Vấp</strong></span>
            </a>
            <a className="clinic-home-access-item" href="tel:0352790904">
              <MessageCircle aria-hidden="true" />
              <span><small>Lễ tân hỗ trợ</small><strong>0352 790 904</strong></span>
            </a>
          </div>
        </section>

        <section className="clinic-home-section clinic-home-about" id="about" aria-labelledby="home-about-title" data-home-reveal="values">
          <div className="clinic-home-container">
            <div className="clinic-home-section-heading">
              <h2 id="home-about-title">Một hành trình chăm sóc da rõ ràng hơn</h2>
              <p>Derm Clinic kết nối bệnh nhân, bác sĩ và lễ tân trên cùng một quy trình, từ đặt lịch đến theo dõi sau khám.</p>
            </div>

            <div className="clinic-home-values">
              <article className="clinic-home-value-featured">
                <BrainCircuit aria-hidden="true" />
                <div><h3>AI hỗ trợ sàng lọc ảnh da</h3><p>Kết quả giúp bạn hiểu thêm về nhóm bệnh có khả năng liên quan trước khi trao đổi với bác sĩ.</p></div>
              </article>
              <div className="clinic-home-value-list">
                <article>
                  <Stethoscope aria-hidden="true" />
                  <div><h3>Bác sĩ xem xét kết quả</h3><p>Triệu chứng, tiền sử và hình ảnh được đánh giá trong bối cảnh lâm sàng.</p></div>
                </article>
                <article>
                  <CalendarDays aria-hidden="true" />
                  <div><h3>Đặt lịch và theo dõi thuận tiện</h3><p>Chọn bác sĩ, giờ khám, nhận thông báo và xem lại hồ sơ trên một nơi.</p></div>
                </article>
              </div>
            </div>
          </div>
        </section>

        <section className="clinic-home-section clinic-home-treatments" aria-labelledby="home-treatments-title" data-home-reveal="treatments">
          <div className="clinic-home-container clinic-home-treatments-layout">
            <div className="clinic-home-section-heading">
              <h2 id="home-treatments-title">Các vấn đề da liễu thường được tiếp nhận</h2>
              <p>Chọn bác sĩ theo chuyên môn phù hợp. Chẩn đoán và kế hoạch điều trị chỉ được xác định sau khi bác sĩ thăm khám.</p>
              <a className="clinic-home-text-link" href="#doctors">Xem đội ngũ bác sĩ</a>
            </div>
            <div className="clinic-home-treatment-list">
              {TREATMENT_GROUPS.map((group) => (
                <article key={group.title}>
                  <h3>{group.title}</h3>
                  <p>{group.description}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="clinic-home-section clinic-home-process" id="process" aria-labelledby="home-process-title" data-home-reveal="process">
          <div className="clinic-home-container">
            <div className="clinic-home-section-heading clinic-home-section-heading-inline">
              <h2 id="home-process-title">Quy trình khám dễ theo dõi</h2>
              <p>Bốn bước nhất quán giúp bạn chủ động trước, trong và sau buổi khám.</p>
            </div>
            <ol className="clinic-home-process-list">
              <li><UserRound aria-hidden="true" /><div><h3>Tạo hồ sơ</h3><p>Cung cấp thông tin liên hệ và tiền sử cần thiết.</p></div></li>
              <li><CalendarDays aria-hidden="true" /><div><h3>Chọn lịch phù hợp</h3><p>Chọn bác sĩ, ngày và giờ còn trống theo nhu cầu.</p></div></li>
              <li><Stethoscope aria-hidden="true" /><div><h3>Khám với bác sĩ</h3><p>Nhận đánh giá chuyên môn và kế hoạch điều trị nếu cần.</p></div></li>
              <li><HeartPulse aria-hidden="true" /><div><h3>Theo dõi sau khám</h3><p>Xem hồ sơ, đơn thuốc và lịch tái khám được chỉ định.</p></div></li>
            </ol>
          </div>
        </section>

        <section className="clinic-home-section clinic-home-faq" id="faq" aria-labelledby="home-faq-title" data-home-reveal="faq">
          <div className="clinic-home-container clinic-home-faq-layout">
            <div className="clinic-home-section-heading">
              <h2 id="home-faq-title">Thông tin cần biết trước khi đặt lịch</h2>
              <p>Câu trả lời ngắn cho những tình huống bệnh nhân thường gặp khi sử dụng Derm Clinic.</p>
              <a className="clinic-home-phone-inline" href="tel:0352790904"><PhoneCall aria-hidden="true" /> Cần hỗ trợ thêm? Gọi 0352 790 904</a>
            </div>
            <div className="clinic-home-faq-list">
              {FAQ_ITEMS.map((item) => (
                <details key={item.question}>
                  <summary><span>{item.question}</span><ChevronDown aria-hidden="true" /></summary>
                  <p>{item.answer}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <section className="clinic-home-ai" id="services" aria-labelledby="home-ai-title" data-home-reveal="ai">
          <div className="clinic-home-container clinic-home-ai-layout">
            <div>
              <BrainCircuit className="clinic-home-ai-icon" aria-hidden="true" />
              <h2 id="home-ai-title">AI hỗ trợ bạn chuẩn bị thông tin tốt hơn</h2>
              <p>Hệ thống phân tích ảnh da, hiển thị các khả năng liên quan, vùng ảnh được chú ý và nội dung tham khảo từ tài liệu y khoa.</p>
              <figure className="clinic-home-ai-visual">
                <img
                  src="/images/home-carousel/co-nen-hoc-nganh-bac-si-da-lieu.png"
                  alt="Bác sĩ da liễu trong môi trường khám và tư vấn chuyên môn"
                  width="1536"
                  height="1024"
                  loading="lazy"
                />
                <span className="clinic-home-ai-scan" aria-hidden="true" />
                <figcaption>Minh họa quy trình xem xét hình ảnh trước khi trao đổi với bác sĩ.</figcaption>
              </figure>
              <button type="button" className="clinic-home-button" onClick={openAuth}>
                Kiểm tra da bằng AI <ArrowRight aria-hidden="true" />
              </button>
            </div>
            <div className="clinic-home-ai-principles">
              <h3>Vai trò của AI trong Derm Clinic</h3>
              <ul>
                <li><Check aria-hidden="true" /><span><strong>Gợi ý để tham khảo</strong> Kết quả không phải kết luận chẩn đoán.</span></li>
                <li><Check aria-hidden="true" /><span><strong>Giải thích trực quan</strong> Vùng ảnh được chú ý giúp kết quả dễ hiểu hơn.</span></li>
                <li><Check aria-hidden="true" /><span><strong>Kết nối với bác sĩ</strong> Bạn có thể chia sẻ ảnh và kết quả trong lần khám.</span></li>
              </ul>
              <p className="clinic-home-ai-notice" role="note">
                <ShieldCheck aria-hidden="true" />
                <span><strong>AI không đưa ra chẩn đoán cuối cùng.</strong> Kết quả cần được bác sĩ xem xét cùng triệu chứng và hồ sơ của bạn.</span>
              </p>
            </div>
          </div>
        </section>

        <section className="clinic-home-section clinic-home-doctors" id="doctors" aria-labelledby="home-doctors-title" data-home-reveal="doctors">
          <div className="clinic-home-container">
            <div className="clinic-home-section-heading clinic-home-section-heading-inline">
              <h2 id="home-doctors-title">Bác sĩ đồng hành cùng bạn</h2>
              <p>Thông tin được lấy trực tiếp từ hồ sơ chuyên môn đang hoạt động tại phòng khám.</p>
            </div>

            {doctorState === "loading" && (
              <div className="clinic-home-data-state" aria-live="polite"><span className="clinic-home-loading-line" /><span>Đang tải đội ngũ bác sĩ...</span></div>
            )}
            {doctorState === "error" && (
              <div className="clinic-home-data-state is-error" role="alert">Chưa thể tải danh sách bác sĩ. Vui lòng thử lại sau.</div>
            )}
            {doctorState === "ready" && doctors.length === 0 && (
              <div className="clinic-home-data-state">Đội ngũ bác sĩ đang được cập nhật.</div>
            )}

            {doctors.length > 0 && (
              <div
                className="clinic-home-doctor-rail"
                role="region"
                aria-label="Danh sách bác sĩ, cuộn ngang để xem thêm"
                tabIndex={doctors.length > 1 ? 0 : undefined}
              >
                {doctors.map((doctor) => (
                  <article className="clinic-home-doctor-card" key={doctor.id}>
                    <div className="clinic-home-doctor-photo"><DoctorPhoto doctor={doctor} /></div>
                    <div className="clinic-home-doctor-content">
                      <DoctorDetails doctor={doctor} />
                      <button type="button" className="clinic-home-text-button" onClick={openAuth}>Đặt lịch khám <ArrowRight aria-hidden="true" /></button>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </div>
        </section>

        <section className="clinic-home-section clinic-home-reviews" id="reviews" aria-labelledby="home-reviews-title" data-home-reveal="reviews">
          <div className="clinic-home-container">
            <div className="clinic-home-section-heading clinic-home-section-heading-inline">
              <h2 id="home-reviews-title">Cảm nhận sau buổi khám</h2>
              <p>Đánh giá đã được duyệt từ những bệnh nhân hoàn thành lịch khám tại Derm Clinic.</p>
            </div>

            {!featuredReview ? (
              <div className="clinic-home-data-state">Chưa có đánh giá nào được duyệt.</div>
            ) : (
              <div className="clinic-home-review-layout">
                <article className="clinic-home-review-featured">
                  <div className="clinic-home-stars" aria-label={`${featuredReview.rating} trên 5 sao`}>
                    {Array.from({ length: featuredReview.rating }, (_, index) => <Star key={index} aria-hidden="true" />)}
                  </div>
                  <blockquote>{featuredReview.comment}</blockquote>
                  <p><strong>{featuredReview.displayName}</strong><span>Bệnh nhân đã khám</span></p>
                </article>
                {supportingReviews.length > 0 && (
                  <div className="clinic-home-review-list">
                    {supportingReviews.map((review) => (
                      <article key={review.id}>
                        <div className="clinic-home-stars" aria-label={`${review.rating} trên 5 sao`}>
                          {Array.from({ length: review.rating }, (_, index) => <Star key={index} aria-hidden="true" />)}
                        </div>
                        <blockquote>{review.comment}</blockquote>
                        <p><strong>{review.displayName}</strong><span>Bệnh nhân đã khám</span></p>
                      </article>
                    ))}
                  </div>
                )}
              </div>
            )}

            {reviews.length > 2 && (
              <div className="clinic-home-review-more">
                <button
                  type="button"
                  className="clinic-home-text-button"
                  aria-haspopup="dialog"
                  onClick={() => setReviewsOpen(true)}
                >
                  Xem thêm đánh giá ({reviews.length}) <ArrowRight aria-hidden="true" />
                </button>
              </div>
            )}
          </div>
        </section>

        {reviewsOpen && (
          <AccessibleDialog
            title="Đánh giá từ bệnh nhân"
            titleId="clinic-review-dialog-title"
            descriptionId="clinic-review-dialog-description"
            className="clinic-home-review-dialog"
            backdropClassName="clinic-home-review-dialog-backdrop"
            closeLabel="Đóng danh sách đánh giá"
            onClose={() => setReviewsOpen(false)}
          >
            <p className="clinic-home-review-dialog-intro">
              {reviews.length} đánh giá đã được duyệt từ những bệnh nhân hoàn thành buổi khám.
            </p>
            <div className="clinic-home-review-dialog-list">
              {reviews.map((review) => (
                <article key={review.id}>
                  <header>
                    <div className="clinic-home-stars" aria-label={`${review.rating} trên 5 sao`}>
                      {Array.from({ length: review.rating }, (_, index) => <Star key={index} aria-hidden="true" />)}
                    </div>
                    <time dateTime={review.createdAt}>
                      {new Date(review.createdAt).toLocaleDateString("vi-VN")}
                    </time>
                  </header>
                  <blockquote>{review.comment}</blockquote>
                  <p><strong>{review.displayName}</strong><span>Bệnh nhân đã khám</span></p>
                </article>
              ))}
            </div>
          </AccessibleDialog>
        )}

        <section className="clinic-home-final" aria-labelledby="home-final-title" data-home-reveal="final">
          <div className="clinic-home-container clinic-home-final-layout">
            <div>
              <h2 id="home-final-title">Sẵn sàng bắt đầu chăm sóc làn da của bạn?</h2>
              <p>Đặt lịch trực tuyến hoặc gọi lễ tân nếu bạn cần hỗ trợ chọn bác sĩ và khung giờ phù hợp.</p>
            </div>
            <div className="clinic-home-final-actions">
              <button type="button" className="clinic-home-button" onClick={openAuth}>Đặt lịch khám</button>
              <a className="clinic-home-phone" href="tel:0352790904">
                <PhoneCall aria-hidden="true" /><span><small>Hotline đặt lịch</small><strong>0352 790 904</strong></span>
              </a>
            </div>
          </div>
        </section>
      </main>

      <AppFooter variant="public" />

      {chat}
    </div>
  );
}

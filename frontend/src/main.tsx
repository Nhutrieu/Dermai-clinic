import { FormEvent, lazy, ReactNode, Suspense, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { createPortal } from "react-dom";
import { Activity, ArrowRight, Bell, BrainCircuit, CalendarCheck, CalendarDays, Check, ChevronRight, Clock3, HeartPulse, LogOut, Menu, PhoneCall, ShieldCheck, Sparkles, Star, Stethoscope, Trash2, UserRound, X } from "lucide-react";
import { ApiError, request } from "./core/api";
import { subscribeRealtime } from "./core/realtime";
import type { Appointment, AvailabilitySlot, ClinicClosure, ClinicReview, Doctor, LeavePeriod, MedicalRecord, Patient, PatientNotification, Prescription, PrescriptionItem, Recommendation, RecommendationResult, ReminderAction, ReminderItem, SupportMessage, Tokens, WorkSchedule } from "./core/types";
import { RecordList, PrescriptionList } from "./components/Records";
import { State } from "./components/Ui";
import "./design-system.css";
import "./styles.css";
import "./navigation.css";
import "./clinic-address.css";
import "./app-motion.css";
import "./workspace-polish.css";
import "./record-filters.css";
import "./hotline.css";
import "./chat.css";
import "./admin-analytics.css";
import GoogleSignIn, { type GoogleLoginResult } from "./features/auth/GoogleSignIn";

const PublicRoute = lazy(() => import("./routes/PublicRoute"));
const PatientRoute = lazy(() => import("./routes/PatientRoute"));
const DoctorRoute = lazy(() => import("./routes/DoctorRoute"));
const ReceptionistRoute = lazy(() => import("./routes/ReceptionistRoute"));
const AdminRoute = lazy(() => import("./routes/AdminRoute"));
const AdminPanel = lazy(() => import("./features/admin/AdminPanel"));
const ReceptionPanel = lazy(() => import("./features/reception/ReceptionPanel"));
const PatientProfile = lazy(() => import("./features/patient/PatientProfile"));
const PatientAppointments = lazy(() => import("./features/patient/PatientAppointments"));
const DoctorProfile = lazy(() => import("./features/doctor/DoctorProfile"));
const DoctorView = lazy(() => import("./features/doctor/DoctorView"));
const ReceptionHotlineBooking = lazy(() => import("./features/reception/HotlineBooking"));
const PatientNotifications = lazy(() => import("./features/patient/PatientNotifications"));
const PatientAiScreen = lazy(() => import("./features/patient/PatientAiScreen"));
const SupportChat = lazy(() => import("./features/support/SupportChat"));

function App() {
    const [session, setSession] = useState<Tokens | null>(() => { try { return JSON.parse(sessionStorage.getItem("dermai-session") || "null") } catch { return null } });
    const [authOpen, setAuthOpen] = useState(false); const [forgotOpen, setForgotOpen] = useState(false);
    useEffect(() => subscribeRealtime(event => {
        if (event.type === "DOCTOR_PROFILE_UPDATED") window.dispatchEvent(new CustomEvent("doctor-profiles-changed", { detail: event }));
    }, { path: "/api/v1/doctors/ws/profile" }), []);
    if (!session) return <Suspense fallback={<State text="Đang tải giao diện..." />}><PublicRoute>{forgotOpen ? <ForgotPassword close={() => setForgotOpen(false)} /> : authOpen ? <><button className="auth-home" onClick={() => setAuthOpen(false)}><X /> Về trang chủ</button><button className="auth-forgot" onClick={() => setForgotOpen(true)}>Quên mật khẩu?</button><Login onLogin={x => { sessionStorage.setItem("dermai-session", JSON.stringify(x)); setSession(x) }} /></> : <Home openAuth={() => setAuthOpen(true)} />}</PublicRoute></Suspense>;
    const workspace = <><Dashboard session={session} logout={() => { sessionStorage.removeItem("dermai-session"); setSession(null) }} />{session.role === "PATIENT" && <PatientNotifications session={session} />}{session.role === "RECEPTIONIST" && <ReceptionHotlineBooking session={session} />}{["PATIENT", "RECEPTIONIST"].includes(session.role) && <SupportChat session={session} />}</>;
    const Route = session.role === "PATIENT" ? PatientRoute : session.role === "DOCTOR" ? DoctorRoute : session.role === "RECEPTIONIST" ? ReceptionistRoute : AdminRoute;
    return <Suspense fallback={<State text="Đang mở không gian làm việc..." />}><Route>{workspace}</Route></Suspense>;
}
function Home({ openAuth }: { openAuth: () => void }) {
    const [doctors, setDoctors] = useState<Doctor[]>([]); const [reviews, setReviews] = useState<ClinicReview[]>([]); const [doctorError, setDoctorError] = useState(""); const [menu, setMenu] = useState(false);
    async function loadDoctors() { const list = await request<Doctor[]>("/doctors"); setDoctors(list.filter(d => d.fullName)); setDoctorError("") }
    useEffect(() => { loadDoctors().catch(() => setDoctorError("Chưa thể tải danh sách bác sĩ."));request<ClinicReview[]>("/appointments/reviews/public").then(setReviews).catch(()=>setReviews([])) }, []);
    useEffect(() => { const refresh = () => { void loadDoctors().catch(() => undefined) }; window.addEventListener("doctor-profiles-changed", refresh); return () => window.removeEventListener("doctor-profiles-changed", refresh) }, []);
    useEffect(() => {
        const page = document.querySelector<HTMLElement>(".home-page");
        if (!page) return;
        const nav = page.querySelector<HTMLElement>(".home-nav");
        const sectionLinks = Array.from(page.querySelectorAll<HTMLAnchorElement>('.home-nav nav a[href^="#"]'));
        const revealTargets = Array.from(page.querySelectorAll<HTMLElement>(
            ".home-about > *, .home-services > *, .home-doctors > *, .doctor-showcase > article, .home-process > *, .process-line > article, .home-reviews > *, .review-grid > article, .home-cta > *"
        ));
        revealTargets.forEach((element, index) => {
            element.classList.add("motion-reveal");
            element.style.setProperty("--reveal-order", String(index % 4));
        });
        const revealObserver = new IntersectionObserver(entries => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    (entry.target as HTMLElement).classList.add("is-visible");
                    revealObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.12, rootMargin: "0px 0px -8% 0px" });
        revealTargets.forEach(element => revealObserver.observe(element));

        const sections = Array.from(page.querySelectorAll<HTMLElement>("main section[id]"));
        const sectionObserver = new IntersectionObserver(entries => {
            entries.forEach(entry => {
                if (!entry.isIntersecting) return;
                sectionLinks.forEach(link => link.classList.toggle("is-active", link.hash === `#${entry.target.id}`));
            });
        }, { rootMargin: "-30% 0px -60% 0px" });
        sections.forEach(section => sectionObserver.observe(section));

        let frame = 0;
        const updateScroll = () => {
            cancelAnimationFrame(frame);
            frame = requestAnimationFrame(() => {
                const max = Math.max(document.documentElement.scrollHeight - window.innerHeight, 1);
                page.style.setProperty("--scroll-progress", String(Math.min(window.scrollY / max, 1)));
                nav?.classList.toggle("is-scrolled", window.scrollY > 18);
            });
        };
        updateScroll();
        window.addEventListener("scroll", updateScroll, { passive: true });

        const hero = page.querySelector<HTMLElement>(".hero-visual");
        const handlePointer = (event: PointerEvent) => {
            if (!hero) return;
            const bounds = hero.getBoundingClientRect();
            hero.style.setProperty("--pointer-x", String((event.clientX - bounds.left) / bounds.width - 0.5));
            hero.style.setProperty("--pointer-y", String((event.clientY - bounds.top) / bounds.height - 0.5));
        };
        const resetPointer = () => { hero?.style.setProperty("--pointer-x", "0"); hero?.style.setProperty("--pointer-y", "0"); };
        hero?.addEventListener("pointermove", handlePointer);
        hero?.addEventListener("pointerleave", resetPointer);
        return () => {
            cancelAnimationFrame(frame);
            window.removeEventListener("scroll", updateScroll);
            hero?.removeEventListener("pointermove", handlePointer);
            hero?.removeEventListener("pointerleave", resetPointer);
            revealObserver.disconnect();
            sectionObserver.disconnect();
        };
    }, [doctors.length, reviews.length]);
    const initials = (name: string) => name.split(/\s+/).slice(-2).map(x => x[0]).join("").toUpperCase();
    return <div className="home-page">
        <header className="home-nav"><a className="home-brand" href="#top"><span><Activity /></span><b>DermAI <em>Clinic</em></b></a><nav className={menu ? "open" : ""}><a href="#about" onClick={() => setMenu(false)}>Về chúng tôi</a><a href="#services" onClick={() => setMenu(false)}>Dịch vụ</a><a href="#doctors" onClick={() => setMenu(false)}>Bác sĩ</a><a href="#reviews" onClick={() => setMenu(false)}>Đánh giá</a><a href="#process" onClick={() => setMenu(false)}>Quy trình</a></nav><div className="home-nav-actions"><a className="nav-hotline" href="tel:0352790904"><PhoneCall /><span>0352 790 904</span></a><button className="nav-login" onClick={openAuth}>Đăng nhập</button><button className="nav-book" onClick={openAuth}>Đặt lịch khám <ArrowRight /></button><button className="menu-button" onClick={() => setMenu(!menu)}>{menu ? <X /> : <Menu />}</button></div></header>
        <main id="top">
            <section className="home-hero"><div className="hero-copy"><div className="hero-kicker"><Sparkles /> Chăm sóc da liễu toàn diện</div><h1>Làn da khỏe mạnh bắt đầu từ sự <i>thấu hiểu.</i></h1><p>DermAI Clinic kết nối đội ngũ bác sĩ da liễu với quy trình khám thuận tiện, hồ sơ y khoa liền mạch và công nghệ hỗ trợ an toàn.</p><div className="hero-actions"><button onClick={openAuth}>Đặt lịch với bác sĩ <ArrowRight /></button><a href="#doctors">Xem đội ngũ <ChevronRight /></a></div><div className="hero-trust"><span><Check /> Bác sĩ phụ trách trực tiếp</span><span><Check /> Bảo mật hồ sơ</span><span><Check /> Theo dõi sau khám</span></div></div><div className="hero-visual"><div className="hero-orbit orbit-one" /><div className="hero-orbit orbit-two" /><div className="hero-medical"><span className="medical-icon"><Stethoscope /></span><div><small>CHĂM SÓC CHUYÊN MÔN</small><strong>Đồng hành cùng làn da của bạn</strong><p>Từ thăm khám, chẩn đoán đến điều trị và tái khám trên một quy trình thống nhất.</p></div></div><div className="floating-card float-top"><CalendarCheck /><div><b>Đặt lịch chủ động</b><small>Chọn bác sĩ và giờ phù hợp</small></div></div><div className="floating-card float-bottom"><ShieldCheck /><div><b>Hồ sơ an toàn</b><small>Dữ liệu được lưu trữ tập trung</small></div></div></div></section>
            <section className="home-strip"><span>CHĂM SÓC DA LIỄU DỰA TRÊN</span><b>Chuyên môn</b><i /> <b>Thấu hiểu</b><i /> <b>Công nghệ</b><i /> <b>An toàn</b></section>
            <section className="home-about" id="about"><div className="section-label">VỀ DERMAI CLINIC</div><div className="about-heading"><h2>Chăm sóc đúng người,<br />đúng thời điểm.</h2><p>Chúng tôi xây dựng trải nghiệm khám da liễu rõ ràng và liên tục: bệnh nhân chủ động chọn lịch, bác sĩ quản lý chuyên môn, lễ tân điều phối và mọi kết quả được lưu trong hồ sơ y khoa.</p></div><div className="about-cards"><article><span>01</span><HeartPulse /><h3>Lấy bệnh nhân làm trung tâm</h3><p>Mỗi kế hoạch điều trị bắt đầu từ tình trạng và nhu cầu thực tế của từng người.</p></article><article><span>02</span><Stethoscope /><h3>Bác sĩ chịu trách nhiệm</h3><p>Chẩn đoán, kê đơn và chỉ định tái khám luôn do bác sĩ trực tiếp thực hiện.</p></article><article><span>03</span><BrainCircuit /><h3>Công nghệ hỗ trợ</h3><p>Hệ thống hỗ trợ điều phối và quản lý; quyết định y khoa không được tự động thay thế.</p></article></div></section>
            <section className="home-services" id="services"><div><div className="section-label light">DỊCH VỤ CỦA CHÚNG TÔI</div><h2>Một hành trình chăm sóc<br /><i>liền mạch.</i></h2><p>Từ nhu cầu khám ban đầu đến theo dõi điều trị, mọi bước đều minh bạch cho bệnh nhân và nhân viên y tế.</p><button onClick={openAuth}>Bắt đầu đặt lịch <ArrowRight /></button></div><div className="service-list"><article><span>01</span><div><h3>Khám da liễu</h3><p>Đặt lịch với bác sĩ phù hợp và theo dõi trạng thái tiếp nhận.</p></div><ChevronRight /></article><article><span>02</span><div><h3>Hồ sơ & chẩn đoán</h3><p>Xem kết luận chuyên môn, kế hoạch điều trị sau buổi khám.</p></div><ChevronRight /></article><article><span>03</span><div><h3>Đơn thuốc điện tử</h3><p>Thông tin thuốc, liều dùng và hướng dẫn do bác sĩ ký.</p></div><ChevronRight /></article><article><span>04</span><div><h3>Tái khám chủ động</h3><p>Bác sĩ chỉ định, bệnh nhân tự chọn giờ trống phù hợp.</p></div><ChevronRight /></article></div></section>
            <section className="home-doctors" id="doctors"><div className="doctors-head"><div><div className="section-label">ĐỘI NGŨ CHUYÊN MÔN</div><h2>Bác sĩ đồng hành<br />cùng bạn.</h2></div><p>Danh sách được đồng bộ trực tiếp từ hồ sơ bác sĩ đang hoạt động tại phòng khám.</p></div>{doctorError && <div className="doctor-empty">{doctorError}</div>}{!doctorError && doctors.length === 0 && <div className="doctor-empty">Đội ngũ bác sĩ đang được cập nhật.</div>}<div className="doctor-showcase">{doctors.slice(0, 6).map((doctor, index) => <article key={doctor.id}><div className={`doctor-portrait portrait-${index % 3}`}>{doctor.avatarUrl ? <img src={doctor.avatarUrl} alt={`BS. ${doctor.fullName}`} /> : <><span>{initials(doctor.fullName)}</span><Stethoscope /></>}</div><div className="doctor-info"><small>{doctor.specialtyCode}</small><h3>BS. {doctor.fullName}</h3><p>{doctor.experienceYears} năm kinh nghiệm{doctor.certificateNo ? ` · Chứng chỉ ${doctor.certificateNo}` : ""}</p>{doctor.bio && <p className="doctor-card-bio">{doctor.bio}</p>}<button onClick={openAuth}>Đặt lịch <ArrowRight /></button></div></article>)}</div></section>
            <section className="home-process" id="process"><div className="section-label">QUY TRÌNH KHÁM</div><h2>Đơn giản trong từng bước.</h2><div className="process-line"><article><b>01</b><div><UserRound /><h3>Tạo hồ sơ</h3><p>Đăng ký tài khoản bệnh nhân và cập nhật thông tin cá nhân.</p></div></article><article><b>02</b><div><CalendarDays /><h3>Chọn lịch khám</h3><p>Chọn bác sĩ, thời gian mong muốn và gửi yêu cầu.</p></div></article><article><b>03</b><div><Stethoscope /><h3>Khám với bác sĩ</h3><p>Nhận chẩn đoán, kế hoạch điều trị và đơn thuốc nếu cần.</p></div></article><article><b>04</b><div><Clock3 /><h3>Theo dõi & tái khám</h3><p>Xem hồ sơ và chủ động chọn giờ tái khám theo chỉ định.</p></div></article></div></section>
            <section className="home-reviews" id="reviews"><div className="reviews-head"><div><div className="section-label">CẢM NHẬN TỪ BỆNH NHÂN</div><h2>Sự tin tưởng được xây dựng<br />từ từng lần thăm khám.</h2></div><p>Đánh giá xác thực từ những bệnh nhân đã hoàn thành buổi khám tại DermAI Clinic.</p></div>{reviews.length===0?<div className="doctor-empty">Chưa có đánh giá nào được duyệt.</div>:<div className="review-grid">{reviews.map(review=><article key={review.id}><div className="review-stars">{Array.from({length:review.rating},(_,x)=><Star key={x}/>)}</div><blockquote>“{review.comment}”</blockquote><footer><span>{review.displayName.slice(0,2).toUpperCase()}</span><div><b>{review.displayName}</b><small>Bệnh nhân đã khám</small></div></footer></article>)}</div>}</section>
            <section className="home-cta"><div><span>DERMAI CLINIC</span><h2>Sẵn sàng chăm sóc<br />làn da của bạn?</h2><p>Tạo hồ sơ và đặt lịch khám phù hợp chỉ trong vài bước.</p></div><div className="home-cta-actions"><button onClick={openAuth}>Đặt lịch ngay <ArrowRight /></button><a href="tel:0352790904"><PhoneCall /><span><small>HOTLINE ĐẶT LỊCH</small><b>0352 790 904</b></span></a></div></section>
        </main><footer className="home-footer"><a className="home-brand" href="#top"><span><Activity /></span><b>DermAI <em>Clinic</em></b></a><p>Chăm sóc da liễu bằng chuyên môn, sự thấu hiểu và công nghệ có trách nhiệm.<a className="footer-hotline" href="tel:0352790904"><PhoneCall /> Hotline: 0352 790 904</a></p><small>© 2026 DermAI Clinic.</small></footer><ChatBox openAuth={openAuth} />
    </div>
}
type ChatMessage = { role: "assistant" | "user"; text: string; citations?: { source: string; page: number }[] };
function ChatBox({ openAuth }: { openAuth: () => void }) {
    const [open, setOpen] = useState(false); const [question, setQuestion] = useState(""); const [busy, setBusy] = useState(false); const [messages, setMessages] = useState<ChatMessage[]>([{ role: "assistant", text: "Xin chào! Tôi có thể tra cứu kiến thức chăm sóc da từ thư viện y khoa của phòng khám. Tôi không chẩn đoán hoặc kê đơn thuốc." }]);
    async function send(e: FormEvent) { e.preventDefault(); const value = question.trim(); if (!value || busy) return; setQuestion(""); setMessages(x => [...x, { role: "user", text: value }]); setBusy(true); try { const result = await request<{ answer: string; citations: { source: string; page: number }[]; disclaimer: string }>("/ai/public-chat", undefined, { method: "POST", body: JSON.stringify({ question: value }) }); setMessages(x => [...x, { role: "assistant", text: result.answer, citations: result.citations }]) } catch (x) { setMessages(items => [...items, { role: "assistant", text: (x as Error).message || "Dịch vụ Gemini hiện chưa sẵn sàng." }]) } finally { setBusy(false) } }
    return createPortal(<div className={`chat-widget ${open ? "chat-open" : ""}`}><button type="button" className="chat-launch" aria-expanded={open} aria-label={open ? "Đóng trợ lý DermAI" : "Mở trợ lý DermAI"} onClick={() => setOpen(value => !value)}>{open ? <X /> : <><Sparkles /><span>Tư vấn da liễu</span></>}</button>{open && <section className="chat-panel" aria-label="Trợ lý DermAI"><header><div><span><Activity /></span><div><b>Trợ lý DermAI</b><small>Tra cứu kiến thức · không thay thế bác sĩ</small></div></div><button type="button" aria-label="Đóng hộp chat" onClick={() => setOpen(false)}><X /></button></header><div className="chat-messages">{messages.map((m, i) => <div className={`chat-message ${m.role}`} key={i}><p>{m.text}</p>{m.citations?.map((c, j) => <small key={j}>Nguồn: {c.source} · trang {c.page}</small>)}</div>)}{busy && <div className="chat-message assistant"><p>Đang tra cứu tài liệu…</p></div>}</div><form onSubmit={send}><input value={question} onChange={e => setQuestion(e.target.value)} minLength={3} maxLength={1000} aria-label="Câu hỏi chăm sóc da" placeholder="Nhập ít nhất 3 ký tự…" /><button type="submit" aria-label="Gửi câu hỏi" disabled={busy || question.trim().length < 3}><ArrowRight /></button></form><button type="button" className="chat-book" onClick={openAuth}>Đặt lịch với bác sĩ</button></section>}</div>, document.body)
}
function ForgotPassword({ close }: { close: () => void }) {
    const [step, setStep] = useState<"request" | "reset" | "done">("request"); const [email, setEmail] = useState(""); const [otp, setOtp] = useState(""); const [password, setPassword] = useState(""); const [message, setMessage] = useState(""); const [busy, setBusy] = useState(false);
    async function requestOtp(e: FormEvent) { e.preventDefault(); setBusy(true); setMessage(""); try { const result = await request<{ message: string }>("/auth/forgot-password", undefined, { method: "POST", body: JSON.stringify({ email }) }); setMessage(result.message); setStep("reset") } catch (x) { setMessage((x as Error).message) } finally { setBusy(false) } }
    async function reset(e: FormEvent) { e.preventDefault(); setBusy(true); setMessage(""); try { await request("/auth/reset-password", undefined, { method: "POST", body: JSON.stringify({ email, otp, newPassword: password }) }); setStep("done"); setMessage("Mật khẩu đã được cập nhật thành công.") } catch (x) { setMessage((x as Error).message) } finally { setBusy(false) } }
    return <div className="auth-page"><button className="auth-home" onClick={close}><X /> Quay lại đăng nhập</button><form className="auth-card" onSubmit={step === "request" ? requestOtp : reset}><div className="brand dark"><div className="mark"><ShieldCheck /></div><div><b>Khôi phục</b><span>Tài khoản</span></div></div><h1>{step === "done" ? "Đã đổi mật khẩu" : step === "request" ? "Quên mật khẩu" : "Nhập mã xác nhận"}</h1>{step === "request" && <label>Email tài khoản<input type="email" required value={email} onChange={e => setEmail(e.target.value)} /></label>}{step === "reset" && <><p>Mã OTP đã được gửi đến email nếu tài khoản tồn tại.</p><label>Mã OTP<input inputMode="numeric" pattern="\d{6}" maxLength={6} required value={otp} onChange={e => setOtp(e.target.value.replace(/\D/g, ""))} /></label><label>Mật khẩu mới<input type="password" minLength={10} required value={password} onChange={e => setPassword(e.target.value)} /></label></>}{message && <div className={step === "done" ? "form-message" : "safety-note"}>{message}</div>}{step !== "done" && <button className="primary" disabled={busy}>{busy ? "Đang xử lý…" : step === "request" ? "Gửi mã OTP" : "Đặt lại mật khẩu"}</button>}{step === "done" && <button type="button" className="primary" onClick={close}>Về đăng nhập</button>}</form></div>
}
function Login({ onLogin }: { onLogin: (tokens: Tokens) => void }) {
    const [register, setRegister] = useState(false);
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [fullName, setFullName] = useState("");
    const [phone, setPhone] = useState("");
    const [error, setError] = useState("");
    const [busy, setBusy] = useState(false);
    const [googlePending, setGooglePending] = useState<{ tokens: Tokens; email: string } | null>(null);
    const [verificationPending, setVerificationPending] = useState(false);
    const [verificationOtp, setVerificationOtp] = useState("");
    const [resendCooldown, setResendCooldown] = useState(0);

    useEffect(() => {
        if (resendCooldown <= 0) return;
        const timer = window.setInterval(() => setResendCooldown(value => Math.max(0, value - 1)), 1000);
        return () => window.clearInterval(timer);
    }, [resendCooldown > 0]);

    function tokensOf(result: GoogleLoginResult): Tokens {
        return { accessToken: result.accessToken, refreshToken: result.refreshToken, expiresIn: result.expiresIn, role: result.role };
    }

    async function handleGoogle(result: GoogleLoginResult) {
        const tokens = tokensOf(result);
        setError("");
        // Tài khoản Google mới phải hoàn thiện số điện thoại trước khi vào khu vực bệnh nhân.
        if (result.newAccount) {
            setFullName(result.fullName);
            setGooglePending({ tokens, email: result.email });
            return;
        }
        try {
            await request<Patient>("/patients/me", tokens.accessToken);
            onLogin(tokens);
        } catch (value) {
            if (value instanceof ApiError && value.status === 404) {
                setFullName(result.fullName);
                setGooglePending({ tokens, email: result.email });
            } else {
                setError((value as Error).message);
            }
        }
    }

    async function completeGoogleProfile(event: FormEvent) {
        event.preventDefault();
        if (!googlePending) return;
        setBusy(true);
        setError("");
        try {
            await request("/patients/me", googlePending.tokens.accessToken, {
                method: "POST",
                body: JSON.stringify({ fullName, phone: phone.trim() }),
            });
            onLogin(googlePending.tokens);
        } catch (value) {
            setError((value as Error).message);
        } finally {
            setBusy(false);
        }
    }

    async function submit(event: FormEvent) {
        event.preventDefault();
        setBusy(true);
        setError("");
        try {
            if (register) {
                await request("/auth/register", undefined, { method: "POST", body: JSON.stringify({ email, password }) });
                // The account stays unusable until the owner proves access to this mailbox.
                setVerificationPending(true);
                setResendCooldown(60);
                return;
            }
            const tokens = await request<Tokens>("/auth/login", undefined, { method: "POST", body: JSON.stringify({ email, password }) });
            onLogin(tokens);
        } catch (value) {
            if (value instanceof ApiError && value.code === "EMAIL_NOT_VERIFIED") {
                setRegister(true);
                setVerificationPending(true);
                setError("Email chưa được xác minh. Nhấn gửi lại mã nếu OTP cũ đã hết hạn.");
                return;
            }
            setError((value as Error).message);
        } finally {
            setBusy(false);
        }
    }

    async function confirmVerification(event: FormEvent) {
        event.preventDefault();setBusy(true);setError("");
        try {
            await request("/auth/verification/confirm", undefined, { method: "POST", body: JSON.stringify({ email, otp: verificationOtp }) });
            const tokens = await request<Tokens>("/auth/login", undefined, { method: "POST", body: JSON.stringify({ email, password }) });
            await request("/patients/me", tokens.accessToken, { method: "POST", body: JSON.stringify({ fullName, phone: phone.trim() }) });
            onLogin(tokens);
        } catch (value) {
            setError((value as Error).message);
        } finally { setBusy(false); }
    }

    async function resendVerification() {
        setBusy(true);setError("");
        try {
            await request("/auth/verification/send", undefined, { method: "POST", body: JSON.stringify({ email }) });
            setResendCooldown(60);
            setError("Mã OTP mới đã được gửi. Mã có hiệu lực trong 5 phút.");
        } catch (value) { setError((value as Error).message); }
        finally { setBusy(false); }
    }

    if (googlePending) {
        return <div className="auth-page"><form className="auth-card google-profile-card" onSubmit={completeGoogleProfile}>
            <div className="brand dark"><div className="mark"><Activity /></div><div><b>DermAI</b><span>Clinic</span></div></div>
            <h1>Hoàn thiện hồ sơ</h1>
            <p>Google đã xác thực <b>{googlePending.email}</b>. Vui lòng bổ sung thông tin liên hệ.</p>
            <label>Họ và tên<input value={fullName} onChange={event => setFullName(event.target.value)} required /></label>
            <label>Số điện thoại<input type="tel" inputMode="tel" pattern="[0-9+ .()\\-]{8,20}" value={phone} onChange={event => setPhone(event.target.value)} required placeholder="Ví dụ: 0352790904" /></label>
            {error && <div className="error">{error}</div>}
            <button className="primary" disabled={busy}>{busy ? "Đang tạo hồ sơ..." : "Hoàn tất đăng nhập"}</button>
            <button type="button" className="auth-switch" onClick={() => { setGooglePending(null); setError(""); }}>Dùng cách đăng nhập khác</button>
        </form></div>;
    }

    if (verificationPending) {
        return <div className="auth-page"><form className="auth-card email-verification-card" onSubmit={confirmVerification}>
            <div className="brand dark"><div className="mark"><ShieldCheck /></div><div><b>DermAI</b><span>Xác minh email</span></div></div>
            <h1>Nhập mã OTP</h1>
            <p>Mã gồm 6 số đã được gửi đến <b>{email}</b> và có hiệu lực trong 5 phút.</p>
            <label>Họ và tên<input value={fullName} onChange={event => setFullName(event.target.value)} required /></label>
            <label>Số điện thoại<input type="tel" inputMode="tel" pattern="[0-9+ .()\\-]{8,20}" value={phone} onChange={event => setPhone(event.target.value)} required placeholder="Ví dụ: 0352790904" /></label>
            <label>Mã OTP<input className="otp-input" inputMode="numeric" autoComplete="one-time-code" pattern="\d{6}" maxLength={6} value={verificationOtp} onChange={event => setVerificationOtp(event.target.value.replace(/\D/g, ""))} required /></label>
            {error && <div className="form-message">{error}</div>}
            <button className="primary" disabled={busy || verificationOtp.length !== 6}>{busy ? "Đang xác minh..." : "Xác minh và hoàn tất"}</button>
            <button type="button" className="auth-switch" disabled={busy || resendCooldown > 0} onClick={resendVerification}>{resendCooldown > 0 ? `Gửi lại mã sau ${resendCooldown}s` : "Gửi lại mã OTP"}</button>
            <button type="button" className="auth-switch" onClick={() => { setVerificationPending(false);setRegister(false);setError(""); }}>Quay lại đăng nhập</button>
        </form></div>;
    }

    return <div className="auth-page"><form className="auth-card" onSubmit={submit}>
        <div className="brand dark"><div className="mark"><Activity /></div><div><b>DermAI</b><span>Clinic</span></div></div>
        <h1>{register ? "Đăng ký bệnh nhân" : "Đăng nhập hệ thống"}</h1>
        {register && <><label>Họ và tên<input value={fullName} onChange={event => setFullName(event.target.value)} required /></label><label>Số điện thoại<input type="tel" inputMode="tel" pattern="[0-9+ .()\\-]{8,20}" value={phone} onChange={event => setPhone(event.target.value)} required placeholder="Ví dụ: 0352790904" /></label></>}
        <label>Email<input type="email" value={email} onChange={event => setEmail(event.target.value)} required /></label>
        <label>Mật khẩu<input type="password" minLength={10} value={password} onChange={event => setPassword(event.target.value)} required /></label>
        {error && <div className="error">{error}</div>}
        <button className="primary" disabled={busy}>{busy ? "Đang xử lý..." : register ? "Tạo tài khoản" : "Đăng nhập"}</button>
        <GoogleSignIn onAuthenticated={handleGoogle} />
        <button type="button" className="auth-switch" onClick={() => { setRegister(!register); setError(""); }}>{register ? "Đã có tài khoản? Đăng nhập" : "Chưa có tài khoản? Đăng ký Patient"}</button>
        <div className="safety-note"><ShieldCheck /></div>
    </form></div>;
}
function Dashboard({ session, logout }: { session: Tokens; logout: () => void }) {
    const [tab, setTab] = useState<"profile" | "appointments" | "records" | "ai">("profile"); const [patient, setPatient] = useState<Patient | null>(null); const [doctor, setDoctor] = useState<Doctor | null>(null); const [appointments, setAppointments] = useState<Appointment[]>([]); const [records, setRecords] = useState<MedicalRecord[]>([]); const [prescriptions, setPrescriptions] = useState<Prescription[]>([]); const [patients, setPatients] = useState<Record<string, Patient>>({}); const [work, setWork] = useState<WorkSchedule[]>([]); const [leave, setLeave] = useState<LeavePeriod[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState("");
    async function loadDoctor() {
        const d = await request<Doctor>("/doctors/me", session.accessToken); const schedule = await request<{ workSchedules: WorkSchedule[]; leavePeriods: LeavePeriod[] }>("/doctors/me/schedule", session.accessToken);
        const from = new Date(); from.setHours(0, 0, 0, 0); const to = new Date(from); to.setFullYear(to.getFullYear() + 1);
        const [a, r] = await Promise.all([request<Appointment[]>(`/appointments/doctor/mine?from=${encodeURIComponent(from.toISOString())}&to=${encodeURIComponent(to.toISOString())}`, session.accessToken), request<MedicalRecord[]>("/medical-records/doctor/mine", session.accessToken)]);
        const unique = [...new Set(a.map(x => x.patientId))]; const entries = await Promise.all(unique.map(async id => [id, await request<Patient>(`/patients/${id}`, session.accessToken)] as const));
        setDoctor(d); setWork(schedule.workSchedules); setLeave(schedule.leavePeriods); setAppointments(a); setRecords(r); setPatients(Object.fromEntries(entries));
    }
    useEffect(() => { let live = true; (async () => { try { if (session.role === "PATIENT") { const [p, a, r, rx] = await Promise.all([request<Patient>("/patients/me", session.accessToken), request<Appointment[]>("/appointments/mine", session.accessToken), request<MedicalRecord[]>("/medical-records/mine", session.accessToken), request<Prescription[]>("/prescriptions/mine", session.accessToken)]); if (live) { setPatient(p); setAppointments(a); setRecords(r); setPrescriptions(rx) } } else if (session.role === "DOCTOR" && live) await loadDoctor() } catch (x) { if (live) setError((x as Error).message) } finally { if (live) setLoading(false) } })(); return () => { live = false } }, [session]);
    useEffect(() => { if (session.role !== "PATIENT") return; const refresh = () => request<Appointment[]>("/appointments/mine", session.accessToken).then(setAppointments).catch(() => undefined); window.addEventListener("appointments-changed", refresh); return () => window.removeEventListener("appointments-changed", refresh) }, [session]);
    async function transition(id: string, action: "start" | "complete") { setError(""); try { await request(`/appointments/${id}/${action}`, session.accessToken, { method: "POST" }); await loadDoctor() } catch (x) { setError((x as Error).message) } }
    async function requireFollowUp(id: string, reason: string, notBefore: string) { setError(""); try { await request(`/appointments/${id}/require-follow-up`, session.accessToken, { method: "POST", body: JSON.stringify({ reason, notBefore }) }); await loadDoctor() } catch (x) { setError((x as Error).message); throw x } }
    const labels = session.role === "ADMIN" ? ["Bệnh nhân", "Bác sĩ", "Tài khoản"] : session.role === "RECEPTIONIST" ? ["Bệnh nhân", "Yêu cầu đặt lịch", "Lịch đã nhận"] : ["Hồ sơ", "Lịch khám", "Hồ sơ y khoa"];
    const roleName = session.role === "PATIENT" ? "Bệnh nhân" : session.role === "DOCTOR" ? "Bác sĩ" : session.role === "RECEPTIONIST" ? "Lễ tân" : "Quản trị viên";
    const roleSubtitle = session.role === "PATIENT" ? "Đặt lịch, theo dõi hồ sơ và kiểm tra da bằng AI" : session.role === "DOCTOR" ? "Quản lý lịch khám và hồ sơ chuyên môn" : session.role === "RECEPTIONIST" ? "Điều phối bệnh nhân và lịch hẹn trong ngày" : "Theo dõi hoạt động và quản trị hệ thống";
    const greeting = patient ? `Xin chào, ${patient.fullName}` : doctor ? `BS. ${doctor.fullName}` : "DermAI Clinic";
    const today = new Intl.DateTimeFormat("vi-VN", { weekday: "long", day: "2-digit", month: "long", year: "numeric" }).format(new Date());
    return <div className={`shell role-${session.role.toLowerCase()}`}>
        <aside className="app-sidebar">
            <div className="brand"><div className="mark"><Activity /></div><div><b>DermAI</b><span>Clinic</span></div></div>
            <div className="workspace-role"><small>KHÔNG GIAN LÀM VIỆC</small><b>{roleName}</b></div>
            <nav aria-label={`Điều hướng ${roleName}`}>
                <button aria-current={tab === "profile" ? "page" : undefined} className={tab === "profile" ? "active" : ""} onClick={() => setTab("profile")}><UserRound /><span>{labels[0]}</span></button>
                <button aria-current={tab === "appointments" ? "page" : undefined} className={tab === "appointments" ? "active" : ""} onClick={() => setTab("appointments")}><CalendarDays /><span>{labels[1]}</span></button>
                <button aria-current={tab === "records" ? "page" : undefined} className={tab === "records" ? "active" : ""} onClick={() => setTab("records")}><Stethoscope /><span>{labels[2]}</span></button>
                {session.role === "PATIENT" && <button aria-current={tab === "ai" ? "page" : undefined} className={tab === "ai" ? "active" : ""} onClick={() => setTab("ai")}><BrainCircuit /><span>Kiểm tra da AI</span></button>}
            </nav>
            <div className="sidebar-footer"><span className="sidebar-avatar">{roleName.slice(0, 1)}</span><div><b>{roleName}</b><small>Phiên làm việc an toàn</small></div></div>
            <button className="logout" onClick={logout}><LogOut /><span>Đăng xuất</span></button>
        </aside>
        <main className="app-main">
            <header className="app-topbar"><div><span className="app-eyebrow">CỔNG {roleName.toUpperCase()}</span><h1>{greeting}</h1><p>{roleSubtitle}</p></div><div className="app-today"><i /><span><small>Hôm nay</small><b>{today}</b></span></div></header>
            {loading && <State text="Đang tải dữ liệu từ hệ thống..." />}
            {error && <State text={error} error />}
            {!loading && !error && session.role === "ADMIN" && <AdminPanel token={session.accessToken} tab={tab} />}
            {!loading && !error && session.role === "RECEPTIONIST" && <ReceptionPanel token={session.accessToken} tab={tab} />}
            {!loading && !error && session.role === "PATIENT" && patient && tab === "profile" && <PatientProfile token={session.accessToken} patient={patient} appointments={appointments} saved={setPatient} />}
            {!loading && !error && session.role === "PATIENT" && patient && tab === "appointments" && <PatientAppointments token={session.accessToken} patient={patient} appointments={appointments} changed={setAppointments} />}
            {!loading && !error && session.role === "PATIENT" && tab === "records" && <><RecordList records={records} patients={{}} /><PrescriptionList prescriptions={prescriptions} token={session.accessToken} /></>}
            {!loading && !error && session.role === "PATIENT" && patient && tab === "ai" && <PatientAiScreen token={session.accessToken} patient={patient} openBooking={() => setTab("appointments")} />}
            {!loading && !error && session.role === "DOCTOR" && doctor && tab === "profile" && <DoctorProfile token={session.accessToken} doctor={doctor} work={work} leave={leave} saved={setDoctor} />}
            {!loading && !error && session.role === "DOCTOR" && doctor && tab === "appointments" && <DoctorView token={session.accessToken} doctor={doctor} appointments={appointments} patients={patients} work={work} leave={leave} transition={transition} requireFollowUp={requireFollowUp} />}
            {!loading && !error && session.role === "DOCTOR" && tab === "records" && <RecordList records={records} patients={patients} />}
        </main>
    </div>;
}
createRoot(document.getElementById("root")!).render(<App />);

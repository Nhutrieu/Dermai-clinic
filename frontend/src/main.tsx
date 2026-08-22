import { FormEvent, lazy, Suspense, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { createPortal } from "react-dom";
import { Activity, ArrowRight, ShieldCheck, Sparkles, X } from "lucide-react";
import { ApiError, configureAccessTokenRecovery, request, requestBlob } from "./core/api";
import { subscribeRealtime } from "./core/realtime";
import type { AccountProfile, Appointment, Doctor, LeavePeriod, MedicalRecord, Patient, Prescription, Tokens, WorkSchedule } from "./core/types";
import { RecordList } from "./components/Records";
import { State } from "./components/Ui";
import AppHeader from "./components/AppHeader";
import AppFooter from "./components/AppFooter";
import PasswordRequirements from "./components/PasswordRequirements";
import { authErrorMessage, isPasswordValid, passwordValidationMessage, PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH } from "./core/passwordPolicy";
import { NAVIGATION_BY_ROLE, ROLE_NAMES } from "./core/appNavigation";
import "./styles/design-system.css";
import "./styles/global.css";
import "./styles/navigation.css";
import "./styles/clinic-address.css";
import "./styles/app-motion.css";
import "./styles/app-chrome.css";
import "./styles/authenticated-states.css";
import "./styles/workspace-polish.css";
import "./styles/record-filters.css";
import "./styles/hotline.css";
import "./styles/chat.css";
import "./styles/support-assignment.css";
import "./styles/support-ai.css";
import "./styles/admin-analytics.css";
import GoogleSignIn, { type GoogleLoginResult } from "./features/auth/GoogleSignIn";
import HomePage from "./components/v2/homepage/HomepageV2";

const PublicRoute = lazy(() => import("./routes/PublicRoute"));
const PatientRoute = lazy(() => import("./routes/PatientRoute"));
const DoctorRoute = lazy(() => import("./routes/DoctorRoute"));
const ReceptionistRoute = lazy(() => import("./routes/ReceptionistRoute"));
const AdminRoute = lazy(() => import("./routes/AdminRoute"));
const AdminPanel = lazy(() => import("./features/admin/AdminPanel"));
const ReceptionWorkspace = lazy(() => import("./features/reception/ReceptionWorkspace"));
const PatientDashboard = lazy(() => import("./features/patient/PatientDashboard"));
const PatientAppointments = lazy(() => import("./features/patient/PatientAppointments"));
const PatientMedicalRecords = lazy(() => import("./features/patient/PatientMedicalRecords"));
const DoctorProfile = lazy(() => import("./features/doctor/DoctorProfileScreen"));
const DoctorView = lazy(() => import("./features/doctor/DoctorView"));
const ReceptionHotlineBooking = lazy(() => import("./features/reception/HotlineBooking"));
const PatientNotifications = lazy(() => import("./features/patient/PatientNotifications"));
const PatientAiScreen = lazy(() => import("./features/patient/PatientAiScreen"));
const SupportChat = lazy(() => import("./features/support/SupportChat"));
const ReceptionistAccountDialog = lazy(() => import("./features/reception/ReceptionistAccountDialog"));
const PatientAccountDialog = lazy(() => import("./features/patient/PatientAccountDialog"));

function App() {
    const [session, setSession] = useState<Tokens | null>(() => { try { return JSON.parse(sessionStorage.getItem("dermai-session") || "null") } catch { return null } });
    const [authOpen, setAuthOpen] = useState(false); const [forgotOpen, setForgotOpen] = useState(false);
    const [authNotice, setAuthNotice] = useState("");
    const [sessionRecoveryReady, setSessionRecoveryReady] = useState(false);

    useEffect(() => {
        if (!session) {
            setSessionRecoveryReady(false);
            return configureAccessTokenRecovery(null);
        }

        // The refresh token is rotated by the backend. Always read the latest
        // stored session so concurrent requests cannot reuse an older token.
        const dispose = configureAccessTokenRecovery(async failedAccessToken => {
            let current: Tokens | null = null;
            try { current = JSON.parse(sessionStorage.getItem("dermai-session") || "null") as Tokens | null } catch { current = null }

            if (!current?.refreshToken) {
                sessionStorage.removeItem("dermai-session");
                setSession(null);
                setForgotOpen(false);
                setAuthOpen(true);
                setAuthNotice("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.");
                return null;
            }

            // Another request may already have refreshed and stored a newer token.
            if (current.accessToken !== failedAccessToken) return current.accessToken;

            try {
                const renewed = await request<Tokens>("/auth/refresh", undefined, {
                    method: "POST",
                    body: JSON.stringify({ refreshToken: current.refreshToken }),
                });
                sessionStorage.setItem("dermai-session", JSON.stringify(renewed));
                setSession(renewed);
                return renewed.accessToken;
            } catch {
                sessionStorage.removeItem("dermai-session");
                setSession(null);
                setForgotOpen(false);
                setAuthOpen(true);
                setAuthNotice("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.");
                return null;
            }
        });

        setSessionRecoveryReady(true);
        return dispose;
    }, [session?.accessToken, session?.refreshToken]);

    useEffect(() => subscribeRealtime(event => {
        if (event.type === "DOCTOR_PROFILE_UPDATED") window.dispatchEvent(new CustomEvent("doctor-profiles-changed", { detail: event }));
    }, { path: "/api/v1/doctors/ws/profile" }), []);
    if (!session) return <Suspense fallback={<State text="Đang tải giao diện..." />}><PublicRoute>{forgotOpen ? <ForgotPassword close={() => setForgotOpen(false)} /> : authOpen ? <><button className="auth-home" onClick={() => setAuthOpen(false)}><X /> Về trang chủ</button><Login notice={authNotice} onForgotPassword={() => setForgotOpen(true)} onLogin={tokens => { sessionStorage.setItem("dermai-session", JSON.stringify(tokens)); setAuthNotice(""); setSession(tokens) }} /></> : <HomePage openAuth={() => { setAuthNotice(""); setAuthOpen(true) }} chat={<ChatBox openAuth={() => { setAuthNotice(""); setAuthOpen(true) }} />} />}</PublicRoute></Suspense>;
    if (!sessionRecoveryReady) return <State text="Đang khôi phục phiên đăng nhập..." />;

    function logout() {
        // Revoke the refresh token server-side, then clear the local session immediately.
        void request("/auth/logout", undefined, { method: "POST", body: JSON.stringify({ refreshToken: session!.refreshToken }) }).catch(() => undefined);
        sessionStorage.removeItem("dermai-session");
        setAuthNotice("");
        setSession(null);
    }

    const workspace = <><Dashboard session={session} logout={logout} />{session.role === "PATIENT" && <PatientNotifications session={session} />}{session.role === "RECEPTIONIST" && <ReceptionHotlineBooking session={session} />}{["PATIENT", "RECEPTIONIST", "ADMIN"].includes(session.role) && <SupportChat session={session} />}</>;
    const Route = session.role === "PATIENT" ? PatientRoute : session.role === "DOCTOR" ? DoctorRoute : session.role === "RECEPTIONIST" ? ReceptionistRoute : AdminRoute;
    return <Suspense fallback={<State text="Đang mở không gian làm việc..." />}><Route>{workspace}</Route></Suspense>;
}
type ChatMessage = { role: "assistant" | "user"; text: string; citations?: { source: string; page: number }[] };
function ChatBox({ openAuth }: { openAuth: () => void }) {
    const [open, setOpen] = useState(false); const [question, setQuestion] = useState(""); const [busy, setBusy] = useState(false); const [messages, setMessages] = useState<ChatMessage[]>([{ role: "assistant", text: "Xin chào! Tôi có thể tra cứu kiến thức chăm sóc da từ thư viện y khoa của phòng khám. Tôi không chẩn đoán hoặc kê đơn thuốc." }]);
    async function send(e: FormEvent) { e.preventDefault(); const value = question.trim(); if (!value || busy) return; setQuestion(""); setMessages(x => [...x, { role: "user", text: value }]); setBusy(true); try { const result = await request<{ answer: string; citations: { source: string; page: number }[]; disclaimer: string }>("/ai/public-chat", undefined, { method: "POST", body: JSON.stringify({ question: value }) }); setMessages(x => [...x, { role: "assistant", text: result.answer, citations: result.citations }]) } catch (x) { setMessages(items => [...items, { role: "assistant", text: (x as Error).message || "Dịch vụ Gemini hiện chưa sẵn sàng." }]) } finally { setBusy(false) } }
    return createPortal(<div className={`chat-widget ${open ? "chat-open" : ""}`}><button type="button" className="chat-launch" aria-expanded={open} aria-label={open ? "Đóng trợ lý Derm" : "Mở trợ lý Derm"} onClick={() => setOpen(value => !value)}>{open ? <X /> : <><Sparkles /><span>Tư vấn da liễu</span></>}</button>{open && <section className="chat-panel" aria-label="Trợ lý Derm"><header><div><span><Activity /></span><div><b>Trợ lý Derm</b><small>Tra cứu kiến thức · không thay thế bác sĩ</small></div></div><button type="button" aria-label="Đóng hộp chat" onClick={() => setOpen(false)}><X /></button></header><div className="chat-messages">{messages.map((m, i) => <div className={`chat-message ${m.role}`} key={i}><p>{m.text}</p>{m.citations?.map((c, j) => <small key={j}>Nguồn: {c.source} · trang {c.page}</small>)}</div>)}{busy && <div className="chat-message assistant"><p>Đang tra cứu tài liệu…</p></div>}</div><form onSubmit={send}><input value={question} onChange={e => setQuestion(e.target.value)} minLength={3} maxLength={1000} aria-label="Câu hỏi chăm sóc da" placeholder="Nhập ít nhất 3 ký tự…" /><button type="submit" aria-label="Gửi câu hỏi" disabled={busy || question.trim().length < 3}><ArrowRight /></button></form><button type="button" className="chat-book" onClick={openAuth}>Đặt lịch với bác sĩ</button></section>}</div>, document.body)
}
function ForgotPassword({ close }: { close: () => void }) {
    const [step, setStep] = useState<"request" | "reset" | "done">("request"); const [email, setEmail] = useState(""); const [otp, setOtp] = useState(""); const [password, setPassword] = useState(""); const [message, setMessage] = useState(""); const [busy, setBusy] = useState(false);
    async function requestOtp(e: FormEvent) { e.preventDefault(); setBusy(true); setMessage(""); try { const result = await request<{ message: string }>("/auth/forgot-password", undefined, { method: "POST", body: JSON.stringify({ email }) }); setMessage(result.message); setStep("reset") } catch (x) { setMessage(authErrorMessage(x)) } finally { setBusy(false) } }
    async function reset(e: FormEvent) { e.preventDefault(); if (!isPasswordValid(password)) { setMessage(`Mật khẩu phải có từ ${PASSWORD_MIN_LENGTH} đến ${PASSWORD_MAX_LENGTH} ký tự.`); return; } setBusy(true); setMessage(""); try { await request("/auth/reset-password", undefined, { method: "POST", body: JSON.stringify({ email, otp, newPassword: password }) }); setStep("done"); setMessage("Mật khẩu đã được cập nhật thành công.") } catch (x) { setMessage(authErrorMessage(x)) } finally { setBusy(false) } }
    return <div className="auth-page"><button className="auth-home" onClick={close}><X /> Quay lại đăng nhập</button><form className="auth-card" onSubmit={step === "request" ? requestOtp : reset}><div className="brand dark"><div className="mark"><ShieldCheck /></div><div><b>Khôi phục</b><span>Tài khoản</span></div></div><h1>{step === "done" ? "Đã đổi mật khẩu" : step === "request" ? "Quên mật khẩu" : "Nhập mã xác nhận"}</h1>{step === "request" && <label>Email tài khoản<input type="email" required value={email} onChange={e => setEmail(e.target.value)} /></label>}{step === "reset" && <><p>Mã OTP đã được gửi đến email nếu tài khoản tồn tại.</p><label>Mã OTP<input inputMode="numeric" pattern="\d{6}" maxLength={6} required value={otp} onChange={e => setOtp(e.target.value.replace(/\D/g, ""))} /></label><label>Mật khẩu mới<input type="password" minLength={PASSWORD_MIN_LENGTH} maxLength={PASSWORD_MAX_LENGTH} required aria-describedby="reset-password-requirements" value={password} onChange={e => setPassword(e.target.value)} onInput={e => e.currentTarget.setCustomValidity("")} onInvalid={e => e.currentTarget.setCustomValidity(passwordValidationMessage(e.currentTarget.value))} /><PasswordRequirements id="reset-password-requirements" password={password} /></label></>}{message && <div className={step === "done" ? "form-message" : "safety-note"} role={step === "done" ? "status" : "alert"}>{message}</div>}{step !== "done" && <button className="primary" disabled={busy || (step === "reset" && !isPasswordValid(password))}>{busy ? "Đang xử lý…" : step === "request" ? "Gửi mã OTP" : "Đặt lại mật khẩu"}</button>}{step === "done" && <button type="button" className="primary" onClick={close}>Về đăng nhập</button>}</form></div>
}
function Login({ onLogin, onForgotPassword, notice = "" }: { onLogin: (tokens: Tokens) => void; onForgotPassword: () => void; notice?: string }) {
    const [register, setRegister] = useState(false);
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [fullName, setFullName] = useState("");
    const [phone, setPhone] = useState("");
    const [error, setError] = useState("");
    const [busy, setBusy] = useState(false);
    const [profilePending, setProfilePending] = useState<{ tokens: Tokens; email: string; provider: "email" | "google" } | null>(null);
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

    function normalizedPatientPhone() {
        let value = phone.replace(/\D/g, "");
        if (value.startsWith("0084")) value = `0${value.slice(4)}`;
        else if (value.startsWith("84")) value = `0${value.slice(2)}`;
        return value;
    }

    function validPatientPhone(value: string) {
        return /^0\d{8,10}$/.test(value);
    }

    async function continuePatientLogin(tokens: Tokens, accountEmail: string, suggestedName = "", provider: "email" | "google" = "email") {
        if (tokens.role !== "PATIENT") {
            onLogin(tokens);
            return;
        }
        try {
            await request<Patient>("/patients/me", tokens.accessToken);
            onLogin(tokens);
        } catch (value) {
            if (value instanceof ApiError && value.status === 404) {
                if (suggestedName) setFullName(suggestedName);
                setProfilePending({ tokens, email: accountEmail, provider });
                return;
            }
            throw value;
        }
    }

    async function handleGoogle(result: GoogleLoginResult) {
        const tokens = tokensOf(result);
        setError("");
        // Tài khoản Google mới phải hoàn thiện số điện thoại trước khi vào khu vực bệnh nhân.
        if (result.newAccount) {
            setFullName(result.fullName);
            setProfilePending({ tokens, email: result.email, provider: "google" });
            return;
        }
        try {
            await continuePatientLogin(tokens, result.email, result.fullName, "google");
        } catch (value) {
            setError(authErrorMessage(value));
        }
    }

    async function completePatientProfile(event: FormEvent) {
        event.preventDefault();
        if (!profilePending) return;
        const normalizedPhone = normalizedPatientPhone();
        if (!validPatientPhone(normalizedPhone)) {
            setError("Số điện thoại phải có từ 9 đến 11 chữ số và bắt đầu bằng 0.");
            return;
        }
        setBusy(true);
        setError("");
        try {
            await request("/patients/me", profilePending.tokens.accessToken, {
                method: "POST",
                body: JSON.stringify({ fullName, phone: normalizedPhone }),
            });
            onLogin(profilePending.tokens);
        } catch (value) {
            setError(authErrorMessage(value));
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
            await continuePatientLogin(tokens, email);
        } catch (value) {
            if (value instanceof ApiError && value.code === "EMAIL_NOT_VERIFIED") {
                setRegister(true);
                setVerificationPending(true);
                setError("Email chưa được xác minh. Nhấn gửi lại mã nếu OTP cũ đã hết hạn.");
                return;
            }
            setError(authErrorMessage(value));
        } finally {
            setBusy(false);
        }
    }

    async function confirmVerification(event: FormEvent) {
        event.preventDefault();setBusy(true);setError("");
        try {
            const normalizedPhone = normalizedPatientPhone();
            if (!validPatientPhone(normalizedPhone)) {
                setError("Số điện thoại phải có từ 9 đến 11 chữ số và bắt đầu bằng 0.");
                return;
            }
            await request("/auth/verification/confirm", undefined, { method: "POST", body: JSON.stringify({ email, otp: verificationOtp }) });
            const tokens = await request<Tokens>("/auth/login", undefined, { method: "POST", body: JSON.stringify({ email, password }) });
            await request("/patients/me", tokens.accessToken, { method: "POST", body: JSON.stringify({ fullName, phone: normalizedPhone }) });
            onLogin(tokens);
        } catch (value) {
            setError(authErrorMessage(value));
        } finally { setBusy(false); }
    }

    async function resendVerification() {
        setBusy(true);setError("");
        try {
            await request("/auth/verification/send", undefined, { method: "POST", body: JSON.stringify({ email }) });
            setResendCooldown(60);
            setError("Mã OTP mới đã được gửi. Mã có hiệu lực trong 5 phút.");
        } catch (value) { setError(authErrorMessage(value)); }
        finally { setBusy(false); }
    }

    if (profilePending) {
        return <div className="auth-page"><form className="auth-card google-profile-card" onSubmit={completePatientProfile}>
            <div className="brand dark"><div className="mark"><Activity /></div><div><b>Derm</b><span>Clinic</span></div></div>
            <h1>Hoàn thiện hồ sơ</h1>
            <p>{profilePending.provider === "google" ? "Google đã xác thực" : "Tài khoản đã xác thực"} <b>{profilePending.email}</b>. Vui lòng bổ sung thông tin liên hệ.</p>
            <label>Họ và tên<input value={fullName} onChange={event => setFullName(event.target.value)} required /></label>
            <label>Số điện thoại<input type="tel" inputMode="tel" pattern="[0-9+ .()\\-]{8,20}" value={phone} onChange={event => setPhone(event.target.value)} required placeholder="Ví dụ: 0352790904" /></label>
            {error && <div className="error">{error}</div>}
            <button className="primary" disabled={busy}>{busy ? "Đang tạo hồ sơ..." : "Hoàn tất đăng nhập"}</button>
            <button type="button" className="auth-switch" onClick={() => { setProfilePending(null); setError(""); }}>Dùng cách đăng nhập khác</button>
        </form></div>;
    }

    if (verificationPending) {
        return <div className="auth-page"><form className="auth-card email-verification-card" onSubmit={confirmVerification}>
            <div className="brand dark"><div className="mark"><ShieldCheck /></div><div><b>Derm</b><span>Xác minh email</span></div></div>
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
        <div className="brand dark"><div className="mark"><Activity /></div><div><b>Derm</b><span>Clinic</span></div></div>
        <h1>{register ? "Đăng ký bệnh nhân" : "Đăng nhập hệ thống"}</h1>
        {notice && !register && <div className="auth-session-notice" role="status"><ShieldCheck /> <span>{notice}</span></div>}
        {register && <><label>Họ và tên<input value={fullName} onChange={event => setFullName(event.target.value)} required /></label><label>Số điện thoại<input type="tel" inputMode="tel" pattern="[0-9+ .()\\-]{8,20}" value={phone} onChange={event => setPhone(event.target.value)} required placeholder="Ví dụ: 0352790904" /></label></>}
        <label>Email<input type="email" value={email} onChange={event => setEmail(event.target.value)} required /></label>
        <label>Mật khẩu<input type="password" minLength={PASSWORD_MIN_LENGTH} maxLength={PASSWORD_MAX_LENGTH} aria-describedby={register ? "register-password-requirements" : undefined} value={password} onChange={event => setPassword(event.target.value)} onInput={event => event.currentTarget.setCustomValidity("")} onInvalid={event => event.currentTarget.setCustomValidity(passwordValidationMessage(event.currentTarget.value))} required />{register && <PasswordRequirements id="register-password-requirements" password={password} />}</label>
        {!register && <button type="button" className="auth-forgot-link" onClick={onForgotPassword}>Quên mật khẩu?</button>}
        {error && <div className="error" role="alert">{error}</div>}
        <button className="primary" disabled={busy || (register && !isPasswordValid(password))}>{busy ? "Đang xử lý..." : register ? "Tạo tài khoản" : "Đăng nhập"}</button>
        <GoogleSignIn onAuthenticated={handleGoogle} />
        <button type="button" className="auth-switch" onClick={() => { setRegister(!register); setError(""); }}>{register ? "Đã có tài khoản? Đăng nhập" : "Chưa có tài khoản? Đăng ký Patient"}</button>
        <div className="safety-note"><ShieldCheck /></div>
    </form></div>;
}
function Dashboard({ session, logout }: { session: Tokens; logout: () => void }) {
    const [tab, setTab] = useState<"profile" | "appointments" | "records" | "ai">("profile"); const [patient, setPatient] = useState<Patient | null>(null); const [doctor, setDoctor] = useState<Doctor | null>(null); const [appointments, setAppointments] = useState<Appointment[]>([]); const [records, setRecords] = useState<MedicalRecord[]>([]); const [prescriptions, setPrescriptions] = useState<Prescription[]>([]); const [patients, setPatients] = useState<Record<string, Patient>>({}); const [work, setWork] = useState<WorkSchedule[]>([]); const [leave, setLeave] = useState<LeavePeriod[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState("");
    const [patientResourceState, setPatientResourceState] = useState({
        appointments: { loading: true, error: "" },
        records: { loading: true, error: "" },
        prescriptions: { loading: true, error: "" },
    });
    const [accountProfile, setAccountProfile] = useState<AccountProfile | null>(null);
    const [accountAvatarSrc, setAccountAvatarSrc] = useState("");
    const [accountDialogOpen, setAccountDialogOpen] = useState(false);
    const accountAvatarObjectUrl = useRef<string | null>(null);

    function replaceAccountAvatar(next: string) {
        if (accountAvatarObjectUrl.current) URL.revokeObjectURL(accountAvatarObjectUrl.current);
        accountAvatarObjectUrl.current = next || null;
        setAccountAvatarSrc(next);
    }

    async function loadAccountAvatar() {
        const blob = await requestBlob("/auth/me/avatar", session.accessToken);
        replaceAccountAvatar(URL.createObjectURL(blob));
    }

    useEffect(() => {
        if (!new Set(["PATIENT", "RECEPTIONIST", "ADMIN"]).has(session.role)) return;
        let active = true;

        request<AccountProfile>("/auth/me", session.accessToken)
            .then(async profile => {
                if (!active) return;
                setAccountProfile(profile);
                if (!profile.hasAvatar) return;
                const blob = await requestBlob("/auth/me/avatar", session.accessToken);
                const source = URL.createObjectURL(blob);
                if (!active) {
                    URL.revokeObjectURL(source);
                    return;
                }
                replaceAccountAvatar(source);
            })
            .catch(() => {
                // Account details stay secondary; operational screens remain usable if this request fails.
            });

        return () => {
            active = false;
            if (accountAvatarObjectUrl.current) URL.revokeObjectURL(accountAvatarObjectUrl.current);
            accountAvatarObjectUrl.current = null;
        };
    }, [session.accessToken, session.role]);
    async function loadDoctor() {
        const d = await request<Doctor>("/doctors/me", session.accessToken); const schedule = await request<{ workSchedules: WorkSchedule[]; leavePeriods: LeavePeriod[] }>("/doctors/me/schedule", session.accessToken);
        // Include recent history so a forgotten IN_PROGRESS visit remains visible to the doctor.
        const from = new Date(); from.setDate(from.getDate() - 90); from.setHours(0, 0, 0, 0); const to = new Date(); to.setFullYear(to.getFullYear() + 1);
        const [a, r] = await Promise.all([request<Appointment[]>(`/appointments/doctor/mine?from=${encodeURIComponent(from.toISOString())}&to=${encodeURIComponent(to.toISOString())}`, session.accessToken), request<MedicalRecord[]>("/medical-records/doctor/mine", session.accessToken)]);
        const unique = [...new Set(a.map(x => x.patientId))]; const entries = await Promise.all(unique.map(async id => [id, await request<Patient>(`/patients/${id}`, session.accessToken)] as const));
        setDoctor(d); setWork(schedule.workSchedules); setLeave(schedule.leavePeriods); setAppointments(a); setRecords(r); setPatients(Object.fromEntries(entries));
    }
    useEffect(() => {
        let live = true;
        setLoading(true);
        setError("");

        if (session.role === "PATIENT") {
            setPatientResourceState({
                appointments: { loading: true, error: "" },
                records: { loading: true, error: "" },
                prescriptions: { loading: true, error: "" },
            });

            // Hồ sơ là dữ liệu thiết yếu để mở Dashboard. Các nguồn còn lại tải độc lập
            // để một dịch vụ lỗi không làm trắng toàn bộ màn hình bệnh nhân.
            request<Patient>("/patients/me", session.accessToken)
                .then(value => { if (live) setPatient(value) })
                .catch(cause => {
                    if (!live) return;
                    setError(cause instanceof ApiError && cause.status === 401
                        ? "Phiên đăng nhập đã hết hạn. Vui lòng đăng xuất và đăng nhập lại."
                        : (cause as Error).message);
                })
                .finally(() => { if (live) setLoading(false) });

            request<Appointment[]>("/appointments/mine", session.accessToken)
                .then(value => { if (live) setAppointments(value) })
                .catch(cause => {
                    if (live) setPatientResourceState(current => ({
                        ...current,
                        appointments: { loading: false, error: (cause as Error).message },
                    }));
                })
                .finally(() => {
                    if (live) setPatientResourceState(current => ({
                        ...current,
                        appointments: { ...current.appointments, loading: false },
                    }));
                });

            request<MedicalRecord[]>("/medical-records/mine", session.accessToken)
                .then(value => { if (live) setRecords(value) })
                .catch(cause => {
                    if (live) setPatientResourceState(current => ({
                        ...current,
                        records: { loading: false, error: (cause as Error).message },
                    }));
                })
                .finally(() => {
                    if (live) setPatientResourceState(current => ({
                        ...current,
                        records: { ...current.records, loading: false },
                    }));
                });

            request<Prescription[]>("/prescriptions/mine", session.accessToken)
                .then(value => { if (live) setPrescriptions(value) })
                .catch(cause => {
                    if (live) setPatientResourceState(current => ({
                        ...current,
                        prescriptions: { loading: false, error: (cause as Error).message },
                    }));
                })
                .finally(() => {
                    if (live) setPatientResourceState(current => ({
                        ...current,
                        prescriptions: { ...current.prescriptions, loading: false },
                    }));
                });
        } else {
            (async () => {
                try {
                    if (session.role === "DOCTOR" && live) await loadDoctor();
                } catch (cause) {
                    if (live) setError((cause as Error).message);
                } finally {
                    if (live) setLoading(false);
                }
            })();
        }

        return () => { live = false };
    }, [session]);
    useEffect(() => {
        if (session.role !== "PATIENT") return;
        const refresh = () => request<Appointment[]>("/appointments/mine", session.accessToken)
            .then(value => {
                setAppointments(value);
                setPatientResourceState(current => ({ ...current, appointments: { loading: false, error: "" } }));
            })
            .catch(cause => setPatientResourceState(current => ({
                ...current,
                appointments: { loading: false, error: (cause as Error).message },
            })));
        window.addEventListener("appointments-changed", refresh);
        return () => window.removeEventListener("appointments-changed", refresh);
    }, [session]);
    useEffect(() => {
        if (session.role !== "DOCTOR") return;
        let refreshTimer: number | undefined;
        const unsubscribe = subscribeRealtime(event => {
            if (event.type !== "SLOTS_CHANGED") return;
            window.clearTimeout(refreshTimer);
            refreshTimer = window.setTimeout(() => { void loadDoctor().catch(() => undefined) }, 150);
        });
        return () => {
            unsubscribe();
            window.clearTimeout(refreshTimer);
        };
    }, [session]);
    async function transition(id: string, action: "start" | "complete") { setError(""); try { await request(`/appointments/${id}/${action}`, session.accessToken, { method: "POST" }); await loadDoctor() } catch (x) { setError((x as Error).message); throw x } }
    async function requireFollowUp(id: string, reason: string, notBefore: string) { setError(""); try { await request(`/appointments/${id}/require-follow-up`, session.accessToken, { method: "POST", body: JSON.stringify({ reason, notBefore }) }); await loadDoctor() } catch (x) { setError((x as Error).message); throw x } }
    const roleName = ROLE_NAMES[session.role];
    const navItems = NAVIGATION_BY_ROLE[session.role];
    const displayName = session.role === "PATIENT"
        ? patient?.fullName || roleName
        : session.role === "DOCTOR"
            ? `BS. ${doctor?.fullName || roleName}`
            : session.role === "RECEPTIONIST" || session.role === "ADMIN"
                ? accountProfile?.displayName || roleName
                : roleName;
    const headerAvatar = accountAvatarSrc || (session.role === "DOCTOR" ? doctor?.avatarUrl : undefined);
    return <div className={`shell role-${session.role.toLowerCase()} ${session.role === "PATIENT" && tab === "profile" ? "patient-dashboard-active" : ""}`}>
        <a className="app-skip-link" href="#app-workspace-content">Đi đến nội dung chính</a>
        <AppHeader
            roleName={roleName}
            displayName={displayName}
            avatarSrc={headerAvatar}
            activeItem={tab}
            items={navItems}
            onNavigate={setTab}
            onOpenAccount={session.role === "PATIENT" || session.role === "RECEPTIONIST"
                ? (accountProfile ? () => setAccountDialogOpen(true) : undefined)
                : session.role === "DOCTOR" ? () => setTab("profile") : undefined}
            onLogout={logout}
        />
        <main id="app-workspace-content" className="app-main" tabIndex={-1}>
            {/* Each role now opens directly on its operational content. The
                shared sidebar already communicates role and account identity. */}
            {loading && <State text="Đang tải dữ liệu từ hệ thống..." />}
            {error && <State text={error} error />}
            {!loading && !error && session.role === "ADMIN" && <AdminPanel token={session.accessToken} tab={tab} />}
            {!loading && !error && session.role === "RECEPTIONIST" && <ReceptionWorkspace token={session.accessToken} tab={tab} onNavigate={setTab} />}
            {!loading && !error && session.role === "PATIENT" && patient && tab === "profile" && <PatientDashboard token={session.accessToken} patient={patient} appointments={appointments} records={records} prescriptions={prescriptions} resourceState={patientResourceState} savedPatient={setPatient} changedAppointments={setAppointments} openAppointments={() => setTab("appointments")} openAi={() => setTab("ai")} openRecords={() => setTab("records")} />}
            {!loading && !error && session.role === "PATIENT" && patient && tab === "appointments" && <PatientAppointments token={session.accessToken} patient={patient} appointments={appointments} changed={setAppointments} />}
            {!loading && !error && session.role === "PATIENT" && patient && tab === "records" && <PatientMedicalRecords token={session.accessToken} patient={patient} appointments={appointments} records={records} prescriptions={prescriptions} resourceState={patientResourceState} openAppointments={() => setTab("appointments")} recordHidden={id => setRecords(current => current.filter(record => record.id !== id))} />}
            {!loading && !error && session.role === "PATIENT" && patient && tab === "ai" && <PatientAiScreen token={session.accessToken} patient={patient} openBooking={() => setTab("appointments")} />}
            {!loading && !error && session.role === "DOCTOR" && doctor && tab === "profile" && <DoctorProfile token={session.accessToken} doctor={doctor} work={work} leave={leave} saved={setDoctor} />}
            {!loading && !error && session.role === "DOCTOR" && doctor && tab === "appointments" && <DoctorView token={session.accessToken} doctor={doctor} appointments={appointments} patients={patients} work={work} leave={leave} transition={transition} requireFollowUp={requireFollowUp} />}
            {!loading && !error && session.role === "DOCTOR" && tab === "records" && <RecordList records={records} patients={patients} />}
        </main>
        {/* Patient screens prioritize appointments and health results, so the
            shared staff footer is intentionally omitted for this role. */}
        {session.role !== "PATIENT" && <AppFooter variant="staff" />}
        {session.role === "RECEPTIONIST" && accountDialogOpen && accountProfile && (
            <ReceptionistAccountDialog
                token={session.accessToken}
                profile={accountProfile}
                avatarSrc={accountAvatarSrc}
                onChanged={(profile, avatarChanged) => {
                    setAccountProfile(profile);
                    if (avatarChanged) void loadAccountAvatar().catch(() => undefined);
                }}
                onClose={() => setAccountDialogOpen(false)}
            />
        )}
        {session.role === "PATIENT" && accountDialogOpen && accountProfile && patient && (
            <PatientAccountDialog
                token={session.accessToken}
                account={accountProfile}
                patient={patient}
                avatarSrc={accountAvatarSrc}
                onChanged={(profile, avatarChanged) => {
                    setAccountProfile(profile);
                    if (avatarChanged) void loadAccountAvatar().catch(() => undefined);
                }}
                onClose={() => setAccountDialogOpen(false)}
            />
        )}
    </div>;
}
createRoot(document.getElementById("root")!).render(<App />);

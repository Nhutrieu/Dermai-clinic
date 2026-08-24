import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Calendar, CheckCircle2, Clock3, LoaderCircle, Star, Stethoscope } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { ApiError, request } from "../../../core/api";
import { formatVnd } from "../../../core/currency";
import type { ClinicReview, ClinicService, Doctor } from "../../../core/types";

const BOOKING_DRAFT_KEY = "derm-home-booking";
const tones = ["from-teal-500/30 to-cyan-950", "from-cyan-500/25 to-slate-950", "from-emerald-500/25 to-zinc-950"];
const specialtyNames: Record<string, string> = {
  DERMATOLOGY: "Da liễu", AESTHETIC_DERMATOLOGY: "Da liễu thẩm mỹ", ACNE: "Điều trị mụn",
  PIGMENT: "Nám & sắc tố", LASER: "Laser & trẻ hóa"
};

type LoadState = "loading" | "success" | "error";
type Props = { openAuth: (destination?: "appointments" | "ai") => void };

function ErrorMessage({ error }: { error: ApiError | Error }) {
  const code = error instanceof ApiError ? error.code : undefined;
  return <motion.div role="alert" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4 text-sm text-rose-100">
    {error.message}{code && <span className="ml-2 font-mono text-xs text-rose-300">[{code}]</span>}
  </motion.div>;
}

export function HomepageReviews() {
  const [reviews, setReviews] = useState<ClinicReview[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState<ApiError | Error | null>(null);

  useEffect(() => {
    let live = true;
    request<ClinicReview[]>("/appointments/reviews/public")
      .then(items => { if (live) setReviews(items); })
      .catch(cause => { if (live) setError(cause as ApiError | Error); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, []);

  return <motion.div initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="v2-review-panel">
    <div className="v2-review-heading"><div><p className="v2-kicker">ĐÁNH GIÁ KHÁCH HÀNG</p><h3>Trải nghiệm được chia sẻ sau buổi khám.</h3></div>{reviews.length > 0 && <div className="v2-review-score"><Star/><b>{(reviews.reduce((sum, item) => sum + item.rating, 0) / reviews.length).toFixed(1)}</b><span>/ 5</span></div>}</div>
    <AnimatePresence mode="wait">
      {loading && <motion.div key="loading" exit={{ opacity: 0 }} className="v2-review-status"><LoaderCircle className="animate-spin"/>Đang tải đánh giá...</motion.div>}
      {!loading && error && <ErrorMessage error={error}/>}
      {!loading && !error && reviews.length === 0 && <motion.p key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="v2-review-status">Chưa có đánh giá công khai. Đánh giá mới sẽ xuất hiện sau khi được duyệt.</motion.p>}
      {!loading && reviews.length > 0 && <motion.div key="reviews"><motion.div className="v2-review-grid" initial="hidden" animate="show" variants={{ show: { transition: { staggerChildren: .08 } } }}>{(expanded ? reviews : reviews.slice(0, 3)).map(item => <motion.article layout key={item.id} variants={{ hidden: { opacity: 0, y: 18 }, show: { opacity: 1, y: 0 } }} whileHover={{ y: -6 }}><div className="v2-review-stars">{Array.from({ length: 5 }, (_, index) => <Star key={index} className={index < item.rating ? "is-filled" : ""}/>)}</div><p>“{item.comment}”</p><div><b>{item.displayName}</b><small>Khách hàng đã thăm khám</small></div></motion.article>)}</motion.div>{reviews.length > 3 && <motion.button type="button" onClick={() => setExpanded(value => !value)} whileHover={{ scale: 1.04 }} whileTap={{ scale: .96 }} className="v2-review-more">{expanded ? "Thu gọn" : `Xem thêm ${reviews.length - 3} đánh giá`}<ArrowRight className={expanded ? "is-expanded" : ""}/></motion.button>}</motion.div>}
    </AnimatePresence>
  </motion.div>;
}
export default function HomepageData({ openAuth }: Props) {
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [services, setServices] = useState<ClinicService[]>([]);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [doctorId, setDoctorId] = useState("");
  const [date, setDate] = useState(() => new Date(Date.now() + 86400000).toISOString().slice(0, 10));
  const [reason, setReason] = useState("");
  const [saved, setSaved] = useState(false);
  const minDate = useMemo(() => new Date().toISOString().slice(0, 10), []);

  useEffect(() => {
    let live = true;
    Promise.all([request<Doctor[]>("/doctors"), request<ClinicService[]>("/services")])
      .then(([doctorList, serviceList]) => {
        if (!live) return;
        setDoctors(doctorList);
        setServices(serviceList);
        setDoctorId(doctorList[0]?.id || "");
        setState("success");
      })
      .catch(cause => { if (live) { setError(cause as ApiError | Error); setState("error"); } });
    return () => { live = false; };
  }, []);

  function continueBooking() {
    if (!doctorId || !date || !reason.trim()) return;
    sessionStorage.setItem(BOOKING_DRAFT_KEY, JSON.stringify({
      doctorId, date, reason: reason.trim()
    }));
    setSaved(true);
    window.setTimeout(() => openAuth("appointments"), 550);
  }

  return <>
    <section id="services" className="px-5 py-28"><div className="mx-auto max-w-7xl">
      <motion.div initial={{ opacity: 0, y: 25 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}><p className="v2-kicker">DỊCH VỤ THỰC TẾ</p><h2 className="v2-title max-w-3xl">Chăm sóc đúng nhu cầu, rõ chi phí từ đầu.</h2></motion.div>
      <AnimatePresence mode="wait">
        {state === "loading" && <motion.div key="loading" exit={{ opacity: 0 }} className="mt-12 flex items-center gap-3 text-teal-200"><LoaderCircle className="animate-spin"/>Đang tải dịch vụ từ hệ thống...</motion.div>}
        {state === "error" && error && <ErrorMessage error={error}/>}
        {state === "success" && <motion.div key="services" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="v2-service-grid">{services.map((service, index) => <motion.article key={service.id} initial={{ opacity: 0, y: 25 }} whileInView={{ opacity: 1, y: 0 }} transition={{ delay: index * .08 }} whileHover={{ y: -8 }} className="rounded-[28px] border border-white/[.08] bg-white/[.035] p-6 hover:border-teal-300/35"><Stethoscope className="text-teal-300"/><h3 className="mt-8 text-xl font-semibold text-white">{service.name}</h3><p className="mt-3 min-h-24 text-sm leading-6 text-slate-400">{service.description}</p><div className="mt-6 flex items-end justify-between"><span><small className="block text-slate-500">Từ</small><b className="text-teal-200">{formatVnd(service.priceFrom)}</b></span><span className="flex items-center gap-1 text-xs text-slate-500"><Clock3 size={14}/>{service.durationMinutes} phút</span></div></motion.article>)}</motion.div>}
      </AnimatePresence>
    </div></section>

    <section id="experts" className="overflow-hidden px-5 py-28"><div className="mx-auto max-w-7xl"><p className="v2-kicker">ĐỘI NGŨ CHUYÊN MÔN</p><h2 className="v2-title max-w-3xl">Đội ngũ bác sĩ đang làm việc tại phòng khám.</h2>
      <div className="v2-doctor-grid">{doctors.map((doctor, index) => <motion.article layout key={doctor.id} whileHover={{ y: -10 }} className="overflow-hidden rounded-[28px] border border-white/[.08] p-1 hover:border-teal-300/40"><div className={`relative flex min-h-[390px] flex-col justify-end overflow-hidden rounded-[24px] bg-gradient-to-br ${tones[index % tones.length]} p-6`}>
        {doctor.avatarUrl ? <img src={doctor.avatarUrl} alt={doctor.fullName} className="v2-doctor-photo absolute inset-0 h-full w-full object-cover object-center opacity-45"/> : <div className="absolute left-6 top-6 grid size-16 place-items-center rounded-2xl bg-white/10 text-2xl font-bold text-teal-200">{doctor.fullName.split(" ").at(-1)?.[0]}</div>}
        <div className="v2-doctor-copy relative"><p className="text-xs font-bold tracking-[.14em] text-teal-300">{specialtyNames[doctor.specialtyCode] || doctor.specialtyCode}</p><h3 className="mt-2 text-2xl font-semibold text-white">{doctor.fullName}</h3><p className="mt-2 text-sm text-slate-300">{doctor.experienceYears} năm kinh nghiệm · {formatVnd(doctor.consultationFee)}</p>{doctor.bio && <p className="mt-4 line-clamp-3 text-sm leading-6 text-slate-400">{doctor.bio}</p>}<button onClick={() => { setDoctorId(doctor.id); document.querySelector("#booking-form")?.scrollIntoView({ behavior: "smooth" }); }} className="mt-6 flex w-full items-center justify-center gap-2 rounded-full bg-teal-300 py-3 font-bold text-slate-950">Chọn bác sĩ <ArrowRight size={16}/></button></div>
      </div></motion.article>)}</div>
    </div></section>

    <section id="booking-form" className="px-5 py-28"><motion.form onSubmit={event => { event.preventDefault(); continueBooking(); }} initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="mx-auto max-w-5xl rounded-[38px] border border-teal-300/20 bg-gradient-to-br from-[#0d292b] to-[#0a111a] p-7 sm:p-12">
      <p className="v2-kicker">ĐẶT LỊCH TRỰC TUYẾN</p><h2 className="text-4xl font-semibold text-white sm:text-5xl">Tạo yêu cầu khám trong vài bước.</h2><p className="mt-4 text-slate-400">Khung giờ trống và chi phí cuối cùng được xác nhận trực tiếp từ hệ thống sau khi đăng nhập.</p>
      <div className="v2-booking-fields"><label className="grid gap-2 text-sm text-slate-300">Bác sĩ<select required value={doctorId} onChange={e => setDoctorId(e.target.value)} className="rounded-2xl border border-white/10 bg-[#0b111b] p-4 text-white"><option value="">Chọn bác sĩ</option>{doctors.map(item => <option key={item.id} value={item.id}>{item.fullName}</option>)}</select></label><label className="grid gap-2 text-sm text-slate-300">Ngày mong muốn<input required type="date" min={minDate} value={date} onChange={e => setDate(e.target.value)} className="rounded-2xl border border-white/10 bg-[#0b111b] p-4 text-white"/></label><label className="v2-booking-reason grid gap-2 text-sm text-slate-300">Lý do khám<input required maxLength={500} value={reason} onChange={e => setReason(e.target.value)} placeholder="Mô tả ngắn tình trạng da" className="rounded-2xl border border-white/10 bg-[#0b111b] p-4 text-white"/></label></div>
      <AnimatePresence mode="wait">{saved ? <motion.div key="saved" initial={{ scale: .9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="mt-7 flex items-center gap-3 text-teal-200"><CheckCircle2/>Đã lưu lựa chọn, đang mở đăng nhập...</motion.div> : <motion.button key="submit" whileHover={{ scale: 1.02 }} whileTap={{ scale: .97 }} disabled={state !== "success"} className="mt-8 flex items-center gap-3 rounded-full bg-teal-300 px-7 py-4 font-bold text-slate-950 disabled:opacity-50"><Calendar size={18}/>Tiếp tục chọn giờ<ArrowRight size={17}/></motion.button>}</AnimatePresence>
      {error && <div className="mt-5"><ErrorMessage error={error}/></div>}
    </motion.form></section>
  </>;
}

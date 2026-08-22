import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Calendar, CheckCircle2, Clock3, LoaderCircle, Stethoscope } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { ApiError, request } from "../../../core/api";
import { formatVnd } from "../../../core/currency";
import type { ClinicService, Doctor } from "../../../core/types";

const BOOKING_DRAFT_KEY = "derm-home-booking";
const tones = ["from-teal-500/30 to-cyan-950", "from-cyan-500/25 to-slate-950", "from-emerald-500/25 to-zinc-950"];
const specialtyNames: Record<string, string> = {
  DERMATOLOGY: "Da liễu", AESTHETIC_DERMATOLOGY: "Da liễu thẩm mỹ", ACNE: "Điều trị mụn",
  PIGMENT: "Nám & sắc tố", LASER: "Laser & trẻ hóa"
};

type LoadState = "loading" | "success" | "error";
type Props = { openAuth: () => void };

function ErrorMessage({ error }: { error: ApiError | Error }) {
  const code = error instanceof ApiError ? error.code : undefined;
  return <motion.div role="alert" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4 text-sm text-rose-100">
    {error.message}{code && <span className="ml-2 font-mono text-xs text-rose-300">[{code}]</span>}
  </motion.div>;
}

export default function HomepageData({ openAuth }: Props) {
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [services, setServices] = useState<ClinicService[]>([]);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [doctorId, setDoctorId] = useState("");
  const [serviceId, setServiceId] = useState("");
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
        setServiceId(serviceList[0]?.id || "");
        setState("success");
      })
      .catch(cause => { if (live) { setError(cause as ApiError | Error); setState("error"); } });
    return () => { live = false; };
  }, []);

  function continueBooking() {
    if (!doctorId || !serviceId || !date || !reason.trim()) return;
    const service = services.find(item => item.id === serviceId);
    sessionStorage.setItem(BOOKING_DRAFT_KEY, JSON.stringify({
      doctorId, serviceId, serviceName: service?.name || "Khám da liễu", date,
      reason: `${service?.name || "Khám da liễu"}: ${reason.trim()}`
    }));
    setSaved(true);
    window.setTimeout(openAuth, 550);
  }

  return <>
    <section id="services" className="px-5 py-28"><div className="mx-auto max-w-7xl">
      <motion.div initial={{ opacity: 0, y: 25 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}><p className="v2-kicker">DỊCH VỤ THỰC TẾ</p><h2 className="v2-title max-w-3xl">Chăm sóc đúng nhu cầu, rõ chi phí từ đầu.</h2></motion.div>
      <AnimatePresence mode="wait">
        {state === "loading" && <motion.div key="loading" exit={{ opacity: 0 }} className="mt-12 flex items-center gap-3 text-teal-200"><LoaderCircle className="animate-spin"/>Đang tải dịch vụ từ hệ thống...</motion.div>}
        {state === "error" && error && <ErrorMessage error={error}/>} 
        {state === "success" && <motion.div key="services" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-12 grid gap-4 md:grid-cols-2 lg:grid-cols-4">{services.map((service, index) => <motion.article key={service.id} initial={{ opacity: 0, y: 25 }} whileInView={{ opacity: 1, y: 0 }} transition={{ delay: index * .08 }} whileHover={{ y: -8 }} className="rounded-[28px] border border-white/[.08] bg-white/[.035] p-6 hover:border-teal-300/35"><Stethoscope className="text-teal-300"/><h3 className="mt-8 text-xl font-semibold text-white">{service.name}</h3><p className="mt-3 min-h-24 text-sm leading-6 text-slate-400">{service.description}</p><div className="mt-6 flex items-end justify-between"><span><small className="block text-slate-500">Từ</small><b className="text-teal-200">{formatVnd(service.priceFrom)}</b></span><span className="flex items-center gap-1 text-xs text-slate-500"><Clock3 size={14}/>{service.durationMinutes} phút</span></div></motion.article>)}</motion.div>}
      </AnimatePresence>
    </div></section>

    <section id="experts" className="overflow-hidden px-5 py-28"><div className="mx-auto max-w-7xl"><p className="v2-kicker">MEDICAL EXPERTS</p><h2 className="v2-title max-w-3xl">Đội ngũ bác sĩ đang làm việc tại phòng khám.</h2>
      <div className="mt-12 grid gap-5 lg:grid-cols-3">{doctors.map((doctor, index) => <motion.article layout key={doctor.id} whileHover={{ y: -10 }} className="overflow-hidden rounded-[28px] border border-white/[.08] p-1 hover:border-teal-300/40"><div className={`relative flex min-h-[390px] flex-col justify-end overflow-hidden rounded-[24px] bg-gradient-to-br ${tones[index % tones.length]} p-6`}>
        {doctor.avatarUrl ? <img src={doctor.avatarUrl} alt={doctor.fullName} className="absolute inset-0 h-full w-full object-cover opacity-45"/> : <div className="absolute left-6 top-6 grid size-16 place-items-center rounded-2xl bg-white/10 text-2xl font-bold text-teal-200">{doctor.fullName.split(" ").at(-1)?.[0]}</div>}
        <div className="relative"><p className="text-xs font-bold tracking-[.14em] text-teal-300">{specialtyNames[doctor.specialtyCode] || doctor.specialtyCode}</p><h3 className="mt-2 text-2xl font-semibold text-white">{doctor.fullName}</h3><p className="mt-2 text-sm text-slate-300">{doctor.experienceYears} năm kinh nghiệm · {formatVnd(doctor.consultationFee)}</p>{doctor.bio && <p className="mt-4 line-clamp-3 text-sm leading-6 text-slate-400">{doctor.bio}</p>}<button onClick={() => { setDoctorId(doctor.id); document.querySelector("#booking-form")?.scrollIntoView({ behavior: "smooth" }); }} className="mt-6 flex w-full items-center justify-center gap-2 rounded-full bg-teal-300 py-3 font-bold text-slate-950">Chọn bác sĩ <ArrowRight size={16}/></button></div>
      </div></motion.article>)}</div>
    </div></section>

    <section id="booking-form" className="px-5 py-28"><motion.form onSubmit={event => { event.preventDefault(); continueBooking(); }} initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="mx-auto max-w-5xl rounded-[38px] border border-teal-300/20 bg-gradient-to-br from-[#0d292b] to-[#0a111a] p-7 sm:p-12">
      <p className="v2-kicker">ĐẶT LỊCH TRỰC TUYẾN</p><h2 className="text-4xl font-semibold text-white sm:text-5xl">Tạo yêu cầu khám trong vài bước.</h2><p className="mt-4 text-slate-400">Khung giờ trống và chi phí cuối cùng được xác nhận trực tiếp từ hệ thống sau khi đăng nhập.</p>
      <div className="mt-9 grid gap-5 md:grid-cols-2"><label className="grid gap-2 text-sm text-slate-300">Dịch vụ<select required value={serviceId} onChange={e => setServiceId(e.target.value)} className="rounded-2xl border border-white/10 bg-[#0b111b] p-4 text-white"><option value="">Chọn dịch vụ</option>{services.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label className="grid gap-2 text-sm text-slate-300">Bác sĩ<select required value={doctorId} onChange={e => setDoctorId(e.target.value)} className="rounded-2xl border border-white/10 bg-[#0b111b] p-4 text-white"><option value="">Chọn bác sĩ</option>{doctors.map(item => <option key={item.id} value={item.id}>{item.fullName}</option>)}</select></label><label className="grid gap-2 text-sm text-slate-300">Ngày mong muốn<input required type="date" min={minDate} value={date} onChange={e => setDate(e.target.value)} className="rounded-2xl border border-white/10 bg-[#0b111b] p-4 text-white"/></label><label className="grid gap-2 text-sm text-slate-300">Lý do khám<input required maxLength={500} value={reason} onChange={e => setReason(e.target.value)} placeholder="Mô tả ngắn tình trạng da" className="rounded-2xl border border-white/10 bg-[#0b111b] p-4 text-white"/></label></div>
      <AnimatePresence mode="wait">{saved ? <motion.div key="saved" initial={{ scale: .9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="mt-7 flex items-center gap-3 text-teal-200"><CheckCircle2/>Đã lưu lựa chọn, đang mở đăng nhập...</motion.div> : <motion.button key="submit" whileHover={{ scale: 1.02 }} whileTap={{ scale: .97 }} disabled={state !== "success"} className="mt-8 flex items-center gap-3 rounded-full bg-teal-300 px-7 py-4 font-bold text-slate-950 disabled:opacity-50"><Calendar size={18}/>Tiếp tục chọn giờ<ArrowRight size={17}/></motion.button>}</AnimatePresence>
      {error && <div className="mt-5"><ErrorMessage error={error}/></div>}
    </motion.form></section>
  </>;
}

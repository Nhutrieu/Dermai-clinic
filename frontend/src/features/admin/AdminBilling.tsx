import { useEffect, useMemo, useState } from "react";
import { Download, TrendingUp } from "lucide-react";
import { request, requestBlob } from "../../core/api";
import { formatVnd } from "../../core/currency";
import AdminDepositSetting from "./AdminDepositSetting";

type Summary = { deposits: number; consultationFees: number; serviceFees: number; medicineRevenue: number; onlineReceived: number; cashReceived: number; paidInvoices: number; awaitingInvoices: number };
type DepositPayment = { id: string; amount: number; status: string; createdAt?: string; refundRequestedAt?: string; refundedAt?: string; refundAmount?: number };
type InvoiceCashFlowPoint = { date: string; onlineReceived: number; cashReceived: number; consultationFees: number; serviceFees: number; medicineRevenue: number };
type CashFlowDay = { date: string; online: number; cash: number; refunded: number; consultation: number; service: number; medicine: number };
type CashFlowPeriod = CashFlowDay & { label: string; balance: number };
const emptySummary: Summary = { deposits: 0, consultationFees: 0, serviceFees: 0, medicineRevenue: 0, onlineReceived: 0, cashReceived: 0, paidInvoices: 0, awaitingInvoices: 0 };

export function isCollectedDeposit(status: string) {
  return status === "SUCCESS" || status === "REFUND_REQUESTED" || status === "REFUNDED";
}

export function sumCollectedDeposits(items: DepositPayment[], from: number, to: number) {
  return items.reduce((sum, item) => {
    const createdAt = item.createdAt ? new Date(item.createdAt).getTime() : Number.NaN;
    return isCollectedDeposit(item.status) && Number.isFinite(createdAt) && createdAt >= from && createdAt <= to
      ? sum + Number(item.amount || 0)
      : sum;
  }, 0);
}

export default function AdminBilling({ token }: { token: string }) {
  const [summary, setSummary] = useState(emptySummary);
  const [allTimeSummary, setAllTimeSummary] = useState(emptySummary);
  const [payments, setPayments] = useState<DepositPayment[]>([]);
  const [invoiceCashFlow, setInvoiceCashFlow] = useState<InvoiceCashFlowPoint[]>([]);
  const [reportWindow, setReportWindow] = useState({ from: 0, to: 0 });
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    async function refresh() {
      const from = new Date(`${toClinicDay(new Date())}T00:00:00+07:00`);
      from.setUTCDate(from.getUTCDate() - 29);
      const to = new Date();
      try {
        const [stats, allTimeStats, deposits, cashFlow] = await Promise.all([
          request<Summary>(`/billing/reports/summary?from=${encodeURIComponent(from.toISOString())}&to=${encodeURIComponent(to.toISOString())}`, token),
          request<Summary>(`/billing/reports/summary?from=${encodeURIComponent(new Date(0).toISOString())}&to=${encodeURIComponent(to.toISOString())}`, token),
          request<DepositPayment[]>(`/payments/reports?from=${encodeURIComponent(from.toISOString())}&to=${encodeURIComponent(to.toISOString())}`, token),
          request<InvoiceCashFlowPoint[]>(`/billing/reports/cash-flow?from=${encodeURIComponent(from.toISOString())}&to=${encodeURIComponent(to.toISOString())}`, token),
        ]);
        if (!active) return;
        setSummary(stats);
        setAllTimeSummary(allTimeStats);
        setPayments(deposits);
        setInvoiceCashFlow(cashFlow);
        setReportWindow({ from: from.getTime(), to: to.getTime() });
        setMessage("");
      } catch (error) {
        if (active) setMessage((error as Error).message);
      }
    }
    void refresh();
    const interval = window.setInterval(() => void refresh(), 15_000);
    const refreshOnFocus = () => void refresh();
    window.addEventListener("focus", refreshOnFocus);
    return () => { active = false; window.clearInterval(interval); window.removeEventListener("focus", refreshOnFocus); };
  }, [token]);

  const withinLast30Days = (value?: string) => {
    if (!value) return false;
    const timestamp = new Date(value).getTime();
    return Number.isFinite(timestamp) && timestamp >= reportWindow.from && timestamp <= reportWindow.to;
  };
  const depositsReceived = useMemo(() => sumCollectedDeposits(payments, reportWindow.from, reportWindow.to), [payments, reportWindow]);

  const refundPending = useMemo(() => payments.filter(item => item.status === "REFUND_REQUESTED" && withinLast30Days(item.refundRequestedAt)).reduce((sum, item) => sum + Number(item.refundAmount || item.amount), 0), [payments, reportWindow]);
  const refunded = useMemo(() => payments.filter(item => item.status === "REFUNDED" && withinLast30Days(item.refundedAt)).reduce((sum, item) => sum + Number(item.refundAmount || 0), 0), [payments, reportWindow]);
  const failed = payments.filter(item => ["FAILED", "EXPIRED"].includes(item.status) && withinLast30Days(item.createdAt)).length;
  const onlineReceived = summary.onlineReceived + depositsReceived;
  const totalRevenue = allTimeSummary.consultationFees + allTimeSummary.serviceFees + allTimeSummary.medicineRevenue;
  const cashFlowDays = useMemo(() => buildCashFlowDays(invoiceCashFlow, payments), [invoiceCashFlow, payments]);

  async function exportCsv() {
    try {
      const blob = await requestBlob("/billing/reports/export.csv", token);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `dermai-doi-soat-${new Date().toISOString().slice(0, 10)}.csv`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setMessage((error as Error).message);
    }
  }

  return <section className="admin-billing panel">
    <header>
      <div><span>Tài chính</span><h2>Đối soát doanh thu</h2><p>Số liệu 30 ngày gần nhất. Dashboard chỉ dùng quản lý, không phải ví giữ tiền.</p></div>
      <button type="button" className="admin-billing-export" onClick={exportCsv}><Download /> Xuất CSV</button>
    </header>

    <AdminDepositSetting token={token} />

    {message && <p className="admin-billing-feedback" role="status">{message}</p>}

    <article className="admin-total-revenue">
      <div><span>Tổng doanh thu toàn phòng khám</span><small>Tất cả phí khám, phí dịch vụ và doanh thu thuốc đã thanh toán từ trước tới nay</small></div>
      <b>{formatVnd(totalRevenue)}</b>
    </article>

    <div className="admin-billing-metrics">
      <Metric label="Tiền cọc đã nhận" value={formatVnd(depositsReceived)} />
      <Metric label="Phí khám" value={formatVnd(summary.consultationFees)} />
      <Metric label="Phí dịch vụ" value={formatVnd(summary.serviceFees)} />
      <Metric label="Doanh thu thuốc" value={formatVnd(summary.medicineRevenue)} />
      <Metric label="Nhận online" value={formatVnd(onlineReceived)} />
      <Metric label="Tiền mặt" value={formatVnd(summary.cashReceived)} />
      <Metric label="Chờ hoàn" value={formatVnd(refundPending)} warning />
      <Metric label="Đã hoàn" value={formatVnd(refunded)} />
      <Metric label="Hết hạn / thất bại" value={`${failed} giao dịch`} warning />
    </div>

    <CashFlowChart items={cashFlowDays} />

  </section>;
}

function Metric({ label, value, warning = false }: { label: string; value: string; warning?: boolean }) {
  return <article className={warning ? "is-warning" : ""}><span>{label}</span><b>{value}</b></article>;
}

function CashFlowChart({ items }: { items: CashFlowDay[] }) {
  const hasData = items.some(item => item.online > 0 || item.cash > 0 || item.refunded > 0);
  const periods = useMemo(() => groupCashFlowDays(items), [items]);
  return <section className="admin-cash-flow" aria-labelledby="admin-cash-flow-title">
    <header>
      <div className="admin-cash-flow-title"><span><TrendingUp aria-hidden="true" /></span><div><h3 id="admin-cash-flow-title">Dòng tiền 30 ngày</h3><p>Tiền thu online, tiền mặt và khoản đã hoàn theo từng ngày.</p></div></div>
      <div className="admin-cash-flow-legend" aria-label="Chú thích biểu đồ"><span className="is-online">Online</span><span className="is-cash">Tiền mặt</span><span className="is-refund">Hoàn tiền</span><span className="is-balance">Số dư</span></div>
    </header>
    {!hasData ? <div className="admin-cash-flow-empty"><TrendingUp aria-hidden="true" /><span>Chưa có dòng tiền trong 30 ngày gần đây.</span></div> : <div className="admin-cash-flow-grid">
      <FinanceChartCard title="Tiền tồn cuối kỳ"><BalanceChart items={periods} /></FinanceChartCard>
      <FinanceChartCard title="Lưu chuyển tiền trong kỳ"><FlowLineChart items={periods} /></FinanceChartCard>
      <FinanceChartCard title="Cơ cấu doanh thu trong kỳ" wide><RevenueChart items={periods} /></FinanceChartCard>
    </div>}
  </section>;
}

function FinanceChartCard({ title, children, wide = false }: { title: string; children: React.ReactNode; wide?: boolean }) {
  return <article className={`admin-finance-chart${wide ? " is-wide" : ""}`}><h4>{title}</h4><div className="admin-cash-flow-scroll">{children}</div></article>;
}

function BalanceChart({ items }: { items: CashFlowPeriod[] }) {
  const chart = chartLayout(items.flatMap(item => [item.online, item.cash, -item.refunded, item.balance]));
  const points = items.map((item, index) => `${chart.x(index, items.length)},${chart.y(item.balance)}`).join(" ");
  return <svg className="admin-finance-svg" viewBox="0 0 640 320" role="img" aria-label="Biểu đồ tiền tồn cuối kỳ"><title>Tiền tồn cuối kỳ theo từng giai đoạn 5 ngày</title>
    <ChartGrid chart={chart} />
    {items.map((item, index) => { const center = chart.x(index, items.length); return <g key={item.date}>
      <CashBar x={center - 17} value={item.online} chart={chart} className="is-online"><title>{`${item.label} · Online: ${formatVnd(item.online)}`}</title></CashBar>
      <CashBar x={center - 3} value={item.cash} chart={chart} className="is-cash"><title>{`${item.label} · Tiền mặt: ${formatVnd(item.cash)}`}</title></CashBar>
      <CashBar x={center + 11} value={-item.refunded} chart={chart} className="is-refund"><title>{`${item.label} · Hoàn tiền: ${formatVnd(item.refunded)}`}</title></CashBar>
      <text className="chart-period-label" x={center} y="292" textAnchor="middle">{item.label}</text>
    </g>; })}
    <polyline className="chart-balance-line" points={points} />
    {items.map((item, index) => <g key={`balance-${item.date}`}><circle className="chart-balance-dot" cx={chart.x(index, items.length)} cy={chart.y(item.balance)} r="4"><title>{`${item.label} · Số dư: ${formatVnd(item.balance)}`}</title></circle>{item.balance !== 0 && <text className="chart-value-label is-balance" x={chart.x(index, items.length)} y={chart.y(item.balance) - 10} textAnchor="middle">{shortMoney(item.balance)}</text>}</g>)}
  </svg>;
}

function FlowLineChart({ items }: { items: CashFlowPeriod[] }) {
  const chart = chartLayout(items.flatMap(item => [item.online, item.cash, -item.refunded]));
  const series = [{ key: "online", className: "is-online", value: (item: CashFlowPeriod) => item.online }, { key: "cash", className: "is-cash", value: (item: CashFlowPeriod) => item.cash }, { key: "refund", className: "is-refund", value: (item: CashFlowPeriod) => -item.refunded }];
  return <svg className="admin-finance-svg" viewBox="0 0 640 320" role="img" aria-label="Biểu đồ lưu chuyển tiền trong kỳ"><title>Lưu chuyển tiền online, tiền mặt và hoàn tiền</title>
    <ChartGrid chart={chart} />
    {series.map(line => { const points = items.map((item, index) => `${chart.x(index, items.length)},${chart.y(line.value(item))}`).join(" "); return <g key={line.key}><polyline className={`chart-flow-line ${line.className}`} points={points} />{items.map((item, index) => { const value = line.value(item); return <g key={`${line.key}-${item.date}`}><circle className={`chart-flow-dot ${line.className}`} cx={chart.x(index, items.length)} cy={chart.y(value)} r="4"><title>{`${item.label}: ${formatVnd(value)}`}</title></circle>{value !== 0 && <text className={`chart-value-label ${line.className}`} x={chart.x(index, items.length)} y={chart.y(value) + (value < 0 ? 16 : -9)} textAnchor="middle">{shortMoney(value)}</text>}</g>; })}</g>; })}
    {items.map((item, index) => <text key={item.date} className="chart-period-label" x={chart.x(index, items.length)} y="292" textAnchor="middle">{item.label}</text>)}
  </svg>;
}

function RevenueChart({ items }: { items: CashFlowPeriod[] }) {
  const chart = chartLayout(items.flatMap(item => [item.consultation, item.service, item.medicine]));
  return <><div className="admin-revenue-legend" aria-label="Chú thích cơ cấu doanh thu"><span className="is-consultation">Phí khám</span><span className="is-service">Phí dịch vụ</span><span className="is-medicine">Tiền thuốc</span></div><svg className="admin-finance-svg is-revenue" viewBox="0 0 960 320" role="img" aria-label="Biểu đồ cơ cấu doanh thu trong kỳ"><title>Phí khám, phí dịch vụ và doanh thu thuốc theo từng giai đoạn 5 ngày</title>
    <RevenueChartGrid chart={chart} />
    {items.map((item, index) => { const center = 62 + (index + .5) * (922 - 62) / items.length; const bars = [{ value: item.consultation, x: center - 22, className: "is-consultation", label: "Phí khám" }, { value: item.service, x: center - 6, className: "is-service", label: "Phí dịch vụ" }, { value: item.medicine, x: center + 10, className: "is-medicine", label: "Tiền thuốc" }]; return <g key={item.date}>{bars.map(bar => <g key={bar.label}><RevenueBar x={bar.x} value={bar.value} chart={chart} className={bar.className}><title>{`${item.label} · ${bar.label}: ${formatVnd(bar.value)}`}</title></RevenueBar>{bar.value > 0 && <text className={`chart-value-label ${bar.className}`} x={bar.x + 6} y={chart.y(bar.value) - 7} textAnchor="middle">{shortMoney(bar.value)}</text>}</g>)}<text className="chart-period-label" x={center} y="292" textAnchor="middle">{item.label}</text></g>; })}
  </svg></>;
}

function RevenueChartGrid({ chart }: { chart: ChartLayout }) { return <g>{chart.ticks.map(tick => <g key={tick}><line className="chart-grid-line" x1="62" x2="922" y1={chart.y(tick)} y2={chart.y(tick)} /><text className="chart-axis-label" x="54" y={chart.y(tick) + 4} textAnchor="end">{shortMoney(tick)}</text></g>)}<line className="chart-zero-line" x1="62" x2="922" y1={chart.y(0)} y2={chart.y(0)} /></g>; }
function RevenueBar({ x, value, chart, className, children }: { x: number; value: number; chart: ChartLayout; className: string; children: React.ReactNode }) { const zero = chart.y(0); const end = chart.y(value); return <rect className={`chart-revenue-bar ${className}`} x={x} y={Math.min(zero, end)} width="12" height={Math.max(1, Math.abs(end - zero))}>{children}</rect>; }

type ChartLayout = ReturnType<typeof chartLayout>;
function ChartGrid({ chart }: { chart: ChartLayout }) { return <g>{chart.ticks.map(tick => <g key={tick}><line className="chart-grid-line" x1="62" x2="622" y1={chart.y(tick)} y2={chart.y(tick)} /><text className="chart-axis-label" x="54" y={chart.y(tick) + 4} textAnchor="end">{shortMoney(tick)}</text></g>)}<line className="chart-zero-line" x1="62" x2="622" y1={chart.y(0)} y2={chart.y(0)} /></g>; }

function CashBar({ x, value, chart, className, children }: { x: number; value: number; chart: ChartLayout; className: string; children: React.ReactNode }) { const zero = chart.y(0); const end = chart.y(value); return <rect className={`chart-cash-bar ${className}`} x={x} y={Math.min(zero, end)} width="11" height={Math.max(1, Math.abs(end - zero))}>{children}</rect>; }

function chartLayout(values: number[]) {
  const rawMin = Math.min(0, ...values); const rawMax = Math.max(0, ...values); const span = Math.max(1, rawMax - rawMin); const min = rawMin - span * .12; const max = rawMax + span * .12; const top = 28; const bottom = 258; const left = 62; const right = 622;
  return { min, max, ticks: Array.from({ length: 5 }, (_, index) => max - (max - min) * index / 4), y: (value: number) => top + (max - value) / (max - min) * (bottom - top), x: (index: number, count: number) => left + (index + .5) * (right - left) / count };
}

function groupCashFlowDays(items: CashFlowDay[]) {
  let balance = 0; const periods: CashFlowPeriod[] = [];
  for (let index = 0; index < items.length; index += 5) { const chunk = items.slice(index, index + 5); const online = chunk.reduce((sum, item) => sum + item.online, 0); const cash = chunk.reduce((sum, item) => sum + item.cash, 0); const refunded = chunk.reduce((sum, item) => sum + item.refunded, 0); const consultation = chunk.reduce((sum, item) => sum + item.consultation, 0); const service = chunk.reduce((sum, item) => sum + item.service, 0); const medicine = chunk.reduce((sum, item) => sum + item.medicine, 0); balance += online + cash - refunded; periods.push({ date: chunk[0].date, label: `${displayDay(chunk[0].date)}–${displayDay(chunk[chunk.length - 1].date)}`, online, cash, refunded, consultation, service, medicine, balance }); }
  return periods;
}

export function buildCashFlowDays(invoiceFlow: InvoiceCashFlowPoint[], payments: DepositPayment[]): CashFlowDay[] {
  const todayKey = toClinicDay(new Date());
  const cursor = new Date(`${todayKey}T00:00:00Z`);
  const days = new Map<string, CashFlowDay>();
  for (let offset = 29; offset >= 0; offset--) {
    const day = new Date(cursor);
    day.setUTCDate(cursor.getUTCDate() - offset);
    const date = day.toISOString().slice(0, 10);
    days.set(date, { date, online: 0, cash: 0, refunded: 0, consultation: 0, service: 0, medicine: 0 });
  }
  invoiceFlow.forEach(item => { const day = days.get(item.date); if (day) { day.online += Number(item.onlineReceived || 0); day.cash += Number(item.cashReceived || 0); day.consultation += Number(item.consultationFees || 0); day.service += Number(item.serviceFees || 0); day.medicine += Number(item.medicineRevenue || 0); } });
  payments.forEach(item => {
    if (isCollectedDeposit(item.status) && item.createdAt) { const day = days.get(toClinicDay(item.createdAt)); if (day) day.online += Number(item.amount || 0); }
    if (item.status === "REFUNDED" && item.refundedAt) { const day = days.get(toClinicDay(item.refundedAt)); if (day) day.refunded += Number(item.refundAmount || 0); }
  });
  return [...days.values()];
}

function toClinicDay(value: string | Date) {
  const parts = new Intl.DateTimeFormat("en-US", { timeZone: "Asia/Ho_Chi_Minh", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date(value));
  const part = (type: Intl.DateTimeFormatPartTypes) => parts.find(item => item.type === type)?.value || "";
  return `${part("year")}-${part("month")}-${part("day")}`;
}

function displayDay(value: string) { const [, month, day] = value.split("-"); return `${day}/${month}`; }
function compactVnd(value: number) { return `${new Intl.NumberFormat("vi-VN", { notation: "compact", maximumFractionDigits: 1 }).format(value)} đ`; }
function shortMoney(value: number) { const label = compactVnd(Math.abs(value)); return value < 0 ? `(${label})` : label; }

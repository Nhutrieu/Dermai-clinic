export type DoctorBookingSelection = { doctorId: string; date?: string };
type Booking = { doctorId?: string | null; startAt: string };

function validDate(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(value + "T00:00:00Z");
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value;
}

function selection(value: unknown): DoctorBookingSelection | undefined {
  if (!value || typeof value !== "object") return undefined;
  const item = value as Partial<DoctorBookingSelection>;
  if (typeof item.doctorId !== "string" || !item.doctorId.trim() || item.doctorId.length > 160) return undefined;
  return { doctorId: item.doctorId.trim(), ...(validDate(item.date) ? { date: item.date } : {}) };
}

export function doctorBookingSelection(search: string): DoctorBookingSelection | undefined {
  const params = new URLSearchParams(search);
  return selection({ doctorId: params.get("doctorId"), date: params.get("date") });
}

export function doctorBookingUrl(value?: DoctorBookingSelection): string {
  const target = selection(value);
  if (!target) return "/";
  const params = new URLSearchParams({ doctorId: target.doctorId });
  if (target.date) params.set("date", target.date);
  return "/?" + params.toString();
}

export async function resolveBookingReturn(
  rawPending: string | null,
  orderCode: string,
  bookingId: string | undefined,
  loadBooking: (id: string) => Promise<Booking>,
): Promise<DoctorBookingSelection | undefined> {
  let pending: { orderCode?: unknown; bookingId?: unknown; bookingSelection?: unknown } | undefined;
  try {
    const parsed: unknown = JSON.parse(rawPending || "null");
    if (parsed && typeof parsed === "object") pending = parsed;
  } catch { /* Older or malformed browser storage must not interrupt payment confirmation. */ }
  const matches = pending && String(pending.orderCode) === orderCode
    && (!bookingId || pending.bookingId === bookingId);
  if (pending && matches) {
    const cached = selection(pending.bookingSelection);
    if (cached?.date) return cached;
  }
  const id = bookingId || (pending && matches && typeof pending.bookingId === "string" ? pending.bookingId : undefined);
  if (!id) return undefined;
  try {
    const booking = await loadBooking(id);
    const start = new Date(booking.startAt);
    if (Number.isNaN(start.getTime())) return selection({ doctorId: booking.doctorId });
    const date = new Intl.DateTimeFormat("en-CA", {
      timeZone: "Asia/Ho_Chi_Minh", year: "numeric", month: "2-digit", day: "2-digit",
    }).format(start);
    return selection({ doctorId: booking.doctorId, date });
  } catch { return undefined; }
}

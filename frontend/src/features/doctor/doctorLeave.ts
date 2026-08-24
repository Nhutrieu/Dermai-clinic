export function fullDayLeaveRange(date: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    throw new Error("Vui lòng chọn ngày nghỉ.");
  }
  const start = new Date(`${date}T00:00:00`);
  if (Number.isNaN(start.getTime())) {
    throw new Error("Ngày nghỉ không hợp lệ.");
  }
  const end = new Date(start);
  end.setDate(end.getDate() + 1);
  return { startAt: start.toISOString(), endAt: end.toISOString() };
}

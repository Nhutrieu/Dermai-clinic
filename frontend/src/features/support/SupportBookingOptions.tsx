import type { SupportBookingOption } from "../../core/types";
import { validChatBooking } from "./supportBooking";

export default function SupportBookingOptions({ options, onChoose }: {
  options?: SupportBookingOption[] | null;
  onChoose: (option: SupportBookingOption) => void;
}) {
  if (!options?.length) return null;
  return <div className="support-booking-options">
    <span>Chọn giờ để mở trang đặt lịch</span>
    <div role="group" aria-label="Giờ khám được gợi ý">
      {options.map(option => <button type="button" key={option.doctorId + option.startAt}
        disabled={!validChatBooking(option)} onClick={() => onChoose(option)}
        aria-label={`Đặt lịch với bác sĩ ${option.doctorName} lúc ${new Date(option.startAt).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh", hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" })}`}>
        {new Date(option.startAt).toLocaleTimeString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh", hour: "2-digit", minute: "2-digit" })}
      </button>)}
    </div>
    <small>Giờ trống sẽ được kiểm tra lại khi bạn chọn. Bạn xem lại thông tin trước khi xác nhận và thanh toán cọc.</small>
  </div>;
}

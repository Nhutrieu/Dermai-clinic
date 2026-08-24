import { Activity, CalendarDays, MapPin, PhoneCall } from "lucide-react";

type AppFooterProps = {
  variant?: "public" | "patient" | "staff";
};

export default function AppFooter({ variant = "staff" }: AppFooterProps) {
  if (variant === "staff") {
    return (
      <footer className="app-footer app-footer-compact">
        <span>Derm Clinic</span>
        <span>Hỗ trợ vận hành phòng khám da liễu</span>
        <a href="tel:0352790904"><PhoneCall aria-hidden="true" />0352 790 904</a>
      </footer>
    );
  }

  if (variant === "public") {
    return (
      <footer className="app-footer app-footer-full app-footer-public">
        <div className="app-footer-public-main">
          <div className="app-footer-layout">
            <div className="app-footer-about">
              <a className="app-footer-brand" href="#top" aria-label="Derm Clinic, về đầu trang">
                <span aria-hidden="true"><Activity /></span>
                <span className="app-footer-wordmark">
                  <strong>Derm Clinic</strong>
                  <small>Đặt lịch da liễu thuận tiện</small>
                </span>
              </a>
              <p>Derm Clinic kết nối bệnh nhân với bác sĩ da liễu, hỗ trợ đặt lịch rõ ràng và theo dõi thông tin khám thuận tiện.</p>
              <address className="app-footer-public-address">
                <span><strong>Địa chỉ:</strong> 32/2 Thống Nhất, phường Gò Vấp, TP. Hồ Chí Minh</span>
                <span><strong>Điện thoại:</strong> <a href="tel:0352790904">0352 790 904</a></span>
                <span><strong>Email:</strong> <a href="mailto:contact@dermai.clinic">contact@dermai.clinic</a></span>
              </address>
            </div>

            <nav aria-label="Dịch vụ nổi bật tại Derm Clinic">
              <strong className="app-footer-heading">Dịch vụ nổi bật</strong>
              <a href="#doctors">Đặt lịch với bác sĩ</a>
              <a href="#services">Kiểm tra da bằng AI</a>
              <a href="#process">Quy trình thăm khám</a>
              <a href="#doctors">Thông tin bác sĩ</a>
            </nav>

            <nav aria-label="Hướng dẫn và hỗ trợ bệnh nhân">
              <strong className="app-footer-heading">Hướng dẫn &amp; hỗ trợ</strong>
              <a href="#process">Hướng dẫn đặt lịch</a>
              <a href="#faq">Đổi và hủy lịch khám</a>
              <a href="#faq">Câu hỏi thường gặp</a>
              <a href="tel:0352790904">Liên hệ lễ tân</a>
              <a href="#reviews">Đánh giá phòng khám</a>
            </nav>

            <nav aria-label="Thông tin về Derm Clinic">
              <strong className="app-footer-heading">Về Derm</strong>
              <a href="#about">Về phòng khám</a>
              <a href="#doctors">Đội ngũ bác sĩ</a>
              <a href="#reviews">Cảm nhận bệnh nhân</a>
              <span className="app-footer-nav-subheading">Liên hệ phòng khám</span>
              <a href="tel:0352790904">Điện thoại đặt lịch</a>
              <a href="mailto:contact@dermai.clinic">Email hỗ trợ</a>
            </nav>
          </div>
        </div>

        <div className="app-footer-bottom">
          <small>© 2026 Derm Clinic. Bản quyền thuộc Derm Clinic.</small>
          <small className="app-footer-clinical-note"><CalendarDays aria-hidden="true" />Đặt lịch trực tuyến, khám trực tiếp tại phòng khám.</small>
        </div>
      </footer>
    );
  }

  return (
    <footer className={`app-footer app-footer-full app-footer-${variant}`}>
      <div className="app-footer-layout">
        <div className="app-footer-about">
          <a className="app-footer-brand" href="#app-workspace-content" aria-label="Derm Clinic, về nội dung chính">
            <span aria-hidden="true"><Activity /></span>
            <strong>Derm Clinic</strong>
          </a>
          <p>Chăm sóc da bằng chuyên môn, sự thấu hiểu và công nghệ có trách nhiệm.</p>
        </div>
        <div className="app-footer-support">
          <strong>Khi cần hỗ trợ</strong>
          <span>Liên hệ lễ tân để đổi, hủy lịch hoặc xử lý trường hợp đặc biệt.</span>
          <a href="tel:0352790904">Gọi 0352 790 904</a>
        </div>
        <address>
          <strong className="app-footer-heading">Liên hệ phòng khám</strong>
          <span className="app-footer-contact-line"><MapPin aria-hidden="true" />32/2 Thống Nhất, phường Gò Vấp, TP. Hồ Chí Minh</span>
          <a className="app-footer-contact-line" href="tel:0352790904"><PhoneCall aria-hidden="true" />0352 790 904</a>
        </address>
      </div>
      <div className="app-footer-bottom">
        <small>© 2026 Derm Clinic.</small>
        <small className="app-footer-clinical-note"><CalendarDays aria-hidden="true" />Đặt lịch trực tuyến, khám trực tiếp tại phòng khám.</small>
      </div>
    </footer>
  );
}

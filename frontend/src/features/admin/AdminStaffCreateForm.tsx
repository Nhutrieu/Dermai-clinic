import type { FormEvent } from "react";
import { ShieldCheck, UserPlus } from "lucide-react";

export type StaffRole = "DOCTOR" | "RECEPTIONIST" | "ADMIN";

type Props = {
  email: string;
  password: string;
  role: StaffRole;
  name: string;
  specialty: string;
  consultationFee: string;
  busy: boolean;
  message: string;
  failed: boolean;
  onEmailChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onRoleChange: (value: StaffRole) => void;
  onNameChange: (value: string) => void;
  onSpecialtyChange: (value: string) => void;
  onConsultationFeeChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

const roleGuidance: Record<StaffRole, { label: string; description: string }> = {
  DOCTOR: {
    label: "Tài khoản bác sĩ",
    description: "Được quản lý hồ sơ chuyên môn, lịch làm việc và các lượt khám được phân công.",
  },
  RECEPTIONIST: {
    label: "Tài khoản lễ tân",
    description: "Được tiếp nhận yêu cầu, đặt lịch hộ, check-in và hỗ trợ bệnh nhân.",
  },
  ADMIN: {
    label: "Tài khoản quản trị viên",
    description: "Có quyền quản trị nhân sự, bác sĩ, bệnh nhân và cấu hình vận hành phòng khám.",
  },
};

export default function AdminStaffCreateForm(props: Props) {
  const guidance = roleGuidance[props.role];
  const submitLabel = props.role === "DOCTOR" ? "Tạo tài khoản bác sĩ" : props.role === "RECEPTIONIST" ? "Tạo tài khoản lễ tân" : "Tạo quản trị viên";

  return <section className="admin-staff-create" aria-labelledby="admin-staff-create-title">
    <header>
      <div>
        <h2 id="admin-staff-create-title">Thêm nhân sự</h2>
        <p>Tạo thông tin đăng nhập riêng để phân quyền và ghi nhận chính xác người thao tác.</p>
      </div>
      <span className="admin-staff-create-mark"><UserPlus aria-hidden="true" />Tài khoản mới</span>
    </header>

    <form onSubmit={props.onSubmit} aria-busy={props.busy}>
      <section className="admin-staff-create-group" aria-labelledby="staff-access-heading">
        <div className="admin-staff-create-group-heading">
          <h3 id="staff-access-heading">Thông tin truy cập</h3>
          <p>Email đăng nhập và mật khẩu ban đầu của nhân viên.</p>
        </div>
        <div className="admin-staff-create-fields">
          <label>
            <span>Email</span>
            <input type="email" autoComplete="off" required value={props.email} onChange={event => props.onEmailChange(event.target.value)} placeholder="tennhanvien@dermai.vn" />
          </label>
          <label>
            <span>Mật khẩu ban đầu</span>
            <input type="password" autoComplete="new-password" minLength={10} required value={props.password} onChange={event => props.onPasswordChange(event.target.value)} placeholder="Tối thiểu 10 ký tự" />
            <small>Nhân viên nên đổi mật khẩu sau lần đăng nhập đầu tiên.</small>
          </label>
          <label>
            <span>Vai trò</span>
            <select value={props.role} onChange={event => props.onRoleChange(event.target.value as StaffRole)}>
              <option value="DOCTOR">Bác sĩ</option>
              <option value="RECEPTIONIST">Lễ tân</option>
              <option value="ADMIN">Quản trị viên</option>
            </select>
          </label>
          {props.role !== "ADMIN" && <label>
            <span>Họ tên nhân viên</span>
            <input required maxLength={150} value={props.name} onChange={event => props.onNameChange(event.target.value)} placeholder={props.role === "DOCTOR" ? "Ví dụ: Nguyễn Minh An" : "Ví dụ: Trần Thu Hà"} />
          </label>}
        </div>
      </section>

      {props.role === "DOCTOR" && <section className="admin-staff-create-group" aria-labelledby="doctor-setup-heading">
        <div className="admin-staff-create-group-heading">
          <h3 id="doctor-setup-heading">Thiết lập bác sĩ ban đầu</h3>
          <p>Thông tin này có thể tiếp tục cập nhật trong danh sách bác sĩ.</p>
        </div>
        <div className="admin-staff-create-fields">
          <label>
            <span>Chuyên môn</span>
            <input required maxLength={150} value={props.specialty} onChange={event => props.onSpecialtyChange(event.target.value)} placeholder="Ví dụ: Da liễu tổng quát" />
          </label>
          <label>
            <span>Giá khám cơ bản</span>
            <span className="admin-staff-money-field"><input type="number" inputMode="numeric" min="0" max="9999999999" step="1000" required value={props.consultationFee} onChange={event => props.onConsultationFeeChange(event.target.value)} /><em>đồng</em></span>
          </label>
        </div>
      </section>}

      <footer>
        <div className="admin-staff-role-note"><ShieldCheck aria-hidden="true" /><span><strong>{guidance.label}</strong><small>{guidance.description}</small></span></div>
        <button type="submit" className="primary" disabled={props.busy}>
          <UserPlus aria-hidden="true" />{props.busy ? "Đang tạo tài khoản..." : submitLabel}
        </button>
      </footer>
    </form>

    {props.message && <p className={`admin-staff-create-feedback ${props.failed ? "is-error" : "is-success"}`} role={props.failed ? "alert" : "status"}>{props.message}</p>}
  </section>;
}

import { useMemo, useState } from "react";
import { BadgeCheck, Search, Stethoscope, X } from "lucide-react";
import { formatVnd } from "../../core/currency";
import type { Doctor } from "../../core/types";
import AdminDoctorFeeEditor from "./AdminDoctorFeeEditor";

type Props = {
  token: string;
  doctors: Doctor[];
  selectedDoctorId: string;
  onSelectDoctor: (id: string) => void;
  onSaved: (doctor: Doctor) => void;
};

function specialtyLabel(doctor: Doctor) {
  return doctor.specialtyCode?.trim() || "Chưa khai báo chuyên môn";
}

export default function AdminDoctorsManagement({ token, doctors, selectedDoctorId, onSelectDoctor, onSaved }: Props) {
  const [query, setQuery] = useState("");
  const needle = query.trim().toLocaleLowerCase("vi-VN");
  const filteredDoctors = useMemo(() => doctors.filter(doctor => {
    if (!needle) return true;
    return `${doctor.fullName} ${doctor.specialtyCode || ""} ${doctor.certificateNo || ""}`
      .toLocaleLowerCase("vi-VN")
      .includes(needle);
  }), [doctors, needle]);
  const selectedDoctor = doctors.find(doctor => doctor.id === selectedDoctorId);
  const configuredFeeCount = doctors.filter(doctor => Number.isFinite(doctor.consultationFee) && doctor.consultationFee >= 0).length;

  return <section className="admin-doctors-page" aria-labelledby="admin-doctors-title">
    <header className="admin-doctors-heading">
      <div>
        <h2 id="admin-doctors-title">Đội ngũ bác sĩ</h2>
        <p>Tra cứu hồ sơ nghề nghiệp và cấu hình mức giá áp dụng cho các lượt đặt lịch mới.</p>
      </div>
      <div className="admin-doctors-summary" aria-label="Tổng hợp hồ sơ bác sĩ">
        <span><strong>{doctors.length}</strong> hồ sơ</span>
        <span><strong>{configuredFeeCount}</strong> đã có giá khám</span>
      </div>
    </header>

    <div className="admin-doctors-toolbar">
      <label htmlFor="admin-doctor-search">Tìm bác sĩ</label>
      <div><Search aria-hidden="true" /><input id="admin-doctor-search" type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Nhập tên, chuyên môn hoặc số chứng chỉ" /></div>
    </div>

    <div className="admin-doctors-layout">
      <nav className="admin-doctors-list" aria-label="Danh sách bác sĩ">
        <header><strong>Danh sách bác sĩ</strong><span>{filteredDoctors.length}</span></header>
        {filteredDoctors.length === 0 ? <div className="admin-doctors-list-empty"><Stethoscope aria-hidden="true" /><strong>{doctors.length === 0 ? "Chưa có hồ sơ bác sĩ" : "Không tìm thấy bác sĩ"}</strong><p>{doctors.length === 0 ? "Hồ sơ được tạo từ mục Nhân sự sẽ xuất hiện tại đây." : "Thử tìm bằng tên hoặc chuyên môn khác."}</p>{doctors.length > 0 && query && <button type="button" onClick={() => setQuery("")}>Xóa tìm kiếm</button>}</div> : filteredDoctors.map(doctor => <button
          type="button"
          key={doctor.id}
          className={selectedDoctorId === doctor.id ? "is-selected" : ""}
          aria-current={selectedDoctorId === doctor.id ? "true" : undefined}
          onClick={() => onSelectDoctor(doctor.id)}
        >
          {doctor.avatarUrl ? <img src={doctor.avatarUrl} alt="" /> : <span className="admin-doctor-avatar" aria-hidden="true">{doctor.fullName.slice(0, 1).toUpperCase()}</span>}
          <span className="admin-doctor-list-identity"><strong>BS. {doctor.fullName}</strong><small>{specialtyLabel(doctor)}</small><em>{doctor.experienceYears} năm kinh nghiệm</em></span>
          <span className="admin-doctor-list-fee"><small>Giá khám</small><strong>{formatVnd(doctor.consultationFee)}</strong></span>
        </button>)}
      </nav>

      {selectedDoctor ? <article className="admin-doctor-detail">
        <header>
          <div className="admin-doctor-detail-identity">
            {selectedDoctor.avatarUrl ? <img src={selectedDoctor.avatarUrl} alt="" /> : <span className="admin-doctor-avatar" aria-hidden="true">{selectedDoctor.fullName.slice(0, 1).toUpperCase()}</span>}
            <div><small>Hồ sơ nghề nghiệp</small><h3>BS. {selectedDoctor.fullName}</h3><p>{specialtyLabel(selectedDoctor)}</p></div>
          </div>
          <button type="button" aria-label="Đóng hồ sơ bác sĩ" onClick={() => onSelectDoctor("")}><X aria-hidden="true" /></button>
        </header>

        <dl>
          <div><dt>Chuyên môn</dt><dd>{specialtyLabel(selectedDoctor)}</dd></div>
          <div><dt>Kinh nghiệm</dt><dd>{selectedDoctor.experienceYears} năm</dd></div>
          <div><dt>Chứng chỉ</dt><dd>{selectedDoctor.certificateNo || "Chưa khai báo"}</dd></div>
        </dl>

        <section className="admin-doctor-bio-section" aria-labelledby={`admin-doctor-bio-${selectedDoctor.id}`}>
          <h4 id={`admin-doctor-bio-${selectedDoctor.id}`}><BadgeCheck aria-hidden="true" />Giới thiệu chuyên môn</h4>
          <p>{selectedDoctor.bio?.trim() || "Bác sĩ chưa cập nhật phần giới thiệu chuyên môn."}</p>
        </section>

        <AdminDoctorFeeEditor doctor={selectedDoctor} token={token} onSaved={onSaved} />
      </article> : <div className="admin-doctor-detail-empty"><Stethoscope aria-hidden="true" /><strong>Chọn một bác sĩ</strong><p>Hồ sơ nghề nghiệp và cấu hình giá khám sẽ xuất hiện tại đây.</p></div>}
    </div>
  </section>;
}

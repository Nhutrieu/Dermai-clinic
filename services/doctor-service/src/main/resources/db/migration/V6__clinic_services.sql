CREATE TABLE clinic_services (
  id uuid PRIMARY KEY,
  code varchar(80) UNIQUE NOT NULL,
  name varchar(160) NOT NULL,
  description varchar(1000) NOT NULL,
  price_from numeric(12, 0) NOT NULL CHECK (price_from >= 0),
  duration_minutes int NOT NULL CHECK (duration_minutes BETWEEN 10 AND 240),
  display_order int NOT NULL DEFAULT 0,
  active boolean NOT NULL DEFAULT true
);

INSERT INTO clinic_services(id, code, name, description, price_from, duration_minutes, display_order) VALUES
('9c121521-0475-4a4c-a378-cd2a96ef31f1', 'DERM_EXAM', 'Khám da liễu chuyên sâu', 'Bác sĩ thăm khám, đánh giá tiền sử và xây dựng hướng chăm sóc phù hợp.', 150000, 30, 1),
('645559da-2625-44aa-8197-f8d35c11f2d2', 'ACNE', 'Điều trị mụn', 'Đánh giá tình trạng mụn, nguyên nhân và theo dõi đáp ứng theo từng giai đoạn.', 300000, 30, 2),
('664ca75a-9286-4ef9-b798-7bf20a15c18c', 'PIGMENT', 'Nám & sắc tố', 'Phân tích sắc tố và tư vấn liệu trình cá nhân hóa dưới sự theo dõi của bác sĩ.', 500000, 45, 3),
('a1fe780d-83e4-4bd7-b36a-77fd83b85ff9', 'REJUVENATION', 'Trẻ hóa làn da', 'Đánh giá cấu trúc da và tư vấn giải pháp cải thiện độ đàn hồi, bề mặt da.', 700000, 45, 4);

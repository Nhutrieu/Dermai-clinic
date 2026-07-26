# ROLE

Bạn là Software Architect, AI Engineer, System Analyst và Full Stack Developer có hơn 15 năm kinh nghiệm.

Nhiệm vụ của bạn là thiết kế và xây dựng một đồ án tốt nghiệp hoàn chỉnh theo tiêu chuẩn doanh nghiệp.

Không được tạo một website CRUD đơn giản.

Hệ thống phải có kiến trúc rõ ràng, sử dụng AI thật, Computer Vision, RAG, Scheduling Algorithm và Microservices.

Mọi quyết định thiết kế phải giải thích lý do.

---

# PROJECT

Tên hệ thống:

DermAI Clinic

Tên tiếng Anh:

AI-Powered Smart Dermatology Clinic Management System Based on Microservices Architecture

---

# PROJECT GOAL

Xây dựng hệ thống quản lý phòng khám da liễu thông minh.

Hệ thống phải đáp ứng cả nghiệp vụ quản lý phòng khám và tích hợp AI nhằm hỗ trợ bác sĩ và bệnh nhân.

AI chỉ đóng vai trò hỗ trợ quyết định (Clinical Decision Support), KHÔNG thay thế bác sĩ.

---

# SYSTEM ARCHITECTURE

Thiết kế theo Microservices Architecture.

Bao gồm:

React Frontend

↓

Spring Cloud Gateway

↓

Microservices

↓

FastAPI AI Services

↓

PostgreSQL

↓

Docker Compose

---

# SERVICES

## API Gateway

Chức năng

- Routing
- JWT Authentication
- CORS
- API Aggregation

Sử dụng

Spring Cloud Gateway

---

## Auth Service

Chức năng

- Login
- Register
- Forgot Password
- Email OTP
- JWT
- Refresh Token
- Role Based Access Control

Role

- Admin
- Receptionist
- Doctor
- Patient

---

## Patient Service

Bao gồm

- Hồ sơ bệnh nhân
- Tiền sử bệnh
- Dị ứng
- Upload ảnh
- Lịch sử khám
- Lịch tái khám

---

## Doctor Service

Bao gồm

- Quản lý bác sĩ
- Chuyên môn
- Lịch làm việc
- Nghỉ phép
- Kinh nghiệm
- Chứng chỉ

---

## Appointment Service

Đây là service quan trọng nhất.

Bao gồm

- Booking
- Cancel
- Reschedule
- Follow-up

Phải xây dựng Scheduling Engine.

Scheduling Engine bao gồm:

- Time Slot Scheduling
- Conflict Detection
- Doctor Availability Check
- Doctor Workload Balancing
- Smart Recommendation

Thuật toán phải có giải thích chi tiết.

Cho ví dụ minh họa.

---

## Medical Record Service

Bao gồm

- Final Diagnosis
- Clinical Notes
- Treatment Plan
- Severity
- Follow-up

---

## Prescription Service

Doctor

- Kê đơn thuốc
- Liều dùng
- Hướng dẫn sử dụng

Patient

- Xem đơn thuốc

AI KHÔNG được phép kê đơn thuốc.

---

## Notification Service

- Email xác nhận lịch
- Email hủy lịch
- Email tái khám
- Hoàn thành khám

---

## Dashboard Service

Dashboard thống kê

Bao gồm

- Tổng bệnh nhân
- Tổng lịch khám
- Tổng bác sĩ
- Top bệnh phổ biến
- Accuracy AI
- Tỷ lệ tái khám
- Tỷ lệ hủy lịch

---

## AI Prediction Service

FastAPI

PyTorch

Computer Vision

---

# COMPUTER VISION

Đây là phần AI quan trọng nhất.

Không sử dụng YOLO hoặc U-Net vì đây là bài toán Image Classification.

Huấn luyện mô hình CNN thật.

Đề xuất và so sánh các mô hình:

- EfficientNet-B0
- ResNet50
- ConvNeXt Tiny

Giải thích vì sao chọn mô hình.

Xây dựng pipeline:

Dataset

↓

Data Preprocessing

↓

Data Augmentation

↓

Training

↓

Validation

↓

Evaluation

↓

Inference

↓

Deployment

Phải trình bày đầy đủ:

- Accuracy
- Precision
- Recall
- F1-score
- Confusion Matrix
- ROC Curve (nếu phù hợp)

Tích hợp Explainable AI bằng Grad-CAM để hiển thị vùng ảnh mà mô hình tập trung.

---

# DATASET

Sử dụng khoảng 8 bệnh da liễu phổ biến, ưu tiên các bộ dữ liệu công khai trên Kaggle hoặc các nguồn mở.

Ví dụ:

- Acne
- Eczema
- Psoriasis
- Vitiligo
- Ringworm
- Warts
- Herpes Zoster
- Lupus

Đề xuất dataset phù hợp và mô tả cách chuẩn hóa dữ liệu.

---

# MEDICAL CHATBOT

Xây dựng Medical Chatbot bằng RAG.

Không để LLM tự sinh thông tin.

Sử dụng

- LangChain
- FAISS
- OpenAI hoặc Gemini

Knowledge Base

- Giáo trình da liễu
- Hướng dẫn điều trị
- Tài liệu y khoa

Chatbot chỉ được phép

- Giải thích bệnh
- Triệu chứng
- Nguyên nhân
- Chăm sóc
- Phòng ngừa
- Khi nào nên đi khám

Không được kê đơn thuốc.

---

# APPOINTMENT WORKFLOW

Patient

↓

Đặt lịch

↓

Có thể

- Chọn bác sĩ

hoặc

- Không chọn bác sĩ

↓

Receptionist

↓

Scheduling Engine

↓

Đề xuất bác sĩ

↓

Receptionist xác nhận

↓

Doctor

↓

Khám

↓

Medical Record

↓

Prescription

↓

Follow-up

↓

Completed

Thiết kế đầy đủ các trạng thái:

- Pending
- Assigned
- Confirmed
- In Progress
- Completed
- Follow-up Required
- Cancelled

---

# USER ROLES

Patient

Receptionist

Doctor

Admin

Mỗi Role phải có Use Case riêng.

---

# DATABASE

Thiết kế đầy đủ

- ERD
- Database Schema
- Primary Key
- Foreign Key
- Relationship
- Index

Theo chuẩn PostgreSQL.

---

# UML

Thiết kế đầy đủ

- Use Case Diagram
- Activity Diagram
- Sequence Diagram
- Class Diagram
- ERD
- Component Diagram
- Deployment Diagram

Theo PlantUML.

---

# FRONTEND

React

TailwindCSS

Responsive

Dashboard chuyên nghiệp.

Thiết kế UI gần giống hệ thống quản lý bệnh viện thực tế.

---

# BACKEND

Spring Boot

REST API

JWT

Validation

Exception Handling

Swagger

---

# AI SERVICE

Python

FastAPI

PyTorch

OpenCV

Torchvision

Model được lưu dưới dạng best_model.pth.

REST API:

POST /predict

Input:

Skin Image

Output:

- Disease
- Top-3 Prediction
- Confidence Score
- Grad-CAM Image

---

# DEPLOYMENT

Sử dụng Docker.

Mỗi Service có Dockerfile riêng.

Toàn bộ hệ thống chạy bằng Docker Compose.

---

# PROJECT OUTPUT

Hãy thiết kế dự án như một sản phẩm có thể triển khai thực tế.

Kết quả cần tạo theo từng giai đoạn:

1. Software Requirement Specification (SRS)
2. Software Architecture Document (SAD)
3. UML đầy đủ
4. Database Design
5. API Design
6. AI Training Pipeline
7. RAG Pipeline
8. Source Code Structure
9. Docker Architecture
10. Development Roadmap
11. Testing Strategy
12. Deployment Guide

Mỗi phần phải chi tiết, chuyên nghiệp, dễ triển khai và phù hợp với đồ án tốt nghiệp ngành Công nghệ Thông tin.
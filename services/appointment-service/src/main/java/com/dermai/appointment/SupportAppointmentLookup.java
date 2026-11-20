package com.dermai.appointment;

import java.math.BigDecimal;
import java.time.*;
import java.time.format.DateTimeFormatter;
import java.text.NumberFormat;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

@Service
class SupportAppointmentLookup {
 private static final ZoneId ZONE=ZoneId.of("Asia/Ho_Chi_Minh");
 private final AppointmentRepository appointments;
 private final SchedulingRecommendationService scheduling;
 private final RestClient payments;
 SupportAppointmentLookup(AppointmentRepository appointments,SchedulingRecommendationService scheduling,RestClient.Builder builder,
   @Value("${payment-service.url:http://payment-service:8089}") String paymentUrl){
  this.appointments=appointments;this.scheduling=scheduling;this.payments=builder.baseUrl(paymentUrl).build();
 }
 String answer(UUID patientIdentityId,String authorization){
  var visible=appointments.findByPatientIdentityIdOrderByStartAtDesc(patientIdentityId).stream()
   .filter(a->patientIdentityId.equals(a.patientIdentityId)&&!a.patientHidden&&a.status!=AppointmentStatus.HELD).toList();
  Instant now=Instant.now();
  var upcoming=visible.stream().filter(a->EnumSet.of(AppointmentStatus.PROPOSED,AppointmentStatus.PENDING,AppointmentStatus.ASSIGNED,
   AppointmentStatus.PENDING_PAYMENT,AppointmentStatus.PENDING_CONFIRMATION,AppointmentStatus.CONFIRMED,AppointmentStatus.CHECKED_IN,AppointmentStatus.IN_PROGRESS).contains(a.status))
   .filter(a->a.endAt.isAfter(now)||a.status==AppointmentStatus.IN_PROGRESS||a.status==AppointmentStatus.CHECKED_IN)
   .sorted(Comparator.comparing(a->a.startAt)).toList();
  if(visible.isEmpty())return "Bạn chưa có lịch khám đã đặt. Bạn có thể hỏi giờ trống của bác sĩ để chọn lịch mới.";
  var selected=(upcoming.isEmpty()?visible:upcoming).stream().limit(3).toList();
  Map<UUID,String> names=new HashMap<>();
  try{for(var doctor:scheduling.lookupDoctorProfiles(null,authorization,"PATIENT").profiles())names.put(doctor.doctorId(),doctor.doctorName());}
  catch(RuntimeException ignored){ /* Keep real appointments visible if the directory is unavailable. */ }
  StringBuilder answer=new StringBuilder(upcoming.isEmpty()?"Bạn không có lịch khám sắp tới. Các lịch gần đây:":"Lịch khám sắp tới của bạn:");
  for(var a:selected){
   String doctor=a.doctorId==null?"Chưa phân công bác sĩ":names.containsKey(a.doctorId)?"Bác sĩ "+names.get(a.doctorId):"Bác sĩ: chưa tải được tên";
   answer.append("\n• ").append(a.startAt.atZone(ZONE).format(DateTimeFormatter.ofPattern("HH:mm dd/MM/yyyy")))
    .append(" – ").append(doctor).append("\n  ").append(status(a.status)).append(" · ").append(deposit(a,patientIdentityId));
  }
  return answer.append("\nThông tin tại thời điểm tra cứu (giờ Việt Nam). Mở Lịch đã đặt để xem chi tiết.").toString();
 }
 private String deposit(Appointment a,UUID patient){
  if(a.status==AppointmentStatus.PROPOSED)return "Đề nghị lịch chờ bạn xác nhận";
  try{
   var p=payments.get().uri("/api/v1/payments/booking/{id}",a.id)
    .header("X-User-Id",patient.toString()).header("X-User-Role","PATIENT").retrieve().body(Deposit.class);
   if(p==null)return "Chưa tải được trạng thái cọc";
   String amount=p.amount()==null?"": " "+NumberFormat.getIntegerInstance(Locale.forLanguageTag("vi-VN")).format(p.amount())+" đ";
   return switch(p.status()){
    case "SUCCESS" -> "Đã cọc"+amount;
    case "REFUND_REQUESTED" -> "Đang chờ hoàn cọc"+amount;
    case "REFUNDED" -> "Đã hoàn cọc";
    case "CREATING","PENDING" -> "Chưa thanh toán cọc"+amount;
    case "CANCEL_REQUESTED" -> "Đang hủy thanh toán cọc";
    case "EXPIRED" -> "Thanh toán cọc hết hạn";
    case "CANCELLED" -> "Đã hủy thanh toán cọc";
    case "FAILED" -> "Thanh toán cọc thất bại";
    default -> "Chưa xác định trạng thái cọc";
   };
  }catch(HttpClientErrorException.NotFound missing){return "Chưa có giao dịch cọc";}
  catch(RestClientException error){return "Chưa tải được trạng thái cọc";}
 }
 private String status(AppointmentStatus status){return switch(status){
  case PROPOSED -> "Chờ xác nhận đề nghị";case PENDING,ASSIGNED -> "Chờ tiếp nhận";
  case PENDING_PAYMENT -> "Chờ thanh toán";case PENDING_CONFIRMATION -> "Chờ lễ tân xác nhận";
  case CONFIRMED -> "Đã xác nhận";case CHECKED_IN -> "Đã check-in";case IN_PROGRESS -> "Đang khám";
  case COMPLETED -> "Đã khám xong";case FOLLOW_UP_REQUIRED -> "Cần tái khám";
  case CANCELLED -> "Đã hủy";case CANCELLED_EXPIRED -> "Đã hủy do hết hạn";case NO_SHOW -> "Không đến khám";
  default -> "Đang giữ chỗ";
 };}
 record Deposit(String status,BigDecimal amount){}
}

package com.dermai.appointment;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

import java.time.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.http.HttpStatus;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

class SupportAppointmentLookupTest {
 final AppointmentRepository repo=mock(AppointmentRepository.class);
 final SchedulingRecommendationService scheduling=mock(SchedulingRecommendationService.class);
 final RestClient.Builder builder=RestClient.builder();
 final MockRestServiceServer server=MockRestServiceServer.bindTo(builder).build();
 final SupportAppointmentLookup lookup=new SupportAppointmentLookup(repo,scheduling,builder,"http://payments");
 final UUID patient=UUID.randomUUID();
 final UUID doctor=UUID.randomUUID();
 Appointment appointment(UUID owner,int days,AppointmentStatus status){
  Instant start=LocalDate.now(ZoneId.of("Asia/Ho_Chi_Minh")).plusDays(days).atTime(9,0).atZone(ZoneId.of("Asia/Ho_Chi_Minh")).toInstant();
  var a=Appointment.pending(UUID.randomUUID(),owner,doctor,UUID.randomUUID(),start,start.plusSeconds(1800),"Khám",null,null);
  a.status=status;return a;
 }
 void directory(){
  var profile=new SchedulingRecommendationService.DoctorProfile(doctor,"Bình","Da liễu",5,null,null,null);
  when(scheduling.lookupDoctorProfiles(null,"Bearer token","PATIENT")).thenReturn(new SchedulingRecommendationService.DoctorProfileLookup("ALL",List.of(profile),List.of()));
 }
 @Test void showsOnlyOwnVisibleAppointmentsSortedSoonestWithRealDeposit(){
  var later=appointment(patient,3,AppointmentStatus.PENDING_PAYMENT);var soon=appointment(patient,1,AppointmentStatus.PENDING_CONFIRMATION);
  var other=appointment(UUID.randomUUID(),1,AppointmentStatus.CONFIRMED);var hidden=appointment(patient,1,AppointmentStatus.CONFIRMED);hidden.patientHidden=true;
  var held=appointment(patient,1,AppointmentStatus.HELD);var cancelled=appointment(patient,1,AppointmentStatus.CANCELLED);
  when(repo.findByPatientIdentityIdOrderByStartAtDesc(patient)).thenReturn(List.of(later,other,hidden,held,cancelled,soon));directory();
  server.expect(requestTo("http://payments/api/v1/payments/booking/"+soon.id)).andExpect(header("X-User-Id",patient.toString()))
   .andExpect(header("X-User-Role","PATIENT")).andRespond(withSuccess("{\"status\":\"SUCCESS\",\"amount\":100000}",MediaType.APPLICATION_JSON));
  server.expect(requestTo("http://payments/api/v1/payments/booking/"+later.id)).andRespond(withSuccess("{\"status\":\"PENDING\",\"amount\":100000}",MediaType.APPLICATION_JSON));
  String result=lookup.answer(patient,"Bearer token");
  assertThat(result).contains("Bác sĩ Bình","Đã cọc 100.000 đ","Chưa thanh toán cọc 100.000 đ","Chờ lễ tân xác nhận");
  assertThat(result.indexOf("Đã cọc")).isLessThan(result.indexOf("Chưa thanh toán cọc"));
  assertThat(result).doesNotContain("Đã hủy","Đang giữ chỗ");server.verify();
 }
 @Test void missingPaymentAndUnavailablePaymentAreDifferent(){
  var soon=appointment(patient,1,AppointmentStatus.CONFIRMED);var later=appointment(patient,2,AppointmentStatus.PENDING_PAYMENT);
  when(repo.findByPatientIdentityIdOrderByStartAtDesc(patient)).thenReturn(List.of(later,soon));directory();
  server.expect(requestTo("http://payments/api/v1/payments/booking/"+soon.id)).andRespond(withStatus(HttpStatus.NOT_FOUND));
  server.expect(requestTo("http://payments/api/v1/payments/booking/"+later.id)).andRespond(withStatus(HttpStatus.SERVICE_UNAVAILABLE));
  assertThat(lookup.answer(patient,"Bearer token")).contains("Chưa có giao dịch cọc","Chưa tải được trạng thái cọc").doesNotContain("Đã cọc");server.verify();
 }
 @Test void noBookingsDoesNotQueryPaymentsOrDoctorDirectory(){
  when(repo.findByPatientIdentityIdOrderByStartAtDesc(patient)).thenReturn(List.of());
  assertThat(lookup.answer(patient,"Bearer token")).contains("chưa có lịch khám");
  verifyNoInteractions(scheduling);server.verify();
 }
 @Test void noUpcomingBookingsShowsRecentHistoryAndRefundStatus(){
  var old=appointment(patient,-1,AppointmentStatus.CANCELLED);
  when(repo.findByPatientIdentityIdOrderByStartAtDesc(patient)).thenReturn(List.of(old));directory();
  server.expect(requestTo("http://payments/api/v1/payments/booking/"+old.id)).andRespond(withSuccess("{\"status\":\"REFUND_REQUESTED\",\"amount\":100000}",MediaType.APPLICATION_JSON));
  assertThat(lookup.answer(patient,"Bearer token")).contains("không có lịch khám sắp tới","Đã hủy","Đang chờ hoàn cọc");server.verify();
 }
}

package com.dermai.appointment;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import java.time.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

class SupportAssistantServiceTest {
 @Test void mandatoryIntentPersistsTranscriptAndEscalatesAutomatically(){
  var fixture=new Fixture();var patient=UUID.randomUUID();
  when(fixture.ai.classify(anyString())).thenReturn(new SupportAiClient.Decision("Cần lễ tân xử lý.","CANCEL_APPOINTMENT",true,"Yêu cầu hủy lịch",.96,false,null,null,null));
  when(fixture.conversations.failureCount(patient)).thenReturn(0);
  when(fixture.conversations.lastIntent(patient)).thenReturn(null);
  when(fixture.conversations.recordAiTurn(eq(patient),eq("CANCEL_APPOINTMENT"),anyDouble(),eq(0),eq(true),anyString(),eq("MANDATORY_CANCEL_APPOINTMENT"))).thenReturn(fixture.state(patient,"WAITING_RECEPTIONIST"));

  var result=fixture.service.process(patient,"PATIENT","Bearer token","Tôi muốn hủy lịch");

  assertThat(result.escalated()).isTrue();
  var saved=ArgumentCaptor.forClass(SupportMessage.class);verify(fixture.messages,times(3)).save(saved.capture());
  assertThat(saved.getAllValues()).extracting(item->item.senderRole).containsExactly("PATIENT","AI","SYSTEM");
  verify(fixture.updates).chatChanged();
 }

 @Test void secondUnresolvedAttemptEscalatesWithoutAskingPatientAgain(){
  var fixture=new Fixture();var patient=UUID.randomUUID();
  when(fixture.ai.classify(anyString())).thenReturn(new SupportAiClient.Decision("Bạn mô tả thêm lỗi đang thấy nhé.","APPOINTMENT_TECHNICAL_ISSUE",false,"Chưa đủ dữ liệu",.82,true,null,null,null));
  when(fixture.conversations.failureCount(patient)).thenReturn(1);
  when(fixture.conversations.lastIntent(patient)).thenReturn("APPOINTMENT_TECHNICAL_ISSUE");
  when(fixture.conversations.recordAiTurn(eq(patient),anyString(),anyDouble(),eq(2),eq(true),anyString(),eq("REPEATED_FAILURE"))).thenReturn(fixture.state(patient,"WAITING_RECEPTIONIST"));

  var result=fixture.service.process(patient,"PATIENT",null,"Sao vẫn không được?");

  assertThat(result.escalated()).isTrue();
  assertThat(result.escalationReason()).isEqualTo("REPEATED_FAILURE");
 }

 @Test void availabilityAnswerUsesSchedulingSourceOfTruth(){
  var fixture=new Fixture();var patient=UUID.randomUUID();var doctor=UUID.randomUUID();var identity=UUID.randomUUID();
  var start=ZonedDateTime.of(LocalDate.of(2026,8,12),LocalTime.of(9,0),ZoneId.of("Asia/Ho_Chi_Minh")).toInstant();
  var slot=new SchedulingRecommendationService.AvailabilityItem(doctor,identity,"Bình","DERMATOLOGY",start,start.plusSeconds(1800),"AVAILABLE",null,null);
  when(fixture.ai.classify(anyString())).thenReturn(new SupportAiClient.Decision("Đang tra cứu","DOCTOR_AVAILABILITY",false,"Tra lịch",.94,false,"Bình","2026-08-12",null));
  when(fixture.conversations.failureCount(patient)).thenReturn(0);
  when(fixture.conversations.lastIntent(patient)).thenReturn(null);
  when(fixture.scheduling.lookupAvailability("Bình",LocalDate.of(2026,8,12),patient,"Bearer token","PATIENT")).thenReturn(new SchedulingRecommendationService.AvailabilityLookup("FOUND","Bình",LocalDate.of(2026,8,12),List.of(slot),List.of()));
  when(fixture.conversations.recordAiTurn(eq(patient),anyString(),anyDouble(),eq(0),eq(false),anyString(),isNull())).thenReturn(fixture.state(patient,"AI_ACTIVE"));

  var result=fixture.service.process(patient,"PATIENT","Bearer token","Lịch bác sĩ Bình ngày 12/08/2026");

  assertThat(result.answer()).contains("09:00").contains("Bác sĩ Bình");
  assertThat(result.bookingOptions()).containsExactly(new SupportBookingOption(doctor,"Bình",start,start.plusSeconds(1800)));
  var saved=ArgumentCaptor.forClass(SupportMessage.class);
  verify(fixture.messages,times(2)).save(saved.capture());
  assertThat(saved.getAllValues().get(1).bookingOptions).isEqualTo(result.bookingOptions());
  assertThat(result.escalated()).isFalse();
 }

 @Test void clinicClosureAnswerUsesTheSchedulingSourceOfTruth(){
  var fixture=new Fixture();var patient=UUID.randomUUID();
  when(fixture.ai.classify(anyString())).thenReturn(new SupportAiClient.Decision("Đang tra cứu","CLINIC_CLOSURE",false,"Tra lịch nghỉ",.96,false,null,"2026-09-02",null));
  when(fixture.conversations.failureCount(patient)).thenReturn(0);
  when(fixture.conversations.lastIntent(patient)).thenReturn(null);
  when(fixture.scheduling.lookupClinicClosure(LocalDate.of(2026,9,2))).thenReturn(new SchedulingRecommendationService.ClinicClosureLookup(LocalDate.of(2026,9,2),true,"Quốc khánh"));
  when(fixture.conversations.recordAiTurn(eq(patient),eq("CLINIC_CLOSURE"),anyDouble(),eq(0),eq(false),anyString(),isNull())).thenReturn(fixture.state(patient,"AI_ACTIVE"));

  var result=fixture.service.process(patient,"PATIENT","Bearer token","Phòng khám có nghỉ ngày 2/9 không?");

  assertThat(result.answer()).contains("nghỉ ngày 02/09/2026").contains("Quốc khánh");
  assertThat(result.escalated()).isFalse();
 }

 @Test void doctorLeaveScheduleAnswerUsesApprovedLeavePeriods(){
  var fixture=new Fixture();var patient=UUID.randomUUID();
  var start=ZonedDateTime.of(LocalDate.of(2026,9,3),LocalTime.of(8,0),ZoneId.of("Asia/Ho_Chi_Minh")).toInstant();
  var end=start.plusSeconds(8*3600);
  when(fixture.ai.classify(anyString())).thenReturn(new SupportAiClient.Decision("Đang tra cứu","DOCTOR_LEAVE_SCHEDULE",false,"Tra lịch nghỉ",.94,false,"Bình",null,null));
  when(fixture.conversations.failureCount(patient)).thenReturn(0);
  when(fixture.conversations.lastIntent(patient)).thenReturn(null);
  when(fixture.scheduling.lookupDoctorLeavePeriods("Bình","Bearer token","PATIENT")).thenReturn(new SchedulingRecommendationService.DoctorLeavePeriodLookup("FOUND","Bình",List.of(new SchedulingRecommendationService.DoctorLeavePeriod(start,end)),List.of()));
  when(fixture.conversations.recordAiTurn(eq(patient),eq("DOCTOR_LEAVE_SCHEDULE"),anyDouble(),eq(0),eq(false),anyString(),isNull())).thenReturn(fixture.state(patient,"AI_ACTIVE"));

  var result=fixture.service.process(patient,"PATIENT","Bearer token","Bác sĩ Bình có nghỉ ngày nào không?");

  assertThat(result.answer()).contains("Bác sĩ Bình").contains("03/09/2026 08:00");
  assertThat(result.escalated()).isFalse();
 }

 @Test void availabilityAnswerChecksTheRequestedTimeExactly(){
  var fixture=new Fixture();var patient=UUID.randomUUID();var doctor=UUID.randomUUID();var identity=UUID.randomUUID();
  var start=ZonedDateTime.of(LocalDate.of(2026,8,14),LocalTime.of(9,0),ZoneId.of("Asia/Ho_Chi_Minh")).toInstant();
  var slot=new SchedulingRecommendationService.AvailabilityItem(doctor,identity,"Bình","DERMATOLOGY",start,start.plusSeconds(1800),"AVAILABLE",null,null);
  when(fixture.ai.classify(anyString())).thenReturn(new SupportAiClient.Decision("Đang tra cứu","DOCTOR_AVAILABILITY",false,"Tra lịch",.94,false,"Bình","2026-08-14","09:00"));
  when(fixture.conversations.failureCount(patient)).thenReturn(0);
  when(fixture.conversations.lastIntent(patient)).thenReturn(null);
  when(fixture.scheduling.lookupAvailability("Bình",LocalDate.of(2026,8,14),patient,"Bearer token","PATIENT")).thenReturn(new SchedulingRecommendationService.AvailabilityLookup("FOUND","Bình",LocalDate.of(2026,8,14),List.of(slot),List.of()));
  when(fixture.conversations.recordAiTurn(eq(patient),anyString(),anyDouble(),eq(0),eq(false),anyString(),isNull())).thenReturn(fixture.state(patient,"AI_ACTIVE"));

  var result=fixture.service.process(patient,"PATIENT","Bearer token","Xem lịch bác sĩ ngày 14/8 lúc 9h bác sĩ Bình");

  assertThat(result.answer()).contains("09:00").contains("hiện còn trống");
  assertThat(result.escalated()).isFalse();
 }

 @Test void availabilityAnswerExplainsApprovedDoctorLeave(){
  var fixture=new Fixture();var patient=UUID.randomUUID();var doctor=UUID.randomUUID();var identity=UUID.randomUUID();
  var start=ZonedDateTime.of(LocalDate.of(2026,8,14),LocalTime.of(9,0),ZoneId.of("Asia/Ho_Chi_Minh")).toInstant();
  var leaveSlot=new SchedulingRecommendationService.AvailabilityItem(doctor,identity,"Bình","DERMATOLOGY",start,start.plusSeconds(1800),"ON_LEAVE",null,null);
  when(fixture.ai.classify(anyString())).thenReturn(new SupportAiClient.Decision("Đang tra cứu","DOCTOR_AVAILABILITY",false,"Tra lịch",.94,false,"Bình","2026-08-14","09:00"));
  when(fixture.conversations.failureCount(patient)).thenReturn(0);
  when(fixture.conversations.lastIntent(patient)).thenReturn(null);
  when(fixture.scheduling.lookupAvailability("Bình",LocalDate.of(2026,8,14),patient,"Bearer token","PATIENT")).thenReturn(new SchedulingRecommendationService.AvailabilityLookup("NO_SLOTS","Bình",LocalDate.of(2026,8,14),List.of(),List.of(),true,List.of(leaveSlot)));
  when(fixture.conversations.recordAiTurn(eq(patient),anyString(),anyDouble(),eq(0),eq(false),anyString(),isNull())).thenReturn(fixture.state(patient,"AI_ACTIVE"));

  var result=fixture.service.process(patient,"PATIENT","Bearer token","Bác sĩ Bình nghỉ ngày 14/8 lúc 9h không?");

  assertThat(result.answer()).contains("nghỉ").contains("admin").contains("chọn ngày khác");
  assertThat(result.escalated()).isFalse();
 }

 @Test void unavailableRequestedTimeReturnsNearestRealSlots(){
  var fixture=new Fixture();var patient=UUID.randomUUID();var doctor=UUID.randomUUID();var identity=UUID.randomUUID();
  var nearby=ZonedDateTime.of(LocalDate.of(2026,8,14),LocalTime.of(9,30),ZoneId.of("Asia/Ho_Chi_Minh")).toInstant();
  var slot=new SchedulingRecommendationService.AvailabilityItem(doctor,identity,"Bình","DERMATOLOGY",nearby,nearby.plusSeconds(1800),"AVAILABLE",null,null);
  when(fixture.ai.classify(anyString())).thenReturn(new SupportAiClient.Decision("Đang tra cứu","DOCTOR_AVAILABILITY",false,"Tra lịch",.94,false,"Bình","2026-08-14","09:00"));
  when(fixture.conversations.failureCount(patient)).thenReturn(0);
  when(fixture.conversations.lastIntent(patient)).thenReturn(null);
  when(fixture.scheduling.lookupAvailability("Bình",LocalDate.of(2026,8,14),patient,"Bearer token","PATIENT")).thenReturn(new SchedulingRecommendationService.AvailabilityLookup("FOUND","Bình",LocalDate.of(2026,8,14),List.of(slot),List.of()));
  when(fixture.conversations.recordAiTurn(eq(patient),anyString(),anyDouble(),eq(0),eq(false),anyString(),isNull())).thenReturn(fixture.state(patient,"AI_ACTIVE"));

  var result=fixture.service.process(patient,"PATIENT","Bearer token","Bác sĩ Bình có lịch lúc 9h ngày 14/8 không?");

  assertThat(result.answer()).contains("09:00").contains("không còn trống").contains("09:30");
  assertThat(result.escalated()).isFalse();
 }

 @Test void availabilityFollowUpUsesStoredFieldsWithoutReplayingThePreviousQuestion(){
  var fixture=new Fixture();var patient=UUID.randomUUID();
  var context=new SupportLookupContext("DOCTOR_AVAILABILITY","Bình",null,"08:00");
  when(fixture.conversations.lookupContext(patient)).thenReturn(context);
  when(fixture.ai.classify("Ngày 14/8/2026",context)).thenReturn(new SupportAiClient.Decision("Đang tra cứu","DOCTOR_AVAILABILITY",false,"Tra lịch",.96,false,"Bình","2026-08-14","08:00"));
  when(fixture.scheduling.lookupAvailability("Bình",LocalDate.of(2026,8,14),patient,"Bearer token","PATIENT")).thenReturn(new SchedulingRecommendationService.AvailabilityLookup("NO_SLOTS","Bình",LocalDate.of(2026,8,14),List.of(),List.of()));
  when(fixture.conversations.recordAiTurn(eq(patient),anyString(),anyDouble(),eq(0),eq(false),anyString(),isNull())).thenReturn(fixture.state(patient,"AI_ACTIVE"));
  var result=fixture.service.process(patient,"PATIENT","Bearer token","Ngày 14/8/2026");
  verify(fixture.ai).classify("Ngày 14/8/2026",context);
  verify(fixture.conversations).rememberLookupContext(patient,new SupportLookupContext("DOCTOR_AVAILABILITY","Bình","2026-08-14","08:00"));
  assertThat(result.answer()).contains("08:00").contains("Bác sĩ Bình");
  assertThat(result.escalated()).isFalse();
 }

 @Test void secondMissingFieldQuestionDoesNotEscalateOrCountAsFailure(){
  var fixture=new Fixture();var patient=UUID.randomUUID();
  when(fixture.conversations.failureCount(patient)).thenReturn(1);
  when(fixture.ai.classify("Bác sĩ Bình vào lúc 8 giờ")).thenReturn(new SupportAiClient.Decision("Bạn cho mình biết ngày muốn khám nhé.","DOCTOR_AVAILABILITY",false,"Thiếu ngày khám",.88,true,"Bình",null,"08:00"));
  when(fixture.conversations.recordAiTurn(eq(patient),eq("DOCTOR_AVAILABILITY"),anyDouble(),eq(0),eq(false),anyString(),isNull())).thenReturn(fixture.state(patient,"AI_ACTIVE"));
  var result=fixture.service.process(patient,"PATIENT",null,"Bác sĩ Bình vào lúc 8 giờ");
  assertThat(result.escalated()).isFalse();
  assertThat(result.answer()).contains("ngày muốn khám").doesNotContain("chuyển");
  verify(fixture.conversations).rememberLookupContext(patient,new SupportLookupContext("DOCTOR_AVAILABILITY","Bình",null,"08:00"));
  verifyNoInteractions(fixture.scheduling);
 }

 @Test void unrelatedRequestClearsOldLookupContext(){
  var fixture=new Fixture();var patient=UUID.randomUUID();
  var context=new SupportLookupContext("DOCTOR_AVAILABILITY","Bình",null,"08:00");
  when(fixture.conversations.lookupContext(patient)).thenReturn(context);
  when(fixture.ai.classify("Lịch của tôi khi nào?",context)).thenReturn(new SupportAiClient.Decision("Đang kiểm tra","APPOINTMENT_STATUS",false,"Tra lịch của tôi",.96,false,null,null,null));
  when(fixture.appointmentLookup.answer(patient,null)).thenReturn("Bạn chưa có lịch khám.");
  when(fixture.conversations.recordAiTurn(eq(patient),eq("APPOINTMENT_STATUS"),anyDouble(),eq(0),eq(false),anyString(),isNull())).thenReturn(fixture.state(patient,"AI_ACTIVE"));
  var result=fixture.service.process(patient,"PATIENT",null,"Lịch của tôi khi nào?");
  assertThat(result.escalated()).isFalse();
  verify(fixture.conversations).rememberLookupContext(patient,null);
  verifyNoInteractions(fixture.scheduling);
 }

 @Test void doctorInformationUsesActiveDoctorProfilesFromDoctorService(){
  var fixture=new Fixture();var patient=UUID.randomUUID();
  var binh=new SchedulingRecommendationService.DoctorProfile(UUID.randomUUID(),"Bình","DA LIỄU TỔNG QUÁT",6,"CCHN-BINH-001",new java.math.BigDecimal("150000"),"Khám và điều trị các bệnh da liễu thường gặp.");
  var linh=new SchedulingRecommendationService.DoctorProfile(UUID.randomUUID(),"Linh","DA LIỄU - ĐIỀU TRỊ MỤN",6,"CCHN-LINH-001",new java.math.BigDecimal("200000"),"Điều trị mụn và chăm sóc da.");
  when(fixture.ai.classify(anyString())).thenReturn(new SupportAiClient.Decision("Đang tra cứu","DOCTOR_INFORMATION",false,"Tra hồ sơ bác sĩ",.96,false,null,null,null));
  when(fixture.conversations.lastIntent(patient)).thenReturn(null);
  when(fixture.scheduling.lookupDoctorProfiles(null,"Bearer token","PATIENT")).thenReturn(new SchedulingRecommendationService.DoctorProfileLookup("ALL",List.of(binh,linh),List.of()));
  when(fixture.conversations.recordAiTurn(eq(patient),eq("DOCTOR_INFORMATION"),anyDouble(),eq(0),eq(false),anyString(),isNull())).thenReturn(fixture.state(patient,"AI_ACTIVE"));

  var result=fixture.service.process(patient,"PATIENT","Bearer token","Cho tôi thông tin về bác sĩ");

  assertThat(result.answer()).contains("Bác sĩ Bình").contains("150.000 đ").contains("Bác sĩ Linh").contains("200.000 đ");
  assertThat(result.escalated()).isFalse();
 }

 @Test void doctorInformationForDateListsApprovedLeaveDoctors(){
  var fixture=new Fixture();var patient=UUID.randomUUID();
  var binh=new SchedulingRecommendationService.DoctorProfile(UUID.randomUUID(),"Bình","DA LIỄU TỔNG QUÁT",6,"CCHN-BINH-001",new java.math.BigDecimal("150000"),"Khám và điều trị các bệnh da liễu thường gặp.");
  var linh=new SchedulingRecommendationService.DoctorProfile(UUID.randomUUID(),"Linh","DA LIỄU - ĐIỀU TRỊ MỤN",6,"CCHN-LINH-001",new java.math.BigDecimal("200000"),"Điều trị mụn và chăm sóc da.");
  when(fixture.ai.classify(anyString())).thenReturn(new SupportAiClient.Decision("Đang tra cứu","DOCTOR_INFORMATION",false,"Tra hồ sơ bác sĩ",.96,false,null,"2026-09-02",null));
  when(fixture.conversations.lastIntent(patient)).thenReturn(null);
  when(fixture.scheduling.lookupDoctorProfiles(null,"Bearer token","PATIENT")).thenReturn(new SchedulingRecommendationService.DoctorProfileLookup("ALL",List.of(binh,linh),List.of()));
  when(fixture.scheduling.lookupDoctorLeaveStatuses(null,LocalDate.of(2026,9,2),"Bearer token","PATIENT")).thenReturn(new SchedulingRecommendationService.DoctorLeaveLookup("ALL",LocalDate.of(2026,9,2),List.of(new SchedulingRecommendationService.DoctorLeaveStatus("Bình",true),new SchedulingRecommendationService.DoctorLeaveStatus("Linh",false)),List.of()));
  when(fixture.conversations.recordAiTurn(eq(patient),eq("DOCTOR_INFORMATION"),anyDouble(),eq(0),eq(false),anyString(),isNull())).thenReturn(fixture.state(patient,"AI_ACTIVE"));

  var result=fixture.service.process(patient,"PATIENT","Bearer token","Cho tôi xem thông tin bác sĩ nào cũng được ngày 2/9");

  assertThat(result.answer()).contains("Bình").contains("lịch nghỉ").contains("admin").contains("02/09/2026");
  assertThat(result.escalated()).isFalse();
 }

 @Test void specificDoctorInformationIncludesProfileDetails(){
  var fixture=new Fixture();var patient=UUID.randomUUID();
  var doctor=new SchedulingRecommendationService.DoctorProfile(UUID.randomUUID(),"Bình","DA LIỄU TỔNG QUÁT",6,"CCHN-BINH-001",new java.math.BigDecimal("150000"),"Khám và điều trị các bệnh da liễu thường gặp.");
  when(fixture.ai.classify(anyString())).thenReturn(new SupportAiClient.Decision("Đang tra cứu","DOCTOR_INFORMATION",false,"Tra hồ sơ bác sĩ",.96,false,"Bình",null,null));
  when(fixture.conversations.lastIntent(patient)).thenReturn(null);
  when(fixture.scheduling.lookupDoctorProfiles("Bình","Bearer token","PATIENT")).thenReturn(new SchedulingRecommendationService.DoctorProfileLookup("FOUND",List.of(doctor),List.of()));
  when(fixture.conversations.recordAiTurn(eq(patient),eq("DOCTOR_INFORMATION"),anyDouble(),eq(0),eq(false),anyString(),isNull())).thenReturn(fixture.state(patient,"AI_ACTIVE"));

  var result=fixture.service.process(patient,"PATIENT","Bearer token","Cho tôi thông tin về bác sĩ Bình");

  assertThat(result.answer()).contains("Bác sĩ Bình").contains("6 năm kinh nghiệm").contains("CCHN-BINH-001").contains("150.000 đ").contains("Khám và điều trị");
  assertThat(result.escalated()).isFalse();
 }

 @Test void fungalSkinQuestionRecommendsDoctorFromRealProfileData(){
  var fixture=new Fixture();var patient=UUID.randomUUID();
  var binh=new SchedulingRecommendationService.DoctorProfile(UUID.randomUUID(),"Bình","DA LIỄU TỔNG QUÁT",6,"CCHN-BINH-001",new java.math.BigDecimal("150000"),"Khám mụn, viêm da, dị ứng, nấm da và rối loạn sắc tố.");
  var linh=new SchedulingRecommendationService.DoctorProfile(UUID.randomUUID(),"Linh","DA LIỄU - ĐIỀU TRỊ MỤN",6,"CCHN-LINH-001",new java.math.BigDecimal("200000"),"Điều trị mụn trứng cá, mụn viêm và thâm sau mụn.");
  when(fixture.ai.classify(anyString())).thenReturn(new SupportAiClient.Decision("Đang đối chiếu","DOCTOR_RECOMMENDATION",false,"Gợi ý bác sĩ",.95,false,null,null,null));
  when(fixture.conversations.lastIntent(patient)).thenReturn(null);
  when(fixture.scheduling.lookupDoctorProfiles(null,"Bearer token","PATIENT")).thenReturn(new SchedulingRecommendationService.DoctorProfileLookup("ALL",List.of(binh,linh),List.of()));
  when(fixture.conversations.recordAiTurn(eq(patient),eq("DOCTOR_RECOMMENDATION"),anyDouble(),eq(0),eq(false),anyString(),isNull())).thenReturn(fixture.state(patient,"AI_ACTIVE"));

  var result=fixture.service.process(patient,"PATIENT","Bearer token","Tôi đang bị nấm da thì nên chọn bác sĩ nào phù hợp");

  assertThat(result.answer()).contains("Bác sĩ Bình").contains("nấm da").contains("không phải kết luận chẩn đoán").doesNotContain("Bác sĩ Linh");
  assertThat(result.escalated()).isFalse();
 }

 @Test void assistantCannotReplyAfterConversationWasHandedToReceptionist(){
  var fixture=new Fixture();var patient=UUID.randomUUID();
  when(fixture.conversations.aiActiveOrNew(patient)).thenReturn(false);

  org.assertj.core.api.Assertions.assertThatThrownBy(()->fixture.service.process(patient,"PATIENT",null,"Tôi cần hỏi thêm"))
   .isInstanceOf(org.springframework.web.server.ResponseStatusException.class)
   .hasMessageContaining("409 CONFLICT");
  verifyNoInteractions(fixture.ai);
  verifyNoInteractions(fixture.messages);
 }

 @Test void ownAppointmentsAreReadForAuthenticatedPatientWithoutEscalation(){
  var fixture=new Fixture();var patient=UUID.randomUUID();
  when(fixture.ai.classify(anyString())).thenReturn(new SupportAiClient.Decision("Đang tra cứu","APPOINTMENT_STATUS",false,"Tra lịch cá nhân",.95,false,null,null,null));
  when(fixture.appointmentLookup.answer(patient,"Bearer patient-token")).thenReturn("Lịch khám sắp tới của bạn: Bác sĩ Bình · Đã cọc");
  when(fixture.conversations.recordAiTurn(eq(patient),eq("APPOINTMENT_STATUS"),anyDouble(),eq(0),eq(false),anyString(),isNull())).thenReturn(fixture.state(patient,"AI_ACTIVE"));
  var result=fixture.service.process(patient,"PATIENT","Bearer patient-token","Lịch của tôi khi nào?");
  assertThat(result.answer()).contains("Bác sĩ Bình").contains("Đã cọc");
  assertThat(result.escalated()).isFalse();
  assertThat(result.bookingOptions()).isEmpty();
  verify(fixture.appointmentLookup).answer(patient,"Bearer patient-token");
 }

 @Test void staffCannotUsePersonalAppointmentAssistant(){
  var fixture=new Fixture();
  org.assertj.core.api.Assertions.assertThatThrownBy(()->fixture.service.process(UUID.randomUUID(),"RECEPTIONIST",null,"Lịch của tôi"))
   .isInstanceOf(org.springframework.web.server.ResponseStatusException.class).hasMessageContaining("403 FORBIDDEN");
  verifyNoInteractions(fixture.appointmentLookup,fixture.ai);
 }

 @Test void clinicDayOffUsesActualReasonInsteadOfNoSlots(){
  var result=closedDayAnswer("CLINIC_CLOSED","Phòng khám nghỉ Thứ Bảy.");
  assertThat(result.answer()).contains("Phòng khám nghỉ ngày 21/11/2026","Phòng khám nghỉ Thứ Bảy.").doesNotContain("không còn trống","không còn khung giờ");
  assertThat(result.bookingOptions()).isEmpty();assertThat(result.escalated()).isFalse();
 }

 @Test void approvedWholeShiftLeaveIsExplainedAsDoctorLeave(){
  var result=closedDayAnswer("DOCTOR_ON_LEAVE",null);
  assertThat(result.answer()).contains("Bác sĩ Bình nghỉ","admin duyệt","21/11/2026").doesNotContain("không còn trống","không còn khung giờ");
  assertThat(result.bookingOptions()).isEmpty();assertThat(result.escalated()).isFalse();
 }

 @Test void missingDoctorShiftDoesNotClaimTheDayIsBooked(){
  var result=closedDayAnswer("NO_WORK_SCHEDULE",null);
  assertThat(result.answer()).contains("chưa có ca làm việc","21/11/2026").doesNotContain("không còn trống");
  assertThat(result.escalated()).isFalse();
 }

 private SupportAssistantService.TurnResult closedDayAnswer(String status,String reason){
  var fixture=new Fixture();var patient=UUID.randomUUID();var date=LocalDate.of(2026,11,21);
  when(fixture.ai.classify(anyString())).thenReturn(new SupportAiClient.Decision("Đang tra lịch","DOCTOR_AVAILABILITY",false,"Tra lịch",.96,false,"Bình",date.toString(),"08:00"));
  when(fixture.scheduling.lookupAvailability("Bình",date,patient,"Bearer token","PATIENT")).thenReturn(
   new SchedulingRecommendationService.AvailabilityLookup(status,"Bình",date,List.of(),List.of(),"DOCTOR_ON_LEAVE".equals(status),List.of(),reason));
  when(fixture.conversations.recordAiTurn(eq(patient),anyString(),anyDouble(),eq(0),eq(false),anyString(),isNull())).thenReturn(fixture.state(patient,"AI_ACTIVE"));
  return fixture.service.process(patient,"PATIENT","Bearer token","Bác sĩ Bình ngày 21 lúc 8 giờ");
 }

 private static class Fixture {
  final SupportAiClient ai=mock(SupportAiClient.class);
  final SupportMessageRepository messages=mock(SupportMessageRepository.class);
  final SupportConversationService conversations=mock(SupportConversationService.class);
  final SchedulingRecommendationService scheduling=mock(SchedulingRecommendationService.class);
  final SlotUpdateBroadcaster updates=mock(SlotUpdateBroadcaster.class);
  final SupportAppointmentLookup appointmentLookup=mock(SupportAppointmentLookup.class);
  final SupportAssistantService service=new SupportAssistantService(ai,messages,conversations,scheduling,updates,appointmentLookup);
  Fixture(){when(messages.save(any(SupportMessage.class))).thenAnswer(call->call.getArgument(0));when(conversations.aiActiveOrNew(any())).thenReturn(true);}
  SupportConversation state(UUID patient,String status){var value=new SupportConversation(patient);value.channelStatus=status;return value;}
 }
}

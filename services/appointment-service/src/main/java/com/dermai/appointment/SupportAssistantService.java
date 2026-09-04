package com.dermai.appointment;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.client.RestClientException;

import java.time.*;
import java.time.format.DateTimeFormatter;
import java.text.NumberFormat;
import java.text.Normalizer;
import java.util.*;

@Service
class SupportAssistantService {
 private static final Logger LOG=LoggerFactory.getLogger(SupportAssistantService.class);
 private static final double CONFIDENCE_THRESHOLD=0.55;
 private static final int MAX_FAILED_ATTEMPTS=2;
 private static final ZoneId CLINIC_ZONE=ZoneId.of("Asia/Ho_Chi_Minh");
 private final SupportAiClient ai;
 private final SupportMessageRepository messages;
 private final SupportConversationService conversations;
 private final SchedulingRecommendationService scheduling;
 private final SlotUpdateBroadcaster updates;

 SupportAssistantService(SupportAiClient ai,SupportMessageRepository messages,SupportConversationService conversations,SchedulingRecommendationService scheduling,SlotUpdateBroadcaster updates){
  this.ai=ai;this.messages=messages;this.conversations=conversations;this.scheduling=scheduling;this.updates=updates;
 }

 TurnResult process(UUID patientIdentityId,String role,String authorization,String question){
  if(!"PATIENT".equals(role))throw new ResponseStatusException(HttpStatus.FORBIDDEN,"Chỉ bệnh nhân được sử dụng trợ lý hỗ trợ.");
  if(!conversations.aiActiveOrNew(patientIdentityId))throw new ResponseStatusException(HttpStatus.CONFLICT,"Cuộc trò chuyện đã được chuyển đến lễ tân. Vui lòng tiếp tục nhắn trong kênh hỗ trợ hiện tại.");
  String previousIntent=conversations.lastIntent(patientIdentityId);
  String routedQuestion=question;
  if("DOCTOR_AVAILABILITY".equals(previousIntent)||"DOCTOR_LEAVE_SCHEDULE".equals(previousIntent)||"CLINIC_CLOSURE".equals(previousIntent)){
   // Keep the previous patient wording so a follow-up such as "14/8 lúc 9h"
   // retains the doctor name without storing a separate synthetic profile.
   routedQuestion=messages.findFirstByPatientIdentityIdAndSenderRoleOrderBySentAtDesc(patientIdentityId,"PATIENT")
    .map(item->item.body+"\n"+question).orElse(question);
  }
  save(patientIdentityId,patientIdentityId,"PATIENT",question.trim());

  SupportAiClient.Decision decision;
  try{
   decision=ai.classify(routedQuestion);
  }catch(RestClientException|IllegalStateException error){
   LOG.warn("AI support classification failed; escalating conversation safely: {}",error.getMessage());
   decision=new SupportAiClient.Decision(
    "Mình chưa thể xử lý chính xác trường hợp này. Mình sẽ chuyển cuộc trò chuyện cho bộ phận lễ tân hỗ trợ tiếp.",
    "AI_UNAVAILABLE",true,"Trợ lý AI không phản hồi.",0,false,null,null,null
   );
  }

  String answer=decision.answer();
  boolean failed=decision.needsClarification();
  String attempt="AI đã phân loại và trả lời hướng dẫn.";
  if("DOCTOR_AVAILABILITY".equals(decision.category())&&!decision.needsClarification()){
   var lookup=lookupAvailability(decision,patientIdentityId,authorization,role);
   answer=lookup.answer();failed=lookup.failed();attempt=lookup.attempt();
  }
  if("DOCTOR_LEAVE_SCHEDULE".equals(decision.category())&&!decision.needsClarification()){
   var lookup=lookupDoctorLeaveSchedule(decision,authorization,role);
   answer=lookup.answer();failed=lookup.failed();attempt=lookup.attempt();
  }
  if("CLINIC_CLOSURE".equals(decision.category())&&!decision.needsClarification()){
   var lookup=lookupClinicClosure(decision);
   answer=lookup.answer();failed=lookup.failed();attempt=lookup.attempt();
  }
  if("DOCTOR_INFORMATION".equals(decision.category())&&!decision.needsClarification()){
   var lookup=lookupDoctorInformation(decision,authorization,role);
   answer=lookup.answer();failed=lookup.failed();attempt=lookup.attempt();
  }
  if("DOCTOR_RECOMMENDATION".equals(decision.category())&&!decision.needsClarification()){
   var lookup=lookupDoctorRecommendation(question,authorization,role);
   answer=lookup.answer();failed=lookup.failed();attempt=lookup.attempt();
  }

  int failureCount=failed?conversations.failureCount(patientIdentityId)+1:0;
  boolean lowConfidence=decision.intentConfidence()<CONFIDENCE_THRESHOLD;
  boolean escalate=decision.requiresHandoff()||lowConfidence||failureCount>=MAX_FAILED_ATTEMPTS;
  String reason=escalationReason(decision,lowConfidence,failureCount);
  if(escalate&&!decision.requiresHandoff()&&!"URGENT".equals(decision.category())){
   answer=answer+"\n\nMình chưa thể xử lý chính xác trường hợp này. Mình sẽ chuyển cuộc trò chuyện cho bộ phận lễ tân hỗ trợ tiếp.";
  }

  save(patientIdentityId,patientIdentityId,"AI",answer);
  String summary=summary(question,decision,attempt,escalate?reason:null);
  var conversation=conversations.recordAiTurn(
   patientIdentityId,decision.category(),decision.intentConfidence(),failureCount,escalate,summary,reason
  );
  if(escalate){
   save(patientIdentityId,patientIdentityId,"SYSTEM","Đã tự động chuyển cuộc trò chuyện đến lễ tân. Lễ tân sẽ tiếp tục hỗ trợ bạn tại đây.");
  }
  updates.chatChanged();
  return new TurnResult(answer,decision.category(),decision.intentConfidence(),escalate,conversation.channelStatus,escalate?reason:null);
 }

 private AvailabilityAnswer lookupAvailability(SupportAiClient.Decision decision,UUID patientIdentityId,String authorization,String role){
  try{
   LocalDate date=LocalDate.parse(decision.requestedDate());
   var result=scheduling.lookupAvailability(decision.doctorName(),date,patientIdentityId,authorization,role);
   String displayDate=date.format(DateTimeFormatter.ofPattern("dd/MM/yyyy"));
   LocalTime requestedTime=decision.requestedTime()==null||decision.requestedTime().isBlank()?null:LocalTime.parse(decision.requestedTime());
   boolean requestedTimeOnLeave=requestedTime!=null&&result.leaveSlots().stream().anyMatch(item->item.startAt().atZone(CLINIC_ZONE).toLocalTime().equals(requestedTime));
   if(requestedTimeOnLeave){
    String displayTime=requestedTime.format(DateTimeFormatter.ofPattern("HH:mm"));
    return new AvailabilityAnswer("Bác sĩ "+result.doctorName()+" có lịch nghỉ đã được admin duyệt vào ngày "+displayDate+"; khung giờ "+displayTime+" không thể đặt. Bạn vui lòng chọn ngày khác hoặc hỏi mình về bác sĩ khác.",false,"Đã xác nhận khung giờ "+displayTime+" nằm trong khoảng nghỉ đã được admin duyệt.");
   }
   if(requestedTime!=null&&"FOUND".equals(result.status())){
    String displayTime=requestedTime.format(DateTimeFormatter.ofPattern("HH:mm"));
    boolean exact=result.items().stream().anyMatch(item->item.startAt().atZone(CLINIC_ZONE).toLocalTime().equals(requestedTime));
    if(exact){
     return new AvailabilityAnswer("Khung giờ "+displayTime+" của Bác sĩ "+result.doctorName()+" ngày "+displayDate+" hiện còn trống. Bạn mở mục Lịch khám để chọn và xác nhận; khung giờ chỉ được giữ sau khi bạn chọn slot.",false,"Đã tra cứu availability thật và xác nhận đúng khung giờ "+displayTime+" còn trống.");
    }
    // Return nearby real slots instead of inventing an alternative time.
    String nearby=result.items().stream()
     .sorted(Comparator.comparingLong(item->Math.abs(Duration.between(requestedTime,item.startAt().atZone(CLINIC_ZONE).toLocalTime()).toMinutes())))
     .limit(4)
     .map(item->item.startAt().atZone(CLINIC_ZONE).format(DateTimeFormatter.ofPattern("HH:mm")))
     .reduce((a,b)->a+", "+b).orElse("");
    String suggestion=nearby.isBlank()?"":" Các giờ còn trống gần nhất: "+nearby+".";
    return new AvailabilityAnswer("Khung giờ "+displayTime+" của Bác sĩ "+result.doctorName()+" ngày "+displayDate+" hiện không còn trống hoặc không nằm trong ca làm việc."+suggestion,false,"Đã tra cứu availability thật; khung giờ "+displayTime+" không có trong danh sách slot trống.");
   }
   return switch(result.status()){
    case "FOUND" -> {
     String slots=result.items().stream().limit(8).map(item->item.startAt().atZone(CLINIC_ZONE).format(DateTimeFormatter.ofPattern("HH:mm"))).reduce((a,b)->a+", "+b).orElse("");
     String leaveNotice=result.doctorOnLeave()?" Lưu ý: Bác sĩ có khoảng nghỉ đã được admin duyệt trong ngày này; các khung trên là thời gian còn làm việc.":"";
     yield new AvailabilityAnswer("Bác sĩ "+result.doctorName()+" còn các khung giờ ngày "+displayDate+": "+slots+". Bạn mở mục Lịch khám để chọn và xác nhận giờ phù hợp."+leaveNotice,false,"Đã tra cứu availability thật và tìm thấy "+result.items().size()+" khung giờ."+(result.doctorOnLeave()?" Có khoảng nghỉ đã được admin duyệt trong ngày.":""));
    }
    case "NO_SLOTS" -> {
     String timePrefix=requestedTime==null?"":"Khung giờ "+requestedTime.format(DateTimeFormatter.ofPattern("HH:mm"))+" không còn trống; ";
     String leaveNotice=result.doctorOnLeave()?" Bác sĩ có lịch nghỉ đã được admin duyệt trong ngày này, nên bạn vui lòng chọn ngày khác hoặc bác sĩ khác.":" Bạn có thể hỏi một ngày khác để mình kiểm tra tiếp.";
     yield new AvailabilityAnswer(timePrefix+"Bác sĩ "+result.doctorName()+" hiện không còn khung giờ trống ngày "+displayDate+"."+leaveNotice,false,"Đã tra cứu availability thật; ngày yêu cầu không còn slot."+(result.doctorOnLeave()?" Có lịch nghỉ đã được admin duyệt.":""));
    }
    case "AMBIGUOUS" -> new AvailabilityAnswer("Mình tìm thấy nhiều bác sĩ phù hợp: "+String.join(", ",result.candidates())+". Bạn cho mình biết chính xác bác sĩ muốn xem nhé.",true,"Tên bác sĩ chưa đủ rõ để tra cứu.");
    default -> new AvailabilityAnswer("Mình chưa tìm thấy bác sĩ “"+decision.doctorName()+"”. Các bác sĩ hiện có: "+String.join(", ",result.candidates())+". Bạn kiểm tra lại tên giúp mình nhé.",true,"Không tìm thấy bác sĩ trong dữ liệu thật.");
   };
  }catch(RuntimeException error){
   return new AvailabilityAnswer("Mình chưa tra cứu được lịch bác sĩ ở thời điểm này. Bạn có thể cung cấp lại tên bác sĩ và ngày muốn khám.",true,"API availability trả lỗi: "+error.getClass().getSimpleName());
  }
 }

 private DoctorLeaveScheduleAnswer lookupDoctorLeaveSchedule(SupportAiClient.Decision decision,String authorization,String role){
  try{
   var result=scheduling.lookupDoctorLeavePeriods(decision.doctorName(),authorization,role);
   return switch(result.status()){
    case "FOUND" -> {
     if(result.periods().isEmpty())yield new DoctorLeaveScheduleAnswer("Hệ thống chưa ghi nhận khoảng nghỉ nào đã được duyệt của Bác sĩ "+result.doctorName()+".",false,"Đã tra cứu lịch nghỉ đã duyệt; không có khoảng nghỉ.");
     String periods=result.periods().stream().limit(8).map(item->item.startAt().atZone(CLINIC_ZONE).format(DateTimeFormatter.ofPattern("dd/MM/yyyy HH:mm"))+" – "+item.endAt().atZone(CLINIC_ZONE).format(DateTimeFormatter.ofPattern("dd/MM/yyyy HH:mm"))).reduce((a,b)->a+"; "+b).orElse("");
     yield new DoctorLeaveScheduleAnswer("Các khoảng nghỉ đã được duyệt của Bác sĩ "+result.doctorName()+": "+periods+". Bạn nên chọn ngày hoặc khung giờ khác trong mục Lịch khám.",false,"Đã tra cứu "+result.periods().size()+" khoảng nghỉ đã duyệt.");
    }
    case "AMBIGUOUS" -> new DoctorLeaveScheduleAnswer("Mình tìm thấy nhiều bác sĩ phù hợp: "+String.join(", ",result.candidates())+". Bạn cho mình biết chính xác tên bác sĩ nhé.",true,"Tên bác sĩ chưa đủ rõ để tra lịch nghỉ.");
    default -> new DoctorLeaveScheduleAnswer("Mình chưa tìm thấy bác sĩ “"+decision.doctorName()+"”. Các bác sĩ hiện có: "+String.join(", ",result.candidates())+". Bạn kiểm tra lại tên giúp mình nhé.",true,"Không tìm thấy bác sĩ trong dữ liệu thật.");
   };
  }catch(RuntimeException error){
   LOG.warn("Doctor leave schedule lookup failed: {}",error.getMessage());
   return new DoctorLeaveScheduleAnswer("Mình chưa tra cứu được lịch nghỉ của bác sĩ ở thời điểm này. Bạn có thể thử lại sau ít phút hoặc để lễ tân kiểm tra giúp.",true,"Tra cứu lịch nghỉ bác sĩ lỗi: "+error.getClass().getSimpleName());
  }
 }

 private ClinicClosureAnswer lookupClinicClosure(SupportAiClient.Decision decision){
  try{
   LocalDate date=LocalDate.parse(decision.requestedDate());
   var result=scheduling.lookupClinicClosure(date);
   String displayDate=date.format(DateTimeFormatter.ofPattern("dd/MM/yyyy"));
   if(result.closed()){
    String reason=result.reason()==null||result.reason().isBlank()?"không nêu lý do":"lý do: "+result.reason();
    return new ClinicClosureAnswer("Phòng khám nghỉ ngày "+displayDate+" ("+reason+"). Bạn vui lòng chọn ngày khác trong mục Lịch khám hoặc liên hệ lễ tân nếu cần hỗ trợ.",false,"Đã tra cứu lịch nghỉ phòng khám ngày "+displayDate+".");
   }
   return new ClinicClosureAnswer("Phòng khám không có lịch nghỉ được ghi nhận ngày "+displayDate+". Khung giờ cụ thể vẫn phụ thuộc lịch làm việc và lịch trống của từng bác sĩ; bạn có thể hỏi tên bác sĩ để mình kiểm tra tiếp.",false,"Đã xác nhận không có lịch nghỉ phòng khám ngày "+displayDate+".");
  }catch(RuntimeException error){
   LOG.warn("Clinic closure lookup failed: {}",error.getMessage());
   return new ClinicClosureAnswer("Mình chưa tra cứu được lịch nghỉ của phòng khám. Bạn có thể thử lại sau ít phút hoặc để lễ tân kiểm tra giúp.",true,"Tra cứu lịch nghỉ phòng khám lỗi: "+error.getClass().getSimpleName());
  }
 }

 private DoctorInformationAnswer lookupDoctorInformation(SupportAiClient.Decision decision,String authorization,String role){
  try{
   var result=scheduling.lookupDoctorProfiles(decision.doctorName(),authorization,role);
   String dateNotice=doctorLeaveNotice(decision,authorization,role);
   return switch(result.status()){
    case "ALL" -> {
     if(result.profiles().isEmpty())yield new DoctorInformationAnswer("Hiện phòng khám chưa có hồ sơ bác sĩ đang hoạt động.",false,"Doctor service trả về danh sách trống.");
     String list=result.profiles().stream().limit(8).map(this::doctorSummaryLine).reduce((a,b)->a+"\n"+b).orElse("");
     yield new DoctorInformationAnswer("Các bác sĩ đang hoạt động tại DermAI Clinic:\n"+list+"\nBạn có thể hỏi tên một bác sĩ cụ thể để xem mô tả chi tiết."+dateNotice,false,"Đã đọc "+result.profiles().size()+" hồ sơ bác sĩ thật."+(dateNotice.isBlank()?"":" Đã đối chiếu lịch nghỉ đã duyệt."));
    }
    case "FOUND" -> {
     var doctor=result.profiles().get(0);
     String certificate=doctor.certificateNo()==null||doctor.certificateNo().isBlank()?"":" Chứng chỉ: "+doctor.certificateNo()+".";
     String bio=doctor.bio()==null||doctor.bio().isBlank()?"":"\n"+compactBio(doctor.bio());
     String answer="Bác sĩ "+doctor.doctorName()+" – "+displaySpecialty(doctor.specialtyCode())+", "+doctor.experienceYears()+" năm kinh nghiệm. Giá khám cơ bản: "+displayFee(doctor.consultationFee())+"."+certificate+bio+dateNotice;
     yield new DoctorInformationAnswer(answer,false,"Đã đọc hồ sơ thật của Bác sĩ "+doctor.doctorName()+"."+(dateNotice.isBlank()?"":" Đã đối chiếu lịch nghỉ đã duyệt."));
    }
    case "AMBIGUOUS" -> new DoctorInformationAnswer("Mình tìm thấy nhiều bác sĩ phù hợp: "+String.join(", ",result.candidates())+". Bạn cho mình biết chính xác tên bác sĩ nhé.",true,"Tên bác sĩ chưa đủ rõ để tra hồ sơ.");
    default -> new DoctorInformationAnswer("Mình chưa tìm thấy bác sĩ “"+decision.doctorName()+"”. Các bác sĩ hiện có: "+String.join(", ",result.candidates())+". Bạn kiểm tra lại tên giúp mình nhé.",true,"Không tìm thấy hồ sơ bác sĩ trong dữ liệu thật.");
   };
  }catch(RuntimeException error){
   LOG.warn("Doctor profile lookup failed: {}",error.getMessage());
   return new DoctorInformationAnswer("Mình chưa tải được thông tin bác sĩ ở thời điểm này. Bạn có thể thử lại sau ít phút.",true,"Doctor service trả lỗi: "+error.getClass().getSimpleName());
  }
 }

 private String doctorLeaveNotice(SupportAiClient.Decision decision,String authorization,String role){
  if(decision.requestedDate()==null||decision.requestedDate().isBlank())return "";
  try{
   LocalDate date=LocalDate.parse(decision.requestedDate());
   var lookup=scheduling.lookupDoctorLeaveStatuses(decision.doctorName(),date,authorization,role);
   String displayDate=date.format(DateTimeFormatter.ofPattern("dd/MM/yyyy"));
   if("FOUND".equals(lookup.status())&&lookup.items().stream().anyMatch(SchedulingRecommendationService.DoctorLeaveStatus::onLeave))
    return "\nLưu ý: Bác sĩ "+lookup.items().get(0).doctorName()+" có lịch nghỉ đã được admin duyệt vào ngày "+displayDate+". Bạn nên chọn ngày khác hoặc bác sĩ khác trong mục Lịch khám.";
   if("ALL".equals(lookup.status())){
    String names=lookup.items().stream().filter(SchedulingRecommendationService.DoctorLeaveStatus::onLeave).map(SchedulingRecommendationService.DoctorLeaveStatus::doctorName).limit(8).reduce((a,b)->a+", "+b).orElse("");
    if(!names.isBlank())return "\nLưu ý ngày "+displayDate+", các bác sĩ có lịch nghỉ đã được admin duyệt: "+names+". Bạn có thể chọn bác sĩ khác trong mục Lịch khám.";
   }
  }catch(RuntimeException error){
   LOG.warn("Doctor leave lookup failed: {}",error.getMessage());
  }
  return "";
 }

 private DoctorInformationAnswer lookupDoctorRecommendation(String question,String authorization,String role){
  try{
   var result=scheduling.lookupDoctorProfiles(null,authorization,role);
   String topic=careTopic(question);
   if(topic==null){
    return new DoctorInformationAnswer(
     "Bạn cho mình biết vấn đề da cần khám, ví dụ mụn, nấm da, viêm da, dị ứng hoặc vảy nến, để mình đối chiếu với hồ sơ bác sĩ nhé.",
     true,"Chưa nhận diện được nhu cầu chuyên môn để gợi ý bác sĩ."
    );
   }
   var matches=result.profiles().stream().filter(doctor->profileMatchesTopic(doctor,topic)).toList();
   if(matches.isEmpty()){
    return new DoctorInformationAnswer(
     "Mình chưa tìm thấy hồ sơ bác sĩ ghi rõ thế mạnh phù hợp với "+displayCareTopic(topic)+". Bạn có thể mở mục Lịch khám để xem hồ sơ hoặc liên hệ lễ tân để được phân công chính xác.",
     false,"Không có hồ sơ bác sĩ khớp rõ với nhu cầu "+displayCareTopic(topic)+"."
    );
   }
   String doctors=matches.stream().limit(3).map(doctor->"Bác sĩ "+doctor.doctorName()+" ("+displaySpecialty(doctor.specialtyCode())+")").reduce((a,b)->a+", "+b).orElse("");
   String reason=matches.size()==1
    ? "Hồ sơ chuyên môn của bác sĩ có đề cập đến "+displayCareTopic(topic)+"."
    : "Các hồ sơ này có chuyên môn hoặc mô tả liên quan đến "+displayCareTopic(topic)+".";
   return new DoctorInformationAnswer(
    "Dựa trên hồ sơ bác sĩ đang hoạt động tại phòng khám, bạn có thể ưu tiên "+doctors+". "+reason+" Đây là gợi ý chọn bác sĩ, không phải kết luận chẩn đoán. Bạn mở mục Lịch khám để xem ngày và giờ còn trống.",
    false,"Đã đối chiếu nhu cầu "+displayCareTopic(topic)+" với "+result.profiles().size()+" hồ sơ bác sĩ thật."
   );
  }catch(RuntimeException error){
   LOG.warn("Doctor recommendation lookup failed: {}",error.getMessage());
   return new DoctorInformationAnswer("Mình chưa tải được hồ sơ bác sĩ để đối chiếu ở thời điểm này. Bạn thử lại sau ít phút nhé.",true,"Doctor service trả lỗi: "+error.getClass().getSimpleName());
  }
 }

 private boolean profileMatchesTopic(SchedulingRecommendationService.DoctorProfile doctor,String topic){
  String profile=foldText((doctor.specialtyCode()==null?"":doctor.specialtyCode())+" "+(doctor.bio()==null?"":doctor.bio()));
  return switch(topic){
   case "fungal" -> profile.contains("nam da")||profile.contains("benh nam")||profile.contains("nam");
   case "acne" -> profile.contains("mun")||profile.contains("trung ca");
   case "dermatitis" -> profile.contains("viem da")||profile.contains("eczema")||profile.contains("cham");
   case "allergy" -> profile.contains("di ung")||profile.contains("me day");
   case "psoriasis" -> profile.contains("vay nen");
   case "pigmentation" -> profile.contains("sac to")||profile.contains("tham");
   case "hair_nail" -> profile.contains("toc")||profile.contains("mong");
   default -> false;
  };
 }

 private String careTopic(String question){
  String value=foldText(question);
  if(value.contains("nam da")||value.matches(".*\\bnam\\b.*"))return "fungal";
  if(value.contains("mun")||value.contains("trung ca"))return "acne";
  if(value.contains("viem da")||value.contains("eczema")||value.matches(".*\\bcham\\b.*"))return "dermatitis";
  if(value.contains("di ung")||value.contains("me day"))return "allergy";
  if(value.contains("vay nen"))return "psoriasis";
  if(value.contains("sac to")||value.contains("tham"))return "pigmentation";
  if(value.matches(".*\\b(toc|mong)\\b.*"))return "hair_nail";
  return null;
 }

 private String displayCareTopic(String topic){
  return switch(topic){
   case "fungal" -> "nấm da";
   case "acne" -> "mụn/trứng cá";
   case "dermatitis" -> "viêm da/chàm";
   case "allergy" -> "dị ứng/mề đay";
   case "psoriasis" -> "vảy nến";
   case "pigmentation" -> "rối loạn sắc tố";
   case "hair_nail" -> "vấn đề tóc hoặc móng";
   default -> "nhu cầu khám da liễu";
  };
 }

 private String foldText(String value){
  return Normalizer.normalize(value==null?"":value,Normalizer.Form.NFD)
   .replaceAll("\\p{M}","").replace('đ','d').replace('Đ','D').toLowerCase(Locale.ROOT).replaceAll("\\s+"," ").trim();
 }

 private String doctorSummaryLine(SchedulingRecommendationService.DoctorProfile doctor){
  return "• Bác sĩ "+doctor.doctorName()+" – "+displaySpecialty(doctor.specialtyCode())+", "+doctor.experienceYears()+" năm kinh nghiệm, giá khám "+displayFee(doctor.consultationFee());
 }

 private String displaySpecialty(String specialty){
  return specialty==null||specialty.isBlank()?"Da liễu":specialty.replace('_',' ').trim();
 }

 private String displayFee(java.math.BigDecimal fee){
  return fee==null?"chưa cập nhật":NumberFormat.getIntegerInstance(Locale.forLanguageTag("vi-VN")).format(fee)+" đ";
 }

 private String compactBio(String bio){
  String value=bio.trim().replaceAll("\\s+"," ");
  return value.length()<=320?value:value.substring(0,317)+"...";
 }

 private String escalationReason(SupportAiClient.Decision decision,boolean lowConfidence,int failureCount){
  if(decision.requiresHandoff())return "MANDATORY_"+decision.category();
  if(lowConfidence)return "LOW_CONFIDENCE";
  if(failureCount>=MAX_FAILED_ATTEMPTS)return "REPEATED_FAILURE";
  return null;
 }

 private String summary(String question,SupportAiClient.Decision decision,String attempt,String reason){
  String value="Yêu cầu gần nhất: "+question.trim()+"\nIntent: "+decision.category()+"\nĐộ chắc chắn: "+Math.round(decision.intentConfidence()*100)+"%\nĐã thử: "+attempt;
  if(reason!=null)value+="\nLý do chuyển: "+reason;
  return value.length()<=4000?value:value.substring(0,4000);
 }

 private SupportMessage save(UUID patientIdentityId,UUID senderIdentityId,String role,String body){
  var item=new SupportMessage();item.id=UUID.randomUUID();item.patientIdentityId=patientIdentityId;item.senderIdentityId=senderIdentityId;item.senderRole=role;item.body=body.length()<=2000?body:body.substring(0,2000);item.sentAt=Instant.now();return messages.save(item);
 }

 record AvailabilityAnswer(String answer,boolean failed,String attempt){}
 record DoctorLeaveScheduleAnswer(String answer,boolean failed,String attempt){}
 record ClinicClosureAnswer(String answer,boolean failed,String attempt){}
 record DoctorInformationAnswer(String answer,boolean failed,String attempt){}
 record TurnResult(String answer,String intent,double intentConfidence,boolean escalated,String conversationStatus,String escalationReason){}
}

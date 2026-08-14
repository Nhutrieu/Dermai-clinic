package com.dermai.appointment;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.client.RestClientException;

import java.time.*;
import java.time.format.DateTimeFormatter;
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
  if("DOCTOR_AVAILABILITY".equals(previousIntent)){
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
     yield new AvailabilityAnswer("Bác sĩ "+result.doctorName()+" còn các khung giờ ngày "+displayDate+": "+slots+". Bạn mở mục Lịch khám để chọn và xác nhận giờ phù hợp.",false,"Đã tra cứu availability thật và tìm thấy "+result.items().size()+" khung giờ.");
    }
    case "NO_SLOTS" -> {
     String timePrefix=requestedTime==null?"":"Khung giờ "+requestedTime.format(DateTimeFormatter.ofPattern("HH:mm"))+" không còn trống; ";
     yield new AvailabilityAnswer(timePrefix+"Bác sĩ "+result.doctorName()+" hiện không còn khung giờ trống ngày "+displayDate+". Bạn có thể hỏi một ngày khác để mình kiểm tra tiếp.",false,"Đã tra cứu availability thật; ngày yêu cầu không còn slot.");
    }
    case "AMBIGUOUS" -> new AvailabilityAnswer("Mình tìm thấy nhiều bác sĩ phù hợp: "+String.join(", ",result.candidates())+". Bạn cho mình biết chính xác bác sĩ muốn xem nhé.",true,"Tên bác sĩ chưa đủ rõ để tra cứu.");
    default -> new AvailabilityAnswer("Mình chưa tìm thấy bác sĩ “"+decision.doctorName()+"”. Các bác sĩ hiện có: "+String.join(", ",result.candidates())+". Bạn kiểm tra lại tên giúp mình nhé.",true,"Không tìm thấy bác sĩ trong dữ liệu thật.");
   };
  }catch(RuntimeException error){
   return new AvailabilityAnswer("Mình chưa tra cứu được lịch bác sĩ ở thời điểm này. Bạn có thể cung cấp lại tên bác sĩ và ngày muốn khám.",true,"API availability trả lỗi: "+error.getClass().getSimpleName());
  }
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
 record TurnResult(String answer,String intent,double intentConfidence,boolean escalated,String conversationStatus,String escalationReason){}
}

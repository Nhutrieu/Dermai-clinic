package com.dermai.appointment;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import java.util.*;

@Service
class SupportConversationService {
 private final SupportConversationRepository conversations;
 SupportConversationService(SupportConversationRepository conversations){this.conversations=conversations;}

 @Transactional(readOnly=true)
 List<SupportConversation> list(UUID identity,String role){
  if("PATIENT".equals(role))return conversations.findById(identity).map(List::of).orElseGet(List::of);
  requireViewer(role);
  return "RECEPTIONIST".equals(role)
   ? conversations.findInboxForReceptionist(identity)
   : conversations.findAllByOrderByUpdatedAtDesc();
 }

 // The atomic upsert guarantees that two receptionists cannot claim the same conversation.
 @Transactional
 SupportConversation claim(UUID patientIdentityId,UUID receptionistIdentityId){
  if(conversations.claim(patientIdentityId,receptionistIdentityId)==0)
   throw new ResponseStatusException(HttpStatus.CONFLICT,"Cuộc trò chuyện đã được lễ tân khác nhận xử lý.");
  return conversations.findById(patientIdentityId).orElseThrow();
 }

 @Transactional
 SupportConversation release(UUID patientIdentityId,UUID receptionistIdentityId){
  if(conversations.release(patientIdentityId,receptionistIdentityId)==0)
   throw new ResponseStatusException(HttpStatus.CONFLICT,"Chỉ lễ tân đang phụ trách mới có thể nhả cuộc trò chuyện.");
  return conversations.findById(patientIdentityId).orElseThrow();
 }

 @Transactional
 SupportConversation resolve(UUID patientIdentityId,UUID receptionistIdentityId){
  if(conversations.resolve(patientIdentityId,receptionistIdentityId)==0)
   throw new ResponseStatusException(HttpStatus.CONFLICT,"Chỉ lễ tân đang phụ trách mới có thể hoàn tất yêu cầu hỗ trợ.");
  return conversations.findById(patientIdentityId).orElseThrow();
 }

 @Transactional
 void touch(UUID patientIdentityId){conversations.touch(patientIdentityId);}

 @Transactional(readOnly=true)
 int failureCount(UUID patientIdentityId){return conversations.findById(patientIdentityId).map(item->item.aiFailureCount).orElse(0);}

 @Transactional(readOnly=true)
 String lastIntent(UUID patientIdentityId){return conversations.findById(patientIdentityId).map(item->item.lastIntent).orElse(null);}

 @Transactional(readOnly=true)
 boolean aiActiveOrNew(UUID patientIdentityId){return conversations.findById(patientIdentityId).map(item->"AI_ACTIVE".equals(item.channelStatus)).orElse(true);}

 @Transactional(readOnly=true)
 boolean visibleToReceptionist(UUID patientIdentityId,UUID receptionistIdentityId){return conversations.findById(patientIdentityId).map(item->!"AI_ACTIVE".equals(item.channelStatus)||receptionistIdentityId.equals(item.resolvedByIdentityId)).orElse(false);}

 @Transactional
 SupportConversation recordAiTurn(UUID patientIdentityId,String intent,double confidence,int failureCount,boolean escalate,String summary,String reason){
  var item=conversations.findById(patientIdentityId).orElseGet(()->new SupportConversation(patientIdentityId));
  item.lastIntent=intent;item.lastIntentConfidence=confidence;item.aiFailureCount=failureCount;item.aiSummary=summary;item.updatedAt=java.time.Instant.now();
  boolean alreadyHuman=!"AI_ACTIVE".equals(item.channelStatus);
  if(escalate&&!alreadyHuman){item.channelStatus="WAITING_RECEPTIONIST";item.escalatedAt=java.time.Instant.now();item.escalationReason=reason;}
  if(escalate&&!alreadyHuman){item.resolvedAt=null;item.resolvedByIdentityId=null;}
  return conversations.save(item);
 }

 @Transactional
 SupportConversation manualEscalate(UUID patientIdentityId){
  var item=conversations.findById(patientIdentityId).orElseGet(()->new SupportConversation(patientIdentityId));
  if("AI_ACTIVE".equals(item.channelStatus)){
   item.channelStatus="WAITING_RECEPTIONIST";item.escalatedAt=java.time.Instant.now();
   item.resolvedAt=null;item.resolvedByIdentityId=null;
   item.escalationReason="PATIENT_DIRECT_MESSAGE";item.lastIntent="HUMAN_SUPPORT";
   item.aiSummary="Bệnh nhân mở kênh hỗ trợ trực tiếp và đang chờ lễ tân tiếp nhận.";
  }
  // A reply inside an existing human handoff only refreshes its timestamp; it
  // must not overwrite the AI intent, summary or original escalation reason.
  item.updatedAt=java.time.Instant.now();
  return conversations.save(item);
 }

 @Transactional(readOnly=true)
 boolean assignedTo(UUID patientIdentityId,UUID receptionistIdentityId){
  return conversations.findById(patientIdentityId)
   .map(item->receptionistIdentityId.equals(item.assignedReceptionistIdentityId)).orElse(false);
 }

 private void requireViewer(String role){
  if(!Set.of("RECEPTIONIST","ADMIN").contains(role))throw new ResponseStatusException(HttpStatus.FORBIDDEN);
 }
}

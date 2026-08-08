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
  requireViewer(role);return conversations.findAllByOrderByUpdatedAtDesc();
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
 void touch(UUID patientIdentityId){conversations.touch(patientIdentityId);}

 @Transactional(readOnly=true)
 boolean assignedTo(UUID patientIdentityId,UUID receptionistIdentityId){
  return conversations.findById(patientIdentityId)
   .map(item->receptionistIdentityId.equals(item.assignedReceptionistIdentityId)).orElse(false);
 }

 private void requireViewer(String role){
  if(!Set.of("RECEPTIONIST","ADMIN").contains(role))throw new ResponseStatusException(HttpStatus.FORBIDDEN);
 }
}

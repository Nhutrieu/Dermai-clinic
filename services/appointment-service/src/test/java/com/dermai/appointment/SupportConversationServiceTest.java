package com.dermai.appointment;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.*;

import java.time.Instant;
import java.util.Optional;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

class SupportConversationServiceTest {
 @Test void onlyOneReceptionistCanClaimAConversation(){
  var repository=mock(SupportConversationRepository.class);
  var service=new SupportConversationService(repository);
  var patient=UUID.randomUUID();var receptionist=UUID.randomUUID();
  when(repository.claim(patient,receptionist)).thenReturn(0);

  assertThatThrownBy(()->service.claim(patient,receptionist))
   .isInstanceOfSatisfying(ResponseStatusException.class,error->assertThat(error.getStatusCode()).isEqualTo(HttpStatus.CONFLICT));
 }

 @Test void assignedReceptionistCanReleaseTheConversation(){
  var repository=mock(SupportConversationRepository.class);
  var service=new SupportConversationService(repository);
  var patient=UUID.randomUUID();var receptionist=UUID.randomUUID();
  var released=new SupportConversation(patient);released.updatedAt=Instant.now();
  when(repository.release(patient,receptionist)).thenReturn(1);
  when(repository.findById(patient)).thenReturn(Optional.of(released));

  assertThat(service.release(patient,receptionist).assignedReceptionistIdentityId).isNull();
  verify(repository).release(patient,receptionist);
 }

 @Test void receptionistInboxExcludesAiOnlyConversations(){
  var repository=mock(SupportConversationRepository.class);
  var service=new SupportConversationService(repository);
  var receptionist=UUID.randomUUID();
  when(repository.findInboxForReceptionist(receptionist)).thenReturn(List.of());

  assertThat(service.list(receptionist,"RECEPTIONIST")).isEmpty();
  verify(repository).findInboxForReceptionist(receptionist);
 }

 @Test void assignedReceptionistCanResolveAndReturnConversationToAi(){
  var repository=mock(SupportConversationRepository.class);
  var service=new SupportConversationService(repository);
  var patient=UUID.randomUUID();var receptionist=UUID.randomUUID();
  var resolved=new SupportConversation(patient);resolved.channelStatus="AI_ACTIVE";resolved.resolvedAt=Instant.now();resolved.resolvedByIdentityId=receptionist;
  when(repository.resolve(patient,receptionist)).thenReturn(1);
  when(repository.findById(patient)).thenReturn(Optional.of(resolved));

  assertThat(service.resolve(patient,receptionist).channelStatus).isEqualTo("AI_ACTIVE");
  verify(repository).resolve(patient,receptionist);
 }

 @Test void receptionistCannotResolveConversationOwnedBySomeoneElse(){
  var repository=mock(SupportConversationRepository.class);
  var service=new SupportConversationService(repository);
  var patient=UUID.randomUUID();var receptionist=UUID.randomUUID();
  when(repository.resolve(patient,receptionist)).thenReturn(0);

  assertThatThrownBy(()->service.resolve(patient,receptionist))
   .isInstanceOfSatisfying(ResponseStatusException.class,error->assertThat(error.getStatusCode()).isEqualTo(HttpStatus.CONFLICT));
 }

 @Test void patientReplyDoesNotOverwriteExistingAiHandoffContext(){
  var repository=mock(SupportConversationRepository.class);
  var service=new SupportConversationService(repository);
  var patient=UUID.randomUUID();
  var conversation=new SupportConversation(patient);conversation.channelStatus="WAITING_RECEPTIONIST";
  conversation.lastIntent="CANCEL_APPOINTMENT";conversation.aiSummary="AI summary";conversation.escalationReason="MANDATORY_CANCEL_APPOINTMENT";
  when(repository.findById(patient)).thenReturn(Optional.of(conversation));
  when(repository.save(conversation)).thenReturn(conversation);

  var updated=service.manualEscalate(patient);

  assertThat(updated.lastIntent).isEqualTo("CANCEL_APPOINTMENT");
  assertThat(updated.aiSummary).isEqualTo("AI summary");
  assertThat(updated.escalationReason).isEqualTo("MANDATORY_CANCEL_APPOINTMENT");
 }
}

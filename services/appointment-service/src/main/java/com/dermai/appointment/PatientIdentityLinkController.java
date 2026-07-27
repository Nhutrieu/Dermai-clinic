package com.dermai.appointment;

import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/v1/appointments/internal/patient-identities")
class PatientIdentityLinkController {
 record Link(UUID patientId,UUID oldIdentityId,UUID newIdentityId){}
 private final AppointmentRepository appointments;private final SupportMessageRepository messages;private final AppointmentNotificationRepository notifications;private final SlotUpdateBroadcaster updates;private final String serviceToken;
 PatientIdentityLinkController(AppointmentRepository a,SupportMessageRepository m,AppointmentNotificationRepository n,SlotUpdateBroadcaster u,@Value("${security.service-token:}")String token){appointments=a;messages=m;notifications=n;updates=u;serviceToken=token;}

 @PatchMapping @Transactional ResponseEntity<Void> link(@RequestHeader("X-Service-Token")String token,@RequestBody Link link){
  if(serviceToken.isBlank()||!serviceToken.equals(token))throw new ResponseStatusException(HttpStatus.FORBIDDEN);
  if(link.patientId()==null||link.oldIdentityId()==null||link.newIdentityId()==null)throw new ResponseStatusException(HttpStatus.BAD_REQUEST);
  appointments.relinkPatientIdentity(link.patientId(),link.oldIdentityId(),link.newIdentityId());
  messages.relinkPatient(link.oldIdentityId(),link.newIdentityId());messages.relinkSender(link.oldIdentityId(),link.newIdentityId());
  notifications.relinkPatient(link.oldIdentityId(),link.newIdentityId());updates.chatChanged();updates.afterCommit();
  return ResponseEntity.noContent().build();
 }
}

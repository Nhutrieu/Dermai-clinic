package com.dermai.appointment;
import org.springframework.dao.DataIntegrityViolationException;import org.springframework.stereotype.Service;import org.springframework.transaction.annotation.Transactional;import java.time.*;import java.util.*;
@Service @Transactional
public class AppointmentService{
 private static final Set<AppointmentStatus> ACTIVE_PATIENT_BOOKING=EnumSet.of(AppointmentStatus.PENDING,AppointmentStatus.ASSIGNED,AppointmentStatus.CONFIRMED,AppointmentStatus.IN_PROGRESS);
 private final AppointmentRepository repo;private final OutboxRepository outbox;private final SlotUpdateBroadcaster slots;
 AppointmentService(AppointmentRepository r,OutboxRepository o,SlotUpdateBroadcaster slots){repo=r;outbox=o;this.slots=slots;}
 public Appointment book(UUID patient,UUID patientIdentity,UUID doctor,UUID doctorIdentity,Instant start,Instant end,String reason,String key){
  if(!start.isBefore(end)||start.isBefore(Instant.now()))throw new IllegalArgumentException("INVALID_INTERVAL");
  if(Duration.between(start,end).toMinutes()>120)throw new IllegalArgumentException("DURATION_TOO_LONG");
  if(key!=null){var old=repo.findByIdempotencyKey(key);if(old.isPresent())return old.get();}
  if(repo.existsByPatientIdentityIdAndStatusIn(patientIdentity,ACTIVE_PATIENT_BOOKING))throw new ActiveAppointmentException();
  try{var x=repo.saveAndFlush(Appointment.pending(patient,patientIdentity,doctor,doctorIdentity,start,end,reason,key));event(x,"AppointmentCreated");slots.afterCommit();return x;}
  catch(DataIntegrityViolationException e){if(String.valueOf(e.getMostSpecificCause().getMessage()).contains("uq_patient_active_appointment"))throw new ActiveAppointmentException();throw new SlotConflictException();}
 }
 public Appointment assign(UUID id,UUID doctor,UUID doctorIdentity,Instant start,Instant end){var x=locked(id);if(x.status!=AppointmentStatus.PENDING)throw new IllegalStateException("INVALID_TRANSITION");if((start==null)!=(end==null))throw new IllegalArgumentException("START_AND_END_REQUIRED_TOGETHER");if(start!=null){if(!start.isBefore(end)||start.isBefore(Instant.now()))throw new IllegalArgumentException("INVALID_INTERVAL");x.startAt=start;x.endAt=end;}x.doctorId=doctor;x.doctorIdentityId=doctorIdentity;x.transition(AppointmentStatus.ASSIGNED);flushConflict(x);event(x,"AppointmentAssigned");slots.afterCommit();return x;}
 public Appointment transition(UUID id,AppointmentStatus target){var x=locked(id);x.transition(target);repo.save(x);event(x,"Appointment"+target);return x;}
 public Appointment cancel(UUID id,String reason){if(reason==null||reason.isBlank())throw new IllegalArgumentException("CANCEL_REASON_REQUIRED");var x=locked(id);x.transition(AppointmentStatus.CANCELLED);x.cancelReason=reason;event(x,"AppointmentCancelled");slots.afterCommit();return x;}
 public Appointment reschedule(UUID id,Instant start,Instant end,String key){var old=locked(id);if(!EnumSet.of(AppointmentStatus.PENDING,AppointmentStatus.ASSIGNED,AppointmentStatus.CONFIRMED).contains(old.status))throw new IllegalStateException("INVALID_TRANSITION");old.transition(AppointmentStatus.CANCELLED);old.cancelReason="RESCHEDULED";repo.flush();var next=book(old.patientId,old.patientIdentityId,old.doctorId,old.doctorIdentityId,start,end,old.reason,key);next.parentId=old.id;event(next,"AppointmentRescheduled");return next;}
 public Appointment requireFollowUp(UUID completed,String reason,Instant notBefore){if(reason==null||reason.isBlank())throw new IllegalArgumentException("FOLLOW_UP_REASON_REQUIRED");if(notBefore==null)throw new IllegalArgumentException("FOLLOW_UP_DATE_REQUIRED");var old=locked(completed);if(old.status==AppointmentStatus.IN_PROGRESS)old.transition(AppointmentStatus.COMPLETED);if(old.status!=AppointmentStatus.COMPLETED)throw new IllegalStateException("INVALID_TRANSITION");old.transition(AppointmentStatus.FOLLOW_UP_REQUIRED);old.followUpReason=reason;old.followUpNotBefore=notBefore;event(old,"FollowUpRequired");return old;}
 public Appointment followUp(UUID parent,Instant start,Instant end,String key){var old=locked(parent);if(old.status!=AppointmentStatus.FOLLOW_UP_REQUIRED)throw new IllegalStateException("FOLLOW_UP_NOT_REQUIRED");if(old.followUpNotBefore!=null&&start.isBefore(old.followUpNotBefore))throw new IllegalArgumentException("FOLLOW_UP_TOO_EARLY");var next=book(old.patientId,old.patientIdentityId,old.doctorId,old.doctorIdentityId,start,end,old.followUpReason,key);next.parentId=old.id;old.status=AppointmentStatus.COMPLETED;event(next,"FollowUpBooked");return next;}
 private Appointment locked(UUID id){return repo.findLocked(id).orElseThrow(NoSuchElementException::new);}
 private void flushConflict(Appointment x){try{repo.saveAndFlush(x);}catch(DataIntegrityViolationException e){throw new SlotConflictException();}}
 private void event(Appointment x,String type){var e=new OutboxEvent(x.id,type,"{}");e.payload="{\"eventId\":\""+e.id+"\",\"appointmentId\":\""+x.id+"\",\"patientIdentityId\":\""+x.patientIdentityId+"\",\"status\":\""+x.status+"\",\"startAt\":\""+x.startAt+"\"}";outbox.save(e);}
 static class SlotConflictException extends RuntimeException{}
 static class ActiveAppointmentException extends RuntimeException{}
}

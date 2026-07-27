package com.dermai.appointment;
import org.springframework.dao.DataIntegrityViolationException;import org.springframework.stereotype.Service;import org.springframework.transaction.annotation.Transactional;import java.time.*;import java.util.*;
@Service @Transactional
public class AppointmentService{
 private final AppointmentRepository repo;private final OutboxRepository outbox;private final SlotUpdateBroadcaster slots;private final AppointmentNotificationRepository notifications;
 AppointmentService(AppointmentRepository r,OutboxRepository o,SlotUpdateBroadcaster slots,AppointmentNotificationRepository notifications){repo=r;outbox=o;this.slots=slots;this.notifications=notifications;}
 public Appointment book(UUID patient,UUID patientIdentity,UUID doctor,UUID doctorIdentity,Instant start,Instant end,String reason,String key){
  if(!start.isBefore(end)||start.isBefore(Instant.now()))throw new IllegalArgumentException("INVALID_INTERVAL");
  if(Duration.between(start,end).toMinutes()>120)throw new IllegalArgumentException("DURATION_TOO_LONG");
  if(key!=null){var old=repo.findByIdempotencyKey(key);if(old.isPresent())return old.get();}
  try{var x=repo.saveAndFlush(Appointment.pending(patient,patientIdentity,doctor,doctorIdentity,start,end,reason,key));event(x,"AppointmentCreated");notify(x,"REQUEST_CREATED","Đã gửi yêu cầu đặt lịch","Yêu cầu đặt lịch của bạn đã được ghi nhận.");slots.afterCommit();return x;}
  catch(DataIntegrityViolationException e){throw conflict(e);}
 }
 public Appointment hold(UUID patient,UUID patientIdentity,UUID doctor,UUID doctorIdentity,Instant start,Instant end){
  if(doctor==null||doctorIdentity==null||!start.isBefore(end)||start.isBefore(Instant.now()))throw new IllegalArgumentException("INVALID_HOLD");
  try{var x=repo.saveAndFlush(Appointment.held(patient,patientIdentity,doctor,doctorIdentity,start,end));slots.afterCommit();return x;}catch(DataIntegrityViolationException e){throw conflict(e);}
 }
 public Appointment propose(UUID patient,UUID patientIdentity,UUID doctor,UUID doctorIdentity,Instant start,Instant end,String reason){
  if(patient==null||patientIdentity==null||doctor==null||doctorIdentity==null||reason==null||reason.isBlank()||!start.isBefore(end)||start.isBefore(Instant.now()))throw new IllegalArgumentException("INVALID_PROPOSAL");
  try{var x=repo.saveAndFlush(Appointment.proposed(patient,patientIdentity,doctor,doctorIdentity,start,end,reason.trim()));event(x,"AppointmentProposed");notify(x,"BOOKING_PROPOSAL","Lễ tân đề nghị lịch khám","Lễ tân đã chọn lịch "+localTime(start)+". Vui lòng xác nhận trong 10 phút.");slots.afterCommit();return x;}catch(DataIntegrityViolationException e){throw conflict(e);}
 }
 public Appointment acceptProposal(UUID id,UUID patientIdentity){
  var x=locked(id);if(x.status!=AppointmentStatus.PROPOSED||!patientIdentity.equals(x.patientIdentityId))throw new IllegalStateException("INVALID_PROPOSAL");
  if(x.holdExpiresAt==null||x.holdExpiresAt.isBefore(Instant.now())){x.transition(AppointmentStatus.CANCELLED);x.cancelReason="PROPOSAL_EXPIRED";x.patientHidden=true;slots.afterCommit();throw new ProposalExpiredException();}
  x.holdExpiresAt=null;x.transition(AppointmentStatus.CONFIRMED);event(x,"AppointmentConfirmedByPatient");notify(x,"PROPOSAL_ACCEPTED","Đã xác nhận lịch khám","Lịch khám "+localTime(x.startAt)+" đã được xác nhận.");slots.afterCommit();return x;
 }
 public Appointment declineProposal(UUID id,UUID patientIdentity){
  var x=locked(id);if(x.status!=AppointmentStatus.PROPOSED||!patientIdentity.equals(x.patientIdentityId))throw new IllegalStateException("INVALID_PROPOSAL");x.transition(AppointmentStatus.CANCELLED);x.cancelReason="PATIENT_DECLINED_PROPOSAL";x.patientHidden=true;event(x,"AppointmentProposalDeclined");notify(x,"PROPOSAL_DECLINED","Đã từ chối lịch đề nghị","Khung giờ đã được trả lại để người khác có thể đặt.");slots.afterCommit();return x;
 }
 public Appointment confirmHold(UUID id,UUID patientIdentity,String reason,String key){
  var x=locked(id);if(x.status!=AppointmentStatus.HELD||!patientIdentity.equals(x.patientIdentityId))throw new IllegalStateException("INVALID_HOLD");
  if(x.holdExpiresAt==null||x.holdExpiresAt.isBefore(Instant.now())){x.transition(AppointmentStatus.CANCELLED);x.cancelReason="HOLD_EXPIRED";slots.afterCommit();throw new HoldExpiredException();}
  if(reason==null||reason.isBlank())throw new IllegalArgumentException("REASON_REQUIRED");x.reason=reason.trim();x.idempotencyKey=key;x.holdExpiresAt=null;x.transition(AppointmentStatus.ASSIGNED);event(x,"AppointmentCreated");notify(x,"REQUEST_CREATED","Đã gửi yêu cầu đặt lịch","Yêu cầu đặt lịch của bạn đã được ghi nhận.");slots.afterCommit();return x;
 }
 public void releaseHold(UUID id,UUID patientIdentity){var x=locked(id);if(!patientIdentity.equals(x.patientIdentityId))throw new IllegalStateException("INVALID_HOLD");if(x.status==AppointmentStatus.HELD){x.transition(AppointmentStatus.CANCELLED);x.cancelReason="HOLD_RELEASED";x.patientHidden=true;slots.afterCommit();}}
 public Appointment assign(UUID id,UUID doctor,UUID doctorIdentity,Instant start,Instant end){var x=locked(id);if(x.status!=AppointmentStatus.PENDING)throw new IllegalStateException("INVALID_TRANSITION");if((start==null)!=(end==null))throw new IllegalArgumentException("START_AND_END_REQUIRED_TOGETHER");if(start!=null){if(!start.isBefore(end)||start.isBefore(Instant.now()))throw new IllegalArgumentException("INVALID_INTERVAL");x.startAt=start;x.endAt=end;}x.doctorId=doctor;x.doctorIdentityId=doctorIdentity;x.transition(AppointmentStatus.ASSIGNED);flushConflict(x);event(x,"AppointmentAssigned");slots.afterCommit();return x;}
 public Appointment transition(UUID id,AppointmentStatus target){var x=locked(id);x.transition(target);repo.save(x);event(x,"Appointment"+target);if(target==AppointmentStatus.CONFIRMED)notify(x,"CONFIRMED","Lịch khám đã được xác nhận","Lễ tân đã xác nhận lịch khám của bạn.");if(target==AppointmentStatus.COMPLETED)notify(x,"COMPLETED","Buổi khám đã hoàn thành","Bạn có thể đánh giá trải nghiệm tại phòng khám.");return x;}
 public Appointment noShow(UUID id){var x=locked(id);if(x.startAt.plus(Duration.ofMinutes(30)).isAfter(Instant.now()))throw new IllegalStateException("NO_SHOW_TOO_EARLY");x.transition(AppointmentStatus.NO_SHOW);event(x,"AppointmentNoShow");notify(x,"NO_SHOW","Ghi nhận không đến khám","Lịch khám đã được ghi nhận là không đến đúng hẹn.");slots.afterCommit();return x;}
 public Appointment cancel(UUID id,String reason){if(reason==null||reason.isBlank())throw new IllegalArgumentException("CANCEL_REASON_REQUIRED");var x=locked(id);x.transition(AppointmentStatus.CANCELLED);x.cancelReason=reason;event(x,"AppointmentCancelled");notify(x,"CANCELLED","Lịch khám đã hủy",reason);slots.afterCommit();return x;}
 public Appointment reschedule(UUID id,Instant start,Instant end,String key){var old=locked(id);if(!EnumSet.of(AppointmentStatus.PENDING,AppointmentStatus.ASSIGNED,AppointmentStatus.CONFIRMED).contains(old.status))throw new IllegalStateException("INVALID_TRANSITION");old.transition(AppointmentStatus.CANCELLED);old.cancelReason="RESCHEDULED";repo.flush();var next=book(old.patientId,old.patientIdentityId,old.doctorId,old.doctorIdentityId,start,end,old.reason,key);next.parentId=old.id;event(next,"AppointmentRescheduled");notify(next,"RESCHEDULED","Lịch khám đã được đổi","Lịch khám của bạn đã chuyển sang thời gian mới.");return next;}
 public Appointment requireFollowUp(UUID completed,String reason,Instant notBefore){if(reason==null||reason.isBlank())throw new IllegalArgumentException("FOLLOW_UP_REASON_REQUIRED");if(notBefore==null)throw new IllegalArgumentException("FOLLOW_UP_DATE_REQUIRED");var old=locked(completed);if(old.status==AppointmentStatus.IN_PROGRESS)old.transition(AppointmentStatus.COMPLETED);if(old.status!=AppointmentStatus.COMPLETED)throw new IllegalStateException("INVALID_TRANSITION");old.transition(AppointmentStatus.FOLLOW_UP_REQUIRED);old.followUpReason=reason;old.followUpNotBefore=notBefore;event(old,"FollowUpRequired");return old;}
 public Appointment followUp(UUID parent,Instant start,Instant end,String key){var old=locked(parent);if(old.status!=AppointmentStatus.FOLLOW_UP_REQUIRED)throw new IllegalStateException("FOLLOW_UP_NOT_REQUIRED");if(old.followUpNotBefore!=null&&start.isBefore(old.followUpNotBefore))throw new IllegalArgumentException("FOLLOW_UP_TOO_EARLY");var next=book(old.patientId,old.patientIdentityId,old.doctorId,old.doctorIdentityId,start,end,old.followUpReason,key);next.parentId=old.id;old.status=AppointmentStatus.COMPLETED;event(next,"FollowUpBooked");return next;}
 private Appointment locked(UUID id){return repo.findLocked(id).orElseThrow(NoSuchElementException::new);}
 private void flushConflict(Appointment x){try{repo.saveAndFlush(x);}catch(DataIntegrityViolationException e){throw new SlotConflictException();}}
 private RuntimeException conflict(DataIntegrityViolationException e){String message=String.valueOf(e.getMostSpecificCause().getMessage());return message.contains("no_patient_overlap")?new PatientOverlapException():new SlotConflictException();}
 private String localTime(Instant value){return java.time.format.DateTimeFormatter.ofPattern("HH:mm 'ngày' dd/MM/yyyy").withZone(ZoneId.of("Asia/Ho_Chi_Minh")).format(value);}
 void notify(Appointment x,String type,String title,String body){if(!notifications.existsByAppointmentIdAndNotificationType(x.id,type))notifications.save(new AppointmentNotification(x,type,title,body));}
 private void event(Appointment x,String type){var e=new OutboxEvent(x.id,type,"{}");e.payload="{\"eventId\":\""+e.id+"\",\"appointmentId\":\""+x.id+"\",\"patientIdentityId\":\""+x.patientIdentityId+"\",\"status\":\""+x.status+"\",\"startAt\":\""+x.startAt+"\"}";outbox.save(e);}
 static class SlotConflictException extends RuntimeException{}
 static class PatientOverlapException extends RuntimeException{}
 static class HoldExpiredException extends RuntimeException{}
 static class ProposalExpiredException extends RuntimeException{}
}

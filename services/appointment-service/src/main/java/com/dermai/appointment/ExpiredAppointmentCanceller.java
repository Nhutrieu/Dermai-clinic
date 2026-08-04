package com.dermai.appointment;
import org.springframework.scheduling.annotation.Scheduled;import org.springframework.stereotype.Component;import org.springframework.transaction.annotation.Transactional;import java.time.*;import java.util.*;
@Component
class ExpiredAppointmentCanceller{
 private static final ZoneId CLINIC_ZONE=ZoneId.of("Asia/Ho_Chi_Minh");
 private static final Set<AppointmentStatus> UNCONFIRMED=EnumSet.of(AppointmentStatus.PENDING,AppointmentStatus.ASSIGNED);
 private final AppointmentRepository appointments;private final AppointmentService service;private final SlotUpdateBroadcaster broadcaster;
 ExpiredAppointmentCanceller(AppointmentRepository appointments,AppointmentService service,SlotUpdateBroadcaster broadcaster){this.appointments=appointments;this.service=service;this.broadcaster=broadcaster;}
 @Transactional @Scheduled(initialDelay=30000,fixedDelayString="${appointments.expiry-delay-ms:60000}")
 public void cancelMissedAppointments(){
  var now=Instant.now();

  // A confirmed appointment that never starts is a patient no-show after the
  // clinic's 30-minute grace period. This keeps NO_SHOW distinct from requests
  // that were never confirmed by reception.
  var absent=appointments.findByStatusAndStartAtBefore(AppointmentStatus.CONFIRMED,now.minus(Duration.ofMinutes(30)));
  absent.forEach(x->service.noShow(x.id));

  Instant startOfToday=LocalDate.now(CLINIC_ZONE).atStartOfDay(CLINIC_ZONE).toInstant();
  var expired=appointments.findByStatusInAndEndAtBefore(UNCONFIRMED,startOfToday);
  expired.forEach(x->{x.status=AppointmentStatus.CANCELLED;x.cancelReason="Tự động hủy: yêu cầu chưa được xác nhận trước khi ngày khám kết thúc.";x.updatedAt=now;});
  if(!expired.isEmpty()){appointments.saveAll(expired);broadcaster.afterCommit();}
 }
}

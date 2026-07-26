package com.dermai.appointment;
import org.springframework.scheduling.annotation.Scheduled;import org.springframework.stereotype.Component;import org.springframework.transaction.annotation.Transactional;import java.time.*;import java.util.*;
@Component
class ExpiredAppointmentCanceller{
 private static final ZoneId CLINIC_ZONE=ZoneId.of("Asia/Ho_Chi_Minh");
 private static final Set<AppointmentStatus> WAITING=EnumSet.of(AppointmentStatus.PENDING,AppointmentStatus.ASSIGNED,AppointmentStatus.CONFIRMED);
 private final AppointmentRepository appointments;private final SlotUpdateBroadcaster broadcaster;
 ExpiredAppointmentCanceller(AppointmentRepository appointments,SlotUpdateBroadcaster broadcaster){this.appointments=appointments;this.broadcaster=broadcaster;}
 @Transactional @Scheduled(initialDelay=30000,fixedDelay=600000)
 public void cancelMissedAppointments(){
  Instant startOfToday=LocalDate.now(CLINIC_ZONE).atStartOfDay(CLINIC_ZONE).toInstant();
  var expired=appointments.findByStatusInAndEndAtBefore(WAITING,startOfToday);if(expired.isEmpty())return;
  var now=Instant.now();expired.forEach(x->{x.status=AppointmentStatus.CANCELLED;x.cancelReason="Tự động hủy: bác sĩ chưa bắt đầu ca khám trước khi ngày khám kết thúc.";x.updatedAt=now;});
  appointments.saveAll(expired);broadcaster.afterCommit();
 }
}

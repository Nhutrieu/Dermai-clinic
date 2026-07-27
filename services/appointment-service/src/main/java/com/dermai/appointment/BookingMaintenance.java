package com.dermai.appointment;
import org.springframework.scheduling.annotation.Scheduled;import org.springframework.stereotype.Component;import org.springframework.transaction.annotation.Transactional;import java.time.*;
@Component class BookingMaintenance{
 private final AppointmentRepository appointments;private final AppointmentService service;private final SlotUpdateBroadcaster slots;
 BookingMaintenance(AppointmentRepository appointments,AppointmentService service,SlotUpdateBroadcaster slots){this.appointments=appointments;this.service=service;this.slots=slots;}
 @Transactional @Scheduled(initialDelay=15000,fixedDelay=30000)
 public void expireHolds(){var now=Instant.now();var holds=appointments.findByStatusAndHoldExpiresAtBefore(AppointmentStatus.HELD,now);var proposals=appointments.findByStatusAndHoldExpiresAtBefore(AppointmentStatus.PROPOSED,now);if(holds.isEmpty()&&proposals.isEmpty())return;holds.forEach(x->{x.status=AppointmentStatus.CANCELLED;x.cancelReason="HOLD_EXPIRED";x.patientHidden=true;x.updatedAt=now;});proposals.forEach(x->{x.status=AppointmentStatus.CANCELLED;x.cancelReason="PROPOSAL_EXPIRED";x.patientHidden=true;x.updatedAt=now;service.notify(x,"PROPOSAL_EXPIRED","Đề nghị lịch đã hết hạn","Khung giờ lễ tân đề nghị đã được trả lại vì chưa được xác nhận trong 10 phút.");});appointments.saveAll(holds);appointments.saveAll(proposals);slots.afterCommit();}
 @Transactional @Scheduled(initialDelay=30000,fixedDelay=60000)
 public void createReminders(){Instant now=Instant.now();remind("REMINDER_24H","Nhắc lịch khám ngày mai",now.plus(Duration.ofHours(23)).plus(Duration.ofMinutes(55)),now.plus(Duration.ofHours(24)).plus(Duration.ofMinutes(5)));remind("REMINDER_2H","Sắp đến giờ khám",now.plus(Duration.ofHours(1)).plus(Duration.ofMinutes(55)),now.plus(Duration.ofHours(2)).plus(Duration.ofMinutes(5)));}
 private void remind(String type,String title,Instant from,Instant to){for(var x:appointments.findByStatusAndStartAtBetween(AppointmentStatus.CONFIRMED,from,to))service.notify(x,type,title,"Bạn có lịch khám vào "+x.startAt+". Vui lòng đến đúng giờ.");}
}

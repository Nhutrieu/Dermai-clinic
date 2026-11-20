package com.dermai.appointment;

import jakarta.validation.constraints.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import java.time.*;
import java.util.*;
import java.util.stream.IntStream;

@Service
public class ClinicScheduleService {
 static final ZoneId ZONE=ZoneId.of("Asia/Ho_Chi_Minh");
 private final ClinicWorkdayRepository workdays;
 private final AppointmentRepository appointments;
 private final SlotUpdateBroadcaster slots;
 private final String defaultClosure;
 ClinicScheduleService(ClinicWorkdayRepository workdays,AppointmentRepository appointments,SlotUpdateBroadcaster slots,
   @Value("${clinic.weekly-closure-day:SUNDAY}") String defaultClosure) {
  this.workdays=workdays;this.appointments=appointments;this.slots=slots;
  this.defaultClosure=defaultClosure.trim().toUpperCase(Locale.ROOT);
 }
 public record Day(@Min(1) @Max(7) int weekday,@NotNull Boolean open,@NotNull LocalTime startTime,@NotNull LocalTime endTime) {}
 public record Schedule(List<Day> days,boolean configured) {}
 public List<Day> week() {return snapshot().days();}
 public Schedule snapshot() {
  var saved=new HashMap<Integer,Day>();
  workdays.findAll().forEach(day->saved.put(day.weekday,new Day(day.weekday,day.open,day.startTime,day.endTime)));
  var days=IntStream.rangeClosed(1,7).mapToObj(day->saved.getOrDefault(day,
   new Day(day,!DayOfWeek.of(day).name().equals(defaultClosure),LocalTime.of(8,0),LocalTime.of(17,0)))).toList();
  return new Schedule(days,!saved.isEmpty());
 }
 @Transactional
 public List<Day> save(List<Day> days) {
  if(days==null||days.size()!=7||days.stream().anyMatch(Objects::isNull)
    ||days.stream().map(Day::weekday).distinct().count()!=7)
   throw invalid("Vui lòng cấu hình đủ 7 ngày trong tuần, mỗi ngày một lần.");
  for(var day:days) {
   if(day.weekday()<1||day.weekday()>7||day.open()==null||day.startTime()==null||day.endTime()==null
     ||!day.startTime().isBefore(day.endTime())||Duration.between(day.startTime(),day.endTime()).toMinutes()<30
     ||day.startTime().getSecond()!=0||day.endTime().getSecond()!=0||day.startTime().getNano()!=0||day.endTime().getNano()!=0)
    throw invalid("Giờ đóng cửa phải sau giờ mở cửa ít nhất 30 phút và chính xác đến phút.");
  }
  var conflicts=appointments.findByStatusInAndEndAtAfterOrderByStartAt(AppointmentStatus.slotBlockingStatuses(),Instant.now())
   .stream().filter(appointment->!covers(days,appointment.startAt,appointment.endAt)).toList();
  if(!conflicts.isEmpty()) {
   var first=conflicts.get(0).startAt.atZone(ZONE).format(java.time.format.DateTimeFormatter.ofPattern("HH:mm dd/MM/yyyy"));
   throw new ResponseStatusException(HttpStatus.CONFLICT,"Không thể đổi lịch phòng khám vì có "+conflicts.size()
    +" lịch đang hoạt động nằm ngoài giờ mới; lịch sớm nhất lúc "+first+". Vui lòng đổi hoặc hủy các lịch này trước.");
  }
  workdays.saveAll(days.stream().map(ClinicWorkday::new).toList());
  slots.afterCommit();
  return days.stream().sorted(Comparator.comparingInt(Day::weekday)).toList();
 }
 static Day forDate(List<Day> days,LocalDate date) {
  return days.stream().filter(day->day.weekday()==date.getDayOfWeek().getValue()).findFirst().orElseThrow();
 }
 static boolean covers(List<Day> days,Instant start,Instant end) {
  var from=start.atZone(ZONE);var to=end.atZone(ZONE);var day=forDate(days,from.toLocalDate());
  return day.open()&&from.toLocalDate().equals(to.toLocalDate())&&!from.toLocalTime().isBefore(day.startTime())
   &&!to.toLocalTime().isAfter(day.endTime());
 }
 private ResponseStatusException invalid(String message){return new ResponseStatusException(HttpStatus.BAD_REQUEST,message);}
}

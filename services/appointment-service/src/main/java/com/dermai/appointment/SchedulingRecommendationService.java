package com.dermai.appointment;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpHeaders;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

import java.time.*;
import java.util.*;

@Service
public class SchedulingRecommendationService {
 private static final ZoneId CLINIC_ZONE=ZoneId.of("Asia/Ho_Chi_Minh");
 private static final LocalTime LUNCH_START=LocalTime.of(12,0),LUNCH_END=LocalTime.of(13,0);
 private static final int BOOKING_WINDOW_DAYS=60;
 private static final Set<AppointmentStatus> ACTIVE=EnumSet.of(AppointmentStatus.HELD,AppointmentStatus.PENDING,AppointmentStatus.ASSIGNED,AppointmentStatus.CONFIRMED,AppointmentStatus.IN_PROGRESS,AppointmentStatus.FOLLOW_UP_REQUIRED);
 private final AppointmentRepository appointments;
 private final SchedulingEngine engine;
 private final RestClient doctors;
 private final ClinicClosureRepository closures;

 SchedulingRecommendationService(AppointmentRepository appointments,ClinicClosureRepository closures,@Value("${doctor-service.url}") String doctorUrl){
  this.appointments=appointments;this.closures=closures;this.engine=new SchedulingEngine();this.doctors=RestClient.builder().baseUrl(doctorUrl).build();
 }

 public Result recommend(Request request,String authorization,String role){
  Instant now=Instant.now(),bookingLimit=now.plus(BOOKING_WINDOW_DAYS,java.time.temporal.ChronoUnit.DAYS);
  if(request.preferredStart()==null||request.preferredStart().isBefore(now))throw new IllegalArgumentException("PREFERRED_START_MUST_BE_IN_FUTURE");
  if(request.preferredStart().isAfter(bookingLimit))throw new IllegalArgumentException("BOOKING_TOO_FAR_AHEAD");
  int duration=request.durationMinutes()==null?30:request.durationMinutes();
  if(duration<10||duration>120)throw new IllegalArgumentException("INVALID_DURATION");
  Instant horizon=request.preferredStart().plus(7,java.time.temporal.ChronoUnit.DAYS);if(horizon.isAfter(bookingLimit))horizon=bookingLimit;
  List<DoctorData> doctorData=loadDoctors(authorization,role);
  var busy=appointments.findActiveOverlapping(request.preferredStart(),horizon);
  var patientHistory=request.patientId()==null?List.<Appointment>of():appointments.findByPatientIdOrderByStartAtDesc(request.patientId());
  Map<UUID,Long> workload=new HashMap<>();
  busy.stream().filter(x->x.doctorId!=null&&ACTIVE.contains(x.status)).forEach(x->workload.merge(x.doctorId,1L,Long::sum));
  long maxLoad=Math.max(1,workload.values().stream().mapToLong(Long::longValue).max().orElse(1));
  var candidates=new ArrayList<SchedulingEngine.Candidate>();
  for(var doctor:doctorData){
   if(request.preferredDoctorId()!=null&&!request.preferredDoctorId().equals(doctor.id()))continue;
   if(request.specialtyCode()!=null&&!request.specialtyCode().isBlank()&&!request.specialtyCode().equalsIgnoreCase(doctor.specialtyCode()))continue;
   for(var schedule:doctor.workSchedules()){
    LocalDate first=request.preferredStart().atZone(CLINIC_ZONE).toLocalDate();
    for(int day=0;day<=7;day++){
     LocalDate date=first.plusDays(day);
     if(closures.existsByClosureDate(date))continue;
     if(date.getDayOfWeek().getValue()!=schedule.weekday())continue;
     ZonedDateTime cursor=ZonedDateTime.of(date,schedule.startTime(),CLINIC_ZONE);
     ZonedDateTime workEnd=ZonedDateTime.of(date,schedule.endTime(),CLINIC_ZONE);
     while(!cursor.plusMinutes(duration).isAfter(workEnd)){
      Instant start=cursor.toInstant(),end=cursor.plusMinutes(duration).toInstant();
      if(!start.isBefore(request.preferredStart())&&start.isBefore(horizon)&&!overlapsLunch(cursor,cursor.plusMinutes(duration))){
       boolean leave=doctor.leavePeriods().stream().anyMatch(x->start.isBefore(x.endAt())&&end.isAfter(x.startAt()));
       boolean conflict=busy.stream().anyMatch(x->doctor.id().equals(x.doctorId)&&ACTIVE.contains(x.status)&&start.isBefore(x.endAt)&&end.isAfter(x.startAt));
       double specialty=request.specialtyCode()==null||request.specialtyCode().isBlank()?0.8:1;
       double earliness=1-Math.min(1,Duration.between(request.preferredStart(),start).toHours()/168d);
       double capacity=1-(workload.getOrDefault(doctor.id(),0L)/(double)(maxLoad+1));
       double continuity=patientHistory.stream().anyMatch(x->doctor.id().equals(x.doctorId))?1:0;
       double preference=doctor.id().equals(request.preferredDoctorId())?1:0;
       candidates.add(new SchedulingEngine.Candidate(doctor.id(),start,end,specialty,earliness,capacity,continuity,preference,true,leave,conflict));
      }
      cursor=cursor.plusMinutes(schedule.slotMinutes());
     }
    }
   }
  }
  var recommendations=engine.recommend(candidates,request.limit()==null?5:request.limit());
  Map<UUID,DoctorData> byId=new HashMap<>();doctorData.forEach(x->byId.put(x.id(),x));
  return new Result(recommendations.stream().map(x->{var d=byId.get(x.doctorId());return new Item(x.doctorId(),d.identityId(),d.fullName(),d.specialtyCode(),x.startAt(),x.endAt(),x.score(),x.reasons());}).toList(),"weighted-fair-v2",CLINIC_ZONE.getId());
 }

 public Availability availability(UUID doctorId,LocalDate date,int duration,UUID viewerIdentity,String authorization,String role){
  if(duration<10||duration>120)throw new IllegalArgumentException("INVALID_DURATION");
  LocalDate today=LocalDate.now(CLINIC_ZONE);
  if(date.isBefore(today)||date.isAfter(today.plusDays(BOOKING_WINDOW_DAYS)))throw new IllegalArgumentException("DATE_OUTSIDE_BOOKING_WINDOW");
  var doctor=loadDoctors(authorization,role).stream().filter(x->doctorId.equals(x.id())).findFirst().orElseThrow(()->new IllegalArgumentException("DOCTOR_NOT_AVAILABLE"));
  if(closures.existsByClosureDate(date))return new Availability(List.of(),CLINIC_ZONE.getId());
  Instant dayStart=date.atStartOfDay(CLINIC_ZONE).toInstant(),dayEnd=date.plusDays(1).atStartOfDay(CLINIC_ZONE).toInstant();
  var busy=appointments.findActiveOverlapping(dayStart,dayEnd);
  var items=new ArrayList<AvailabilityItem>();
  for(var schedule:doctor.workSchedules()){
   if(date.getDayOfWeek().getValue()!=schedule.weekday())continue;
   ZonedDateTime cursor=ZonedDateTime.of(date,schedule.startTime(),CLINIC_ZONE),workEnd=ZonedDateTime.of(date,schedule.endTime(),CLINIC_ZONE);
   while(!cursor.plusMinutes(duration).isAfter(workEnd)){
    Instant start=cursor.toInstant(),end=cursor.plusMinutes(duration).toInstant();
    if(start.isAfter(Instant.now())&&!overlapsLunch(cursor,cursor.plusMinutes(duration))){
     boolean onLeave=doctor.leavePeriods().stream().anyMatch(x->start.isBefore(x.endAt())&&end.isAfter(x.startAt()));
     var conflict=busy.stream().filter(x->doctorId.equals(x.doctorId)&&ACTIVE.contains(x.status)&&start.isBefore(x.endAt)&&end.isAfter(x.startAt)).findFirst();
     boolean ownHold=conflict.filter(x->x.status==AppointmentStatus.HELD&&viewerIdentity.equals(x.patientIdentityId)).isPresent();
     boolean otherHold=conflict.filter(x->x.status==AppointmentStatus.HELD&&!viewerIdentity.equals(x.patientIdentityId)).isPresent();
     String status=onLeave?"ON_LEAVE":ownHold?"HELD_BY_YOU":otherHold?"HELD_BY_OTHER":conflict.isPresent()?"BOOKED":"AVAILABLE";
     items.add(new AvailabilityItem(doctor.id(),doctor.identityId(),doctor.fullName(),doctor.specialtyCode(),start,end,status,ownHold?conflict.get().id:null,ownHold?conflict.get().holdExpiresAt:null));
    }
    cursor=cursor.plusMinutes(schedule.slotMinutes());
   }
  }
  items.sort(Comparator.comparing(AvailabilityItem::startAt));
  return new Availability(items,CLINIC_ZONE.getId());
 }

 public void assertAvailable(UUID doctorId,Instant start,Instant end,UUID excludedAppointmentId,String authorization,String role){
  if(doctorId==null)return;
  if(start==null||end==null||!start.isBefore(end)||start.isBefore(Instant.now()))throw new IllegalArgumentException("INVALID_INTERVAL");
  if(start.isAfter(Instant.now().plus(BOOKING_WINDOW_DAYS,java.time.temporal.ChronoUnit.DAYS)))throw new SlotUnavailableException("BOOKING_TOO_FAR_AHEAD");
  var doctor=loadDoctors(authorization,role).stream().filter(x->doctorId.equals(x.id())).findFirst().orElseThrow(()->new IllegalArgumentException("DOCTOR_NOT_AVAILABLE"));
  ZonedDateTime localStart=start.atZone(CLINIC_ZONE),localEnd=end.atZone(CLINIC_ZONE);
  if(closures.existsByClosureDate(localStart.toLocalDate()))throw new SlotUnavailableException("CLINIC_CLOSED");
  boolean inWorkSchedule=doctor.workSchedules().stream().anyMatch(x->{
   if(localStart.getDayOfWeek().getValue()!=x.weekday()||!localStart.toLocalDate().equals(localEnd.toLocalDate()))return false;
   boolean within=!localStart.toLocalTime().isBefore(x.startTime())&&!localEnd.toLocalTime().isAfter(x.endTime());
   long offset=Duration.between(x.startTime(),localStart.toLocalTime()).toMinutes();
   return within&&offset>=0&&offset%x.slotMinutes()==0&&!overlapsLunch(localStart,localEnd);
  });
  if(!inWorkSchedule)throw new SlotUnavailableException("OUTSIDE_DOCTOR_WORK_SCHEDULE");
  if(doctor.leavePeriods().stream().anyMatch(x->start.isBefore(x.endAt())&&end.isAfter(x.startAt())))throw new SlotUnavailableException("DOCTOR_ON_LEAVE");
  boolean conflict=appointments.findActiveOverlapping(start,end).stream().anyMatch(x->doctorId.equals(x.doctorId)&&!x.id.equals(excludedAppointmentId));
 if(conflict)throw new SlotUnavailableException("DOCTOR_SLOT_CONFLICT");
 }
 private boolean overlapsLunch(ZonedDateTime start,ZonedDateTime end){return start.toLocalTime().isBefore(LUNCH_END)&&end.toLocalTime().isAfter(LUNCH_START);}

 private List<DoctorData> loadDoctors(String authorization,String role){
  List<DoctorData> data=doctors.get().uri("/api/v1/doctors/scheduling-data")
   .header(HttpHeaders.AUTHORIZATION,authorization==null?"":authorization).header("X-User-Role",role)
   .retrieve().body(new ParameterizedTypeReference<>(){});
  return data==null?List.of():data;
 }

 public record Request(UUID patientId,String specialtyCode,UUID preferredDoctorId,Instant preferredStart,Integer durationMinutes,Integer limit){}
 public record Result(List<Item> items,String algorithmVersion,String timezone){}
 public record Item(UUID doctorId,UUID doctorIdentityId,String doctorName,String specialtyCode,Instant startAt,Instant endAt,double score,List<String> reasons){}
 public record Availability(List<AvailabilityItem> items,String timezone){}
 public record AvailabilityItem(UUID doctorId,UUID doctorIdentityId,String doctorName,String specialtyCode,Instant startAt,Instant endAt,String status,UUID holdId,Instant holdExpiresAt){}
 record DoctorData(UUID id,UUID identityId,String fullName,String specialtyCode,int experienceYears,List<ScheduleData> workSchedules,List<LeaveData> leavePeriods){}
 record ScheduleData(UUID id,UUID doctorId,short weekday,LocalTime startTime,LocalTime endTime,int slotMinutes){}
 record LeaveData(Instant startAt,Instant endAt){}
 public static class SlotUnavailableException extends RuntimeException{SlotUnavailableException(String message){super(message);}}
}

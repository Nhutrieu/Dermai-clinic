package com.dermai.appointment;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.any;
import java.time.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

class ClinicScheduleServiceTest {
 private final ClinicWorkdayRepository repository=mock(ClinicWorkdayRepository.class);
 private final AppointmentRepository appointments=mock(AppointmentRepository.class);
 private final SlotUpdateBroadcaster slots=mock(SlotUpdateBroadcaster.class);
 private final ClinicScheduleService service=new ClinicScheduleService(repository,appointments,slots,"SUNDAY");
 @Test void savesAllSevenDaysAndOverridesTheEnvironmentAfterReload() {
  var days=service.week().stream().map(day->new ClinicScheduleService.Day(day.weekday(),true,day.startTime(),day.endTime())).toList();
  when(repository.saveAll(any())).thenAnswer(call->{
   List<ClinicWorkday> saved=call.getArgument(0);
   when(repository.findAll()).thenReturn(saved);
   return saved;
  });
  service.save(days);
  var reloaded=new ClinicScheduleService(repository,appointments,slots,"SUNDAY");
  assertThat(reloaded.week()).hasSize(7).allSatisfy(day->assertThat(day.open()).isTrue());
  verify(slots).afterCommit();
 }
 @Test void refusesClosingAWeekdayThatHasAnActiveAppointmentWithoutWriting() {
  var start=LocalDate.now(ClinicScheduleService.ZONE).plusDays(1).atTime(9,0).atZone(ClinicScheduleService.ZONE).toInstant();
  var appointment=new Appointment();appointment.startAt=start;appointment.endAt=start.plusSeconds(1800);
  when(appointments.findByStatusInAndEndAtAfterOrderByStartAt(any(),any())).thenReturn(List.of(appointment));
  var closed=service.week().stream().map(day->new ClinicScheduleService.Day(day.weekday(),false,day.startTime(),day.endTime())).toList();
  assertThatThrownBy(()->service.save(closed)).isInstanceOfSatisfying(ResponseStatusException.class,
    error->assertThat(error.getStatusCode()).isEqualTo(HttpStatus.CONFLICT));
  verify(repository,never()).saveAll(any());verifyNoInteractions(slots);
 }
 @Test void refusesShortenedHoursOverlappingAnAppointmentEnd() {
  var start=LocalDate.now(ClinicScheduleService.ZONE).plusDays(1).atTime(16,30).atZone(ClinicScheduleService.ZONE).toInstant();
  var appointment=new Appointment();appointment.startAt=start;appointment.endAt=start.plusSeconds(1800);
  when(appointments.findByStatusInAndEndAtAfterOrderByStartAt(any(),any())).thenReturn(List.of(appointment));
  var days=service.week().stream().map(day->new ClinicScheduleService.Day(day.weekday(),true,LocalTime.of(8,0),LocalTime.of(16,45))).toList();
  assertThatThrownBy(()->service.save(days)).isInstanceOfSatisfying(ResponseStatusException.class,
    error->assertThat(error.getStatusCode()).isEqualTo(HttpStatus.CONFLICT));
  verify(repository,never()).saveAll(any());
 }
 @Test void rejectsMissingDaysDuplicateDaysAndInvalidTimes() {
  var week=service.week();
  assertThatThrownBy(()->service.save(week.subList(0,6))).isInstanceOf(ResponseStatusException.class);
  assertThatThrownBy(()->service.save(Collections.nCopies(7,week.get(0)))).isInstanceOf(ResponseStatusException.class);
  var bad=new ArrayList<>(week);bad.set(0,new ClinicScheduleService.Day(1,true,LocalTime.of(10,0),LocalTime.of(9,0)));
  assertThatThrownBy(()->service.save(bad)).isInstanceOf(ResponseStatusException.class);
  bad.set(0,new ClinicScheduleService.Day(1,true,LocalTime.of(9,0),LocalTime.of(9,15)));
  assertThatThrownBy(()->service.save(bad)).isInstanceOf(ResponseStatusException.class);
  verify(repository,never()).saveAll(any());
 }
 @Test void onlyAdminCanChangeTheScheduleAndDoctorsCanReadItsOverview() {
  var controller=new ClinicScheduleController(service);
  for(var role:List.of("PATIENT","DOCTOR","RECEPTIONIST")) {
   assertThatThrownBy(()->controller.get(role)).isInstanceOf(AppointmentController.Forbidden.class);
   assertThatThrownBy(()->controller.save(role,List.of())).isInstanceOf(AppointmentController.Forbidden.class);
  }
  assertThat(controller.overview("DOCTOR").days()).hasSize(7);
  assertThatThrownBy(()->controller.overview("PATIENT")).isInstanceOf(AppointmentController.Forbidden.class);
  assertThatThrownBy(()->controller.overview("RECEPTIONIST")).isInstanceOf(AppointmentController.Forbidden.class);
  assertThat(controller.get("ADMIN")).hasSize(7);
  assertThat(controller.save("ADMIN",service.week())).hasSize(7);
 }
}

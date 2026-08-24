package com.dermai.doctor;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.DayOfWeek;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.ZoneId;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

class DoctorScheduleConflictTest {
  private static final ZoneId CLINIC_ZONE = ZoneId.of("Asia/Ho_Chi_Minh");

  @Test
  void conflictResponseHasAStableCodeAndHumanReadableDetail() {
    var response = new DoctorErrors().activeAppointmentConflict(
        new ActiveAppointmentConflict("Khoảng nghỉ xung đột với lịch đang hoạt động."));

    assertThat(response.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
    assertThat(response.getBody().getDetail()).contains("lịch đang hoạt động");
    assertThat(response.getBody().getProperties()).containsEntry(
        "code", "ACTIVE_APPOINTMENT_CONFLICT");
  }

  @Test
  void rejectsScheduleThatWouldOrphanAConfirmedAppointment() {
    var doctors = mock(DoctorRepository.class);
    var schedules = mock(ScheduleRepository.class);
    var leaves = mock(LeaveRepository.class);
    var appointments = mock(AppointmentScheduleClient.class);
    var doctor = doctor();
    when(doctors.findById(doctor.id)).thenReturn(Optional.of(doctor));
    var visit = futureVisitAt(LocalTime.of(9, 0));
    when(appointments.upcomingBlocking(doctor.id)).thenReturn(List.of(visit));
    var controller = new DoctorController(doctors, schedules, leaves,
        mock(DoctorProfileWebSocketHandler.class), appointments);
    short weekday = (short) visit.startAt().atZone(CLINIC_ZONE).getDayOfWeek().getValue();

    assertThatThrownBy(() -> controller.schedule(doctor.id, UUID.randomUUID(), "ADMIN", List.of(
        new DoctorController.ScheduleBody(weekday, LocalTime.of(10, 0), LocalTime.of(12, 0), 30))))
        .isInstanceOfSatisfying(ResponseStatusException.class, error -> {
          assertThat(error.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
          assertThat(error.getReason()).contains("lịch đang hoạt động").contains("đổi hoặc hủy");
        });

    verify(schedules, never()).deleteAll(any());
    verify(schedules, never()).saveAll(any());
  }

  @Test
  void permitsScheduleThatStillContainsEveryConfirmedAppointment() {
    var doctors = mock(DoctorRepository.class);
    var schedules = mock(ScheduleRepository.class);
    var leaves = mock(LeaveRepository.class);
    var appointments = mock(AppointmentScheduleClient.class);
    var doctor = doctor();
    when(doctors.findById(doctor.id)).thenReturn(Optional.of(doctor));
    when(schedules.findByDoctorId(doctor.id)).thenReturn(List.of());
    var visit = futureVisitAt(LocalTime.of(9, 0));
    when(appointments.upcomingBlocking(doctor.id)).thenReturn(List.of(visit));
    var controller = new DoctorController(doctors, schedules, leaves,
        mock(DoctorProfileWebSocketHandler.class), appointments);
    short weekday = (short) visit.startAt().atZone(CLINIC_ZONE).getDayOfWeek().getValue();

    controller.schedule(doctor.id, UUID.randomUUID(), "ADMIN", List.of(
        new DoctorController.ScheduleBody(weekday, LocalTime.of(8, 0), LocalTime.of(12, 0), 30)));

    verify(schedules).deleteAll(List.of());
    verify(schedules).saveAll(any());
  }

  @Test
  void rejectsLeaveThatOverlapsAConfirmedAppointment() {
    var doctors = mock(DoctorRepository.class);
    var leaves = mock(LeaveRepository.class);
    var appointments = mock(AppointmentScheduleClient.class);
    var doctor = doctor();
    when(doctors.findById(doctor.id)).thenReturn(Optional.of(doctor));
    var visit = futureVisitAt(LocalTime.of(9, 0));
    when(appointments.upcomingBlocking(doctor.id)).thenReturn(List.of(visit));
    var controller = new DoctorController(doctors, mock(ScheduleRepository.class), leaves,
        mock(DoctorProfileWebSocketHandler.class), appointments);

    assertThatThrownBy(() -> controller.leave(doctor.id, UUID.randomUUID(), "ADMIN",
        new DoctorController.LeaveBody(visit.startAt().minusSeconds(60), visit.endAt(), "Nghỉ")))
        .isInstanceOfSatisfying(ResponseStatusException.class, error -> {
          assertThat(error.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
          assertThat(error.getReason()).contains("lịch đang hoạt động").contains("đổi hoặc hủy");
        });

    verify(leaves, never()).save(any());
  }

  private Doctor doctor() {
    return new Doctor(UUID.randomUUID(), "Bác sĩ Bình", "GENERAL_DERMATOLOGY");
  }

  private AppointmentScheduleClient.AppointmentSlot futureVisitAt(LocalTime time) {
    LocalDate date = LocalDate.now(CLINIC_ZONE).plusDays(7);
    while (date.getDayOfWeek() == DayOfWeek.SUNDAY) date = date.plusDays(1);
    Instant start = date.atTime(time).atZone(CLINIC_ZONE).toInstant();
    return new AppointmentScheduleClient.AppointmentSlot(UUID.randomUUID(), start, start.plusSeconds(1_800), "ASSIGNED");
  }
}

package com.dermai.appointment;

import java.time.Instant;
import java.util.EnumSet;
import java.util.List;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/v1/appointments/internal/doctors")
class AppointmentScheduleQueryController {
  private static final EnumSet<AppointmentStatus> SCHEDULE_BLOCKING_STATUSES = EnumSet.of(
      AppointmentStatus.HELD,
      AppointmentStatus.PROPOSED,
      AppointmentStatus.PENDING,
      AppointmentStatus.ASSIGNED,
      AppointmentStatus.CONFIRMED,
      AppointmentStatus.CHECKED_IN,
      AppointmentStatus.IN_PROGRESS
  );

  private final AppointmentRepository appointments;
  private final String serviceToken;

  AppointmentScheduleQueryController(
      AppointmentRepository appointments,
      @Value("${security.service-token:}") String serviceToken) {
    this.appointments = appointments;
    this.serviceToken = serviceToken;
  }

  @GetMapping("/{doctorId}/blocking-upcoming")
  List<AppointmentSlot> blockingUpcoming(
      @PathVariable UUID doctorId,
      @RequestHeader("X-Service-Token") String suppliedToken) {
    requireServiceToken(suppliedToken);
    return appointments.findByDoctorIdAndStatusInAndEndAtAfterOrderByStartAt(
        doctorId,
        SCHEDULE_BLOCKING_STATUSES,
        Instant.now()
    ).stream().map(item -> new AppointmentSlot(item.id, item.startAt, item.endAt, item.status)).toList();
  }

  private void requireServiceToken(String suppliedToken) {
    // This endpoint bypasses end-user authorization and is intentionally service-to-service only.
    if (serviceToken.isBlank() || !serviceToken.equals(suppliedToken)) {
      throw new ResponseStatusException(HttpStatus.FORBIDDEN);
    }
  }

  record AppointmentSlot(UUID id, Instant startAt, Instant endAt, AppointmentStatus status) {}
}

package com.dermai.appointment;

import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.EnumSet;
import java.util.Set;
import java.util.UUID;
import org.springframework.stereotype.Component;

@Component
class BookingPolicy {
  static final int MAX_UPCOMING_APPOINTMENTS = 3;
  static final Set<AppointmentStatus> ACTIVE = EnumSet.of(
      AppointmentStatus.HELD,
      AppointmentStatus.PROPOSED,
      AppointmentStatus.PENDING,
      AppointmentStatus.ASSIGNED,
      AppointmentStatus.CONFIRMED,
      AppointmentStatus.IN_PROGRESS
  );
  private static final ZoneId CLINIC_ZONE = ZoneId.of("Asia/Ho_Chi_Minh");

  private final AppointmentRepository appointments;

  BookingPolicy(AppointmentRepository appointments) {
    this.appointments = appointments;
  }

  void validateNewBooking(
      UUID patientIdentityId,
      UUID doctorId,
      Instant startAt,
      boolean bypassActiveLimit
  ) {
    lock(patientIdentityId);
    var now = Instant.now();
    if (!bypassActiveLimit
        && appointments.countByPatientIdentityIdAndStatusInAndEndAtAfter(
            patientIdentityId, ACTIVE, now
        ) >= MAX_UPCOMING_APPOINTMENTS) {
      throw new ActiveAppointmentLimitException();
    }
    validateSameDoctorDayLocked(patientIdentityId, doctorId, startAt, null);
  }

  void validateDoctorAssignment(
      UUID appointmentId,
      UUID patientIdentityId,
      UUID doctorId,
      Instant startAt
  ) {
    lock(patientIdentityId);
    validateSameDoctorDayLocked(patientIdentityId, doctorId, startAt, appointmentId);
  }

  private void validateSameDoctorDayLocked(
      UUID patientIdentityId,
      UUID doctorId,
      Instant startAt,
      UUID excludedAppointmentId
  ) {
    if (doctorId == null) return;
    LocalDate clinicDate = startAt.atZone(CLINIC_ZONE).toLocalDate();
    Instant from = clinicDate.atStartOfDay(CLINIC_ZONE).toInstant();
    Instant to = clinicDate.plusDays(1).atStartOfDay(CLINIC_ZONE).toInstant();
    boolean duplicate = appointments
        .findByPatientIdentityIdAndDoctorIdAndStatusInAndStartAtGreaterThanEqualAndStartAtLessThan(
            patientIdentityId, doctorId, ACTIVE, from, to
        )
        .stream()
        .anyMatch(existing -> !existing.id.equals(excludedAppointmentId));
    if (duplicate) throw new SameDoctorDayException();
  }

  private void lock(UUID patientIdentityId) {
    appointments.lockPatientBookings(patientIdentityId);
  }

  static class ActiveAppointmentLimitException extends RuntimeException {}
  static class SameDoctorDayException extends RuntimeException {}
}

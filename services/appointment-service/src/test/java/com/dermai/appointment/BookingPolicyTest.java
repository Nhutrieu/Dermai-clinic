package com.dermai.appointment;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.Instant;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class BookingPolicyTest {
  private static final ZoneId CLINIC_ZONE = ZoneId.of("Asia/Ho_Chi_Minh");

  @Test
  void patientCannotCreateAFourthUpcomingAppointment() {
    var repository = mock(AppointmentRepository.class);
    var patient = UUID.randomUUID();
    when(repository.countByPatientIdentityIdAndStatusInAndEndAtAfter(
        eq(patient), eq(BookingPolicy.ACTIVE), any(Instant.class)
    )).thenReturn(3L);
    var policy = new BookingPolicy(repository);

    assertThatThrownBy(() -> policy.validateNewBooking(
        patient, UUID.randomUUID(), Instant.now().plusSeconds(86_400), false
    )).isInstanceOf(BookingPolicy.ActiveAppointmentLimitException.class);
    verify(repository).lockPatientBookings(patient);
  }

  @Test
  void receptionistCanBypassOnlyTheThreeAppointmentLimit() {
    var repository = mock(AppointmentRepository.class);
    var patient = UUID.randomUUID();
    var doctor = UUID.randomUUID();
    var start = Instant.now().plusSeconds(86_400);
    when(repository.findByPatientIdentityIdAndDoctorIdAndStatusInAndStartAtGreaterThanEqualAndStartAtLessThan(
        eq(patient), eq(doctor), eq(BookingPolicy.ACTIVE), any(Instant.class), any(Instant.class)
    )).thenReturn(List.of());
    var policy = new BookingPolicy(repository);

    assertThatCode(() -> policy.validateNewBooking(patient, doctor, start, true))
        .doesNotThrowAnyException();
  }

  @Test
  void sameDoctorCannotBeBookedTwiceOnTheSameClinicDay() {
    var repository = mock(AppointmentRepository.class);
    var patient = UUID.randomUUID();
    var doctor = UUID.randomUUID();
    var start = LocalDate.now(CLINIC_ZONE).plusDays(2).atTime(15, 30).atZone(CLINIC_ZONE).toInstant();
    var existing = Appointment.held(
        UUID.randomUUID(), patient, doctor, UUID.randomUUID(),
        start.minusSeconds(3_600), start.minusSeconds(1_800), new BigDecimal("150000")
    );
    when(repository.findByPatientIdentityIdAndDoctorIdAndStatusInAndStartAtGreaterThanEqualAndStartAtLessThan(
        eq(patient), eq(doctor), eq(BookingPolicy.ACTIVE), any(Instant.class), any(Instant.class)
    )).thenReturn(List.of(existing));
    var policy = new BookingPolicy(repository);

    assertThatThrownBy(() -> policy.validateNewBooking(patient, doctor, start, true))
        .isInstanceOf(BookingPolicy.SameDoctorDayException.class);
  }

  @Test
  void assigningTheSameAppointmentDoesNotConflictWithItself() {
    var repository = mock(AppointmentRepository.class);
    var patient = UUID.randomUUID();
    var doctor = UUID.randomUUID();
    var start = Instant.now().plusSeconds(86_400);
    var current = Appointment.held(
        UUID.randomUUID(), patient, doctor, UUID.randomUUID(), start, start.plusSeconds(1_800), new BigDecimal("150000")
    );
    when(repository.findByPatientIdentityIdAndDoctorIdAndStatusInAndStartAtGreaterThanEqualAndStartAtLessThan(
        eq(patient), eq(doctor), eq(BookingPolicy.ACTIVE), any(Instant.class), any(Instant.class)
    )).thenReturn(List.of(current));
    var policy = new BookingPolicy(repository);

    assertThatCode(() -> policy.validateDoctorAssignment(current.id, patient, doctor, start))
        .doesNotThrowAnyException();
  }
}

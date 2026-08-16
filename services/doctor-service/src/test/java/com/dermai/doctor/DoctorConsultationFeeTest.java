package com.dermai.doctor;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.math.BigDecimal;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.web.server.ResponseStatusException;

class DoctorConsultationFeeTest {
  @Test
  void adminCanUpdateConsultationFeeAndBroadcastTheChange() {
    var doctors = mock(DoctorRepository.class);
    var updates = mock(DoctorProfileWebSocketHandler.class);
    var doctor = new Doctor(UUID.randomUUID(), "Bình", "GENERAL_DERMATOLOGY");
    doctor.consultationFee = new BigDecimal("150000");
    when(doctors.findById(doctor.id)).thenReturn(Optional.of(doctor));
    when(doctors.save(doctor)).thenReturn(doctor);
    var controller = new DoctorController(
        doctors,
        mock(ScheduleRepository.class),
        mock(LeaveRepository.class),
        updates,
        mock(AppointmentScheduleClient.class)
    );

    var updated = controller.updateConsultationFee(
        doctor.id,
        "ADMIN",
        new DoctorController.ConsultationFeeBody(new BigDecimal("180000"))
    );

    assertThat(updated.consultationFee).isEqualByComparingTo("180000");
    verify(updates).broadcastUpdated(doctor.id);
  }

  @Test
  void doctorCannotChangeTheAdminManagedFee() {
    var controller = new DoctorController(
        mock(DoctorRepository.class),
        mock(ScheduleRepository.class),
        mock(LeaveRepository.class),
        mock(DoctorProfileWebSocketHandler.class),
        mock(AppointmentScheduleClient.class)
    );

    assertThatThrownBy(() -> controller.updateConsultationFee(
        UUID.randomUUID(),
        "DOCTOR",
        new DoctorController.ConsultationFeeBody(new BigDecimal("1000"))
    )).isInstanceOf(ResponseStatusException.class);
  }
}

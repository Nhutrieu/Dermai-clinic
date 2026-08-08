package com.dermai.appointment;

import static org.assertj.core.api.Assertions.assertThat;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class AppointmentFeeSnapshotTest {
  @Test
  void heldSlotKeepsTheDoctorFeeAtBookingTime() {
    var quotedFee = new BigDecimal("180000");

    var appointment = Appointment.held(
        UUID.randomUUID(),
        UUID.randomUUID(),
        UUID.randomUUID(),
        UUID.randomUUID(),
        Instant.now().plusSeconds(86_400),
        Instant.now().plusSeconds(88_200),
        quotedFee
    );

    assertThat(appointment.consultationFeeSnapshot).isEqualByComparingTo(quotedFee);
  }

  @Test
  void unassignedSupportRequestMayWaitForDoctorBeforePriceIsQuoted() {
    var appointment = Appointment.pending(
        UUID.randomUUID(),
        UUID.randomUUID(),
        null,
        null,
        Instant.now().plusSeconds(86_400),
        Instant.now().plusSeconds(88_200),
        "Cần lễ tân hỗ trợ chọn bác sĩ",
        null,
        null
    );

    assertThat(appointment.consultationFeeSnapshot).isNull();
  }
}

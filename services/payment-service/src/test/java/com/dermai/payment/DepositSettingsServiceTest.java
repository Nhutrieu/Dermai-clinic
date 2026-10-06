package com.dermai.payment;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.*;
import java.math.BigDecimal;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.server.ResponseStatusException;

class DepositSettingsServiceTest {
  @Test void rejectsInvalidAmountsBeforeWriting() {
    var jdbc = mock(JdbcTemplate.class);
    var service = new DepositSettingsService(jdbc, new BigDecimal("100000"));
    for (var amount : new String[] {"0", "999", "1000.5", "100000001"}) {
      assertThatThrownBy(() -> service.update(new BigDecimal(amount), UUID.randomUUID()))
        .isInstanceOf(ResponseStatusException.class);
    }
    verifyNoInteractions(jdbc);
  }
}

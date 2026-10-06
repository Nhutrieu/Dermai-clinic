package com.dermai.payment;

import java.math.BigDecimal;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.HttpStatus;

@Service
public class DepositSettingsService {
  private final JdbcTemplate jdbc;
  private final BigDecimal defaultAmount;

  DepositSettingsService(JdbcTemplate jdbc, @Value("${payment.deposit-amount:100000}") BigDecimal defaultAmount) {
    this.jdbc = jdbc;
    this.defaultAmount = defaultAmount;
  }

  public DepositSetting current() {
    var values = jdbc.query("SELECT amount, updated_at, updated_by FROM deposit_settings WHERE id = 1",
      (rs, row) -> new DepositSetting(rs.getBigDecimal("amount"), rs.getTimestamp("updated_at").toInstant(),
        rs.getObject("updated_by", UUID.class)));
    return values.isEmpty() ? new DepositSetting(defaultAmount, null, null) : values.get(0);
  }

  public DepositSetting update(BigDecimal amount, UUID actor) {
    if (amount == null || amount.scale() > 0 || amount.compareTo(new BigDecimal("1000")) < 0
      || amount.compareTo(new BigDecimal("100000000")) > 0) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "INVALID_DEPOSIT_AMOUNT");
    jdbc.update("INSERT INTO deposit_settings (id, amount, updated_at, updated_by) VALUES (1, ?, now(), ?) "
      + "ON CONFLICT (id) DO UPDATE SET amount = EXCLUDED.amount, updated_at = EXCLUDED.updated_at, updated_by = EXCLUDED.updated_by",
      amount, actor);
    return current();
  }

  public record DepositSetting(BigDecimal amount, java.time.Instant updatedAt, UUID updatedBy) {}
}

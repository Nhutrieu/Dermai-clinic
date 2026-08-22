package com.dermai.doctor;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.util.UUID;

@Entity
@Table(name = "clinic_services")
public class ClinicService {
  @Id public UUID id;
  @Column(nullable = false, unique = true, length = 80) public String code;
  @Column(nullable = false, length = 160) public String name;
  @Column(nullable = false, length = 1000) public String description;
  @Column(name = "price_from", nullable = false, precision = 12, scale = 0) public BigDecimal priceFrom;
  @Column(name = "duration_minutes", nullable = false) public int durationMinutes;
  @Column(name = "display_order", nullable = false) public int displayOrder;
  @Column(nullable = false) public boolean active = true;
}

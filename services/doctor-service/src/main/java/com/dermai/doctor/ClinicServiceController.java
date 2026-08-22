package com.dermai.doctor;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.web.bind.annotation.*;
import java.util.*;

interface ClinicServiceRepository extends JpaRepository<ClinicService, UUID> {
  List<ClinicService> findByActiveTrueOrderByDisplayOrderAsc();
}

@RestController
@RequestMapping("/api/v1/services")
public class ClinicServiceController {
  private final ClinicServiceRepository services;
  ClinicServiceController(ClinicServiceRepository services) { this.services = services; }
  @GetMapping List<ClinicService> list() { return services.findByActiveTrueOrderByDisplayOrderAsc(); }
}

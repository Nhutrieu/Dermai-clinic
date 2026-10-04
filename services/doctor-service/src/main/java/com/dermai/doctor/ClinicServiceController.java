package com.dermai.doctor;

import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.math.BigDecimal;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import java.util.*;

interface ClinicServiceRepository extends JpaRepository<ClinicService, UUID> {
  List<ClinicService> findByActiveTrueOrderByDisplayOrderAsc();
  List<ClinicService> findAllByOrderByDisplayOrderAscNameAsc();
  Optional<ClinicService> findByCodeIgnoreCase(String code);
  @Query("select s from ClinicService s where s.active=true and upper(trim(s.specialtyCode))=upper(trim(:specialty)) order by s.displayOrder")
  List<ClinicService> findActiveForSpecialty(@Param("specialty") String specialty);
  @Query("select distinct s from ClinicService s join s.doctorIds doctorId where s.active=true and doctorId=:doctorId order by s.displayOrder")
  List<ClinicService> findActiveForDoctor(@Param("doctorId") UUID doctorId);
}

@RestController
@RequestMapping("/api/v1/services")
public class ClinicServiceController {
  private final ClinicServiceRepository services;
  private final DoctorRepository doctors;
  ClinicServiceController(ClinicServiceRepository services, DoctorRepository doctors) { this.services = services; this.doctors = doctors; }
  record Body(@NotBlank @Size(max=80) @Pattern(regexp="[A-Za-z0-9_-]+") String code,@NotBlank @Size(max=160) String name,@NotBlank @Size(max=1000) String description,@NotBlank @Size(max=80) String specialtyCode,@NotEmpty Set<@NotNull UUID> doctorIds,@NotNull @DecimalMin("0") @Digits(integer=10,fraction=0) BigDecimal priceFrom,@Min(10) @Max(240) int durationMinutes,@Min(0) @Max(10000) int displayOrder,boolean active){}
  @GetMapping List<ClinicService> list(@RequestParam(required=false) UUID doctorId,@RequestParam(required=false) String specialty) {
    if(doctorId!=null){doctors.findById(doctorId).filter(item->item.active).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND,"Không tìm thấy bác sĩ đang hoạt động"));return services.findActiveForDoctor(doctorId);}
    if(specialty!=null&&!specialty.isBlank())return services.findActiveForSpecialty(specialty);
    return services.findByActiveTrueOrderByDisplayOrderAsc();
  }
  @GetMapping("/admin") List<ClinicService> adminList(@RequestHeader("X-User-Role") String role){requireAdmin(role);return services.findAllByOrderByDisplayOrderAscNameAsc();}
  @PostMapping ClinicService create(@RequestHeader("X-User-Role") String role,@Valid @RequestBody Body body){requireAdmin(role);if(services.findByCodeIgnoreCase(body.code()).isPresent())throw new ResponseStatusException(HttpStatus.CONFLICT,"Mã dịch vụ đã tồn tại");var item=new ClinicService();item.id=UUID.randomUUID();apply(item,body);return services.save(item);}
  @PutMapping("/{id}") ClinicService update(@PathVariable UUID id,@RequestHeader("X-User-Role") String role,@Valid @RequestBody Body body){requireAdmin(role);var item=services.findById(id).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND,"Không tìm thấy dịch vụ"));var duplicate=services.findByCodeIgnoreCase(body.code());if(duplicate.isPresent()&&!duplicate.get().id.equals(id))throw new ResponseStatusException(HttpStatus.CONFLICT,"Mã dịch vụ đã tồn tại");apply(item,body);return services.save(item);}
  private void apply(ClinicService item,Body body){var specialty=body.specialtyCode().trim().toUpperCase(Locale.ROOT);var selectedIds=new LinkedHashSet<>(body.doctorIds());var selectedDoctors=doctors.findAllById(selectedIds);if(selectedDoctors.size()!=selectedIds.size())throw new ResponseStatusException(HttpStatus.CONFLICT,"Có bác sĩ không tồn tại");if(selectedDoctors.stream().anyMatch(doctor->!doctor.active))throw new ResponseStatusException(HttpStatus.CONFLICT,"Không thể gán dịch vụ cho bác sĩ đang ngừng hoạt động");if(selectedDoctors.stream().anyMatch(doctor->!specialty.equalsIgnoreCase(doctor.specialtyCode.trim())))throw new ResponseStatusException(HttpStatus.CONFLICT,"Bác sĩ được chọn không cùng chuyên khoa dịch vụ");item.code=body.code().trim().toUpperCase(Locale.ROOT);item.name=body.name().trim();item.description=body.description().trim();item.specialtyCode=specialty;item.doctorIds=new LinkedHashSet<>(selectedIds);item.priceFrom=body.priceFrom();item.durationMinutes=body.durationMinutes();item.displayOrder=body.displayOrder();item.active=body.active();}
  private void requireAdmin(String role){if(!"ADMIN".equals(role))throw new ResponseStatusException(HttpStatus.FORBIDDEN);}
}

package com.dermai.appointment;

import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.*;
import java.util.List;
import com.dermai.appointment.ClinicScheduleService.Day;
import org.springframework.http.*;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/v1/appointments/clinic-schedule")
public class ClinicScheduleController {
 private final ClinicScheduleService schedules;
 ClinicScheduleController(ClinicScheduleService schedules){this.schedules=schedules;}
 @GetMapping List<ClinicScheduleService.Day> get(@RequestHeader("X-User-Role") String role) {
  requireAdmin(role);return schedules.week();
 }
 @GetMapping("/overview") ClinicScheduleService.Schedule overview(@RequestHeader("X-User-Role") String role) {
  if(!"ADMIN".equals(role)&&!"DOCTOR".equals(role))throw new AppointmentController.Forbidden();
  return schedules.snapshot();
 }
 @PutMapping List<ClinicScheduleService.Day> save(@RequestHeader("X-User-Role") String role,
   @Valid @RequestBody List<@Valid Day> days) {
  requireAdmin(role);return schedules.save(days);
 }
 @ExceptionHandler(ResponseStatusException.class)
 ResponseEntity<ProblemDetail> invalidSchedule(ResponseStatusException error) {
  return ResponseEntity.status(error.getStatusCode()).body(ProblemDetail.forStatusAndDetail(error.getStatusCode(),error.getReason()));
 }
 private void requireAdmin(String role){if(!"ADMIN".equals(role))throw new AppointmentController.Forbidden();}
}

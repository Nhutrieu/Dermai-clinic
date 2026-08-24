package com.dermai.doctor;

import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.server.ResponseStatusException;

@RestControllerAdvice
class DoctorErrors {
  @ExceptionHandler(ActiveAppointmentConflict.class)
  ResponseEntity<ProblemDetail> activeAppointmentConflict(ActiveAppointmentConflict error) {
    var problem = ProblemDetail.forStatusAndDetail(HttpStatus.CONFLICT, error.getReason());
    problem.setProperty("code", "ACTIVE_APPOINTMENT_CONFLICT");
    return ResponseEntity.status(HttpStatus.CONFLICT).body(problem);
  }
}

class ActiveAppointmentConflict extends ResponseStatusException {
  ActiveAppointmentConflict(String detail) {
    super(HttpStatus.CONFLICT, detail);
  }
}

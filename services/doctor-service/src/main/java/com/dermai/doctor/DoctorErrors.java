package com.dermai.doctor;

import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.server.ResponseStatusException;

@RestControllerAdvice
class DoctorErrors {
  @ExceptionHandler(ConfirmedAppointmentConflict.class)
  ResponseEntity<ProblemDetail> confirmedAppointmentConflict(ConfirmedAppointmentConflict error) {
    var problem = ProblemDetail.forStatusAndDetail(HttpStatus.CONFLICT, error.getReason());
    problem.setProperty("code", "CONFIRMED_APPOINTMENT_CONFLICT");
    return ResponseEntity.status(HttpStatus.CONFLICT).body(problem);
  }
}

class ConfirmedAppointmentConflict extends ResponseStatusException {
  ConfirmedAppointmentConflict(String detail) {
    super(HttpStatus.CONFLICT, detail);
  }
}

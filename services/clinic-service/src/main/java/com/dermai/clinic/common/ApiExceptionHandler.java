package com.dermai.clinic.common;
import org.springframework.http.*;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.*;
import java.net.URI;
@RestControllerAdvice public class ApiExceptionHandler {
  @ExceptionHandler(MethodArgumentNotValidException.class)
  ResponseEntity<ProblemDetail> invalid(MethodArgumentNotValidException ex) {
    var p=ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST,"Dữ liệu đầu vào không hợp lệ.");
    p.setType(URI.create("https://dermai.local/problems/validation"));
    p.setProperty("errors",ex.getBindingResult().getFieldErrors().stream()
        .map(e->java.util.Map.of("field",e.getField(),"message",e.getDefaultMessage())).toList());
    return ResponseEntity.badRequest().body(p);
  }
}

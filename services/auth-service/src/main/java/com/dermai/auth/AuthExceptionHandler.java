package com.dermai.auth;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
@RestControllerAdvice public class AuthExceptionHandler {
 @ExceptionHandler(IllegalArgumentException.class) ResponseEntity<ProblemDetail> bad(IllegalArgumentException e){
  var p=ProblemDetail.forStatusAndDetail(HttpStatus.UNAUTHORIZED,"Thông tin xác thực không hợp lệ.");p.setProperty("code",e.getMessage());return ResponseEntity.status(401).body(p);
 }
 @ExceptionHandler(IllegalStateException.class) ResponseEntity<ProblemDetail> conflict(IllegalStateException e){
  var p=ProblemDetail.forStatusAndDetail(HttpStatus.CONFLICT,"Email đã được sử dụng.");p.setProperty("code",e.getMessage());return ResponseEntity.status(409).body(p);
 }
}

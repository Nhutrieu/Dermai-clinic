package com.dermai.auth;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
@RestControllerAdvice public class AuthExceptionHandler {
 @ExceptionHandler(AuthService.StaffManagementException.class) ResponseEntity<ProblemDetail> staff(AuthService.StaffManagementException e){
  String detail=switch(e.getMessage()){
   case "DISPLAY_NAME_REQUIRED"->"Vui lòng nhập họ tên lễ tân.";
   case "STAFF_NOT_FOUND"->"Không tìm thấy tài khoản nhân viên.";
   case "NOT_RECEPTIONIST"->"Tài khoản này không thuộc vai trò lễ tân.";
   case "STAFF_PASSWORD_NOT_MANAGED"->"Chỉ có thể đặt mật khẩu cho tài khoản bác sĩ hoặc lễ tân.";
   default->"Không thể cập nhật tài khoản nhân viên.";
  };
  var p=ProblemDetail.forStatusAndDetail(HttpStatus.CONFLICT,detail);p.setProperty("code",e.getMessage());return ResponseEntity.status(409).body(p);
 }
 @ExceptionHandler(IllegalArgumentException.class) ResponseEntity<ProblemDetail> bad(IllegalArgumentException e){
  String detail="EMAIL_NOT_VERIFIED".equals(e.getMessage())?"Email chưa được xác minh. Vui lòng nhập mã OTP đã gửi đến email.":"Thông tin xác thực không hợp lệ.";
  var p=ProblemDetail.forStatusAndDetail(HttpStatus.UNAUTHORIZED,detail);p.setProperty("code",e.getMessage());return ResponseEntity.status(401).body(p);
 }
 @ExceptionHandler(IllegalStateException.class) ResponseEntity<ProblemDetail> conflict(IllegalStateException e){
  if("OTP_COOLDOWN".equals(e.getMessage())){
   var p=ProblemDetail.forStatusAndDetail(HttpStatus.TOO_MANY_REQUESTS,"Vui lòng chờ 60 giây trước khi gửi lại mã OTP.");p.setProperty("code",e.getMessage());return ResponseEntity.status(429).body(p);
  }
  var p=ProblemDetail.forStatusAndDetail(HttpStatus.CONFLICT,"Email đã được sử dụng.");p.setProperty("code",e.getMessage());return ResponseEntity.status(409).body(p);
 }
}

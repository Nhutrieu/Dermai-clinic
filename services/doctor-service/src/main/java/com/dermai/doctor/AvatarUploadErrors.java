package com.dermai.doctor;

import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.multipart.MaxUploadSizeExceededException;

@RestControllerAdvice
class AvatarUploadErrors {
  @ExceptionHandler(MaxUploadSizeExceededException.class)
  ResponseEntity<Map<String, String>> tooLarge(MaxUploadSizeExceededException error) {
    return ResponseEntity.status(HttpStatus.PAYLOAD_TOO_LARGE).body(Map.of(
        "code", "AVATAR_TOO_LARGE",
        "detail", "Ảnh đại diện tối đa 2 MB. Vui lòng chọn ảnh nhỏ hơn."
    ));
  }
}

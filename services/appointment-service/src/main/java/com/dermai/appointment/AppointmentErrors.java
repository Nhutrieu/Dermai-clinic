package com.dermai.appointment;
import org.springframework.http.*;import org.springframework.web.bind.annotation.*;import java.util.NoSuchElementException;
@RestControllerAdvice class AppointmentErrors{
 @ExceptionHandler(AppointmentService.SlotConflictException.class) ResponseEntity<ProblemDetail> conflict(){var p=ProblemDetail.forStatusAndDetail(HttpStatus.CONFLICT,"Bác sĩ đã có lịch trong khoảng thời gian này.");p.setProperty("code","SLOT_CONFLICT");return ResponseEntity.status(409).body(p);}
 @ExceptionHandler(AppointmentService.ActiveAppointmentException.class) ResponseEntity<ProblemDetail> activeAppointment(){var p=ProblemDetail.forStatusAndDetail(HttpStatus.CONFLICT,"Bệnh nhân đã có một lịch khám đang hoạt động. Hãy hoàn thành hoặc hủy lịch hiện tại trước khi đặt lịch mới.");p.setProperty("code","PATIENT_ALREADY_HAS_ACTIVE_APPOINTMENT");return ResponseEntity.status(409).body(p);}
 @ExceptionHandler(SchedulingRecommendationService.SlotUnavailableException.class) ResponseEntity<ProblemDetail> unavailable(SchedulingRecommendationService.SlotUnavailableException e){var p=ProblemDetail.forStatusAndDetail(HttpStatus.CONFLICT,"Khung giờ không còn phù hợp với lịch làm việc của bác sĩ.");p.setProperty("code",e.getMessage());return ResponseEntity.status(409).body(p);}
 @ExceptionHandler(IllegalStateException.class) ResponseEntity<ProblemDetail> state(IllegalStateException e){var p=ProblemDetail.forStatusAndDetail(HttpStatus.CONFLICT,"Không thể chuyển trạng thái lịch khám.");p.setProperty("code",e.getMessage());return ResponseEntity.status(409).body(p);}
 @ExceptionHandler(IllegalArgumentException.class) ResponseEntity<ProblemDetail> bad(IllegalArgumentException e){var p=ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST,"Yêu cầu lịch khám không hợp lệ.");p.setProperty("code",e.getMessage());return ResponseEntity.badRequest().body(p);}
 @ExceptionHandler(NoSuchElementException.class) ResponseEntity<Void> missing(){return ResponseEntity.notFound().build();}
}

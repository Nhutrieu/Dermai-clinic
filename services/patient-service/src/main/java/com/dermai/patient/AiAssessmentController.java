package com.dermai.patient;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.http.*;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;
import java.io.IOException;
import java.time.Instant;
import java.util.*;

@RestController
@RequestMapping("/api/v1/patients")
public class AiAssessmentController {
  private static final Set<String> LABELS = Set.of(
      "Acne", "Candidiasis", "Eczema", "Lupus", "Psoriasis", "SkinCancer", "Tinea", "Warts");
  private final AiAssessmentRepository assessments;
  private final PatientRepository patients;
  private final AppointmentIdentityClient appointments;
  private final ObjectMapper mapper;

  public AiAssessmentController(AiAssessmentRepository assessments, PatientRepository patients,
      AppointmentIdentityClient appointments, ObjectMapper mapper) {
    this.assessments = assessments;
    this.patients = patients;
    this.appointments = appointments;
    this.mapper = mapper;
  }

  public record RankedPrediction(
      @NotBlank @Size(max = 80) String label,
      @DecimalMin("0.0") @DecimalMax("1.0") double probability) {}
  public record CreateBody(
      @NotBlank @Size(max = 80) String predictedLabel,
      @DecimalMin("0.0") @DecimalMax("1.0") double confidence,
      @NotEmpty @Size(max = 3) List<@Valid RankedPrediction> top3,
      boolean uncertain,
      @NotBlank @Size(max = 120) String modelVersion,
      boolean sharedWithDoctor) {}
  public record SharingBody(boolean sharedWithDoctor, UUID appointmentId) {}
  public record View(
      UUID id,
      UUID patientId,
      String predictedLabel,
      double confidence,
      List<RankedPrediction> top3,
      boolean uncertain,
      String modelVersion,
      boolean sharedWithDoctor,
      UUID appointmentId,
      boolean imageAvailable,
      Instant createdAt) {}

  @GetMapping("/me/ai-assessments")
  List<View> mine(
      @RequestHeader("X-User-Id") UUID identity,
      @RequestHeader("X-User-Role") String role) {
    requirePatient(role);
    return assessments.findByPatientIdentityIdOrderByCreatedAtDesc(identity).stream().map(this::view).toList();
  }

  @PostMapping("/me/ai-assessments")
  @Transactional
  ResponseEntity<View> create(
      @RequestHeader("X-User-Id") UUID identity,
      @RequestHeader("X-User-Role") String role,
      @Valid @RequestBody CreateBody body) {
    requirePatient(role);
    validateLabels(body);
    Patient patient = patients.findByIdentityId(identity)
        .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Chưa có hồ sơ bệnh nhân."));
    AiAssessment assessment = new AiAssessment(patient.id, identity);
    assessment.predictedLabel = body.predictedLabel();
    assessment.confidence = body.confidence();
    assessment.top3Json = writeTop3(body.top3());
    assessment.uncertain = body.uncertain();
    assessment.modelVersion = body.modelVersion();
    assessment.sharedWithDoctor = body.sharedWithDoctor();
    return ResponseEntity.status(HttpStatus.CREATED).body(view(assessments.save(assessment)));
  }

  @PutMapping(value = "/me/ai-assessments/{id}/image", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
  @ResponseStatus(HttpStatus.NO_CONTENT)
  @Transactional
  void uploadImage(
      @PathVariable UUID id,
      @RequestHeader("X-User-Id") UUID identity,
      @RequestHeader("X-User-Role") String role,
      @RequestPart("image") MultipartFile image) {
    requirePatient(role);
    // Không tin dữ liệu kiểm tra từ trình duyệt: backend kiểm tra lại dung lượng và MIME trước khi lưu.
    if (image.isEmpty() || image.getSize() > 10L * 1024 * 1024) {
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Ảnh phải có dung lượng từ 1 byte đến 10 MB.");
    }
    String contentType = Optional.ofNullable(image.getContentType()).orElse("");
    if (!Set.of(MediaType.IMAGE_JPEG_VALUE, MediaType.IMAGE_PNG_VALUE, "image/webp").contains(contentType)) {
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Chỉ chấp nhận ảnh JPEG, PNG hoặc WebP.");
    }
    AiAssessment assessment = own(id, identity);
    try {
      assessment.imageBytes = image.getBytes();
      assessment.imageContentType = contentType;
      assessments.save(assessment);
    } catch (IOException error) {
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Không thể đọc ảnh tải lên.", error);
    }
  }

  @GetMapping("/me/ai-assessments/{id}/image")
  ResponseEntity<byte[]> ownImage(
      @PathVariable UUID id,
      @RequestHeader("X-User-Id") UUID identity,
      @RequestHeader("X-User-Role") String role) {
    requirePatient(role);
    return image(own(id, identity));
  }

  @PatchMapping("/me/ai-assessments/{id}/sharing")
  @Transactional
  View sharing(
      @PathVariable UUID id,
      @RequestHeader("X-User-Id") UUID identity,
      @RequestHeader("X-User-Role") String role,
      @Valid @RequestBody SharingBody body) {
    requirePatient(role);
    AiAssessment assessment = own(id, identity);
    if (body.sharedWithDoctor() && body.appointmentId() != null) {
      // Gắn kết quả với đúng lịch; bệnh nhân không thể chia sẻ ảnh vào lịch của tài khoản khác.
      var appointment = appointments.requireAccess(body.appointmentId(), identity, "PATIENT");
      if (!assessment.patientId.equals(appointment.patientId())) {
        throw new ResponseStatusException(HttpStatus.CONFLICT, "Kết quả AI không thuộc bệnh nhân của lịch khám này.");
      }
      assessment.appointmentId = body.appointmentId();
    }
    assessment.sharedWithDoctor = body.sharedWithDoctor();
    return view(assessments.save(assessment));
  }

  @GetMapping("/appointments/{appointmentId}/shared-ai-assessment")
  ResponseEntity<View> sharedForDoctor(
      @PathVariable UUID appointmentId,
      @RequestHeader("X-User-Id") UUID identity,
      @RequestHeader("X-User-Role") String role) {
    if (!"DOCTOR".equals(role)) throw new ResponseStatusException(HttpStatus.FORBIDDEN);
    // Appointment-service xác nhận bác sĩ đang đăng nhập chính là bác sĩ phụ trách lịch này.
    var appointment = appointments.requireAccess(appointmentId, identity, role);
    return assessments.findFirstByAppointmentIdAndSharedWithDoctorTrueOrderByCreatedAtDesc(appointmentId)
        .filter(value -> value.patientId.equals(appointment.patientId()))
        .map(value -> ResponseEntity.ok(view(value)))
        .orElseGet(() -> ResponseEntity.noContent().build());
  }

  @GetMapping("/appointments/{appointmentId}/shared-ai-assessment/image")
  ResponseEntity<byte[]> sharedImageForDoctor(
      @PathVariable UUID appointmentId,
      @RequestHeader("X-User-Id") UUID identity,
      @RequestHeader("X-User-Role") String role) {
    if (!"DOCTOR".equals(role)) throw new ResponseStatusException(HttpStatus.FORBIDDEN);
    var appointment = appointments.requireAccess(appointmentId, identity, role);
    AiAssessment assessment = assessments
        .findFirstByAppointmentIdAndSharedWithDoctorTrueOrderByCreatedAtDesc(appointmentId)
        .filter(value -> value.patientId.equals(appointment.patientId()))
        .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
    return image(assessment);
  }

  @DeleteMapping("/me/ai-assessments/{id}")
  @ResponseStatus(HttpStatus.NO_CONTENT)
  @Transactional
  void delete(
      @PathVariable UUID id,
      @RequestHeader("X-User-Id") UUID identity,
      @RequestHeader("X-User-Role") String role) {
    requirePatient(role);
    assessments.delete(own(id, identity));
  }

  private AiAssessment own(UUID id, UUID identity) {
    return assessments.findByIdAndPatientIdentityId(id, identity)
        .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
  }

  private void validateLabels(CreateBody body) {
    if (!LABELS.contains(body.predictedLabel()) || body.top3().stream().anyMatch(item -> !LABELS.contains(item.label()))) {
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Nhãn AI không thuộc class map được hỗ trợ.");
    }
  }

  private String writeTop3(List<RankedPrediction> top3) {
    try {
      return mapper.writeValueAsString(top3);
    } catch (JsonProcessingException error) {
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Top-3 không hợp lệ.", error);
    }
  }

  private List<RankedPrediction> readTop3(String json) {
    try {
      return mapper.readValue(json, new TypeReference<List<RankedPrediction>>() {});
    } catch (JsonProcessingException error) {
      return List.of();
    }
  }

  private View view(AiAssessment value) {
    return new View(value.id, value.patientId, value.predictedLabel, value.confidence,
        readTop3(value.top3Json), value.uncertain, value.modelVersion,
        value.sharedWithDoctor, value.appointmentId, value.imageBytes != null && value.imageBytes.length > 0,
        value.createdAt);
  }

  private ResponseEntity<byte[]> image(AiAssessment assessment) {
    if (assessment.imageBytes == null || assessment.imageBytes.length == 0) {
      throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Kết quả này không có ảnh đính kèm.");
    }
    MediaType contentType;
    try {
      contentType = MediaType.parseMediaType(assessment.imageContentType);
    } catch (Exception ignored) {
      contentType = MediaType.APPLICATION_OCTET_STREAM;
    }
    return ResponseEntity.ok()
        .contentType(contentType)
        // Ảnh y tế không được cache lại trong trình duyệt hoặc proxy dùng chung.
        .cacheControl(CacheControl.noStore())
        .body(assessment.imageBytes);
  }

  private void requirePatient(String role) {
    if (!"PATIENT".equals(role)) throw new ResponseStatusException(HttpStatus.FORBIDDEN);
  }
}

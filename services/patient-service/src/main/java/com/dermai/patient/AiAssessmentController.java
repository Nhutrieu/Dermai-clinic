package com.dermai.patient;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.http.*;
import org.springframework.beans.factory.annotation.Value;
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
  private final AiInferenceClient inference;
  private final AiPrivacyService privacy;
  private final long imageRetentionDays;

  public AiAssessmentController(AiAssessmentRepository assessments, PatientRepository patients,
      AppointmentIdentityClient appointments, ObjectMapper mapper, AiInferenceClient inference,
      AiPrivacyService privacy,
      @Value("${privacy.ai-image-retention-days:180}") long imageRetentionDays) {
    this.assessments = assessments;
    this.patients = patients;
    this.appointments = appointments;
    this.mapper = mapper;
    this.inference = inference;
    this.privacy = privacy;
    if (imageRetentionDays < 1 || imageRetentionDays > 3650) {
      throw new IllegalArgumentException("AI_IMAGE_RETENTION_DAYS must be between 1 and 3650.");
    }
    this.imageRetentionDays = imageRetentionDays;
  }

  public record RankedPrediction(
      @NotBlank @Size(max = 80) String label,
      @DecimalMin("0.0") @DecimalMax("1.0") double probability) {}
  public record SharingBody(boolean sharedWithDoctor, UUID appointmentId) {}
  public record AnalyzeResponse(View assessment, AiInferenceClient.Prediction prediction) {}
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
    List<View> result = assessments.findByPatientIdentityIdAndDeletedAtIsNullOrderByCreatedAtDesc(identity)
        .stream().map(this::view).toList();
    privacy.audit(null, identity, identity, role, "LIST_OWN");
    return result;
  }

  @PostMapping(value = "/me/ai-assessments/analyze", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
  @Transactional
  ResponseEntity<AnalyzeResponse> analyze(
      @RequestHeader("X-User-Id") UUID identity,
      @RequestHeader("X-User-Role") String role,
      @RequestParam(defaultValue = "false") boolean sharedWithDoctor,
      @RequestParam(defaultValue = "false") boolean consentAccepted,
      @RequestPart("image") MultipartFile image) {
    requirePatient(role);
    if (!consentAccepted) {
      throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY,
          "Explicit consent is required before an image can be analyzed.");
    }
    ValidatedImage validated = validateImage(image);
    AiInferenceClient.Prediction prediction = inference.predict(
        validated.bytes(), validated.contentType(), image.getOriginalFilename());
    List<RankedPrediction> top3 = validatePrediction(prediction);
    Patient patient = patients.findByIdentityId(identity)
        .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Patient profile not found."));
    AiConsentEvent consent = privacy.grant(identity);

    AiAssessment assessment = new AiAssessment(patient.id, identity);
    assessment.predictedLabel = prediction.disease();
    assessment.confidence = prediction.confidence();
    assessment.top3Json = writeTop3(top3);
    assessment.uncertain = prediction.uncertain();
    assessment.modelVersion = prediction.modelVersion();
    assessment.sharedWithDoctor = sharedWithDoctor;
    assessment.imageBytes = validated.bytes();
    assessment.imageContentType = validated.contentType();
    assessment.consentEventId = consent.id;
    assessment.imageRetentionUntil = Instant.now().plusSeconds(imageRetentionDays * 24L * 60L * 60L);
    AiAssessment saved = assessments.save(assessment);
    privacy.audit(saved.id, saved.patientIdentityId, identity, role, "CREATED_FROM_SERVER_INFERENCE");
    return ResponseEntity.status(HttpStatus.CREATED).body(new AnalyzeResponse(view(saved), prediction));
  }

  @GetMapping("/me/ai-assessments/{id}/image")
  ResponseEntity<byte[]> ownImage(
      @PathVariable UUID id,
      @RequestHeader("X-User-Id") UUID identity,
      @RequestHeader("X-User-Role") String role) {
    requirePatient(role);
    AiAssessment assessment = own(id, identity);
    ResponseEntity<byte[]> response = image(assessment);
    privacy.audit(assessment.id, assessment.patientIdentityId, identity, role, "VIEWED_IMAGE");
    return response;
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
    AiAssessment saved = assessments.save(assessment);
    privacy.audit(saved.id, saved.patientIdentityId, identity, role,
        saved.sharedWithDoctor ? "SHARING_ENABLED" : "SHARING_DISABLED");
    return view(saved);
  }

  @GetMapping("/appointments/{appointmentId}/shared-ai-assessment")
  ResponseEntity<View> sharedForDoctor(
      @PathVariable UUID appointmentId,
      @RequestHeader("X-User-Id") UUID identity,
      @RequestHeader("X-User-Role") String role) {
    if (!"DOCTOR".equals(role)) throw new ResponseStatusException(HttpStatus.FORBIDDEN);
    // Appointment-service xác nhận bác sĩ đang đăng nhập chính là bác sĩ phụ trách lịch này.
    var appointment = appointments.requireAccess(appointmentId, identity, role);
    return assessments.findFirstByAppointmentIdAndSharedWithDoctorTrueAndDeletedAtIsNullOrderByCreatedAtDesc(appointmentId)
        .filter(value -> value.patientId.equals(appointment.patientId()))
        .map(value -> {
          privacy.audit(value.id, value.patientIdentityId, identity, role, "DOCTOR_VIEWED_RESULT");
          return ResponseEntity.ok(view(value));
        })
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
        .findFirstByAppointmentIdAndSharedWithDoctorTrueAndDeletedAtIsNullOrderByCreatedAtDesc(appointmentId)
        .filter(value -> value.patientId.equals(appointment.patientId()))
        .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
    ResponseEntity<byte[]> response = image(assessment);
    privacy.audit(assessment.id, assessment.patientIdentityId, identity, role, "DOCTOR_VIEWED_IMAGE");
    return response;
  }

  @DeleteMapping("/me/ai-assessments/{id}")
  @ResponseStatus(HttpStatus.NO_CONTENT)
  @Transactional
  void delete(
      @PathVariable UUID id,
      @RequestHeader("X-User-Id") UUID identity,
      @RequestHeader("X-User-Role") String role) {
    requirePatient(role);
    AiAssessment assessment = own(id, identity);
    assessment.deletedAt = Instant.now();
    assessment.sharedWithDoctor = false;
    assessment.appointmentId = null;
    assessment.imageBytes = null;
    assessment.imageContentType = null;
    assessments.save(assessment);
    privacy.audit(assessment.id, assessment.patientIdentityId, identity, role, "SOFT_DELETED_AND_IMAGE_ERASED");
  }

  private AiAssessment own(UUID id, UUID identity) {
    return assessments.findByIdAndPatientIdentityIdAndDeletedAtIsNull(id, identity)
        .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
  }

  private List<RankedPrediction> validatePrediction(AiInferenceClient.Prediction prediction) {
    if (prediction.disease() == null || !LABELS.contains(prediction.disease())
        || prediction.modelVersion() == null || prediction.modelVersion().isBlank()
        || prediction.modelVersion().length() > 120
        || prediction.confidence() < 0 || prediction.confidence() > 1
        || prediction.top3() == null || prediction.top3().isEmpty() || prediction.top3().size() > 3) {
      throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "AI service returned an invalid result.");
    }
    List<RankedPrediction> top3 = prediction.top3().stream()
        .map(item -> new RankedPrediction(item.label(), item.probability()))
        .toList();
    if (top3.stream().anyMatch(item -> item.label() == null || !LABELS.contains(item.label())
        || item.probability() < 0 || item.probability() > 1)
        || !prediction.disease().equals(top3.get(0).label())) {
      throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "AI service returned an invalid class map.");
    }
    return top3;
  }

  private ValidatedImage validateImage(MultipartFile image) {
    if (image.isEmpty() || image.getSize() > 10L * 1024 * 1024) {
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Image size must be between 1 byte and 10 MB.");
    }
    try {
      byte[] bytes = image.getBytes();
      String contentType = detectedImageType(bytes);
      if (contentType == null) {
        throw new ResponseStatusException(HttpStatus.UNSUPPORTED_MEDIA_TYPE, "Only valid JPEG, PNG, or WebP images are accepted.");
      }
      return new ValidatedImage(bytes, contentType);
    } catch (IOException error) {
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "The uploaded image could not be read.", error);
    }
  }

  private String detectedImageType(byte[] bytes) {
    if (bytes.length >= 3 && (bytes[0] & 255) == 0xff && (bytes[1] & 255) == 0xd8 && (bytes[2] & 255) == 0xff) {
      return MediaType.IMAGE_JPEG_VALUE;
    }
    if (bytes.length >= 8 && (bytes[0] & 255) == 0x89 && bytes[1] == 0x50 && bytes[2] == 0x4e
        && bytes[3] == 0x47 && bytes[4] == 0x0d && bytes[5] == 0x0a && bytes[6] == 0x1a && bytes[7] == 0x0a) {
      return MediaType.IMAGE_PNG_VALUE;
    }
    if (bytes.length >= 12 && bytes[0] == 'R' && bytes[1] == 'I' && bytes[2] == 'F' && bytes[3] == 'F'
        && bytes[8] == 'W' && bytes[9] == 'E' && bytes[10] == 'B' && bytes[11] == 'P') {
      return "image/webp";
    }
    return null;
  }

  private record ValidatedImage(byte[] bytes, String contentType) {}

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
        value.sharedWithDoctor, value.appointmentId, imageAvailable(value),
        value.createdAt);
  }

  private ResponseEntity<byte[]> image(AiAssessment assessment) {
    if (!imageAvailable(assessment)) {
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

  private boolean imageAvailable(AiAssessment assessment) {
    return assessment.imageBytes != null && assessment.imageBytes.length > 0
        && (assessment.imageRetentionUntil == null || assessment.imageRetentionUntil.isAfter(Instant.now()));
  }

  private void requirePatient(String role) {
    if (!"PATIENT".equals(role)) throw new ResponseStatusException(HttpStatus.FORBIDDEN);
  }
}

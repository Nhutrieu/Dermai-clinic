package com.dermai.record;
import jakarta.validation.Valid;import jakarta.validation.constraints.*;import org.springframework.beans.factory.annotation.Value;import org.springframework.data.jpa.repository.*;import org.springframework.http.*;import org.springframework.jdbc.core.JdbcTemplate;import org.springframework.web.bind.annotation.*;import org.springframework.web.client.RestClient;import org.springframework.web.server.ResponseStatusException;import java.time.*;import java.util.*;
interface MedicalRecordRepository extends JpaRepository<MedicalRecord,UUID>{
 Optional<MedicalRecord> findByAppointmentId(UUID id);List<MedicalRecord> findByPatientIdOrderBySignedAtDesc(UUID id);List<MedicalRecord> findByPatientIdentityIdOrderBySignedAtDesc(UUID id);List<MedicalRecord> findByDoctorIdOrderBySignedAtDesc(UUID id);
 @Query(value="SELECT r.* FROM medical_records r WHERE r.patient_identity_id=?1 AND NOT EXISTS (SELECT 1 FROM patient_record_visibility v WHERE v.record_id=r.id AND v.patient_identity_id=?1) ORDER BY r.signed_at DESC",nativeQuery=true) List<MedicalRecord> findVisibleByPatientIdentityIdOrderBySignedAtDesc(UUID id);
 @Query(value="SELECT EXISTS (SELECT 1 FROM patient_record_visibility v WHERE v.record_id=?1 AND v.patient_identity_id=?2)",nativeQuery=true) boolean isHiddenForPatient(UUID recordId,UUID patientIdentityId);
}
@RestController @RequestMapping("/api/v1/medical-records")
public class MedicalRecordController{
 private final MedicalRecordRepository repo;private final RestClient appointments;private final JdbcTemplate jdbc;
 MedicalRecordController(MedicalRecordRepository r,@Value("${services.appointment-url}") String url,JdbcTemplate jdbc){repo=r;appointments=RestClient.builder().baseUrl(url).build();this.jdbc=jdbc;}
 record Body(@NotNull UUID appointmentId,@NotNull UUID patientId,@NotBlank @Size(max=2000) String finalDiagnosis,@Size(max=10000) String clinicalNotes,@Size(max=5000) String treatmentPlan,@NotNull MedicalRecord.Severity severity,Instant followUpAt){}
 @PostMapping ResponseEntity<MedicalRecord> create(@RequestHeader("X-User-Id") UUID doctor,@RequestHeader("X-User-Role") String role,@Valid @RequestBody Body b){
  require(role,"DOCTOR");var ownership=appointments.get().uri("/api/v1/appointments/{id}",b.appointmentId()).header("X-User-Id",doctor.toString()).header("X-User-Role",role).retrieve().body(AppointmentOwnership.class);
  if(ownership==null||!b.patientId().equals(ownership.patientId())||!"IN_PROGRESS".equals(ownership.status()))throw new ResponseStatusException(HttpStatus.CONFLICT,"Lịch không thuộc bác sĩ, sai bệnh nhân hoặc chưa bắt đầu");
  if(repo.findByAppointmentId(b.appointmentId()).isPresent())throw new ResponseStatusException(HttpStatus.CONFLICT,"Hồ sơ đã tồn tại");
  var x=new MedicalRecord();x.id=UUID.randomUUID();x.appointmentId=b.appointmentId();x.patientId=b.patientId();x.patientIdentityId=ownership.patientIdentityId();x.doctorId=doctor;x.finalDiagnosis=b.finalDiagnosis();x.clinicalNotes=b.clinicalNotes();x.treatmentPlan=b.treatmentPlan();x.severity=b.severity();x.followUpAt=b.followUpAt();x.signedAt=Instant.now();return ResponseEntity.status(201).body(repo.save(x));
 }
 @GetMapping("/{id}") MedicalRecord get(@PathVariable UUID id,@RequestHeader("X-User-Id") UUID user,@RequestHeader("X-User-Role") String role){requireAny(role,"DOCTOR","PATIENT","ADMIN");var x=repo.findById(id).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND));if(role.equals("DOCTOR")&&!x.doctorId.equals(user))throw new ResponseStatusException(HttpStatus.FORBIDDEN);if(role.equals("PATIENT")){if(!x.patientIdentityId.equals(user))throw new ResponseStatusException(HttpStatus.FORBIDDEN);if(repo.isHiddenForPatient(x.id,user))throw new ResponseStatusException(HttpStatus.NOT_FOUND);}return x;}
 @GetMapping("/appointment/{id}") MedicalRecord byAppointment(@PathVariable UUID id,@RequestHeader("X-User-Id") UUID user,@RequestHeader("X-User-Role") String role){var x=repo.findByAppointmentId(id).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND));if(role.equals("DOCTOR")&&!x.doctorId.equals(user))throw new ResponseStatusException(HttpStatus.FORBIDDEN);requireAny(role,"DOCTOR","ADMIN");return x;}
 @GetMapping("/mine") List<MedicalRecord> mine(@RequestHeader("X-User-Id") UUID user,@RequestHeader("X-User-Role") String role){require(role,"PATIENT");return repo.findVisibleByPatientIdentityIdOrderBySignedAtDesc(user);}
 @PatchMapping("/{id}/hide") ResponseEntity<Void> hideFromPatientHistory(@PathVariable UUID id,@RequestHeader("X-User-Id") UUID user,@RequestHeader("X-User-Role") String role){
  require(role,"PATIENT");var x=repo.findById(id).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND));if(!x.patientIdentityId.equals(user))throw new ResponseStatusException(HttpStatus.FORBIDDEN);
  // Keep the signed clinical row untouched; this table stores only the patient's display preference.
  jdbc.update("INSERT INTO patient_record_visibility(record_id,patient_identity_id,hidden_at) VALUES (?,?,CURRENT_TIMESTAMP) ON CONFLICT (record_id) DO NOTHING",x.id,user);return ResponseEntity.noContent().build();
 }
 @GetMapping("/doctor/mine") List<MedicalRecord> doctorMine(@RequestHeader("X-User-Id") UUID user,@RequestHeader("X-User-Role") String role){require(role,"DOCTOR");return repo.findByDoctorIdOrderBySignedAtDesc(user);}
 @GetMapping("/patient/{id}") List<MedicalRecord> patient(@PathVariable UUID id,@RequestHeader("X-User-Role") String role){requireAny(role,"DOCTOR","ADMIN");return repo.findByPatientIdOrderBySignedAtDesc(id);}
 private void require(String got,String want){if(!want.equals(got))throw new ResponseStatusException(HttpStatus.FORBIDDEN);}private void requireAny(String got,String...r){if(Arrays.stream(r).noneMatch(got::equals))throw new ResponseStatusException(HttpStatus.FORBIDDEN);}
 record AppointmentOwnership(UUID patientId,UUID patientIdentityId,UUID doctorIdentityId,String status){}
}

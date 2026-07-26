package com.dermai.prescription;
import jakarta.validation.Valid;import jakarta.validation.constraints.*;import org.springframework.beans.factory.annotation.Value;import org.springframework.data.jpa.repository.JpaRepository;import org.springframework.http.*;import org.springframework.web.bind.annotation.*;import org.springframework.web.client.RestClient;import org.springframework.web.server.ResponseStatusException;import java.time.*;import java.util.*;
interface PrescriptionRepository extends JpaRepository<Prescription,UUID>{Optional<Prescription> findByRecordId(UUID id);List<Prescription> findByPatientIdOrderBySignedAtDesc(UUID id);List<Prescription> findByPatientIdentityIdOrderBySignedAtDesc(UUID id);}
@RestController @RequestMapping("/api/v1/prescriptions")
public class PrescriptionController{
 private final PrescriptionRepository repo;private final RestClient records;PrescriptionController(PrescriptionRepository r,@Value("${services.record-url}") String url){repo=r;records=RestClient.builder().baseUrl(url).build();}
 record ItemBody(@NotBlank @Size(max=200) String drugName,@NotBlank @Size(max=120) String dosage,@Size(max=120) String frequency,@Size(max=120) String duration,@Size(max=1000) String instructions){}
 record Body(@NotNull UUID recordId,@NotNull UUID patientId,@Size(max=3000) String instructions,@NotEmpty @Size(max=30) List<@Valid ItemBody> items){}
 @PostMapping ResponseEntity<Prescription> create(@RequestHeader("X-User-Id") UUID doctor,@RequestHeader("X-User-Role") String role,@Valid @RequestBody Body b){
  if(!role.equals("DOCTOR"))throw new ResponseStatusException(HttpStatus.FORBIDDEN,"Chỉ bác sĩ được kê đơn");
  if(repo.findByRecordId(b.recordId()).isPresent())throw new ResponseStatusException(HttpStatus.CONFLICT,"Hồ sơ này đã có đơn thuốc được ký");
  var record=records.get().uri("/api/v1/medical-records/{id}",b.recordId()).header("X-User-Id",doctor.toString()).header("X-User-Role",role).retrieve().body(RecordOwnership.class);
  if(record==null||!b.patientId().equals(record.patientId())||!doctor.equals(record.doctorId()))throw new ResponseStatusException(HttpStatus.CONFLICT,"Hồ sơ không thuộc bác sĩ hoặc sai bệnh nhân");
  var x=new Prescription();x.id=UUID.randomUUID();x.recordId=b.recordId();x.patientId=b.patientId();x.patientIdentityId=record.patientIdentityId();x.doctorId=doctor;x.instructions=b.instructions();x.signedAt=Instant.now();x.items=b.items().stream().map(i->{var z=new Prescription.Item();z.drugName=i.drugName();z.dosage=i.dosage();z.frequency=i.frequency();z.duration=i.duration();z.instructions=i.instructions();return z;}).toList();return ResponseEntity.status(201).body(repo.save(x));
 }
 @GetMapping("/mine") List<Prescription> mine(@RequestHeader("X-User-Id") UUID user,@RequestHeader("X-User-Role") String role){if(!role.equals("PATIENT"))throw new ResponseStatusException(HttpStatus.FORBIDDEN);return repo.findByPatientIdentityIdOrderBySignedAtDesc(user);}
 @GetMapping("/patient/{id}") List<Prescription> patient(@PathVariable UUID id,@RequestHeader("X-User-Role") String role){if(!Set.of("DOCTOR","ADMIN").contains(role))throw new ResponseStatusException(HttpStatus.FORBIDDEN);return repo.findByPatientIdOrderBySignedAtDesc(id);}
 record RecordOwnership(UUID id,UUID patientId,UUID patientIdentityId,UUID doctorId){}
}

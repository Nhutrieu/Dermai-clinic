package com.dermai.patient;
import jakarta.validation.Valid;import jakarta.validation.constraints.*;import org.springframework.data.domain.*;import org.springframework.http.*;import org.springframework.web.bind.annotation.*;import org.springframework.web.server.ResponseStatusException;import java.time.*;import java.util.*;
import org.springframework.transaction.annotation.Transactional;
@RestController @RequestMapping("/api/v1/patients")
public class PatientController {
 private final PatientRepository repo;private final AppointmentIdentityClient appointments;public PatientController(PatientRepository r,AppointmentIdentityClient a){repo=r;appointments=a;}
 record Body(@NotBlank @Size(max=160) String fullName,LocalDate dob,@NotBlank @Pattern(regexp="[0-9+ .()-]{8,20}") String phone,@Size(max=4000) String medicalHistory,@Size(max=2000) String allergies){}
 record HotlineBody(@NotBlank @Size(max=160) String fullName,LocalDate dob,@NotBlank @Pattern(regexp="[0-9+ .()-]{8,20}") String phone){}
 @PostMapping("/me") @Transactional ResponseEntity<?> create(@RequestHeader("X-User-Id") UUID user,@RequestHeader("X-User-Role") String role,@Valid @RequestBody Body b){
  require(role,"PATIENT");if(repo.findByIdentityId(user).isPresent())return ResponseEntity.status(409).body(Map.of("code","PROFILE_EXISTS"));
  String phone=normalizePhone(b.phone());var existing=repo.findFirstByPhone(phone);
  if(existing.isPresent()){
   var p=existing.get();if(p.accountLinked)return ResponseEntity.status(409).body(Map.of("code","PHONE_ALREADY_LINKED","detail","Số điện thoại đã thuộc một tài khoản khác."));
   UUID oldIdentity=p.identityId;p.identityId=user;p.accountLinked=true;apply(p,b);repo.saveAndFlush(p);appointments.relink(p.id,oldIdentity,user);return ResponseEntity.ok(p);
  }
  var p=new Patient(user,b.fullName());apply(p,b);return ResponseEntity.status(201).body(repo.save(p));
 }
 @GetMapping("/me") Patient me(@RequestHeader("X-User-Id") UUID user){return repo.findByIdentityId(user).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND));}
 @PatchMapping("/me") Patient update(@RequestHeader("X-User-Id") UUID user,@Valid @RequestBody Body b){var p=repo.findByIdentityId(user).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND));apply(p,b);return repo.save(p);}
 @GetMapping("/identity/{identityId}") Patient byIdentityId(@PathVariable UUID identityId,@RequestHeader("X-User-Role") String role){requireAny(role,"RECEPTIONIST","ADMIN");return repo.findByIdentityId(identityId).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND));}
 @GetMapping("/{id}") Patient byId(@PathVariable UUID id,@RequestHeader("X-User-Id") UUID user,@RequestHeader("X-User-Role") String role){if("DOCTOR".equals(role))appointments.requireDoctorPatientAccess(id,user);else requireAny(role,"RECEPTIONIST","ADMIN");return repo.findById(id).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND));}
 @PostMapping("/hotline") ResponseEntity<Patient> createHotline(@RequestHeader("X-User-Role") String role,@Valid @RequestBody HotlineBody b){requireAny(role,"RECEPTIONIST","ADMIN");String phone=normalizePhone(b.phone());var existing=repo.findFirstByPhone(phone);if(existing.isPresent())return ResponseEntity.ok(existing.get());var patient=new Patient(UUID.randomUUID(),b.fullName().trim());patient.dob=b.dob();patient.phone=phone;patient.accountLinked=false;return ResponseEntity.status(201).body(repo.save(patient));}
 @GetMapping Page<Patient> search(@RequestParam(defaultValue="") @Size(max=160) String query,@RequestParam(defaultValue="0") @Min(0) int page,@RequestParam(defaultValue="20") @Min(1) @Max(100) int size,@RequestHeader("X-User-Role") String role){requireAny(role,"RECEPTIONIST","ADMIN");String value=query.trim();return repo.findByFullNameContainingIgnoreCaseOrPhoneContaining(value,value,PageRequest.of(page,size,Sort.by("fullName")));}
 private void apply(Patient p,Body b){p.fullName=b.fullName().trim();p.dob=b.dob();p.phone=normalizePhone(b.phone());p.medicalHistory=b.medicalHistory();p.allergies=b.allergies();}
 static String normalizePhone(String value){
  String phone=value==null?"":value.replaceAll("[^0-9]","");
  if(phone.startsWith("0084"))phone="0"+phone.substring(4);
  else if(phone.startsWith("84"))phone="0"+phone.substring(2);
  if(!phone.matches("0[0-9]{8,10}"))throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Số điện thoại không hợp lệ.");
  return phone;
 }
 private void require(String got,String expected){if(!expected.equals(got))throw new ResponseStatusException(HttpStatus.FORBIDDEN);}
 private void requireAny(String got,String... roles){if(Arrays.stream(roles).noneMatch(got::equals))throw new ResponseStatusException(HttpStatus.FORBIDDEN);}
}

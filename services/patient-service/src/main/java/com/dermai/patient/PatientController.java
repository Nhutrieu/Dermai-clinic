package com.dermai.patient;
import jakarta.validation.Valid;import jakarta.validation.constraints.*;import org.springframework.data.domain.*;import org.springframework.http.*;import org.springframework.web.bind.annotation.*;import org.springframework.web.server.ResponseStatusException;import java.time.*;import java.util.*;
@RestController @RequestMapping("/api/v1/patients")
public class PatientController {
 private final PatientRepository repo;public PatientController(PatientRepository r){repo=r;}
 record Body(@NotBlank @Size(max=160) String fullName,LocalDate dob,@Size(max=30) String phone,@Size(max=4000) String medicalHistory,@Size(max=2000) String allergies){}
 @PostMapping("/me") ResponseEntity<?> create(@RequestHeader("X-User-Id") UUID user,@RequestHeader("X-User-Role") String role,@Valid @RequestBody Body b){
  require(role,"PATIENT");if(repo.findByIdentityId(user).isPresent())return ResponseEntity.status(409).body(Map.of("code","PROFILE_EXISTS"));
  var p=new Patient(user,b.fullName());apply(p,b);return ResponseEntity.status(201).body(repo.save(p));
 }
 @GetMapping("/me") Patient me(@RequestHeader("X-User-Id") UUID user){return repo.findByIdentityId(user).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND));}
 @PatchMapping("/me") Patient update(@RequestHeader("X-User-Id") UUID user,@Valid @RequestBody Body b){var p=repo.findByIdentityId(user).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND));apply(p,b);return repo.save(p);}
 @GetMapping("/identity/{identityId}") Patient byIdentityId(@PathVariable UUID identityId,@RequestHeader("X-User-Role") String role){requireAny(role,"RECEPTIONIST","ADMIN");return repo.findByIdentityId(identityId).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND));}
 @GetMapping("/{id}") Patient byId(@PathVariable UUID id,@RequestHeader("X-User-Role") String role){requireAny(role,"DOCTOR","RECEPTIONIST","ADMIN");return repo.findById(id).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND));}
 @GetMapping Page<Patient> search(@RequestParam(defaultValue="") @Size(max=160) String query,@RequestParam(defaultValue="0") @Min(0) int page,@RequestParam(defaultValue="20") @Min(1) @Max(100) int size,@RequestHeader("X-User-Role") String role){requireAny(role,"DOCTOR","RECEPTIONIST","ADMIN");return repo.findByFullNameContainingIgnoreCase(query,PageRequest.of(page,size,Sort.by("fullName")));} 
 private void apply(Patient p,Body b){p.fullName=b.fullName();p.dob=b.dob();p.phone=b.phone();p.medicalHistory=b.medicalHistory();p.allergies=b.allergies();}
 private void require(String got,String expected){if(!expected.equals(got))throw new ResponseStatusException(HttpStatus.FORBIDDEN);}
 private void requireAny(String got,String... roles){if(Arrays.stream(roles).noneMatch(got::equals))throw new ResponseStatusException(HttpStatus.FORBIDDEN);}
}

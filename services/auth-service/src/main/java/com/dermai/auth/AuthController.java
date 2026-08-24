package com.dermai.auth;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;
import java.io.IOException;
import java.time.Instant;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
@RestController @RequestMapping("/api/v1/auth")
public class AuthController {
 private final AuthService service;private final GoogleIdentityVerifier google;private final String bootstrapToken;private final String serviceToken;
 public AuthController(AuthService service,GoogleIdentityVerifier google,@Value("${security.bootstrap-token}") String token,@Value("${security.service-token}") String serviceToken){this.service=service;this.google=google;this.bootstrapToken=token;this.serviceToken=serviceToken;}
 record Credentials(@Email @NotBlank String email,@NotBlank @Size(min=10,max=100) String password){}
 record LoginCredentials(@Email @NotBlank String email,@NotBlank @Size(max=100) String password){}
 record Refresh(@NotBlank String refreshToken){}
 record Forgot(@Email @NotBlank String email){}
 record VerifyEmail(@Email @NotBlank String email,@Pattern(regexp="\\d{6}") String otp){}
 record Reset(@Email @NotBlank String email,@Pattern(regexp="\\d{6}") String otp,@Size(min=10,max=100) String newPassword){}
 record Staff(@Email @NotBlank String email,@NotBlank @Size(min=10,max=100) String password,@NotNull com.dermai.auth.domain.Identity.Role role,@Size(max=150) String displayName){}
 record BlockPatient(boolean blocked){}
 record BlockStaff(boolean blocked){}
 record StaffPassword(@NotBlank @Size(min=10,max=100) String newPassword){}
 record StaffName(@NotBlank @Size(max=150) String displayName){}
 record StaffView(UUID identityId,String displayName,String email,com.dermai.auth.domain.Identity.Role role,com.dermai.auth.domain.Identity.Status status,Instant createdAt,boolean hasAvatar){}
 record StaffDirectoryView(UUID identityId,String displayName,com.dermai.auth.domain.Identity.Status status){}
 record GoogleCredential(@NotBlank @Size(max=6000) String credential){}
 @PostMapping("/register") ResponseEntity<?> register(@Valid @RequestBody Credentials x){
  var u=service.register(x.email(),x.password());return ResponseEntity.status(201).body(Map.of("id",u.id,"email",u.email,"role",u.role));
 }
 @PostMapping("/login") AuthService.Tokens login(@Valid @RequestBody LoginCredentials x){return service.login(x.email(),x.password());}
 @PostMapping("/verification/send") Map<String,String> resendVerification(@Valid @RequestBody Forgot x){
  service.resendVerification(x.email());return Map.of("message","Nếu email đang chờ xác minh, mã OTP mới đã được gửi.");
 }
 @PostMapping("/verification/confirm") ResponseEntity<Void> verifyEmail(@Valid @RequestBody VerifyEmail x){
  service.verifyEmail(x.email(),x.otp());return ResponseEntity.noContent().build();
 }
 @GetMapping("/google/config") Map<String,Object> googleConfig(){return Map.of("enabled",google.enabled(),"clientId",google.clientId());}
 @PostMapping("/google") AuthService.GoogleLogin google(@Valid @RequestBody GoogleCredential x){return service.googleLogin(google.verify(x.credential()));}
 @PostMapping("/refresh") AuthService.Tokens refresh(@Valid @RequestBody Refresh x){return service.refresh(x.refreshToken());}
 @PostMapping("/logout") ResponseEntity<Void> logout(@Valid @RequestBody Refresh x){service.logout(x.refreshToken());return ResponseEntity.noContent().build();}
 @PostMapping("/forgot-password") Map<String,String> forgot(@Valid @RequestBody Forgot x){
  service.createOtp(x.email()); return Map.of("message","Nếu email tồn tại, mã OTP đã được gửi.");
 }
 @PostMapping("/reset-password") ResponseEntity<Void> reset(@Valid @RequestBody Reset x){service.reset(x.email(),x.otp(),x.newPassword());return ResponseEntity.noContent().build();}
 @PostMapping("/staff") ResponseEntity<?> staff(@RequestHeader("X-User-Id") UUID actor,@RequestHeader("X-User-Role") String caller,@Valid @RequestBody Staff x){
  if(!"ADMIN".equals(caller))return ResponseEntity.status(403).body(Map.of("code","FORBIDDEN"));
  var u=service.createStaff(x.email(),x.password(),x.role(),x.displayName(),actor);return ResponseEntity.status(201).body(view(u));
 }
 @GetMapping("/staff") ResponseEntity<?> staffAccounts(@RequestHeader("X-User-Role") String caller,@RequestParam(defaultValue="RECEPTIONIST") com.dermai.auth.domain.Identity.Role role){
  if(!"ADMIN".equals(caller))return ResponseEntity.status(403).body(Map.of("code","FORBIDDEN"));
  return ResponseEntity.ok(service.listStaff(role).stream().map(this::view).toList());
 }
 @GetMapping("/staff/directory") ResponseEntity<?> staffDirectory(@RequestHeader("X-User-Role") String caller){
  if(!Set.of("PATIENT","RECEPTIONIST","ADMIN").contains(caller))return ResponseEntity.status(403).body(Map.of("code","FORBIDDEN"));
  return ResponseEntity.ok(service.listStaff(com.dermai.auth.domain.Identity.Role.RECEPTIONIST).stream().map(x->new StaffDirectoryView(x.id,x.displayName,x.status)).toList());
 }
 @GetMapping("/me") ResponseEntity<?> me(@RequestHeader("X-User-Id") UUID actor,@RequestHeader("X-User-Role") String caller){
  if(!Set.of("PATIENT","RECEPTIONIST").contains(caller))return ResponseEntity.status(403).body(Map.of("code","FORBIDDEN"));
  var staff=service.findIdentity(actor).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND));return ResponseEntity.ok(view(staff));
 }
 @PatchMapping("/me/profile") ResponseEntity<?> updateMyProfile(@RequestHeader("X-User-Id") UUID actor,@RequestHeader("X-User-Role") String caller,@Valid @RequestBody StaffName x){
  if(!"RECEPTIONIST".equals(caller))return ResponseEntity.status(403).body(Map.of("code","FORBIDDEN"));
  return ResponseEntity.ok(view(service.updateOwnReceptionistProfile(actor,x.displayName())));
 }
 @PostMapping(value="/me/avatar",consumes=MediaType.MULTIPART_FORM_DATA_VALUE) ResponseEntity<?> uploadMyAvatar(@RequestHeader("X-User-Id") UUID actor,@RequestHeader("X-User-Role") String caller,@RequestPart("image") MultipartFile image) throws IOException{
  if(!Set.of("PATIENT","RECEPTIONIST").contains(caller))return ResponseEntity.status(403).body(Map.of("code","FORBIDDEN"));
  if(image.isEmpty()||image.getSize()>2*1024*1024)throw new ResponseStatusException(HttpStatus.PAYLOAD_TOO_LARGE,"Ảnh đại diện tối đa 2 MB");
  var mime=image.getContentType();if(!Set.of("image/jpeg","image/png","image/webp").contains(mime))throw new ResponseStatusException(HttpStatus.UNSUPPORTED_MEDIA_TYPE,"Chỉ nhận JPG, PNG hoặc WebP");
  return ResponseEntity.ok(view(service.updateOwnAvatar(actor,image.getBytes(),mime)));
 }
 @GetMapping("/me/avatar") ResponseEntity<byte[]> myAvatar(@RequestHeader("X-User-Id") UUID actor,@RequestHeader("X-User-Role") String caller){
  if(!Set.of("PATIENT","RECEPTIONIST").contains(caller))throw new ResponseStatusException(HttpStatus.FORBIDDEN);
  return avatarResponse(service.findIdentity(actor).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND)));
 }
 @GetMapping("/accounts/{id}/avatar") ResponseEntity<byte[]> accountAvatar(@RequestHeader("X-User-Role") String caller,@PathVariable UUID id){
  if(!"ADMIN".equals(caller))throw new ResponseStatusException(HttpStatus.FORBIDDEN);
  var account=service.findIdentity(id).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND));
  if(!Set.of(com.dermai.auth.domain.Identity.Role.PATIENT,com.dermai.auth.domain.Identity.Role.RECEPTIONIST).contains(account.role))throw new ResponseStatusException(HttpStatus.NOT_FOUND);
  return avatarResponse(account);
 }
 @PatchMapping("/staff/{id}/account") ResponseEntity<?> updateStaffAccount(@RequestHeader("X-User-Id") UUID actor,@RequestHeader("X-User-Role") String caller,@PathVariable UUID id,@Valid @RequestBody BlockStaff x){
  if(!"ADMIN".equals(caller))return ResponseEntity.status(403).body(Map.of("code","FORBIDDEN"));
  return ResponseEntity.ok(view(service.setStaffBlocked(id,x.blocked(),actor)));
 }
 @PatchMapping("/staff/{id}/password") ResponseEntity<?> resetStaffPassword(@RequestHeader("X-User-Id") UUID actor,@RequestHeader("X-User-Role") String caller,@PathVariable UUID id,@Valid @RequestBody StaffPassword x){
  if(!"ADMIN".equals(caller))return ResponseEntity.status(403).body(Map.of("code","FORBIDDEN"));
  return ResponseEntity.ok(view(service.resetStaffPassword(id,x.newPassword(),actor)));
 }
 @PatchMapping("/staff/{id}/profile") ResponseEntity<?> updateStaffProfile(@RequestHeader("X-User-Id") UUID actor,@RequestHeader("X-User-Role") String caller,@PathVariable UUID id,@Valid @RequestBody StaffName x){
  if(!"ADMIN".equals(caller))return ResponseEntity.status(403).body(Map.of("code","FORBIDDEN"));
  return ResponseEntity.ok(view(service.renameReceptionist(id,x.displayName(),actor)));
 }
 @GetMapping("/staff/{id}/events") ResponseEntity<?> staffEvents(@RequestHeader("X-User-Role") String caller,@PathVariable UUID id){
  if(!"ADMIN".equals(caller))return ResponseEntity.status(403).body(Map.of("code","FORBIDDEN"));
  return ResponseEntity.ok(service.staffEvents(id));
 }
 @GetMapping("/patients/{id}/account") ResponseEntity<?> patientAccount(@RequestHeader("X-User-Role") String caller,@PathVariable java.util.UUID id){
  if(!"ADMIN".equals(caller))return ResponseEntity.status(403).body(Map.of("code","FORBIDDEN"));
  var u=service.patientAccount(id);return ResponseEntity.ok(Map.of("identityId",u.id,"email",u.email,"status",u.status));
 }
 @PatchMapping("/patients/{id}/account") ResponseEntity<?> updatePatientAccount(@RequestHeader("X-User-Role") String caller,@PathVariable java.util.UUID id,@RequestBody BlockPatient x){
  if(!"ADMIN".equals(caller))return ResponseEntity.status(403).body(Map.of("code","FORBIDDEN"));
  var u=service.setPatientBlocked(id,x.blocked());return ResponseEntity.ok(Map.of("identityId",u.id,"email",u.email,"status",u.status));
 }
 @PostMapping("/bootstrap-admin") ResponseEntity<?> bootstrap(@RequestHeader("X-Bootstrap-Token") String token,@Valid @RequestBody Credentials x){
  if(bootstrapToken.isBlank()||!java.security.MessageDigest.isEqual(bootstrapToken.getBytes(java.nio.charset.StandardCharsets.UTF_8),token.getBytes(java.nio.charset.StandardCharsets.UTF_8)))return ResponseEntity.status(403).body(Map.of("code","FORBIDDEN"));
  var u=service.bootstrapAdmin(x.email(),x.password());return ResponseEntity.status(201).body(Map.of("identityId",u.id,"email",u.email,"role",u.role));
 }
 @GetMapping("/internal/identities/{id}") ResponseEntity<?> identity(@PathVariable java.util.UUID id,@RequestHeader("X-Service-Token") String token){
  if(serviceToken.isBlank()||!java.security.MessageDigest.isEqual(serviceToken.getBytes(java.nio.charset.StandardCharsets.UTF_8),token.getBytes(java.nio.charset.StandardCharsets.UTF_8)))return ResponseEntity.status(403).build();
  return service.findIdentity(id).<ResponseEntity<?>>map(x->ResponseEntity.ok(Map.of("identityId",x.id,"email",x.email,"role",x.role))).orElseGet(()->ResponseEntity.notFound().build());
 }
 private StaffView view(com.dermai.auth.domain.Identity x){return new StaffView(x.id,x.displayName,x.email,x.role,x.status,x.createdAt,x.avatarData!=null);}
 private ResponseEntity<byte[]> avatarResponse(com.dermai.auth.domain.Identity account){
  if(account.avatarData==null||account.avatarMime==null)throw new ResponseStatusException(HttpStatus.NOT_FOUND);
  return ResponseEntity.ok().contentType(MediaType.parseMediaType(account.avatarMime)).cacheControl(CacheControl.noStore()).body(account.avatarData);
 }
}

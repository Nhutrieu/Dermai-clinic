package com.dermai.auth;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
@RestController @RequestMapping("/api/v1/auth")
public class AuthController {
 private final AuthService service;private final GoogleIdentityVerifier google;private final String bootstrapToken;private final String serviceToken;
 public AuthController(AuthService service,GoogleIdentityVerifier google,@Value("${security.bootstrap-token}") String token,@Value("${security.service-token}") String serviceToken){this.service=service;this.google=google;this.bootstrapToken=token;this.serviceToken=serviceToken;}
 record Credentials(@Email @NotBlank String email,@NotBlank @Size(min=10,max=100) String password){}
 record Refresh(@NotBlank String refreshToken){}
 record Forgot(@Email @NotBlank String email){}
 record VerifyEmail(@Email @NotBlank String email,@Pattern(regexp="\\d{6}") String otp){}
 record Reset(@Email @NotBlank String email,@Pattern(regexp="\\d{6}") String otp,@Size(min=10,max=100) String newPassword){}
 record Staff(@Email @NotBlank String email,@Size(min=10,max=100) String password,@NotNull com.dermai.auth.domain.Identity.Role role){}
 record BlockPatient(boolean blocked){}
 record GoogleCredential(@NotBlank @Size(max=6000) String credential){}
 @PostMapping("/register") ResponseEntity<?> register(@Valid @RequestBody Credentials x){
  var u=service.register(x.email(),x.password());return ResponseEntity.status(201).body(Map.of("id",u.id,"email",u.email,"role",u.role));
 }
 @PostMapping("/login") AuthService.Tokens login(@Valid @RequestBody Credentials x){return service.login(x.email(),x.password());}
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
 @PostMapping("/staff") ResponseEntity<?> staff(@RequestHeader("X-User-Role") String caller,@Valid @RequestBody Staff x){
  if(!"ADMIN".equals(caller))return ResponseEntity.status(403).body(Map.of("code","FORBIDDEN"));
  var u=service.createStaff(x.email(),x.password(),x.role());return ResponseEntity.status(201).body(Map.of("identityId",u.id,"email",u.email,"role",u.role));
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
}

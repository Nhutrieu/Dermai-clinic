package com.dermai.auth;
import com.dermai.auth.domain.*;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.*;
import java.util.*;

@Service @Transactional
public class AuthService {
 private final IdentityRepository users; private final RefreshTokenRepository refreshes;
 private final PasswordOtpRepository otps; private final EmailVerificationOtpRepository verificationOtps;
 private final StaffAccountEventRepository staffEvents;
 private final BCryptPasswordEncoder encoder=new BCryptPasswordEncoder(12);
 private final JavaMailSender mail;
 private final String mailFrom;
 private final SecureRandom random=new SecureRandom(); private final byte[] secret;
 public AuthService(IdentityRepository u,RefreshTokenRepository r,PasswordOtpRepository o,EmailVerificationOtpRepository verificationOtps,StaffAccountEventRepository staffEvents,JavaMailSender mail,@Value("${security.jwt.secret}") String key,@Value("${app.mail.from}") String mailFrom){
  users=u;refreshes=r;otps=o;this.verificationOtps=verificationOtps;this.staffEvents=staffEvents;this.mail=mail;this.mailFrom=mailFrom;secret=key.getBytes(StandardCharsets.UTF_8);
  if(secret.length<32) throw new IllegalArgumentException("JWT_SECRET phải có ít nhất 32 byte");
 }
 public Identity register(String email,String password){
  if(users.findByEmailIgnoreCase(email).isPresent()) throw new IllegalStateException("EMAIL_EXISTS");
  var user=users.save(new Identity(email,encoder.encode(password)));
  sendVerificationOtp(user,false);
  return user;
 }
 public Identity createStaff(String email,String password,Identity.Role role,String displayName,UUID actorIdentityId){
  if(users.findByEmailIgnoreCase(email).isPresent())throw new IllegalStateException("EMAIL_EXISTS");
  if(role==Identity.Role.RECEPTIONIST&&(displayName==null||displayName.isBlank()))throw new StaffManagementException("DISPLAY_NAME_REQUIRED");
  var staff=users.save(Identity.staff(email,encoder.encode(password),role,displayName));
  staffEvents.save(new StaffAccountEvent(staff.id,actorIdentityId,"CREATED"));return staff;
 }
 public Identity bootstrapAdmin(String email,String password){
  if(users.count()!=0)throw new IllegalStateException("BOOTSTRAP_CLOSED");
  return users.save(Identity.staff(email,encoder.encode(password),Identity.Role.ADMIN,null));
 }
 @Transactional(readOnly=true) public List<Identity> listStaff(Identity.Role role){
  if(role==Identity.Role.PATIENT)throw new StaffManagementException("INVALID_STAFF_ROLE");
  return users.findByRoleOrderByCreatedAtDesc(role);
 }
 @Transactional(readOnly=true) public List<StaffAccountEvent> staffEvents(UUID staffIdentityId){
  receptionist(staffIdentityId);return staffEvents.findTop50ByStaffIdentityIdOrderByCreatedAtDesc(staffIdentityId);
 }
 public Identity setStaffBlocked(UUID id,boolean blocked,UUID actorIdentityId){
  var staff=receptionist(id);staff.status=blocked?Identity.Status.LOCKED:Identity.Status.ACTIVE;
  if(blocked)revokeSessions(id);
  staffEvents.save(new StaffAccountEvent(id,actorIdentityId,blocked?"LOCKED":"UNLOCKED"));return staff;
 }
 public Identity resetStaffPassword(UUID id,String newPassword,UUID actorIdentityId){
  var staff=receptionist(id);staff.passwordHash=encoder.encode(newPassword);revokeSessions(id);
  staffEvents.save(new StaffAccountEvent(id,actorIdentityId,"PASSWORD_RESET"));return staff;
 }
 public Identity renameReceptionist(UUID id,String displayName,UUID actorIdentityId){
  var staff=receptionist(id);staff.displayName=displayName.trim();
  staffEvents.save(new StaffAccountEvent(id,actorIdentityId,"PROFILE_UPDATED"));return staff;
 }
 public Identity updateOwnReceptionistProfile(UUID id,String displayName){
  var staff=receptionist(id);staff.displayName=displayName.trim();
  staffEvents.save(new StaffAccountEvent(id,id,"PROFILE_UPDATED"));return staff;
 }
 public Identity updateOwnAvatar(UUID id,byte[] data,String mime){
  var account=users.findById(id).orElseThrow(()->new StaffManagementException("ACCOUNT_NOT_FOUND"));
  if(account.role!=Identity.Role.RECEPTIONIST&&account.role!=Identity.Role.PATIENT)throw new StaffManagementException("AVATAR_NOT_SUPPORTED");
  account.avatarData=data;account.avatarMime=mime;
  if(account.role==Identity.Role.RECEPTIONIST)staffEvents.save(new StaffAccountEvent(id,id,"AVATAR_UPDATED"));
  return account;
 }
 @Transactional(readOnly=true) public Optional<Identity> findIdentity(UUID id){return users.findById(id);}
 public Tokens login(String email,String password){
  var user=users.findByEmailIgnoreCase(email).orElseThrow(()->new IllegalArgumentException("BAD_CREDENTIALS"));
  if(user.status!=Identity.Status.ACTIVE || user.passwordHash==null || !encoder.matches(password,user.passwordHash)) throw new IllegalArgumentException("BAD_CREDENTIALS");
  if(user.role==Identity.Role.PATIENT&&user.emailVerifiedAt==null)throw new IllegalArgumentException("EMAIL_NOT_VERIFIED");
  return issue(user);
 }
 public GoogleLogin googleLogin(GoogleIdentityVerifier.GoogleProfile profile){
  boolean created=false;
  var bySubject=users.findByGoogleSubject(profile.subject());
  Identity user;
  if(bySubject.isPresent()){
   // Google sub là định danh ổn định; email chỉ dùng hiển thị và tìm tài khoản ở lần liên kết đầu.
   user=bySubject.get();
  }else{
   var byEmail=users.findByEmailIgnoreCase(profile.email());
   if(byEmail.isPresent()){
    user=byEmail.get();
    if(user.role!=Identity.Role.PATIENT)throw new IllegalArgumentException("GOOGLE_PATIENT_ONLY");
    if(user.googleSubject!=null&&!user.googleSubject.equals(profile.subject()))throw new IllegalArgumentException("GOOGLE_ACCOUNT_MISMATCH");
    // Chỉ tự liên kết email mà Google là bên xác thực có thẩm quyền (Gmail/Workspace).
    if(!profile.authoritativeEmail())throw new IllegalArgumentException("GOOGLE_LINK_REQUIRES_PASSWORD");
    user.googleSubject=profile.subject();
    user.emailVerifiedAt=Instant.now();
   }else{
    user=users.save(Identity.googlePatient(profile.email(),profile.subject()));
    created=true;
   }
  }
  if(user.role!=Identity.Role.PATIENT)throw new IllegalArgumentException("GOOGLE_PATIENT_ONLY");
  if(user.status!=Identity.Status.ACTIVE)throw new IllegalArgumentException("ACCOUNT_BLOCKED");
  Tokens tokens=issue(user);
  return new GoogleLogin(tokens.accessToken(),tokens.refreshToken(),tokens.expiresIn(),tokens.role(),created,profile.email(),profile.fullName());
 }
 public Tokens refresh(String raw){
  var stored=refreshes.findByTokenHash(hash(raw)).orElseThrow(()->new IllegalArgumentException("INVALID_REFRESH"));
  if(stored.revokedAt!=null || stored.expiresAt.isBefore(Instant.now())) throw new IllegalArgumentException("INVALID_REFRESH");
  stored.revokedAt=Instant.now();
  var user=users.findById(stored.identityId).orElseThrow();
  if(user.status!=Identity.Status.ACTIVE) throw new IllegalArgumentException("ACCOUNT_BLOCKED");
  return issue(user);
 }
 public void logout(String raw){refreshes.findByTokenHash(hash(raw)).ifPresent(t->t.revokedAt=Instant.now());}
 public void resendVerification(String email){
  var user=users.findByEmailIgnoreCase(email).orElse(null);
  // Keep the public response generic so this endpoint cannot be used to enumerate accounts.
  if(user==null||user.emailVerifiedAt!=null)return;
  sendVerificationOtp(user,true);
 }
 public void verifyEmail(String email,String code){
  var user=users.findByEmailIgnoreCase(email).orElseThrow(()->new IllegalArgumentException("INVALID_OTP"));
  if(user.emailVerifiedAt!=null)return;
  var otp=verificationOtps.findTopByIdentityIdOrderByCreatedAtDesc(user.id)
   .orElseThrow(()->new IllegalArgumentException("INVALID_OTP"));
  otp.attempts++;
  if(otp.usedAt!=null||otp.expiresAt.isBefore(Instant.now())||otp.attempts>5||!encoder.matches(code,otp.otpHash))
   throw new IllegalArgumentException("INVALID_OTP");
  otp.usedAt=Instant.now();user.emailVerifiedAt=Instant.now();
 }
 @Transactional(readOnly=true) public Identity patientAccount(UUID id){
  var user=users.findById(id).orElseThrow(()->new NoSuchElementException("IDENTITY_NOT_FOUND"));
  if(user.role!=Identity.Role.PATIENT)throw new IllegalArgumentException("NOT_PATIENT");
  return user;
 }
 public Identity setPatientBlocked(UUID id,boolean blocked){
  var user=patientAccount(id);
  user.status=blocked?Identity.Status.LOCKED:Identity.Status.ACTIVE;
  if(blocked){
   revokeSessions(id);
  }
  return user;
 }
 private Identity receptionist(UUID id){
  var user=users.findById(id).orElseThrow(()->new StaffManagementException("STAFF_NOT_FOUND"));
  if(user.role!=Identity.Role.RECEPTIONIST)throw new StaffManagementException("NOT_RECEPTIONIST");return user;
 }
 private void revokeSessions(UUID id){var now=Instant.now();refreshes.findAllByIdentityId(id).forEach(token->token.revokedAt=now);}
 public String createOtp(String email){
  var user=users.findByEmailIgnoreCase(email).orElse(null);
  if(user==null) return null;
  String code="%06d".formatted(random.nextInt(1_000_000));
  otps.save(new PasswordOtp(user.id,encoder.encode(code)));
  var message=new SimpleMailMessage();message.setTo(user.email);message.setFrom(mailFrom);message.setSubject("Mã xác nhận đặt lại mật khẩu DermAI");message.setText("Mã OTP của bạn là: "+code+"\n\nMã có hiệu lực trong thời gian giới hạn. Không chia sẻ mã này với người khác.");mail.send(message);return code;
 }
 private void sendVerificationOtp(Identity user,boolean enforceCooldown){
  var latest=verificationOtps.findTopByIdentityIdOrderByCreatedAtDesc(user.id);
  if(enforceCooldown&&latest.filter(x->x.createdAt.plusSeconds(60).isAfter(Instant.now())).isPresent())
   throw new IllegalStateException("OTP_COOLDOWN");
  // A newly issued code invalidates the previous one and is stored only as a BCrypt hash.
  latest.filter(x->x.usedAt==null).ifPresent(x->x.usedAt=Instant.now());
  String code="%06d".formatted(random.nextInt(1_000_000));
  verificationOtps.save(new EmailVerificationOtp(user.id,encoder.encode(code)));
  var message=new SimpleMailMessage();
  message.setTo(user.email);message.setFrom(mailFrom);
  message.setSubject("Xác minh email DermAI Clinic");
  message.setText("Mã OTP xác minh email của bạn là: "+code+"\n\nMã có hiệu lực trong 5 phút. Không chia sẻ mã này với người khác.");
  mail.send(message);
 }
 public void reset(String email,String code,String password){
  var user=users.findByEmailIgnoreCase(email).orElseThrow(()->new IllegalArgumentException("INVALID_OTP"));
  var otp=otps.findTopByIdentityIdOrderByExpiresAtDesc(user.id).orElseThrow(()->new IllegalArgumentException("INVALID_OTP"));
  otp.attempts++;
  if(otp.usedAt!=null || otp.expiresAt.isBefore(Instant.now()) || otp.attempts>5 || !encoder.matches(code,otp.otpHash))
   throw new IllegalArgumentException("INVALID_OTP");
  otp.usedAt=Instant.now();user.passwordHash=encoder.encode(password);
 }
 private Tokens issue(Identity user){
  Instant now=Instant.now();
  String access=Jwts.builder().subject(user.id.toString()).claim("role",user.role.name()).issuedAt(Date.from(now))
   .expiration(Date.from(now.plusSeconds(900))).signWith(Keys.hmacShaKeyFor(secret)).compact();
  String raw=Base64.getUrlEncoder().withoutPadding().encodeToString(random.generateSeed(48));
  refreshes.save(new RefreshToken(user.id,hash(raw),now.plus(Duration.ofDays(14))));
  return new Tokens(access,raw,900,user.role.name());
 }
 private String hash(String value){try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)));}catch(NoSuchAlgorithmException e){throw new IllegalStateException(e);}}
 public record Tokens(String accessToken,String refreshToken,long expiresIn,String role){}
 public record GoogleLogin(String accessToken,String refreshToken,long expiresIn,String role,boolean newAccount,String email,String fullName){}
 static class StaffManagementException extends RuntimeException{StaffManagementException(String code){super(code);}}
}

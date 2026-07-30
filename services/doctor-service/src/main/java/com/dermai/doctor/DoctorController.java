package com.dermai.doctor;
import jakarta.validation.Valid;import jakarta.validation.constraints.*;import org.springframework.http.*;import org.springframework.transaction.annotation.Transactional;import org.springframework.web.bind.annotation.*;import org.springframework.web.multipart.MultipartFile;import org.springframework.web.server.ResponseStatusException;import java.io.IOException;import java.time.*;import java.util.*;
@RestController @RequestMapping("/api/v1/doctors")
public class DoctorController{
 private final DoctorRepository doctors;private final ScheduleRepository schedules;private final LeaveRepository leaves;private final DoctorProfileWebSocketHandler profileUpdates;
 DoctorController(DoctorRepository d,ScheduleRepository s,LeaveRepository l,DoctorProfileWebSocketHandler p){doctors=d;schedules=s;leaves=l;profileUpdates=p;}
 record DoctorBody(@NotNull UUID identityId,@NotBlank String fullName,@NotBlank String specialtyCode,@Min(0) int experienceYears,String certificateNo){}
 record DoctorProfileBody(@NotBlank @Size(max=160) String fullName,@NotBlank @Size(max=80) String specialtyCode,@Min(0) @Max(80) int experienceYears,@Size(max=120) String certificateNo){}
 record ScheduleBody(@Min(1) @Max(7) short weekday,@NotNull LocalTime startTime,@NotNull LocalTime endTime,@Min(10) @Max(120) int slotMinutes){}
 record LeaveBody(@NotNull Instant startAt,@NotNull Instant endAt,@Size(max=250) String reason){}
 record BioBody(@Size(max=1200) String bio){}
 record SchedulingDoctor(UUID id,UUID identityId,String fullName,String specialtyCode,int experienceYears,List<WorkSchedule> workSchedules,List<SchedulingLeave> leavePeriods){}
 record SchedulingLeave(Instant startAt,Instant endAt){}
 @GetMapping List<Doctor> list(@RequestParam(required=false) String specialty){return specialty==null?doctors.findAll():doctors.findBySpecialtyCodeAndActiveTrue(specialty);}
 @GetMapping("/me") Doctor me(@RequestHeader("X-User-Id") UUID identity,@RequestHeader("X-User-Role") String role){require(role,"DOCTOR");return doctors.findByIdentityId(identity).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND,"Tài khoản chưa có hồ sơ bác sĩ"));}
 @PatchMapping("/me") Doctor updateMe(@RequestHeader("X-User-Id") UUID identity,@RequestHeader("X-User-Role") String role,@Valid @RequestBody DoctorProfileBody body){
  require(role,"DOCTOR");var doctor=doctors.findByIdentityId(identity).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND,"Tài khoản chưa có hồ sơ bác sĩ"));
  doctor.fullName=body.fullName().trim();doctor.specialtyCode=body.specialtyCode().trim().toUpperCase(Locale.ROOT);doctor.experienceYears=body.experienceYears();doctor.certificateNo=body.certificateNo()==null||body.certificateNo().isBlank()?null:body.certificateNo().trim();
  var saved=doctors.save(doctor);profileUpdates.broadcastUpdated(saved.id);return saved;
 }
 @PostMapping(value="/me/avatar",consumes=MediaType.MULTIPART_FORM_DATA_VALUE) Doctor uploadAvatar(@RequestHeader("X-User-Id") UUID identity,@RequestHeader("X-User-Role") String role,@RequestPart("image") MultipartFile image) throws IOException{
  require(role,"DOCTOR");var doctor=doctors.findByIdentityId(identity).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND));
  if(image.isEmpty()||image.getSize()>2*1024*1024)throw new ResponseStatusException(HttpStatus.PAYLOAD_TOO_LARGE,"Ảnh đại diện tối đa 2 MB");
  var mime=image.getContentType();if(!Set.of("image/jpeg","image/png","image/webp").contains(mime))throw new ResponseStatusException(HttpStatus.UNSUPPORTED_MEDIA_TYPE,"Chỉ nhận JPG, PNG hoặc WebP");
  doctor.avatarData=image.getBytes();doctor.avatarMime=mime;doctor.avatarUrl="/api/v1/doctors/"+doctor.id+"/avatar?v="+System.currentTimeMillis();var saved=doctors.save(doctor);profileUpdates.broadcastUpdated(saved.id);return saved;
 }
 @PatchMapping("/me/bio") Doctor updateBio(@RequestHeader("X-User-Id") UUID identity,@RequestHeader("X-User-Role") String role,@Valid @RequestBody BioBody body){require(role,"DOCTOR");var doctor=doctors.findByIdentityId(identity).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND));doctor.bio=body.bio()==null||body.bio().isBlank()?null:body.bio().trim();var saved=doctors.save(doctor);profileUpdates.broadcastUpdated(saved.id);return saved;}
 @GetMapping("/{id}/avatar") ResponseEntity<byte[]> avatar(@PathVariable UUID id){var doctor=doctors.findById(id).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND));if(doctor.avatarData==null)throw new ResponseStatusException(HttpStatus.NOT_FOUND);return ResponseEntity.ok().contentType(MediaType.parseMediaType(doctor.avatarMime)).cacheControl(CacheControl.noCache()).body(doctor.avatarData);}
 @GetMapping("/me/schedule") Map<String,Object> mySchedule(@RequestHeader("X-User-Id") UUID identity,@RequestHeader("X-User-Role") String role){require(role,"DOCTOR");var d=doctors.findByIdentityId(identity).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND));return Map.of("workSchedules",schedules.findByDoctorId(d.id),"leavePeriods",leaves.findByDoctorId(d.id));}
 @GetMapping("/scheduling-data") List<SchedulingDoctor> schedulingData(@RequestHeader("X-User-Role") String role){
  requireAny(role,"PATIENT","RECEPTIONIST","DOCTOR","ADMIN");
  return doctors.findAll().stream().filter(d->d.active).map(d->new SchedulingDoctor(d.id,d.identityId,d.fullName,d.specialtyCode,d.experienceYears,schedules.findByDoctorId(d.id),leaves.findByDoctorId(d.id).stream().map(x->new SchedulingLeave(x.startAt,x.endAt)).toList())).toList();
 }
 @PostMapping ResponseEntity<Doctor> create(@RequestHeader("X-User-Role") String role,@Valid @RequestBody DoctorBody b){
  require(role,"ADMIN");if(doctors.findByIdentityId(b.identityId()).isPresent())throw new ResponseStatusException(HttpStatus.CONFLICT,"Tài khoản đã có hồ sơ bác sĩ");var d=new Doctor(b.identityId(),b.fullName(),b.specialtyCode());d.experienceYears=b.experienceYears();d.certificateNo=b.certificateNo();var saved=doctors.save(d);profileUpdates.broadcastUpdated(saved.id);return ResponseEntity.status(201).body(saved);
 }
 @Transactional @PutMapping("/{id}/schedule") List<WorkSchedule> schedule(@PathVariable UUID id,@RequestHeader("X-User-Id") UUID identity,@RequestHeader("X-User-Role") String role,@Valid @RequestBody List<ScheduleBody> body){
  requireOwner(id,role,identity);if(doctors.findById(id).isEmpty())throw new ResponseStatusException(HttpStatus.NOT_FOUND);
  for(var x:body)if(!x.startTime().isBefore(x.endTime())||Duration.between(x.startTime(),x.endTime()).toMinutes()<x.slotMinutes())throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Khoảng giờ phải chứa ít nhất một slot");
  for(int i=0;i<body.size();i++)for(int j=i+1;j<body.size();j++){var a=body.get(i);var b=body.get(j);if(a.weekday()==b.weekday()&&a.startTime().isBefore(b.endTime())&&b.startTime().isBefore(a.endTime()))throw new ResponseStatusException(HttpStatus.CONFLICT,"Các ca làm cùng ngày không được chồng lấn");}
  var next=body.stream().map(x->{var s=new WorkSchedule();s.id=UUID.randomUUID();s.doctorId=id;s.weekday=x.weekday();s.startTime=x.startTime();s.endTime=x.endTime();s.slotMinutes=x.slotMinutes();return s;}).toList();
  schedules.deleteAll(schedules.findByDoctorId(id));schedules.flush();return schedules.saveAll(next);
 }
 @PostMapping("/{id}/leave") ResponseEntity<LeavePeriod> leave(@PathVariable UUID id,@RequestHeader("X-User-Id") UUID identity,@RequestHeader("X-User-Role") String role,@Valid @RequestBody LeaveBody b){
  requireOwner(id,role,identity);if(!b.startAt().isBefore(b.endAt()))throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Khoảng nghỉ sai");
  var x=new LeavePeriod();x.id=UUID.randomUUID();x.doctorId=id;x.startAt=b.startAt();x.endAt=b.endAt();x.reason=b.reason();return ResponseEntity.status(201).body(leaves.save(x));
 }
 @DeleteMapping("/{id}/leave/{leaveId}") @ResponseStatus(HttpStatus.NO_CONTENT) void deleteLeave(@PathVariable UUID id,@PathVariable UUID leaveId,@RequestHeader("X-User-Id") UUID identity,@RequestHeader("X-User-Role") String role){
  requireOwner(id,role,identity);var leave=leaves.findById(leaveId).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND));if(!id.equals(leave.doctorId))throw new ResponseStatusException(HttpStatus.NOT_FOUND);leaves.delete(leave);
 }
 private void require(String got,String r){if(!r.equals(got))throw new ResponseStatusException(HttpStatus.FORBIDDEN);}
 private void requireAny(String got,String... r){if(Arrays.stream(r).noneMatch(got::equals))throw new ResponseStatusException(HttpStatus.FORBIDDEN);}
 private void requireOwner(UUID doctorId,String role,UUID identity){if("ADMIN".equals(role))return;if(!"DOCTOR".equals(role)||identity==null||doctors.findByIdentityId(identity).map(d->!d.id.equals(doctorId)).orElse(true))throw new ResponseStatusException(HttpStatus.FORBIDDEN);}
}

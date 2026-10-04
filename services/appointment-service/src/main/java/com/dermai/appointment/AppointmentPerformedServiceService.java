package com.dermai.appointment;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.RestClient;
import org.springframework.web.server.ResponseStatusException;

@Service
@Transactional
public class AppointmentPerformedServiceService {
 private final AppointmentRepository appointments;
 private final AppointmentPerformedServiceRepository performed;
 private final RestClient clinic;

 AppointmentPerformedServiceService(AppointmentRepository appointments,AppointmentPerformedServiceRepository performed,@Value("${doctor-service.url}") String doctorUrl){
  this.appointments=appointments;this.performed=performed;this.clinic=RestClient.builder().baseUrl(doctorUrl).build();
 }

 public View confirm(UUID appointmentId,Set<UUID> serviceIds,UUID doctorIdentity){
  var appointment=appointments.findLocked(appointmentId).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND));
  if(!doctorIdentity.equals(appointment.doctorIdentityId))throw new ResponseStatusException(HttpStatus.FORBIDDEN);
  if(appointment.status!=AppointmentStatus.IN_PROGRESS)throw new ResponseStatusException(HttpStatus.CONFLICT,"Chỉ được xác nhận dịch vụ khi ca khám đang diễn ra.");
  var requested=serviceIds==null?Set.<UUID>of():new LinkedHashSet<>(serviceIds);
  if(appointment.doctorId==null)throw new ResponseStatusException(HttpStatus.CONFLICT,"Ca khám chưa có bác sĩ phụ trách.");
  var catalog=Optional.ofNullable(clinic.get().uri("/api/v1/services?doctorId={doctorId}",appointment.doctorId).retrieve().body(ClinicServiceView[].class)).map(Arrays::asList).orElseGet(List::of);
  var byId=new HashMap<UUID,ClinicServiceView>();
  catalog.stream().filter(ClinicServiceView::active).forEach(item->byId.put(item.id(),item));
  if(!byId.keySet().containsAll(requested))throw new ResponseStatusException(HttpStatus.CONFLICT,"Có dịch vụ không thuộc chuyên khoa của bác sĩ hoặc không còn hoạt động. Vui lòng tải lại danh sách.");
  var confirmedAt=Instant.now();
  performed.deleteForAppointment(appointmentId);
  var snapshots=new ArrayList<AppointmentPerformedService>();
  for(var serviceId:requested){var source=byId.get(serviceId);if(source.priceFrom()==null||source.priceFrom().signum()<0)throw new ResponseStatusException(HttpStatus.CONFLICT,"Giá dịch vụ không hợp lệ: "+source.name());var item=new AppointmentPerformedService();item.id=UUID.randomUUID();item.appointmentId=appointmentId;item.serviceId=source.id();item.serviceCode=source.code();item.serviceName=source.name();item.unitPrice=source.priceFrom();item.confirmedBy=doctorIdentity;item.confirmedAt=confirmedAt;snapshots.add(item);}
  performed.saveAll(snapshots);
  appointment.servicesConfirmedAt=confirmedAt;appointment.servicesConfirmedBy=doctorIdentity;appointment.updatedAt=confirmedAt;appointments.save(appointment);
  return view(appointment,snapshots);
 }

 @Transactional(readOnly=true)
 public View get(UUID appointmentId,UUID identity,String role){
  var appointment=appointments.findById(appointmentId).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND));
  var staff=Set.of("RECEPTIONIST","ADMIN").contains(role);
  if(!staff&&!("DOCTOR".equals(role)&&identity.equals(appointment.doctorIdentityId)))throw new ResponseStatusException(HttpStatus.FORBIDDEN);
  return view(appointment,performed.findByAppointmentIdOrderByServiceNameAsc(appointmentId));
 }

 private View view(Appointment appointment,List<AppointmentPerformedService> items){return new View(appointment.id,appointment.servicesConfirmedAt,appointment.servicesConfirmedBy,items.stream().map(item->new Item(item.serviceId,item.serviceCode,item.serviceName,item.unitPrice)).toList());}
 record ClinicServiceView(UUID id,String code,String name,String specialtyCode,BigDecimal priceFrom,boolean active){}
 public record Item(UUID serviceId,String serviceCode,String serviceName,BigDecimal unitPrice){}
 public record View(UUID appointmentId,Instant confirmedAt,UUID confirmedBy,List<Item> items){}
}

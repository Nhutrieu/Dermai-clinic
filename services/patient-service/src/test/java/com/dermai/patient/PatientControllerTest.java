package com.dermai.patient;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

class PatientControllerTest {
 @Test void normalizesCommonVietnamesePhoneFormats(){
  assertThat(PatientController.normalizePhone("0352 790 904")).isEqualTo("0352790904");
  assertThat(PatientController.normalizePhone("+84 352-790-904")).isEqualTo("0352790904");
  assertThat(PatientController.normalizePhone("84 (352) 790 904")).isEqualTo("0352790904");
  assertThat(PatientController.normalizePhone("0084 352 790 904")).isEqualTo("0352790904");
 }

 @Test void rejectsMalformedPhoneNumbers(){
  assertThatThrownBy(()->PatientController.normalizePhone("++++++++"))
   .hasMessageContaining("Số điện thoại không hợp lệ");
  assertThatThrownBy(()->PatientController.normalizePhone("12345"))
   .hasMessageContaining("Số điện thoại không hợp lệ");
 }

 @Test void claimsAnUnlinkedHotlineProfileWithoutChangingPatientId(){
  var repository=mock(PatientRepository.class);var appointmentClient=mock(AppointmentIdentityClient.class);var controller=new PatientController(repository,appointmentClient);
  var oldIdentity=UUID.randomUUID();var newIdentity=UUID.randomUUID();var patient=new Patient(oldIdentity,"Khách hotline");patient.phone="0352790904";patient.accountLinked=false;
  when(repository.findByIdentityId(newIdentity)).thenReturn(Optional.empty());when(repository.findFirstByPhone("0352790904")).thenReturn(Optional.of(patient));when(repository.saveAndFlush(patient)).thenReturn(patient);
  var body=new PatientController.Body("Nguyễn Văn A",null,"0352 790 904",null,null);var response=controller.create(newIdentity,"PATIENT",body);
  assertThat(response.getStatusCode().value()).isEqualTo(200);assertThat(patient.identityId).isEqualTo(newIdentity);assertThat(patient.id).isNotNull();assertThat(patient.accountLinked).isTrue();
  verify(appointmentClient).relink(patient.id,oldIdentity,newIdentity);
 }

 @Test void refusesToClaimAPhoneAlreadyLinkedToAnotherAccount(){
  var repository=mock(PatientRepository.class);var appointmentClient=mock(AppointmentIdentityClient.class);var controller=new PatientController(repository,appointmentClient);var newIdentity=UUID.randomUUID();var patient=new Patient(UUID.randomUUID(),"Đã có tài khoản");patient.phone="0352790904";patient.accountLinked=true;
  when(repository.findByIdentityId(newIdentity)).thenReturn(Optional.empty());when(repository.findFirstByPhone("0352790904")).thenReturn(Optional.of(patient));
  var response=controller.create(newIdentity,"PATIENT",new PatientController.Body("Người khác",null,"0352790904",null,null));
  assertThat(response.getStatusCode().value()).isEqualTo(409);verifyNoInteractions(appointmentClient);
 }

 @Test void doctorCanReadOnlyAPatientBackedByAnAppointmentRelationship(){
  var repository=mock(PatientRepository.class);var appointmentClient=mock(AppointmentIdentityClient.class);var controller=new PatientController(repository,appointmentClient);
  var doctorIdentity=UUID.randomUUID();var patient=new Patient(UUID.randomUUID(),"Bệnh nhân được phân công");
  when(repository.findById(patient.id)).thenReturn(Optional.of(patient));

  assertThat(controller.byId(patient.id,doctorIdentity,"DOCTOR")).isSameAs(patient);

  verify(appointmentClient).requireDoctorPatientAccess(patient.id,doctorIdentity);
 }

 @Test void doctorCannotUseTheStaffDirectoryToEnumerateUnrelatedPatients(){
  var controller=new PatientController(mock(PatientRepository.class),mock(AppointmentIdentityClient.class));

  assertThatThrownBy(()->controller.search("",0,20,"DOCTOR"))
   .isInstanceOfSatisfying(ResponseStatusException.class,error->
    assertThat(error.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN));
 }
}

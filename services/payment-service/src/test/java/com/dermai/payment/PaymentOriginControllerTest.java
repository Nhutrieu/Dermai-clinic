package com.dermai.payment;

import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

class PaymentOriginControllerTest {
 private PaymentService deposits;
 private InvoicePaymentService invoices;
 private MockMvc mvc;
 private final UUID actor=UUID.randomUUID(), booking=UUID.randomUUID();
 @BeforeEach void setUp() {
  deposits=mock(PaymentService.class);invoices=mock(InvoicePaymentService.class);
  var origins=new PaymentReturnOrigins("http://localhost:3000/payment/success",
    "http://localhost:3000/payment/cancel","https://clinic-tunnel.example");
  mvc=MockMvcBuilders.standaloneSetup(new PaymentController(deposits,invoices,
    mock(DepositSettingsService.class),"internal-test-token",origins))
    .setControllerAdvice(new PaymentExceptionHandler()).build();
 }
 @ParameterizedTest @ValueSource(strings={"http://localhost:3000","https://clinic-tunnel.example"})
 void forwardsTheBrowserOriginForDepositsAndInvoices(String origin) throws Exception {
  mvc.perform(post("/api/v1/payments").header("X-User-Id",actor).header("X-User-Role","PATIENT")
    .header("Origin",origin).contentType(MediaType.APPLICATION_JSON)
    .content("{\"bookingId\":\""+booking+"\"}")).andExpect(status().isCreated());
  verify(deposits).create(booking,actor,null,origin);
  mvc.perform(post("/api/v1/payments/internal/invoices").header("X-Service-Token","internal-test-token")
    .header("Origin",origin).contentType(MediaType.APPLICATION_JSON)
    .content("{\"invoiceId\":\""+booking+"\",\"patientIdentityId\":\""+actor+"\",\"amount\":200000}"))
    .andExpect(status().isCreated());
  verify(invoices).create(booking,actor,new java.math.BigDecimal("200000"),origin);
 }
 @Test void requestsWithoutOriginRemainCompatible() throws Exception {
  mvc.perform(post("/api/v1/payments").header("X-User-Id",actor).header("X-User-Role","PATIENT")
    .contentType(MediaType.APPLICATION_JSON).content("{\"bookingId\":\""+booking+"\"}"))
    .andExpect(status().isCreated());
  verify(deposits).create(booking,actor,null,null);
 }
 @Test void rejectsUnknownOriginBeforeCreatingAnyPayment() throws Exception {
  mvc.perform(post("/api/v1/payments").header("X-User-Id",actor).header("X-User-Role","PATIENT")
    .header("Origin","https://evil.example").contentType(MediaType.APPLICATION_JSON)
    .content("{\"bookingId\":\""+booking+"\"}")).andExpect(status().isConflict());
  verifyNoInteractions(deposits,invoices);
 }
}

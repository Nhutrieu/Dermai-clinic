package com.dermai.prescription;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.util.*;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class BillingPaymentOriginTest {
 @ParameterizedTest @ValueSource(strings={"http://localhost:3000","https://clinic-tunnel.example"})
 void forwardsBrowserOriginToTheInternalInvoicePaymentEndpoint(String origin) throws Exception {
  var seenOrigin=new AtomicReference<String>();
  var server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
  server.createContext("/api/v1/payments",exchange->{
   exchange.getRequestBody().readAllBytes();
   var invoiceRequest=exchange.getRequestMethod().equals("POST");
   if(invoiceRequest)seenOrigin.set(exchange.getRequestHeaders().getFirst("Origin"));
   var body=(invoiceRequest?"{\"checkoutUrl\":\"https://checkout.example/invoice\"}":
     "{\"status\":\"SUCCESS\",\"amount\":100000}").getBytes(StandardCharsets.UTF_8);
   exchange.getResponseHeaders().set("Content-Type","application/json");
   exchange.sendResponseHeaders(200,body.length);
   try(var output=exchange.getResponseBody()){output.write(body);}
  });
  server.start();
  try {
   var invoices=mock(InvoiceRepository.class);
   var actor=UUID.randomUUID();var invoice=new Invoice();invoice.id=UUID.randomUUID();
   invoice.appointmentId=UUID.randomUUID();invoice.patientIdentityId=actor;
   invoice.status=Invoice.Status.AWAITING_PAYMENT;invoice.depositApplied=new BigDecimal("100000");
   invoice.totalAmount=new BigDecimal("300000");invoice.remainingAmount=new BigDecimal("200000");
   when(invoices.findById(invoice.id)).thenReturn(Optional.of(invoice));
   var base="http://127.0.0.1:"+server.getAddress().getPort();
   var service=new BillingService(invoices,mock(InvoiceCashPaymentRepository.class),
     mock(InventoryMovementRepository.class),mock(InvoiceAdjustmentRepository.class),
     mock(MedicineRepository.class),mock(PrescriptionRepository.class),base,base,"test-token",
     Clock.systemUTC(),mock(BillingReceptionEvents.class));
   service.createOnlinePayment(invoice.id,actor,"PATIENT",origin);
   assertThat(seenOrigin.get()).isEqualTo(origin);
  } finally {server.stop(0);}
 }
}

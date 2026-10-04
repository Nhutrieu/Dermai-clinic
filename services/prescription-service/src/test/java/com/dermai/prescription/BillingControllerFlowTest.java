package com.dermai.prescription;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;

import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

class BillingControllerFlowTest {
 @Test
 void receptionistCannotDispenseBecausePaidInvoicesBelongToThePharmacyQueue(){
  var billing=mock(BillingService.class);
  var controller=new BillingController(billing);

  assertThatThrownBy(()->controller.dispense(UUID.randomUUID(),UUID.randomUUID(),"RECEPTIONIST"))
    .isInstanceOfSatisfying(ResponseStatusException.class,error->{
     org.assertj.core.api.Assertions.assertThat(error.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
     org.assertj.core.api.Assertions.assertThat(error.getReason()).contains("quầy Dược").contains("dược sĩ");
    });
  verifyNoInteractions(billing);
 }
}

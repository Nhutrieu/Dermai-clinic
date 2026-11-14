package com.dermai.payment;

import static org.assertj.core.api.Assertions.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class PaymentReturnOriginsTest {
 private final PaymentReturnOrigins origins = new PaymentReturnOrigins(
   "http://localhost:3000/payment/success", "http://localhost:3000/payment/cancel",
   "https://clinic-tunnel.example");
 @ParameterizedTest @ValueSource(strings={"http://localhost:3000", "https://clinic-tunnel.example"})
 void returnsToTheAllowedBrowserOrigin(String origin) {
  assertThat(origins.validate(origin)).isEqualTo(origin);
  assertThat(PaymentReturnOrigins.redirectUrl("http://localhost:3000/payment/success",origin))
    .isEqualTo(origin+"/payment/success");
  assertThat(PaymentReturnOrigins.redirectUrl("http://localhost:3000/payment/cancel",origin))
    .isEqualTo(origin+"/payment/cancel");
 }
 @Test void missingOriginUsesTheConfiguredFallback() {
  assertThat(origins.validate(null)).isNull();
  assertThat(PaymentReturnOrigins.redirectUrl("http://localhost:3000/payment/success",null))
    .isEqualTo("http://localhost:3000/payment/success");
 }
 @ParameterizedTest @ValueSource(strings={"null", "https://evil.example", "http://localhost:3001",
   "https://clinic-tunnel.example.evil.example", "https://clinic-tunnel.example/path",
   "https://clinic-tunnel.example@evil.example"})
 void rejectsUnconfiguredReturnDestinations(String origin) {
  assertThatThrownBy(()->origins.validate(origin)).isInstanceOf(PaymentConflict.class);
 }
 @Test void preservesConfiguredReturnPathAndQuery() {
  assertThat(PaymentReturnOrigins.redirectUrl("https://clinic.example/custom/success?flow=invoice#done",
    "http://localhost:3000")).isEqualTo("http://localhost:3000/custom/success?flow=invoice#done");
 }
}

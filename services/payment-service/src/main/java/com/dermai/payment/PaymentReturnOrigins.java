package com.dermai.payment;

import java.net.URI;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/** Only configured frontend origins may receive payment returns. */
@Component
class PaymentReturnOrigins {
 private final Set<String> allowed = new HashSet<>();
 PaymentReturnOrigins(@Value("${payment.return-url}") String returnUrl,
   @Value("${payment.cancel-url}") String cancelUrl,
   @Value("${payment.allowed-return-origins:}") String additionalOrigins) {
  allowed.add(originOf(returnUrl));
  allowed.add(originOf(cancelUrl));
  for (var origin : additionalOrigins.split(",")) {
   if (!origin.isBlank()) allowed.add(originOf(origin.trim()));
  }
 }
 String validate(String origin) {
  if (origin == null || origin.isBlank()) return null;
  if (!allowed.contains(origin)) throw new PaymentConflict("PAYMENT_RETURN_ORIGIN_NOT_ALLOWED");
  return origin;
 }
 static String redirectUrl(String configuredUrl, String origin) {
  if (origin == null) return configuredUrl;
  var url = URI.create(configuredUrl);
  return origin + Optional.ofNullable(url.getRawPath()).orElse("")
    + (url.getRawQuery() == null ? "" : "?" + url.getRawQuery())
    + (url.getRawFragment() == null ? "" : "#" + url.getRawFragment());
 }
 private static String originOf(String url) {
  var uri = URI.create(url);
  if (!Set.of("http", "https").contains(uri.getScheme()) || uri.getHost() == null || uri.getRawUserInfo() != null)
   throw new IllegalArgumentException("Invalid payment frontend URL");
  return uri.getScheme() + "://" + uri.getRawAuthority();
 }
}

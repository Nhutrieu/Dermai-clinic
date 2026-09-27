package com.dermai.gateway;

import org.springframework.cloud.gateway.filter.ratelimit.KeyResolver;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import reactor.core.publisher.Mono;

@Configuration
class RateLimitConfiguration {
  @Bean
  KeyResolver clientIpKeyResolver() {
    return exchange -> {
      String forwarded = exchange.getRequest().getHeaders().getFirst("X-Forwarded-For");
      if (forwarded != null && !forwarded.isBlank()) {
        String[] chain = forwarded.split(",");
        String address = chain[chain.length - 1].trim();
        if (!address.isBlank()) return Mono.just(address);
      }
      var remote = exchange.getRequest().getRemoteAddress();
      return Mono.just(remote == null ? "unknown" : remote.getAddress().getHostAddress());
    };
  }
}

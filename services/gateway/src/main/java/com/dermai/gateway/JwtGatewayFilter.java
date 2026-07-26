package com.dermai.gateway;

import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cloud.gateway.filter.*;
import org.springframework.core.Ordered;
import org.springframework.http.*;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;
import java.nio.charset.StandardCharsets;
import java.util.Set;

@Component
public class JwtGatewayFilter implements GlobalFilter, Ordered {
  private final byte[] secret;
  private static final Set<String> PUBLIC = Set.of(
      "/api/v1/auth/register", "/api/v1/auth/login", "/api/v1/auth/refresh",
      "/api/v1/auth/forgot-password", "/api/v1/auth/reset-password",
      "/api/v1/auth/bootstrap-admin");
  public JwtGatewayFilter(@Value("${security.jwt.secret}") String secret) {
    if (secret.getBytes(StandardCharsets.UTF_8).length < 32)
      throw new IllegalArgumentException("JWT_SECRET phải có ít nhất 32 byte");
    this.secret = secret.getBytes(StandardCharsets.UTF_8);
  }
  @Override public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
    String path=exchange.getRequest().getURI().getPath();
    boolean publicDoctorDirectory = exchange.getRequest().getMethod() == HttpMethod.GET && path.equals("/api/v1/doctors");
    boolean publicDoctorAvatar = exchange.getRequest().getMethod() == HttpMethod.GET && path.matches("/api/v1/doctors/[0-9a-fA-F-]+/avatar");
    boolean publicGeminiChat = exchange.getRequest().getMethod() == HttpMethod.POST && path.equals("/ai/public-chat");
    boolean publicSlotUpdates = path.equals("/api/v1/appointments/ws/slots");
    boolean publicReviews = exchange.getRequest().getMethod() == HttpMethod.GET && path.equals("/api/v1/appointments/reviews/public");
    if (PUBLIC.contains(path) || publicDoctorDirectory || publicDoctorAvatar || publicGeminiChat || publicSlotUpdates || publicReviews || path.startsWith("/actuator/") || path.startsWith("/ai/health"))
      return chain.filter(exchange);
    String value=exchange.getRequest().getHeaders().getFirst(HttpHeaders.AUTHORIZATION);
    if (value==null || !value.startsWith("Bearer ")) return unauthorized(exchange);
    try {
      var claims=Jwts.parser().verifyWith(Keys.hmacShaKeyFor(secret)).build()
          .parseSignedClaims(value.substring(7)).getPayload();
      var request=exchange.getRequest().mutate()
          .header("X-User-Id", claims.getSubject())
          .header("X-User-Role", String.valueOf(claims.get("role"))).build();
      return chain.filter(exchange.mutate().request(request).build());
    } catch (Exception ignored) { return unauthorized(exchange); }
  }
  private Mono<Void> unauthorized(ServerWebExchange exchange) {
    exchange.getResponse().setStatusCode(HttpStatus.UNAUTHORIZED);
    exchange.getResponse().getHeaders().setContentType(MediaType.APPLICATION_PROBLEM_JSON);
    byte[] body="{\"title\":\"Unauthorized\",\"status\":401,\"detail\":\"Access token không hợp lệ hoặc đã hết hạn.\"}".getBytes(StandardCharsets.UTF_8);
    return exchange.getResponse().writeWith(Mono.just(exchange.getResponse().bufferFactory().wrap(body)));
  }
  @Override public int getOrder(){ return -100; }
}

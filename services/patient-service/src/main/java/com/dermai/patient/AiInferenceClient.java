package com.dermai.patient;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.server.ResponseStatusException;

import java.time.Duration;
import java.util.List;

@Component
class AiInferenceClient {
  private final RestClient client;
  private final ObjectMapper mapper;

  AiInferenceClient(@Value("${services.ai-url:http://ai-service:8000}") String baseUrl, ObjectMapper mapper) {
    var requestFactory = new SimpleClientHttpRequestFactory();
    requestFactory.setConnectTimeout(Duration.ofSeconds(3));
    requestFactory.setReadTimeout(Duration.ofSeconds(45));
    this.client = RestClient.builder().baseUrl(baseUrl).requestFactory(requestFactory).build();
    this.mapper = mapper;
  }

  Prediction predict(byte[] image, String contentType, String originalFilename) {
    var resource = new ByteArrayResource(image) {
      @Override public String getFilename() {
        return safeFilename(originalFilename, contentType);
      }
    };
    var partHeaders = new HttpHeaders();
    partHeaders.setContentType(MediaType.parseMediaType(contentType));
    var multipart = new LinkedMultiValueMap<String, Object>();
    multipart.add("image", new HttpEntity<>(resource, partHeaders));
    try {
      Prediction prediction = client.post()
          .uri("/predict")
          .header("X-User-Role", "PATIENT")
          .contentType(MediaType.MULTIPART_FORM_DATA)
          .body(multipart)
          .retrieve()
          .body(Prediction.class);
      if (prediction == null) throw new ResponseStatusException(HttpStatusCode.valueOf(502), "AI service returned no result.");
      return prediction;
    } catch (RestClientResponseException error) {
      int status = error.getStatusCode().value();
      if (status == 413 || status == 415 || status == 422) {
        throw new ResponseStatusException(error.getStatusCode(), safeDetail(error), error);
      }
      throw new ResponseStatusException(HttpStatusCode.valueOf(502), "AI service is temporarily unavailable.", error);
    }
  }

  private String safeDetail(RestClientResponseException error) {
    try {
      JsonNode body = mapper.readTree(error.getResponseBodyAsString());
      String detail = body.path("detail").asText("").trim();
      return detail.isEmpty() || detail.length() > 500 ? "The image could not be analyzed." : detail;
    } catch (Exception ignored) {
      return "The image could not be analyzed.";
    }
  }

  private static String safeFilename(String value, String contentType) {
    String extension = switch (contentType) {
      case MediaType.IMAGE_PNG_VALUE -> ".png";
      case "image/webp" -> ".webp";
      default -> ".jpg";
    };
    if (value == null || value.isBlank()) return "skin-image" + extension;
    String filename = value.replace('\\', '/');
    filename = filename.substring(filename.lastIndexOf('/') + 1).replaceAll("[^\\p{L}\\p{N}._ -]", "_").trim();
    if (filename.isBlank()) return "skin-image" + extension;
    return filename.length() > 160 ? filename.substring(filename.length() - 160) : filename;
  }

  record RankedPrediction(String label, double probability) {}

  record Prediction(
      String disease,
      double confidence,
      List<RankedPrediction> top3,
      @JsonProperty("gradcam_image") String gradcamImage,
      @JsonProperty("model_version") String modelVersion,
      boolean uncertain,
      String disclaimer,
      JsonNode guidance) {}
}

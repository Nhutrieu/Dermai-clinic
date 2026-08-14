package com.dermai.appointment;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;

@Service
class SupportAiClient {
 private final HttpClient client;
 private final URI endpoint;
 private final ObjectMapper json;

 SupportAiClient(@Value("${ai-service.url:http://ai-service:8000}") String url,ObjectMapper json){
  // Uvicorn serves HTTP/1.1 in Docker; disabling the default h2c upgrade keeps
  // the POST body intact when the Java service calls the AI service directly.
  client=HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1).build();
  endpoint=URI.create(url+"/support-chat");
  this.json=json;
 }

 Decision classify(String question){
  try{
   String payload=json.writeValueAsString(new Request(question));
   var request=HttpRequest.newBuilder(endpoint)
    .header("Content-Type","application/json")
    .header("Accept","application/json")
    .header("X-User-Role","PATIENT")
    .POST(HttpRequest.BodyPublishers.ofString(payload,StandardCharsets.UTF_8))
    .build();
   var response=client.send(request,HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
   if(response.statusCode()<200||response.statusCode()>=300){
    throw new IllegalStateException("AI_SUPPORT_HTTP_"+response.statusCode()+": "+response.body());
   }
   var result=json.readValue(response.body(),Decision.class);
   if(result==null)throw new IllegalStateException("AI_SUPPORT_EMPTY_RESPONSE");
   return result;
  }catch(JsonProcessingException error){
   throw new IllegalStateException("AI_SUPPORT_REQUEST_SERIALIZATION_FAILED",error);
  }catch(InterruptedException error){
   Thread.currentThread().interrupt();
   throw new IllegalStateException("AI_SUPPORT_INTERRUPTED",error);
  }catch(IOException error){
   throw new IllegalStateException("AI_SUPPORT_IO_FAILED",error);
  }
 }

 private record Request(String question){}

 @JsonIgnoreProperties(ignoreUnknown=true)
 record Decision(
  String answer,
  String category,
  @JsonProperty("requires_handoff") boolean requiresHandoff,
  @JsonProperty("handoff_summary") String handoffSummary,
  @JsonProperty("intent_confidence") double intentConfidence,
  @JsonProperty("needs_clarification") boolean needsClarification,
  @JsonProperty("doctor_name") String doctorName,
  @JsonProperty("requested_date") String requestedDate,
  @JsonProperty("requested_time") String requestedTime
 ){}
}

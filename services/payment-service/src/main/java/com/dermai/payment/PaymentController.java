package com.dermai.payment;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

@RestController @RequestMapping("/api/v1/payments")
public class PaymentController{
 private final PaymentService service;private final InvoicePaymentService invoicePayments;private final String serviceToken;
 PaymentController(PaymentService service,InvoicePaymentService invoicePayments,@Value("${services.token:}")String serviceToken){this.service=service;this.invoicePayments=invoicePayments;this.serviceToken=serviceToken;}
 record CreatePayment(@NotNull UUID bookingId,UUID patientIdentityId,@Email @Size(max=320) String recipientEmail){}
 record CreateInvoicePayment(@NotNull UUID invoiceId,@NotNull UUID patientIdentityId,@NotNull @Positive BigDecimal amount){}
 record PatientRefundRequest(@Size(max=500) String reason){}
 @PostMapping ResponseEntity<PaymentService.PaymentResponse> create(@RequestHeader("X-User-Id")UUID actorIdentityId,@RequestHeader("X-User-Role")String role,@Valid @RequestBody CreatePayment request){UUID patientIdentityId;if("PATIENT".equals(role))patientIdentityId=actorIdentityId;else if(Set.of("RECEPTIONIST","ADMIN").contains(role)){if(request.patientIdentityId()==null)throw new PaymentConflict("PATIENT_IDENTITY_REQUIRED");patientIdentityId=request.patientIdentityId();}else throw new PaymentForbidden();return ResponseEntity.status(HttpStatus.CREATED).body(service.create(request.bookingId(),patientIdentityId,request.recipientEmail()));}
 @GetMapping("/booking/{bookingId}") PaymentService.PaymentResponse get(@PathVariable UUID bookingId,@RequestHeader("X-User-Id")UUID patientIdentityId,@RequestHeader("X-User-Role")String role){if("PATIENT".equals(role))return service.get(bookingId,patientIdentityId);if(Set.of("RECEPTIONIST","ADMIN").contains(role))return service.getForStaff(bookingId);throw new PaymentForbidden();}
 @PostMapping("/{orderCode}/cancel") Object cancel(@PathVariable long orderCode,@RequestHeader("X-User-Id")UUID patientIdentityId,@RequestHeader("X-User-Role")String role){if(!"PATIENT".equals(role))throw new PaymentForbidden();try{return service.cancel(orderCode,patientIdentityId);}catch(PaymentNotFound missing){return invoicePayments.cancel(orderCode,patientIdentityId,role);}}
 @PostMapping("/{orderCode}/reconcile") Object reconcile(@PathVariable long orderCode,@RequestHeader("X-User-Id")UUID actorIdentityId,@RequestHeader("X-User-Role")String role){try{return service.reconcile(orderCode,actorIdentityId,role);}catch(PaymentNotFound missing){return invoicePayments.reconcile(orderCode,actorIdentityId,role);}}
 @PostMapping("/invoices/{orderCode}/cancel") InvoicePaymentService.Response cancelInvoice(@PathVariable long orderCode,@RequestHeader("X-User-Id")UUID actorIdentityId,@RequestHeader("X-User-Role")String role){return invoicePayments.cancel(orderCode,actorIdentityId,role);}
 @PostMapping("/invoices/{orderCode}/reconcile") InvoicePaymentService.Response reconcileInvoice(@PathVariable long orderCode,@RequestHeader("X-User-Id")UUID actorIdentityId,@RequestHeader("X-User-Role")String role){return invoicePayments.reconcile(orderCode,actorIdentityId,role);}
 @PostMapping("/booking/{bookingId}/refunds/request") PaymentService.PaymentResponse requestRefund(@PathVariable UUID bookingId,@RequestHeader("X-User-Id")UUID patientIdentityId,@RequestHeader("X-User-Role")String role,@Valid @RequestBody(required=false)PatientRefundRequest request){if(!"PATIENT".equals(role))throw new PaymentForbidden();return service.requestPatientRefund(bookingId,patientIdentityId,request==null?null:request.reason());}
 @GetMapping("/refunds") List<PaymentService.PaymentResponse> refunds(@RequestHeader("X-User-Role")String role){requireStaff(role);return service.refunds();}
 @GetMapping("/reports") List<PaymentService.PaymentResponse> reports(@RequestHeader("X-User-Role")String role){if(!"ADMIN".equals(role))throw new PaymentForbidden();return service.all();}
 @PostMapping(value="/{paymentId}/refunds/complete",consumes=MediaType.MULTIPART_FORM_DATA_VALUE) PaymentService.PaymentResponse completeRefund(@PathVariable UUID paymentId,@RequestHeader("X-User-Id")UUID actorIdentityId,@RequestHeader("X-User-Role")String role,@RequestParam BigDecimal amount,@RequestParam String method,@RequestParam(required=false)String reference,@RequestParam(required=false)String recipientName,@RequestPart(value="evidence",required=false)MultipartFile evidence)throws Exception{if(!"RECEPTIONIST".equals(role))throw new PaymentForbidden();if(reference!=null&&reference.length()>200)throw new PaymentConflict("REFUND_REFERENCE_TOO_LONG");if(recipientName!=null&&recipientName.length()>200)throw new PaymentConflict("REFUND_RECIPIENT_TOO_LONG");PaymentService.RefundEvidence proof=null;if(evidence!=null&&!evidence.isEmpty()){if(evidence.getSize()>5L*1024*1024)throw new PaymentConflict("REFUND_EVIDENCE_TOO_LARGE");var bytes=evidence.getBytes();var contentType=imageContentType(bytes);if(contentType==null)throw new PaymentConflict("REFUND_EVIDENCE_TYPE_INVALID");proof=new PaymentService.RefundEvidence(contentType,safeFilename(evidence.getOriginalFilename()),bytes);}return service.completeRefund(paymentId,amount,method,reference,recipientName,proof,actorIdentityId,role);}
 @GetMapping("/{paymentId}/refunds/evidence") ResponseEntity<byte[]> refundEvidence(@PathVariable UUID paymentId,@RequestHeader("X-User-Role")String role){requireStaff(role);var evidence=service.refundEvidence(paymentId);var disposition=ContentDisposition.inline().filename(evidence.originalName()==null?"bien-lai-hoan-tien":evidence.originalName(),StandardCharsets.UTF_8).build();return ResponseEntity.ok().cacheControl(CacheControl.noStore()).contentType(MediaType.parseMediaType(evidence.contentType())).contentLength(evidence.data().length).header(HttpHeaders.CONTENT_DISPOSITION,disposition.toString()).body(evidence.data());}
 @PostMapping("/internal/invoices") ResponseEntity<InvoicePaymentService.Response> createInvoicePayment(@RequestHeader("X-Service-Token")String token,@Valid @RequestBody CreateInvoicePayment request){if(serviceToken.isBlank()||!MessageDigest.isEqual(serviceToken.getBytes(StandardCharsets.UTF_8),token.getBytes(StandardCharsets.UTF_8)))throw new PaymentForbidden();return ResponseEntity.status(201).body(invoicePayments.create(request.invoiceId(),request.patientIdentityId(),request.amount()));}
 @PostMapping("/payos-webhook") Map<String,Object> webhook(@RequestBody Map<String,Object> payload){if(!service.handleWebhook(payload))invoicePayments.handleWebhook(payload);return Map.of("success",true);}
 private String imageContentType(byte[] b){if(b.length>=3&&(b[0]&255)==0xff&&(b[1]&255)==0xd8&&(b[2]&255)==0xff)return MediaType.IMAGE_JPEG_VALUE;if(b.length>=8&&(b[0]&255)==0x89&&b[1]==0x50&&b[2]==0x4e&&b[3]==0x47&&b[4]==0x0d&&b[5]==0x0a&&b[6]==0x1a&&b[7]==0x0a)return MediaType.IMAGE_PNG_VALUE;if(b.length>=12&&b[0]=='R'&&b[1]=='I'&&b[2]=='F'&&b[3]=='F'&&b[8]=='W'&&b[9]=='E'&&b[10]=='B'&&b[11]=='P')return "image/webp";return null;}
 private String safeFilename(String value){var name=value==null?"bien-lai-hoan-tien":value.replace('\\','/');name=name.substring(name.lastIndexOf('/')+1).replaceAll("[^\\p{L}\\p{N}._ -]","_").trim();if(name.isBlank())name="bien-lai-hoan-tien";return name.length()>200?name.substring(name.length()-200):name;}
 private void requireStaff(String role){if(!Set.of("RECEPTIONIST","ADMIN").contains(role))throw new PaymentForbidden();}
}
@RestControllerAdvice class PaymentExceptionHandler{
 @ExceptionHandler(PaymentNotFound.class) ResponseEntity<?> notFound(){return problem(HttpStatus.NOT_FOUND,"Payment not found");}
 @ExceptionHandler(PaymentForbidden.class) ResponseEntity<?> forbidden(){return problem(HttpStatus.FORBIDDEN,"Forbidden");}
 @ExceptionHandler({InvalidWebhookException.class,WebhookMismatchException.class}) ResponseEntity<?> invalidWebhook(RuntimeException error){return problem(HttpStatus.BAD_REQUEST,error.getMessage());}
 @ExceptionHandler(PaymentConflict.class) ResponseEntity<?> conflict(PaymentConflict error){return problem(HttpStatus.CONFLICT,error.getMessage());}
 @ExceptionHandler(PaymentProviderException.class) ResponseEntity<?> provider(){return problem(HttpStatus.BAD_GATEWAY,"Dịch vụ thanh toán tạm thời không khả dụng");}
 private ResponseEntity<?> problem(HttpStatus status,String detail){return ResponseEntity.status(status).contentType(MediaType.APPLICATION_PROBLEM_JSON).body(Map.of("title",status.getReasonPhrase(),"status",status.value(),"detail",detail));}
}
class PaymentNotFound extends RuntimeException{}
class PaymentForbidden extends RuntimeException{}
class PaymentProviderException extends RuntimeException{PaymentProviderException(Throwable cause){super(cause);}}
class InvalidWebhookException extends RuntimeException{InvalidWebhookException(Throwable cause){super("INVALID_PAYMENT_SIGNATURE",cause);}}
class WebhookMismatchException extends RuntimeException{WebhookMismatchException(String message){super(message);}}
class PaymentConflict extends RuntimeException{PaymentConflict(String message){super(message);}}

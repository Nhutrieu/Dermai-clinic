package com.dermai.prescription;

import jakarta.validation.Valid;import jakarta.validation.constraints.*;import java.math.BigDecimal;import java.nio.charset.StandardCharsets;import java.time.*;import java.util.*;import org.springframework.http.*;import org.springframework.web.bind.annotation.*;import org.springframework.web.server.ResponseStatusException;

@RestController @RequestMapping("/api/v1/medicines")
class MedicineController{
 private final MedicineRepository medicines;MedicineController(MedicineRepository medicines){this.medicines=medicines;}
 record Body(@NotBlank @Size(max=60)String sku,@NotBlank @Size(max=200)String name,@NotBlank @Size(max=40)String unit,@NotNull @PositiveOrZero BigDecimal salePrice,@Min(0)int stockQuantity,boolean active){}
 @GetMapping List<Medicine> list(@RequestHeader("X-User-Role")String role){if(!Set.of("DOCTOR","RECEPTIONIST","ADMIN").contains(role))throw new ResponseStatusException(HttpStatus.FORBIDDEN);return "ADMIN".equals(role)?medicines.findAll():medicines.findByActiveTrueOrderByName();}
 @PostMapping ResponseEntity<Medicine> create(@RequestHeader("X-User-Role")String role,@Valid @RequestBody Body body){requireAdmin(role);if(medicines.findBySkuIgnoreCase(body.sku()).isPresent())throw new ResponseStatusException(HttpStatus.CONFLICT,"Mã thuốc đã tồn tại");var x=new Medicine();x.id=UUID.randomUUID();apply(x,body);return ResponseEntity.status(201).body(medicines.save(x));}
 @PutMapping("/{id}") Medicine update(@PathVariable UUID id,@RequestHeader("X-User-Role")String role,@Valid @RequestBody Body body){requireAdmin(role);var x=medicines.findById(id).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND));var duplicate=medicines.findBySkuIgnoreCase(body.sku());if(duplicate.isPresent()&&!duplicate.get().id.equals(id))throw new ResponseStatusException(HttpStatus.CONFLICT,"Mã thuốc đã tồn tại");apply(x,body);return medicines.save(x);}
 private void apply(Medicine x,Body b){x.sku=b.sku().trim().toUpperCase(Locale.ROOT);x.name=b.name().trim();x.unit=b.unit().trim();x.salePrice=b.salePrice();x.stockQuantity=b.stockQuantity();x.active=b.active();x.updatedAt=Instant.now();}private void requireAdmin(String role){if(!"ADMIN".equals(role))throw new ResponseStatusException(HttpStatus.FORBIDDEN);}
}

@RestController @RequestMapping("/api/v1/billing")
class BillingController{
 private final BillingService billing;BillingController(BillingService billing){this.billing=billing;}
 record Create(@NotNull UUID appointmentId,UUID prescriptionId,boolean buyMedicines){}
 record Cash(@NotNull @Positive BigDecimal amountReceived,@NotBlank @Size(max=120)String cashierStation){}
 record Adjustment(@NotNull BigDecimal amountDelta,@NotBlank @Size(max=500)String reason){}
 @PostMapping("/invoices") ResponseEntity<Invoice> create(@RequestHeader("X-User-Id")UUID actor,@RequestHeader("X-User-Role")String role,@Valid @RequestBody Create body){require(role,"RECEPTIONIST");return ResponseEntity.status(201).body(billing.create(body.appointmentId(),body.prescriptionId(),body.buyMedicines(),actor));}
 @GetMapping("/invoices") List<Invoice> list(@RequestHeader("X-User-Id")UUID actor,@RequestHeader("X-User-Role")String role){return billing.list(actor,role);}
 @GetMapping("/invoices/{id}") Invoice get(@PathVariable UUID id,@RequestHeader("X-User-Id")UUID actor,@RequestHeader("X-User-Role")String role){return billing.get(id,actor,role);}
 @PostMapping("/invoices/{id}/refresh-deposit") Invoice refreshDeposit(@PathVariable UUID id,@RequestHeader("X-User-Id")UUID actor,@RequestHeader("X-User-Role")String role){if(!Set.of("RECEPTIONIST","PATIENT").contains(role))throw new ResponseStatusException(HttpStatus.FORBIDDEN);return billing.refreshDeposit(id,actor,role);}
 @PostMapping("/invoices/{id}/cash") BillingService.Receipt cash(@PathVariable UUID id,@RequestHeader("X-User-Id")UUID actor,@RequestHeader("X-User-Role")String role,@Valid @RequestBody Cash body){require(role,"RECEPTIONIST");return billing.collectCash(id,body.amountReceived(),body.cashierStation(),actor);}
 @PostMapping("/invoices/{id}/online-payment") Object online(@PathVariable UUID id,@RequestHeader("X-User-Id")UUID actor,@RequestHeader("X-User-Role")String role){if(!Set.of("RECEPTIONIST","PATIENT").contains(role))throw new ResponseStatusException(HttpStatus.FORBIDDEN);return billing.createOnlinePayment(id,actor,role);}
 @PostMapping("/invoices/{id}/dispense") Invoice dispense(@PathVariable UUID id,@RequestHeader("X-User-Id")UUID actor,@RequestHeader("X-User-Role")String role){throw new ResponseStatusException(HttpStatus.CONFLICT,"Hóa đơn đã thanh toán được chuyển tự động sang quầy Dược. Chỉ dược sĩ mới được giao thuốc và trừ kho.");}
 @PostMapping("/invoices/{id}/adjustments") InvoiceAdjustment adjust(@PathVariable UUID id,@RequestHeader("X-User-Id")UUID actor,@RequestHeader("X-User-Role")String role,@Valid @RequestBody Adjustment body){require(role,"ADMIN");return billing.adjust(id,body.amountDelta(),body.reason(),actor);}
 @GetMapping("/reports/summary") BillingService.Summary summary(@RequestHeader("X-User-Role")String role,@RequestParam Instant from,@RequestParam Instant to){require(role,"ADMIN");return billing.summary(from,to);}
 @GetMapping("/reports/cash-flow") List<BillingService.DailyCashFlow> cashFlow(@RequestHeader("X-User-Role")String role,@RequestParam Instant from,@RequestParam Instant to){require(role,"ADMIN");return billing.cashFlow(from,to);}
 @GetMapping(value="/reports/export.csv",produces="text/csv;charset=UTF-8") ResponseEntity<byte[]> csv(@RequestHeader("X-User-Role")String role,@RequestHeader("X-User-Id")UUID actor){require(role,"ADMIN");var rows=billing.list(actor,role);var out=new StringBuilder("invoice_id,appointment_id,status,consultation_fee,service_fee,medicine_total,deposit_applied,remaining_amount,created_at\n");for(var i:rows)out.append(i.id).append(',').append(i.appointmentId).append(',').append(i.status).append(',').append(i.consultationFee).append(',').append(i.serviceFee).append(',').append(i.medicineTotal).append(',').append(i.depositApplied).append(',').append(i.remainingAmount).append(',').append(i.createdAt).append('\n');return ResponseEntity.ok().header(HttpHeaders.CONTENT_DISPOSITION,"attachment; filename=dermai-billing.csv").body(out.toString().getBytes(StandardCharsets.UTF_8));}
 private void require(String role,String expected){if(!expected.equals(role))throw new ResponseStatusException(HttpStatus.FORBIDDEN);}
}

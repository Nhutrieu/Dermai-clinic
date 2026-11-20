package com.dermai.appointment;

import com.fasterxml.jackson.annotation.JsonProperty;

public record SupportLookupContext(
 String intent,
 @JsonProperty("doctor_name") String doctorName,
 @JsonProperty("requested_date") String requestedDate,
 @JsonProperty("requested_time") String requestedTime
) {}

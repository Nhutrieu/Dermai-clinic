package com.dermai.appointment;

import java.time.Instant;
import java.util.UUID;

public record SupportBookingOption(UUID doctorId, String doctorName, Instant startAt, Instant endAt) {}

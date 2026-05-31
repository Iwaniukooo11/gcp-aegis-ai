package com.aegis.mockclient.javaapi.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;

public record FailureStatusResponse(
		String status,
		@JsonProperty("pricing_latency_active") boolean pricingLatencyActive,
		@JsonProperty("pricing_latency_expires_at") Instant pricingLatencyExpiresAt,
		@JsonProperty("pricing_unavailable_active") boolean pricingUnavailableActive,
		@JsonProperty("pricing_unavailable_expires_at") Instant pricingUnavailableExpiresAt) {
}

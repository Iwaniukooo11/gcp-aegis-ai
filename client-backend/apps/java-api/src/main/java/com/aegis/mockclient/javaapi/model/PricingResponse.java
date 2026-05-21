package com.aegis.mockclient.javaapi.model;

import com.fasterxml.jackson.annotation.JsonProperty;

public record PricingResponse(
		@JsonProperty("service_name") String serviceName,
		@JsonProperty("client_project_id") String clientProjectId,
		String environment,
		String scenario,
		String currency,
		@JsonProperty("subtotal_cents") int subtotalCents,
		@JsonProperty("tax_cents") int taxCents,
		@JsonProperty("total_cents") int totalCents) {
}

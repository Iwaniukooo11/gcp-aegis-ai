package com.aegis.mockclient.javaapi.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;

public record ChaosAcceptedResponse(
		String status,
		String scenario,
		@JsonProperty("expires_at") Instant expiresAt) {
}

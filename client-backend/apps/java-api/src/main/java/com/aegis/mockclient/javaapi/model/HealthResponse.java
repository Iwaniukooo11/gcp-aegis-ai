package com.aegis.mockclient.javaapi.model;

import com.fasterxml.jackson.annotation.JsonProperty;

public record HealthResponse(
		String status,
		@JsonProperty("service_name") String serviceName,
		String environment,
		@JsonProperty("client_project_id") String clientProjectId) {
}

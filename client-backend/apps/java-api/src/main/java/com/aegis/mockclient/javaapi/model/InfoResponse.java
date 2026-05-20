package com.aegis.mockclient.javaapi.model;

import com.fasterxml.jackson.annotation.JsonProperty;

public record InfoResponse(
		@JsonProperty("service_name") String serviceName,
		@JsonProperty("client_project_id") String clientProjectId,
		String environment,
		String team,
		String version) {
}

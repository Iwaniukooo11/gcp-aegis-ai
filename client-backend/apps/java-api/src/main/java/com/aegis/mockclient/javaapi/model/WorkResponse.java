package com.aegis.mockclient.javaapi.model;

import com.fasterxml.jackson.annotation.JsonProperty;

public record WorkResponse(
		@JsonProperty("service_name") String serviceName,
		@JsonProperty("client_project_id") String clientProjectId,
		String environment,
		String scenario,
		@JsonProperty("work_units") int workUnits,
		String result) {
}

package com.aegis.mockclient.javaapi.model;

import com.fasterxml.jackson.annotation.JsonProperty;

public record ErrorEnvelope(ErrorBody error) {

	public static ErrorEnvelope of(
			String code,
			String message,
			String serviceName,
			String scenario,
			String correlationId,
			String errorType) {
		return new ErrorEnvelope(new ErrorBody(code, message, serviceName, scenario, correlationId, errorType));
	}

	public static ErrorEnvelope of(
			String code,
			String message,
			String serviceName,
			String scenario,
			String correlationId) {
		return of(code, message, serviceName, scenario, correlationId, code);
	}

	public record ErrorBody(
			String code,
			String message,
			@JsonProperty("service_name") String serviceName,
			String scenario,
			@JsonProperty("correlation_id") String correlationId,
			@JsonProperty("error_type") String errorType) {
	}
}

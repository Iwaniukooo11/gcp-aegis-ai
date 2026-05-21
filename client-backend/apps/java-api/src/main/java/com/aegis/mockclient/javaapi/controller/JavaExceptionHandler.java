package com.aegis.mockclient.javaapi.controller;

import com.aegis.mockclient.javaapi.config.AegisProperties;
import com.aegis.mockclient.javaapi.exception.ChaosDisabledException;
import com.aegis.mockclient.javaapi.exception.InvalidChaosRequestException;
import com.aegis.mockclient.javaapi.exception.PricingUnavailableException;
import com.aegis.mockclient.javaapi.filter.ObservabilityAttributes;
import com.aegis.mockclient.javaapi.observability.StackTracePreview;
import com.aegis.mockclient.javaapi.model.ErrorEnvelope;
import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.MDC;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

@RestControllerAdvice
public class JavaExceptionHandler {

	private final AegisProperties properties;

	public JavaExceptionHandler(AegisProperties properties) {
		this.properties = properties;
	}

	@ExceptionHandler(NullPointerException.class)
	ResponseEntity<ErrorEnvelope> nullPointer(NullPointerException ex, HttpServletRequest request) {
		return error(
				HttpStatus.INTERNAL_SERVER_ERROR,
				"JAVA_NULL_POINTER",
				"Java null pointer chaos exception",
				"JAVA_EXCEPTION_NULL_POINTER",
				ex,
				request);
	}

	@ExceptionHandler(IllegalStateException.class)
	ResponseEntity<ErrorEnvelope> illegalState(IllegalStateException ex, HttpServletRequest request) {
		return error(
				HttpStatus.INTERNAL_SERVER_ERROR,
				"JAVA_ILLEGAL_STATE",
				"Java illegal state chaos exception",
				"JAVA_EXCEPTION_ILLEGAL_STATE",
				ex,
				request);
	}

	@ExceptionHandler(PricingUnavailableException.class)
	ResponseEntity<ErrorEnvelope> pricingUnavailable(PricingUnavailableException ex, HttpServletRequest request) {
		return error(
				HttpStatus.SERVICE_UNAVAILABLE,
				"JAVA_PRICING_UNAVAILABLE",
				"java-api pricing is temporarily unavailable",
				"JAVA_PRICING_5XX",
				ex,
				request);
	}

	@ExceptionHandler(ChaosDisabledException.class)
	ResponseEntity<ErrorEnvelope> chaosDisabled(ChaosDisabledException ex, HttpServletRequest request) {
		return error(
				HttpStatus.FORBIDDEN,
				"CHAOS_DISABLED",
				ex.getMessage(),
				"JAVA_CHAOS_DISABLED",
				ex,
				request);
	}

	@ExceptionHandler(InvalidChaosRequestException.class)
	ResponseEntity<ErrorEnvelope> invalidChaos(InvalidChaosRequestException ex, HttpServletRequest request) {
		return error(
				HttpStatus.BAD_REQUEST,
				"INVALID_CHAOS_REQUEST",
				ex.getMessage(),
				ex.scenario(),
				ex,
				request);
	}

	@ExceptionHandler({
			MethodArgumentTypeMismatchException.class,
			MissingServletRequestParameterException.class
	})
	ResponseEntity<ErrorEnvelope> invalidRequest(Exception ex, HttpServletRequest request) {
		return error(
				HttpStatus.BAD_REQUEST,
				"INVALID_REQUEST",
				"Invalid request parameters",
				"JAVA_INVALID_REQUEST",
				ex,
				request);
	}

	private ResponseEntity<ErrorEnvelope> error(
			HttpStatus status,
			String code,
			String message,
			String scenario,
			Exception ex,
			HttpServletRequest request) {
		String errorType = ex.getClass().getSimpleName();
		request.setAttribute(ObservabilityAttributes.SCENARIO, scenario);
		request.setAttribute(ObservabilityAttributes.ERROR_TYPE, errorType);
		request.setAttribute(ObservabilityAttributes.STACK_TRACE_PREVIEW, StackTracePreview.from(ex));
		return ResponseEntity.status(status).body(ErrorEnvelope.of(
				code,
				message,
				properties.serviceName(),
				scenario,
				correlationId(),
				errorType));
	}

	private String correlationId() {
		String correlationId = MDC.get("correlation_id");
		if (correlationId == null || correlationId.isBlank()) {
			return "unknown";
		}
		return correlationId;
	}

}

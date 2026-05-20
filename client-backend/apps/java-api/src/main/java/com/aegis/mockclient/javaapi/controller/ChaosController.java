package com.aegis.mockclient.javaapi.controller;

import com.aegis.mockclient.javaapi.chaos.JavaChaosState;
import com.aegis.mockclient.javaapi.config.AegisProperties;
import com.aegis.mockclient.javaapi.exception.ChaosDisabledException;
import com.aegis.mockclient.javaapi.exception.InvalidChaosRequestException;
import com.aegis.mockclient.javaapi.filter.ObservabilityAttributes;
import com.aegis.mockclient.javaapi.model.ChaosAcceptedResponse;
import jakarta.servlet.http.HttpServletRequest;
import java.time.Duration;
import java.time.Instant;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/chaos")
public class ChaosController {

	private final AegisProperties properties;
	private final JavaChaosState chaosState;

	public ChaosController(AegisProperties properties, JavaChaosState chaosState) {
		this.properties = properties;
		this.chaosState = chaosState;
	}

	@PostMapping("/exception")
	public void exception(@RequestParam String type, HttpServletRequest request) {
		requireChaosEnabled();
		if ("null_pointer".equals(type)) {
			request.setAttribute(ObservabilityAttributes.SCENARIO, "JAVA_EXCEPTION_NULL_POINTER");
			request.setAttribute(ObservabilityAttributes.ERROR_TYPE, NullPointerException.class.getSimpleName());
			request.setAttribute(ObservabilityAttributes.STACK_TRACE_PREVIEW, "intentional null pointer chaos exception");
			throw new NullPointerException("intentional null pointer chaos exception");
		}
		if ("illegal_state".equals(type)) {
			request.setAttribute(ObservabilityAttributes.SCENARIO, "JAVA_EXCEPTION_ILLEGAL_STATE");
			request.setAttribute(ObservabilityAttributes.ERROR_TYPE, IllegalStateException.class.getSimpleName());
			request.setAttribute(ObservabilityAttributes.STACK_TRACE_PREVIEW, "intentional illegal state chaos exception");
			throw new IllegalStateException("intentional illegal state chaos exception");
		}
		throw new InvalidChaosRequestException("Unsupported Java exception chaos type: " + type, "JAVA_EXCEPTION_INVALID_TYPE");
	}

	@PostMapping("/slow")
	@ResponseStatus(HttpStatus.ACCEPTED)
	public ChaosAcceptedResponse slow(@RequestParam int seconds) {
		requireChaosEnabled();
		validateSeconds(seconds, properties.chaosMaxSlowSeconds(), "JAVA_SLOW");
		Instant expiresAt = chaosState.enableSlow(Duration.ofSeconds(seconds));
		return new ChaosAcceptedResponse("accepted", "JAVA_SLOW", expiresAt);
	}

	@PostMapping("/pricing-5xx")
	@ResponseStatus(HttpStatus.ACCEPTED)
	public ChaosAcceptedResponse pricing5xx(@RequestParam int seconds) {
		requireChaosEnabled();
		validateSeconds(seconds, properties.chaosMaxPricing5xxSeconds(), "JAVA_PRICING_5XX");
		Instant expiresAt = chaosState.enablePricingFailure(Duration.ofSeconds(seconds));
		return new ChaosAcceptedResponse("accepted", "JAVA_PRICING_5XX", expiresAt);
	}

	private void requireChaosEnabled() {
		if (!properties.chaosEnabled()) {
			throw new ChaosDisabledException();
		}
	}

	private void validateSeconds(int seconds, int maxSeconds, String scenario) {
		if (seconds < 1 || seconds > maxSeconds) {
			throw new InvalidChaosRequestException(
					"seconds must be between 1 and " + maxSeconds,
					scenario);
		}
	}
}

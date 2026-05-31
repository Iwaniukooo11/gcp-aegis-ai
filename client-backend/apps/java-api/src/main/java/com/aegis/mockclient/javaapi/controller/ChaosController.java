package com.aegis.mockclient.javaapi.controller;

import com.aegis.mockclient.javaapi.chaos.JavaChaosState;
import com.aegis.mockclient.javaapi.config.AegisProperties;
import com.aegis.mockclient.javaapi.exception.ChaosDisabledException;
import com.aegis.mockclient.javaapi.exception.InvalidChaosRequestException;
import com.aegis.mockclient.javaapi.filter.ObservabilityAttributes;
import com.aegis.mockclient.javaapi.model.ChaosAcceptedResponse;
import com.aegis.mockclient.javaapi.model.FailureStatusResponse;
import jakarta.servlet.http.HttpServletRequest;
import java.time.Duration;
import java.time.Instant;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class ChaosController {

	private final AegisProperties properties;
	private final JavaChaosState chaosState;

	public ChaosController(AegisProperties properties, JavaChaosState chaosState) {
		this.properties = properties;
		this.chaosState = chaosState;
	}

	@PostMapping("/chaos/exception")
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

	@PostMapping("/chaos/slow")
	@ResponseStatus(HttpStatus.ACCEPTED)
	public ChaosAcceptedResponse slow(@RequestParam int seconds) {
		return enableSlow(seconds, "JAVA_SLOW");
	}

	@PostMapping("/admin/failures/pricing-latency")
	@ResponseStatus(HttpStatus.ACCEPTED)
	public ChaosAcceptedResponse pricingLatency(@RequestParam int seconds) {
		return enableSlow(seconds, "JAVA_PRICING_LATENCY");
	}

	@PostMapping("/chaos/pricing-5xx")
	@ResponseStatus(HttpStatus.ACCEPTED)
	public ChaosAcceptedResponse pricing5xx(@RequestParam int seconds) {
		return enablePricingFailure(seconds, "JAVA_PRICING_5XX");
	}

	@PostMapping("/admin/failures/pricing-unavailable")
	@ResponseStatus(HttpStatus.ACCEPTED)
	public ChaosAcceptedResponse pricingUnavailable(@RequestParam int seconds) {
		return enablePricingFailure(seconds, "JAVA_PRICING_5XX");
	}

	@GetMapping("/admin/failures")
	public FailureStatusResponse status() {
		return statusResponse("ok");
	}

	@PostMapping("/admin/failures/reset")
	public FailureStatusResponse reset() {
		chaosState.reset();
		return statusResponse("reset");
	}

	private ChaosAcceptedResponse enableSlow(int seconds, String scenario) {
		requireChaosEnabled();
		validateSeconds(seconds, properties.chaosMaxSlowSeconds(), scenario);
		Instant expiresAt = chaosState.enableSlow(Duration.ofSeconds(seconds));
		return new ChaosAcceptedResponse("accepted", scenario, expiresAt);
	}

	private ChaosAcceptedResponse enablePricingFailure(int seconds, String scenario) {
		requireChaosEnabled();
		validateSeconds(seconds, properties.chaosMaxPricing5xxSeconds(), scenario);
		Instant expiresAt = chaosState.enablePricingFailure(Duration.ofSeconds(seconds));
		return new ChaosAcceptedResponse("accepted", scenario, expiresAt);
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

	private FailureStatusResponse statusResponse(String status) {
		return new FailureStatusResponse(
				status,
				chaosState.isSlowActive(),
				chaosState.slowExpiresAt(),
				chaosState.isPricingFailureActive(),
				chaosState.pricingFailureExpiresAt());
	}
}

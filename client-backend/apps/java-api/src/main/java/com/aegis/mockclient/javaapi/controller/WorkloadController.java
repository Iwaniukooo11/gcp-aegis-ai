package com.aegis.mockclient.javaapi.controller;

import com.aegis.mockclient.javaapi.chaos.JavaChaosState;
import com.aegis.mockclient.javaapi.config.AegisProperties;
import com.aegis.mockclient.javaapi.exception.PricingUnavailableException;
import com.aegis.mockclient.javaapi.filter.ObservabilityAttributes;
import com.aegis.mockclient.javaapi.model.PricingResponse;
import com.aegis.mockclient.javaapi.model.WorkResponse;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api")
public class WorkloadController {

	private static final int SUBTOTAL_CENTS = 1299;
	private static final int TAX_CENTS = 104;
	private static final int WORK_UNITS = 42;

	private final AegisProperties properties;
	private final JavaChaosState chaosState;

	public WorkloadController(AegisProperties properties, JavaChaosState chaosState) {
		this.properties = properties;
		this.chaosState = chaosState;
	}

	@GetMapping("/pricing")
	public PricingResponse pricing(HttpServletRequest request) throws InterruptedException {
		request.setAttribute(ObservabilityAttributes.SCENARIO, "JAVA_PRICING");
		applySlowMode();
		if (chaosState.isPricingFailureActive()) {
			request.setAttribute(ObservabilityAttributes.SCENARIO, "JAVA_PRICING_5XX");
			request.setAttribute(ObservabilityAttributes.ERROR_TYPE, PricingUnavailableException.class.getSimpleName());
			request.setAttribute(
					ObservabilityAttributes.STACK_TRACE_PREVIEW,
					"java-api pricing returned HTTP 503 for pricing requests");
			throw new PricingUnavailableException();
		}
		return new PricingResponse(
				properties.serviceName(),
				properties.clientProjectId(),
				properties.environment(),
				"JAVA_PRICING",
				"USD",
				SUBTOTAL_CENTS,
				TAX_CENTS,
				SUBTOTAL_CENTS + TAX_CENTS);
	}

	@GetMapping("/work")
	public WorkResponse work(HttpServletRequest request) throws InterruptedException {
		request.setAttribute(ObservabilityAttributes.SCENARIO, "JAVA_WORK");
		applySlowMode();
		return new WorkResponse(
				properties.serviceName(),
				properties.clientProjectId(),
				properties.environment(),
				"JAVA_WORK",
				WORK_UNITS,
				"completed");
	}

	private void applySlowMode() throws InterruptedException {
		int slowSeconds = chaosState.activeSlowSeconds();
		if (slowSeconds > 0) {
			Thread.sleep(slowSeconds * 1_000L);
		}
	}
}

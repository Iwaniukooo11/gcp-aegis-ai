package com.aegis.mockclient.javaapi.controller;

import com.aegis.mockclient.javaapi.config.AegisProperties;
import com.aegis.mockclient.javaapi.model.HealthResponse;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/healthz")
public class HealthController {

	private final AegisProperties properties;

	public HealthController(AegisProperties properties) {
		this.properties = properties;
	}

	@GetMapping("/live")
	public HealthResponse live() {
		return new HealthResponse(
				"live",
				properties.serviceName(),
				properties.environment(),
				properties.clientProjectId());
	}

	@GetMapping("/ready")
	public HealthResponse ready() {
		return new HealthResponse(
				"ready",
				properties.serviceName(),
				properties.environment(),
				properties.clientProjectId());
	}
}

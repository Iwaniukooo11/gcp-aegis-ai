package com.aegis.mockclient.javaapi.controller;

import com.aegis.mockclient.javaapi.config.AegisProperties;
import com.aegis.mockclient.javaapi.model.InfoResponse;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api")
public class InfoController {

	private final AegisProperties properties;

	public InfoController(AegisProperties properties) {
		this.properties = properties;
	}

	@GetMapping("/info")
	public InfoResponse info() {
		return new InfoResponse(
				properties.serviceName(),
				properties.clientProjectId(),
				properties.environment(),
				properties.team(),
				properties.version());
	}
}

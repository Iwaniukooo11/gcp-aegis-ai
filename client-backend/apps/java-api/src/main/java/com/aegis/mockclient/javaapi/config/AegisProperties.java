package com.aegis.mockclient.javaapi.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "aegis")
public record AegisProperties(
		String serviceName,
		String clientProjectId,
		String environment,
		String team,
		String version,
		boolean chaosEnabled,
		boolean chaosAutoMode,
		int chaosAutoIntervalSeconds,
		int chaosAutoPricing5xxSeconds,
		int chaosMaxSlowSeconds,
		int chaosMaxPricing5xxSeconds) {
}

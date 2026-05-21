package com.aegis.mockclient.javaapi.chaos;

import com.aegis.mockclient.javaapi.config.AegisProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

@Component
@ConditionalOnProperty(prefix = "aegis", name = "chaos-auto-mode", havingValue = "true")
public class ChaosAutoScheduler {

	private static final Logger LOGGER = LoggerFactory.getLogger(ChaosAutoScheduler.class);

	private final AegisProperties properties;
	private final RestClient restClient;

	public ChaosAutoScheduler(AegisProperties properties, RestClient.Builder restClientBuilder) {
		this.properties = properties;
		this.restClient = restClientBuilder.baseUrl("http://localhost:8080").build();
	}

	@Scheduled(
			initialDelayString = "${aegis.chaos-auto-interval-seconds:120}000",
			fixedDelayString = "${aegis.chaos-auto-interval-seconds:120}000")
	public void runChaosCycle() {
		if (!properties.chaosEnabled()) {
			return;
		}

		LOGGER.info("chaos auto triggering JAVA_EXCEPTION_NULL_POINTER");
		triggerException("null_pointer");
	}

	private void triggerException(String type) {
		try {
			restClient.post().uri("/chaos/exception?type={type}", type).retrieve().toBodilessEntity();
		} catch (Exception ex) {
			LOGGER.debug("chaos auto exception trigger completed with {}", ex.getClass().getSimpleName());
		}
	}

}

package com.aegis.mockclient.javaapi.chaos;

import com.aegis.mockclient.javaapi.config.AegisProperties;
import java.time.Duration;
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
	private final JavaChaosState chaosState;
	private final RestClient restClient;

	public ChaosAutoScheduler(AegisProperties properties, JavaChaosState chaosState, RestClient.Builder restClientBuilder) {
		this.properties = properties;
		this.chaosState = chaosState;
		this.restClient = restClientBuilder.baseUrl("http://localhost:8080").build();
	}

	@Scheduled(
			initialDelayString = "${aegis.chaos-auto-interval-seconds:30}000",
			fixedDelayString = "${aegis.chaos-auto-interval-seconds:30}000")
	public void runChaosCycle() {
		if (!properties.chaosEnabled()) {
			return;
		}

		int pricingSeconds = Math.min(properties.chaosAutoPricing5xxSeconds(), properties.chaosMaxPricing5xxSeconds());
		chaosState.enablePricingFailure(Duration.ofSeconds(pricingSeconds));
		LOGGER.info("chaos auto enabled JAVA_PRICING_5XX for {} seconds", pricingSeconds);

		triggerException("null_pointer");
		triggerPricingRequest();
	}

	private void triggerException(String type) {
		try {
			restClient.post().uri("/chaos/exception?type={type}", type).retrieve().toBodilessEntity();
		} catch (Exception ex) {
			LOGGER.debug("chaos auto exception trigger completed with {}", ex.getClass().getSimpleName());
		}
	}

	private void triggerPricingRequest() {
		try {
			restClient.get().uri("/api/pricing").retrieve().toBodilessEntity();
		} catch (Exception ex) {
			LOGGER.debug("chaos auto pricing trigger completed with {}", ex.getClass().getSimpleName());
		}
	}
}

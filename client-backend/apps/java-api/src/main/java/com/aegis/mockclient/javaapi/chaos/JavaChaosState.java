package com.aegis.mockclient.javaapi.chaos;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import org.springframework.stereotype.Component;

@Component
public class JavaChaosState {

	private final Clock clock;
	private volatile Instant slowUntil = Instant.EPOCH;
	private volatile Instant pricingFailureUntil = Instant.EPOCH;
	private volatile int slowSeconds = 0;

	public JavaChaosState() {
		this(Clock.systemUTC());
	}

	JavaChaosState(Clock clock) {
		this.clock = clock;
	}

	public Instant enableSlow(Duration duration) {
		Instant expiresAt = clock.instant().plus(duration);
		slowSeconds = Math.toIntExact(duration.toSeconds());
		slowUntil = expiresAt;
		return expiresAt;
	}

	public Instant enablePricingFailure(Duration duration) {
		Instant expiresAt = clock.instant().plus(duration);
		pricingFailureUntil = expiresAt;
		return expiresAt;
	}

	public boolean isSlowActive() {
		return clock.instant().isBefore(slowUntil);
	}

	public int activeSlowSeconds() {
		if (!isSlowActive()) {
			return 0;
		}
		return slowSeconds;
	}

	public Instant slowExpiresAt() {
		if (!isSlowActive()) {
			return null;
		}
		return slowUntil;
	}

	public boolean isPricingFailureActive() {
		return clock.instant().isBefore(pricingFailureUntil);
	}

	public Instant pricingFailureExpiresAt() {
		if (!isPricingFailureActive()) {
			return null;
		}
		return pricingFailureUntil;
	}

	public void reset() {
		slowUntil = Instant.EPOCH;
		pricingFailureUntil = Instant.EPOCH;
		slowSeconds = 0;
	}
}

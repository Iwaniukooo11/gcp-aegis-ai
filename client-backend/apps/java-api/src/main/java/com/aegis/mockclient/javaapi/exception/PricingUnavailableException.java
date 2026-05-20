package com.aegis.mockclient.javaapi.exception;

public class PricingUnavailableException extends RuntimeException {

	public PricingUnavailableException() {
		super("java-api pricing is temporarily unavailable");
	}
}

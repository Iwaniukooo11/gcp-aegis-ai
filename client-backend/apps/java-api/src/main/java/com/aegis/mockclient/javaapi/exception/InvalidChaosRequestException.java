package com.aegis.mockclient.javaapi.exception;

public class InvalidChaosRequestException extends RuntimeException {

	private final String scenario;

	public InvalidChaosRequestException(String message, String scenario) {
		super(message);
		this.scenario = scenario;
	}

	public String scenario() {
		return scenario;
	}
}

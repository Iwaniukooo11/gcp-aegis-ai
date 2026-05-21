package com.aegis.mockclient.javaapi.exception;

public class ChaosDisabledException extends RuntimeException {

	public ChaosDisabledException() {
		super("Chaos endpoints are disabled");
	}
}

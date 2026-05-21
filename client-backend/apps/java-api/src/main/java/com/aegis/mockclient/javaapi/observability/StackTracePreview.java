package com.aegis.mockclient.javaapi.observability;

import java.io.PrintWriter;
import java.io.StringWriter;

public final class StackTracePreview {

	private static final int MAX_CHARS = 4096;

	private StackTracePreview() {
	}

	public static String from(Throwable throwable) {
		StringWriter writer = new StringWriter();
		throwable.printStackTrace(new PrintWriter(writer));
		String text = writer.toString().strip();
		if (text.length() <= MAX_CHARS) {
			return text;
		}
		return text.substring(0, MAX_CHARS).stripTrailing() + "\n... (truncated)";
	}
}

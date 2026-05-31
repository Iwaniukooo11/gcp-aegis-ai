package com.aegis.mockclient.javaapi.filter;

import com.aegis.mockclient.javaapi.config.AegisProperties;
import com.aegis.mockclient.javaapi.observability.StackTracePreview;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import org.slf4j.MDC;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

@Component
public class CorrelationIdFilter extends OncePerRequestFilter {

	public static final String CORRELATION_HEADER = "X-Correlation-ID";

	private final AegisProperties properties;
	private final ObjectMapper objectMapper;

	public CorrelationIdFilter(AegisProperties properties, ObjectMapper objectMapper) {
		this.properties = properties;
		this.objectMapper = objectMapper;
	}

	@Override
	protected void doFilterInternal(
			HttpServletRequest request,
			HttpServletResponse response,
			FilterChain filterChain) throws ServletException, IOException {
		String correlationId = request.getHeader(CORRELATION_HEADER);
		if (correlationId == null || correlationId.isBlank()) {
			correlationId = UUID.randomUUID().toString();
		}

		long startedAt = System.nanoTime();
		boolean logged = false;
		response.setHeader(CORRELATION_HEADER, correlationId);
		MDC.put("correlation_id", correlationId);

		try {
			filterChain.doFilter(request, response);
		} catch (ServletException | IOException | RuntimeException ex) {
			request.setAttribute(ObservabilityAttributes.ERROR_TYPE, ex.getClass().getSimpleName());
			request.setAttribute(ObservabilityAttributes.STACK_TRACE_PREVIEW, StackTracePreview.from(ex));
			logRequest(request, correlationId, 500, startedAt);
			logged = true;
			throw ex;
		} finally {
			if (!logged) {
				logRequest(request, correlationId, response.getStatus(), startedAt);
			}
			MDC.remove("correlation_id");
		}
	}

	private void logRequest(
			HttpServletRequest request,
			String correlationId,
			int statusCode,
			long startedAt) throws IOException {
		double durationMs = (System.nanoTime() - startedAt) / 1_000_000.0;
		boolean isError = statusCode >= 500;
		Map<String, Object> payload = new LinkedHashMap<>();
		payload.put("timestamp", OffsetDateTime.now(ZoneOffset.UTC).toString());
		payload.put("severity", isError ? "ERROR" : "INFO");
		Object errorTypeAttr = request.getAttribute(ObservabilityAttributes.ERROR_TYPE);
		String message = isError
				? (errorTypeAttr != null
						? errorTypeAttr + " on " + request.getMethod() + " " + request.getRequestURI()
						: "HTTP " + statusCode + " on " + request.getMethod() + " " + request.getRequestURI())
				: "Request completed";
		payload.put("message", message);
		payload.put("service_name", properties.serviceName());
		payload.put("client_project_id", properties.clientProjectId());
		payload.put("environment", properties.environment());
		payload.put("team", properties.team());
		putIfPresent(payload, "scenario", request.getAttribute(ObservabilityAttributes.SCENARIO));
		putIfPresent(payload, "error_type", request.getAttribute(ObservabilityAttributes.ERROR_TYPE));
		payload.put("incident_candidate", isError);
		payload.put("correlation_id", correlationId);
		payload.put("http_method", request.getMethod());
		payload.put("path", request.getRequestURI());
		payload.put("status_code", statusCode);
		payload.put("duration_ms", Math.round(durationMs * 100.0) / 100.0);
		putIfPresent(payload, "stack_trace_preview", request.getAttribute(ObservabilityAttributes.STACK_TRACE_PREVIEW));
		System.out.println(toJson(payload));
	}

	private void putIfPresent(Map<String, Object> payload, String key, Object value) {
		if (value != null) {
			payload.put(key, value);
		}
	}

	private String toJson(Map<String, Object> payload) throws IOException {
		try {
			return objectMapper.writeValueAsString(payload);
		} catch (JsonProcessingException ex) {
			throw new IOException("failed to serialize structured request log", ex);
		}
	}
}

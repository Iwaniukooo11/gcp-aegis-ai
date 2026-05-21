package com.aegis.mockclient.javaapi;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.aegis.mockclient.javaapi.filter.CorrelationIdFilter;
import com.aegis.mockclient.javaapi.model.ErrorEnvelope;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

@SpringBootTest
@AutoConfigureMockMvc
@ExtendWith(OutputCaptureExtension.class)
class JavaApiApplicationTests {

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private ObjectMapper objectMapper;

	@Test
	void livenessReturnsDefaultMetadata() throws Exception {
		mockMvc.perform(get("/healthz/live"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.status").value("live"))
				.andExpect(jsonPath("$.service_name").value("java-api"))
				.andExpect(jsonPath("$.environment").value("local"))
				.andExpect(jsonPath("$.client_project_id").value("aegis-client-420"))
				.andExpect(header().exists(CorrelationIdFilter.CORRELATION_HEADER));
	}

	@Test
	void readinessReturnsDefaultMetadata() throws Exception {
		mockMvc.perform(get("/healthz/ready"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.status").value("ready"))
				.andExpect(jsonPath("$.service_name").value("java-api"))
				.andExpect(jsonPath("$.environment").value("local"))
				.andExpect(jsonPath("$.client_project_id").value("aegis-client-420"));
	}

	@Test
	void infoReturnsServiceMetadata() throws Exception {
		mockMvc.perform(get("/api/info"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.service_name").value("java-api"))
				.andExpect(jsonPath("$.client_project_id").value("aegis-client-420"))
				.andExpect(jsonPath("$.environment").value("local"))
				.andExpect(jsonPath("$.team").value("demo"))
				.andExpect(jsonPath("$.version").value("0.1.0"));
	}

	@Test
	void pricingReturnsDeterministicWorkloadResponse() throws Exception {
		mockMvc.perform(get("/api/pricing"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.service_name").value("java-api"))
				.andExpect(jsonPath("$.client_project_id").value("aegis-client-420"))
				.andExpect(jsonPath("$.environment").value("local"))
				.andExpect(jsonPath("$.scenario").value("JAVA_PRICING"))
				.andExpect(jsonPath("$.currency").value("USD"))
				.andExpect(jsonPath("$.subtotal_cents").value(1299))
				.andExpect(jsonPath("$.tax_cents").value(104))
				.andExpect(jsonPath("$.total_cents").value(1403));
	}

	@Test
	void workReturnsDeterministicWorkloadResponse() throws Exception {
		mockMvc.perform(get("/api/work"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.service_name").value("java-api"))
				.andExpect(jsonPath("$.client_project_id").value("aegis-client-420"))
				.andExpect(jsonPath("$.environment").value("local"))
				.andExpect(jsonPath("$.scenario").value("JAVA_WORK"))
				.andExpect(jsonPath("$.work_units").value(42))
				.andExpect(jsonPath("$.result").value("completed"));
	}

	@Test
	void correlationIdIsPropagated() throws Exception {
		mockMvc.perform(get("/api/info").header(CorrelationIdFilter.CORRELATION_HEADER, "local-test-001"))
				.andExpect(status().isOk())
				.andExpect(header().string(CorrelationIdFilter.CORRELATION_HEADER, "local-test-001"));
	}

	@Test
	void correlationIdIsGeneratedWhenMissing() throws Exception {
		MvcResult result = mockMvc.perform(get("/api/info"))
				.andExpect(status().isOk())
				.andReturn();

		assertThat(result.getResponse().getHeader(CorrelationIdFilter.CORRELATION_HEADER)).isNotBlank();
	}

	@Test
	void errorEnvelopeSerializesToExpectedShape() throws Exception {
		ErrorEnvelope envelope = ErrorEnvelope.of(
				"DOWNSTREAM_TIMEOUT",
				"Timed out while calling java-api",
				"java-api",
				"JAVA_DOWNSTREAM_TIMEOUT",
				"local-test-001");

		JsonNode payload = objectMapper.valueToTree(envelope);

		assertThat(payload.at("/error/code").asText()).isEqualTo("DOWNSTREAM_TIMEOUT");
		assertThat(payload.at("/error/message").asText()).isEqualTo("Timed out while calling java-api");
		assertThat(payload.at("/error/service_name").asText()).isEqualTo("java-api");
		assertThat(payload.at("/error/scenario").asText()).isEqualTo("JAVA_DOWNSTREAM_TIMEOUT");
		assertThat(payload.at("/error/correlation_id").asText()).isEqualTo("local-test-001");
		assertThat(payload.at("/error/error_type").asText()).isEqualTo("DOWNSTREAM_TIMEOUT");
	}

	@Test
	void requestLogIsSingleLineJson(CapturedOutput output) throws Exception {
		mockMvc.perform(get("/api/info").header(CorrelationIdFilter.CORRELATION_HEADER, "log-test-001"))
				.andExpect(status().isOk());

		String logLine = output.getOut().lines()
				.filter(line -> line.contains("\"message\":\"Request completed\""))
				.reduce((first, second) -> second)
				.orElseThrow();
		JsonNode payload = objectMapper.readTree(logLine);

		assertThat(payload.path("severity").asText()).isEqualTo("INFO");
		assertThat(payload.path("message").asText()).isEqualTo("Request completed");
		assertThat(payload.path("service_name").asText()).isEqualTo("java-api");
		assertThat(payload.path("client_project_id").asText()).isEqualTo("aegis-client-420");
		assertThat(payload.path("environment").asText()).isEqualTo("local");
		assertThat(payload.path("team").asText()).isEqualTo("demo");
		assertThat(payload.path("correlation_id").asText()).isEqualTo("log-test-001");
		assertThat(payload.path("http_method").asText()).isEqualTo("GET");
		assertThat(payload.path("path").asText()).isEqualTo("/api/info");
		assertThat(payload.path("status_code").asInt()).isEqualTo(200);
		assertThat(payload.path("duration_ms").isNumber()).isTrue();
	}

	@Test
	void nullPointerChaosReturnsStandardError(CapturedOutput output) throws Exception {
		mockMvc.perform(post("/chaos/exception")
						.param("type", "null_pointer")
						.header(CorrelationIdFilter.CORRELATION_HEADER, "java-error-001"))
				.andExpect(status().isInternalServerError())
				.andExpect(header().string(CorrelationIdFilter.CORRELATION_HEADER, "java-error-001"))
				.andExpect(jsonPath("$.error.code").value("JAVA_NULL_POINTER"))
				.andExpect(jsonPath("$.error.service_name").value("java-api"))
				.andExpect(jsonPath("$.error.scenario").value("JAVA_EXCEPTION_NULL_POINTER"))
				.andExpect(jsonPath("$.error.correlation_id").value("java-error-001"))
				.andExpect(jsonPath("$.error.error_type").value("NullPointerException"));

		JsonNode payload = latestRequestLog(output);
		assertThat(payload.path("severity").asText()).isEqualTo("ERROR");
		assertThat(payload.path("incident_candidate").asBoolean()).isTrue();
		assertThat(payload.path("client_project_id").asText()).isEqualTo("aegis-client-420");
		assertThat(payload.path("service_name").asText()).isEqualTo("java-api");
		assertThat(payload.path("scenario").asText()).isEqualTo("JAVA_EXCEPTION_NULL_POINTER");
		assertThat(payload.path("error_type").asText()).isEqualTo("NullPointerException");
		assertThat(payload.path("correlation_id").asText()).isEqualTo("java-error-001");
		assertThat(payload.path("stack_trace_preview").asText())
				.contains("NullPointerException")
				.contains("ChaosController");
	}

	@Test
	void illegalStateChaosReturnsStandardError() throws Exception {
		mockMvc.perform(post("/chaos/exception")
						.param("type", "illegal_state")
						.header(CorrelationIdFilter.CORRELATION_HEADER, "java-error-002"))
				.andExpect(status().isInternalServerError())
				.andExpect(jsonPath("$.error.code").value("JAVA_ILLEGAL_STATE"))
				.andExpect(jsonPath("$.error.scenario").value("JAVA_EXCEPTION_ILLEGAL_STATE"))
				.andExpect(jsonPath("$.error.error_type").value("IllegalStateException"));
	}

	@Test
	void invalidChaosTypeReturnsBadRequest() throws Exception {
		mockMvc.perform(post("/chaos/exception").param("type", "unsupported"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.error.code").value("INVALID_CHAOS_REQUEST"))
				.andExpect(jsonPath("$.error.scenario").value("JAVA_EXCEPTION_INVALID_TYPE"))
				.andExpect(jsonPath("$.error.error_type").value("InvalidChaosRequestException"));
	}

	@Test
	void invalidChaosSecondsReturnBadRequest() throws Exception {
		mockMvc.perform(post("/chaos/slow").param("seconds", "0"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.error.code").value("INVALID_CHAOS_REQUEST"))
				.andExpect(jsonPath("$.error.scenario").value("JAVA_SLOW"));
	}

	@Test
	void pricing5xxModeReturnsServiceUnavailableUntilExpiry() throws Exception {
		mockMvc.perform(post("/chaos/pricing-5xx").param("seconds", "1"))
				.andExpect(status().isAccepted())
				.andExpect(jsonPath("$.status").value("accepted"))
				.andExpect(jsonPath("$.scenario").value("JAVA_PRICING_5XX"));

		mockMvc.perform(get("/api/pricing").header(CorrelationIdFilter.CORRELATION_HEADER, "pricing-5xx-001"))
				.andExpect(status().isServiceUnavailable())
				.andExpect(jsonPath("$.error.code").value("JAVA_PRICING_UNAVAILABLE"))
				.andExpect(jsonPath("$.error.scenario").value("JAVA_PRICING_5XX"))
				.andExpect(jsonPath("$.error.correlation_id").value("pricing-5xx-001"));

		Thread.sleep(1100);
		mockMvc.perform(get("/api/pricing"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.scenario").value("JAVA_PRICING"));
	}

	@Test
	void slowModeDelaysWorkloadButNotHealth() throws Exception {
		mockMvc.perform(post("/chaos/slow").param("seconds", "1"))
				.andExpect(status().isAccepted())
				.andExpect(jsonPath("$.scenario").value("JAVA_SLOW"));

		long workStartedAt = System.nanoTime();
		mockMvc.perform(get("/api/work"))
				.andExpect(status().isOk());
		double workDurationMs = (System.nanoTime() - workStartedAt) / 1_000_000.0;

		long healthStartedAt = System.nanoTime();
		mockMvc.perform(get("/healthz/ready"))
				.andExpect(status().isOk());
		double healthDurationMs = (System.nanoTime() - healthStartedAt) / 1_000_000.0;

		assertThat(workDurationMs).isGreaterThanOrEqualTo(900.0);
		assertThat(healthDurationMs).isLessThan(500.0);
	}

	private JsonNode latestRequestLog(CapturedOutput output) throws Exception {
		String logLine = output.getOut().lines()
				.filter(line -> line.contains("\"message\":\"Request completed\""))
				.reduce((first, second) -> second)
				.orElseThrow();
		return objectMapper.readTree(logLine);
	}
}

package com.aegis.mockclient.javaapi;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest(properties = {
		"aegis.service-name=java-api-test",
		"aegis.client-project-id=test-project",
		"aegis.environment=test",
		"aegis.team=platform",
		"aegis.version=9.9.9"
})
@AutoConfigureMockMvc
class JavaApiApplicationOverrideTests {

	@Autowired
	private MockMvc mockMvc;

	@Test
	void infoUsesOverriddenMetadata() throws Exception {
		mockMvc.perform(get("/api/info"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.service_name").value("java-api-test"))
				.andExpect(jsonPath("$.client_project_id").value("test-project"))
				.andExpect(jsonPath("$.environment").value("test"))
				.andExpect(jsonPath("$.team").value("platform"))
				.andExpect(jsonPath("$.version").value("9.9.9"));
	}
}

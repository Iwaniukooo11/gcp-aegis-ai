package com.aegis.mockclient.javaapi;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest(properties = "aegis.chaos-enabled=false")
@AutoConfigureMockMvc
class JavaApiChaosDisabledTests {

	@Autowired
	private MockMvc mockMvc;

	@Test
	void chaosEndpointsReturnForbiddenWhenDisabled() throws Exception {
		mockMvc.perform(post("/chaos/slow").param("seconds", "1"))
				.andExpect(status().isForbidden())
				.andExpect(jsonPath("$.error.code").value("CHAOS_DISABLED"))
				.andExpect(jsonPath("$.error.scenario").value("JAVA_CHAOS_DISABLED"));
	}
}

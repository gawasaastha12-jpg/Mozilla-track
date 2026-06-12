from any_agent import AnyAgent, AgentConfig

print("Starting...")

try:
    agent = AnyAgent.create(
        "tinyagent",
      AgentConfig(
    model_id="openai:Qwen3.5-0.8B-Q8_0.gguf",
    api_base="http://localhost:8080/v1",
    api_key="dummy",
    instructions="You are a helpful assistant."
)
    )

    print("Agent created")

    response = agent.run(
        "Explain Python in one sentence."
    )

    print("Response type:", type(response.final_output))
    print("Response:", repr(response.final_output))

except Exception as e:
    print("ERROR:")
    print(type(e).__name__)
    print(e)
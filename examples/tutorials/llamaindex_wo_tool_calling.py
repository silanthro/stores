"""
This example shows how to use stores with LlamaIndex without native tool calling.
"""

import os

from llama_index.core.llms import ChatMessage
from llama_index.llms.google_genai import GoogleGenAI

import stores


def main():
    # Load tools and set the required environment variables
    index = stores.Index(
        ["silanthro/send-gmail"],
        env_vars={
            "silanthro/send-gmail": {
                "GMAIL_ADDRESS": os.environ["GMAIL_ADDRESS"],
                "GMAIL_PASSWORD": os.environ["GMAIL_PASSWORD"],
            },
        },
    )

    # Set up the user request, system instruction, model parameters, tools, and initial messages
    user_request = "Make up a parenting poem and email it to x@gmail.com, without asking any questions"
    system_instruction = "You are a helpful assistant who can generate poems in emails. You do not have to ask for confirmations."
    model = "models/gemini-2.0-flash-001"
    messages = [
        ChatMessage(role="system", content=system_instruction),
        ChatMessage(
            role="user", content=stores.format_query(user_request, index.tools)
        ),  # Describe the tools to the model
    ]

    # Initialize the model with Gemini
    llm = GoogleGenAI(model=model)

    # Run the agent loop
    while True:
        # Get the response from the model
        response = llm.chat(messages)
        response_content = str(response).split("assistant: ", 1)[
            -1
        ]  # Get the content we want as a str

        # Check if the response contains only text and no tool calls, which indicates task completion for this example
        parsed_response = stores.llm_parse_json(response_content)
        text = parsed_response.get("text")
        tool_calls = parsed_response.get("tool_calls")

        if text and tool_calls == []:
            print(f"Assistant response: {text}")
            return  # End the agent loop

        # Otherwise, process the response, which could include both text and tool calls
        if text:
            print(f"Assistant response: {text}")
            messages.append(ChatMessage(role="assistant", content=text))

        if tool_calls:
            for tool_call in tool_calls:
                name = tool_call.get("toolname")
                args = tool_call.get("kwargs")

                # Otherwise, execute the tool call
                print(f"Executing tool call: {name}({args})")
                output = index.execute(name, args)
                print(f"Tool output: {output}")
                messages.append(ChatMessage(role="assistant", content=str(tool_call)))  # Append the assistant's tool call as context
                messages.append(
                    ChatMessage(
                        role="user",
                        content=str(output),
                    )
                )  # Append the tool call result as context


if __name__ == "__main__":
    main()

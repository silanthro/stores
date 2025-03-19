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
        response_text = str(response).split("assistant: ", 1)[
            -1
        ]  # Get the content we want as a str

        # Append the assistant's response as context
        messages.append(ChatMessage(role="assistant", content=response_text))

        # Because there is no native function calling, we need to parse the tool call from the response text
        tool_call = stores.llm_parse_json(response_text)
        print(f"Tool Call: {tool_call}")

        # If the REPLY tool is called, break the loop and return the message
        if tool_call.get("toolname") == "REPLY":
            print(f"Assistant Response: {tool_call.get('kwargs', {}).get('msg')}")
            break

        # Execute the tool
        output = index.execute(tool_call.get("toolname"), tool_call.get("kwargs"))
        messages.append(
            ChatMessage(role="user", content=f"Tool Output: {output}")
        )  # Some APIs require a tool role instead
        print(f"Tool Output: {output}")


if __name__ == "__main__":
    main()

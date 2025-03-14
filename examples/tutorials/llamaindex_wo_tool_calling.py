"""
This example shows how to use stores with LlamaIndex without native tool calling.
"""

import os

from llama_index.core.llms import ChatMessage
from llama_index.llms.gemini import Gemini

import stores


def main():
    # Example request and system prompt to demonstrate the use of tools with LlamaIndex
    request = "Make up a parenting poem and email it to alfredlua@gmail.com, without asking any questions"
    system_prompt = "You are a helpful assistant who can generate poems in emails. When necessary, you have tools at your disposal."

    # Load custom tools and set the required environment variables
    index = stores.Index(
        ["./custom_tools"],
        env_vars={
            "./custom_tools": {
                "GMAIL_ADDRESS": os.environ["GMAIL_ADDRESS"],
                "GMAIL_PASSWORD": os.environ["GMAIL_PASSWORD"],
            },    
        },
    )
    
    # Set up the initial messages for the system and from the user
    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=stores.format_query(request, index.tools)),
    ]

    # Initialize the model with Gemini
    llm = Gemini(model="gemini-2.0-flash-001")

    # Get the response from the model
    response = llm.chat(messages)
    response_text = str(response).split("assistant: ", 1)[-1] # Get the content we want as a str
    print(f"Assistant Response: {response_text}")
    messages.append(ChatMessage(role="assistant", content=response_text))

    # Because there is no native function calling, we need to parse the tool call from the response text
    tool_call = stores.llm_parse_json(response_text)
    print(f"Tool Call: {tool_call}")

    # Execute the tool
    output = index.execute(tool_call.get("toolname"), tool_call.get("kwargs"))
    print(f"Tool Output: {output}")

    # Gemini will only generate a response if the last message in messages is from the user role.
    # For other models, you can set the role of the tool output to "tool". Example:
    # messages.append({"role": "tool", "tool_call_id": tool_call.get("id"), "content": output})
    messages.append(ChatMessage(role="user", content=f"Tool Output: {output}"))

    # Get the final response from the model. The model will return a string with a REPLY tool call so 
    # we need to parse and execute it.
    final_response = llm.chat(messages)
    final_response_text = str(final_response).split("assistant: ", 1)[-1] # Get the content we want as a str
    final_response_content = index.parse_and_execute(final_response_text)
    print(f"Assistant Response: {final_response_content}")

if __name__ == "__main__":
    main()
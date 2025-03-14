"""
This example shows how to use stores with LangChain without native function calls.
"""

import os

from langchain_google_genai import ChatGoogleGenerativeAI

import stores


def main():
    # Example request and system instruction to demonstrate the use of tools with LangChain
    request = "Make up a parenting poem and email it to x@gmail.com"
    system_instruction = "You are a helpful assistant who can generate poems in emails. When necessary, you have tools at your disposal."

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

    # Set up the initial message from the user to the model. stores.format_query
    # will add the descriptions of the loaded tools to the user request.
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": stores.format_query(request, index.tools)}
    ]

    # Initialize the model with Gemini 2.0 Flash
    model = ChatGoogleGenerativeAI(model="gemini-2.0-flash-001")

    # Get the response from the model
    response = model.invoke(messages)
    print(f"Assistant Response: {response.content}")
    messages.append({"role": "assistant", "content": response.content})

    # Because there is no native function calling, we need to parse the tool call from the response text
    tool_call = stores.llm_parse_json(response.content)
    print(f"Tool Call: {tool_call}")

    # Execute the tool
    output = index.execute(tool_call.get("toolname"), tool_call.get("kwargs"))
    print(f"Tool Output: {output}")
    
    # Gemini will only generate a response if the last message in messages is from the user role.
    # For other models, you can set the role of the tool output to "tool". Example:
    # messages.append({"role": "tool", "tool_call_id": tool_call.get("id"), "content": output})
    messages.append({"role": "user", "content": f"Tool Output: {output}"})

    # Get the final response from the model. The model will return a string with a REPLY tool call so 
    # we need to parse and execute it.
    final_response = model.invoke(messages)
    final_response_text = index.parse_and_execute(final_response.content)
    print(f"Assistant Response: {final_response_text}")

if __name__ == "__main__":
    main()

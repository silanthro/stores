"""
This example shows how to use stores with OpenAI's Responses API.
"""
import json
import os

from openai import OpenAI

import stores


def main():
    # Example request and developer instruction to demonstrate the use of tools with OpenAI
    request = "Make up a parenting poem and email it to x@gmail.com"
    developer_instruction = "You are a helpful assistant who can generate poems in emails. When necessary, you have tools at your disposal."
    
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

    # Initialize the model with OpenAI
    client = OpenAI()

    # Set up the initial messages for the model and from the user
    messages = [
        {"role": "developer", "content": developer_instruction},
        {"role": "user", "content": request}
    ]

    # Get the response from the model
    response = client.responses.create(
        model="gpt-4o-mini-2024-07-18",
        input=messages,
        tools=index.format_tools("openai-responses"),
    )

    print(f"Model Response: {response.output}")
    
    # Execute the tool calls
    for tool_call in response.output:
        print(f"Tool Call: {tool_call}")
        name = tool_call.name.replace("-", ".")
        args = json.loads(tool_call.arguments)
        output = index.execute(name, args)
        messages.append(tool_call)
        messages.append({
            "type": "function_call_output", 
            "call_id": tool_call.call_id,
            "output": output})
        print(f"Tool Output: {output}")

    # Get the final response from the model
    final_response = client.responses.create(
        model="gpt-4o-mini-2024-07-18",
        input=messages,
        tools=index.format_tools("openai-responses"),
    )

    print(f"Final Model Response: {final_response.output_text}")

if __name__ == "__main__":
    main()
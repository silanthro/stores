"""
This example shows how to use stores with OpenAI's Chat Completions API.
"""
import os
from dotenv import load_dotenv

from openai import OpenAI
import json

load_dotenv()

import stores

def main():
    # Example request to demonstrate the use of tools with OpenAI
    request = "Make up a parenting poem and email it to alfredlua@gmail.com"

    # Load default and custom tools and set the required environment variables
    from stores.tools import DEFAULT_TOOLS
    index = stores.Index(
        DEFAULT_TOOLS + ["./custom_tools"],
        env_vars={
            "./custom_tools": {
                "GMAIL_ADDRESS": os.environ["GMAIL_ADDRESS"],
                "GMAIL_PASSWORD": os.environ["GMAIL_PASSWORD"],
            },    
        },
    )

    # Set up the initial message from the user to the model
    messages = [{"role": "user", "content": request}]

    # Initialize the model with OpenAI
    client = OpenAI()

    # Get the response from the model
    completion = client.chat.completions.create(
        model="gpt-4o-mini-2024-07-18",
        messages=messages,
        tools=index.format_tools("openai-chat-completions"),
    )

    print(f"Model Response: {completion.choices[0].message.content}")

    # Get the tool calls
    tool_calls = completion.choices[0].message.tool_calls
    
    # Execute the tool calls
    for tool_call in tool_calls:
        print(f"Tool Call: {tool_call}")
        name = tool_call.function.name.replace("-", ".")
        args = json.loads(tool_call.function.arguments)
        output = index.execute(name, args)
        messages.append(completion.choices[0].message)
        messages.append({
            "role": "tool", 
            "tool_call_id": tool_call.id,
            "content": output})
        print(f"Tool Output: {output}")

    # Get the final response from the model
    final_completion = client.chat.completions.create(
        model="gpt-4o-mini-2024-07-18",
        messages=messages,
        tools=index.format_tools("openai-chat-completions"),
    )

    print(f"Final Model Response: {final_completion.choices[0].message.content}")

if __name__ == "__main__":
    main()
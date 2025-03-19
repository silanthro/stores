"""
This example shows how to use stores with Google's Gemini API.
"""

import os

from google import genai
from google.genai import types

import stores


def main():
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

    # Set up the user request, system prompt, model parameters, tools, and initial messages
    user_request = "Make up a parenting poem and email it to x@gmail.com"
    system = "You are a helpful assistant who can generate poems in emails. When necessary, you have tools at your disposal. Always use the REPLY tool when you have completed the task. You do not have to ask for confirmations."
    model = "gemini-1.5-flash"
    tools = index.tools
    print(tools)

    # Initialize the model with Google Gemini
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    config = types.GenerateContentConfig(tools=tools)
    chat = client.chats.create(model=model, config=config)

    # Get the response from the model
    response = chat.send_message(user_request)
    print(f"Model Response: {response.content}")

    # # Get the tool calls
    # tool_calls = response.tool_calls

    # # Execute the tool calls
    # for tool_call in tool_calls:
    #     print(f"Tool Call: {tool_call}")
    #     name = tool_call.function.name.replace("-", ".")
    #     args = json.loads(tool_call.function.arguments)
    #     output = index.execute(name, args)
    #     messages.append(completion.choices[0].message)
    #     messages.append({
    #         "role": "tool",
    #         "tool_call_id": tool_call.id,
    #         "content": output})
    #     print(f"Tool Output: {output}")

    # # Get the final response from the model
    # final_response = chat.send(
    #     messages=messages,
    #     tools=index.format_tools("openai-chat-completions"),
    # )

    # print(f"Final Model Response: {final_response.content}")


if __name__ == "__main__":
    main()

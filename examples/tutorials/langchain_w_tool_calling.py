"""
This example shows how to use stores with LangChain with native function calls.
"""

import os

from langchain_google_genai import ChatGoogleGenerativeAI

import stores


def main():
    # Load custom tools and set the required environment variables
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
    user_request = "Make up a parenting poem and email it to x@gmail.com"
    system_instruction = "You are a helpful assistant who can generate poems in emails. You do not have to ask for confirmations."
    model = "gemini-2.0-flash-001"
    tools = index.tools
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": user_request},
    ]

    # Initialize the model with LangChain
    model = ChatGoogleGenerativeAI(model=model)
    model_with_tools = model.bind_tools(tools)

    # Run the agent loop
    while True:
        # Get the response from the model
        response = model_with_tools.invoke(messages)

        # Execute the tool calls
        tool_calls = response.tool_calls
        for tool_call in tool_calls:
            print(f"Tool Call: {tool_call}")

            # If the REPLY tool is called, break the loop and return the message
            if tool_call["name"] == "REPLY":
                print(f"Assistant Response: {tool_call['args']['msg']}")
                return

            # Otherwise, execute the tool call
            selected_tool = index.tools_dict[tool_call["name"]]
            output = selected_tool(**tool_call["args"])
            messages.append(
                {"role": "assistant", "content": str(tool_call)}
            )  # Append the assistant's tool call as context
            messages.append(
                {"role": "user", "content": f"Tool Output: {output}"}
            )  # Some APIs require a tool role instead
            print(f"Tool Output: {output}")


if __name__ == "__main__":
    main()

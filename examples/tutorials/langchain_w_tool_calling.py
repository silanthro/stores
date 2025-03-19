"""
This example shows how to use stores with LangChain with native function calls.
"""

import os

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI

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
    user_request = "Make up a parenting poem and email it to x@gmail.com"
    system_instruction = "You are a helpful assistant who can generate poems in emails. You do not have to ask for confirmations."
    model = "gemini-2.0-flash-001"
    tools = index.tools
    messages = [
        SystemMessage(content=system_instruction),
        HumanMessage(content=user_request),
    ]

    # Initialize the model with LangChain
    model = ChatGoogleGenerativeAI(model=model)
    model_with_tools = model.bind_tools(tools)

    # Run the agent loop
    while True:
        # Get the response from the model
        response = model_with_tools.invoke(messages)

        # Check if the response contains only text and no tool calls, which indicates task completion for this example
        if response.content and not response.tool_calls:
            print(f"Assistant response: {response.content}")
            return  # End the agent loop

        # Otherwise, process the response, which could include both text and tool calls
        messages.append(response)  # Append the response as context
        if response.content:
            print(f"Assistant response: {response.content}")

        if response.tool_calls:
            tool_calls = response.tool_calls
            for tool_call in tool_calls:
                name = tool_call["name"]
                args = tool_call["args"]

                # If the REPLY tool is called, break the loop and return the message
                if name == "REPLY":
                    print(f"Assistant response: {args['msg']}")
                    return

                # Otherwise, execute the tool call
                print(f"Executing tool call: {name}({args})")
                selected_tool = index.tools_dict[name]
                output = selected_tool(**args)
                print(f"Tool Output: {output}")
                messages.append(
                    ToolMessage(content=output, tool_call_id=tool_call["id"])
                )  # Append the tool call result as context


if __name__ == "__main__":
    main()

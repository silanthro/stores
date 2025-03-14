"""
This example shows how to use stores with LangChain with native function calls.
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

    # Set up the initial messages for the system and from the user
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": request},
    ]

    # Initialize the model and bind the tools to the model
    model = ChatGoogleGenerativeAI(model="gemini-2.0-flash-001")
    model_with_tools = model.bind_tools(index.tools)

    # Get the response from the model
    response = model_with_tools.invoke(messages)
    print(f"Assistant Response: {response.content}")

    # Get the tool calls from the response
    tool_calls = response.tool_calls
    print(f"Tool Calls: {tool_calls}")
    # Gemini returns an empty "content" while Gemini requires content to not be empty
    # So we fill content with a string of the tool calls to give it context
    messages.append({"role": "assistant", "content": str(tool_calls)})
    
    # Execute the tool calls
    for tool_call in tool_calls:
        print(f"Tool Call: {tool_call}")
        selected_tool = index.tools_dict[tool_call["name"]]
        tool_msg = selected_tool(**tool_call["args"])
        print(f"Tool Output: {tool_msg}")
        # Gemini will only generate a response if the last message in messages is from the user role.
        # For other models, you can set the role of the tool output to "tool". Example:
        # messages.append({"role": "tool", "tool_call_id": tool_call.get("id"), "content": tool_msg})
        messages.append({"role": "user", "content": f"Tool Output: {tool_msg}"})

    # Get the final response from the model. The model will return a REPLY tool call so we need to execute it.
    final_response = model_with_tools.invoke(messages)
    final_response_text = index.execute(final_response.tool_calls[0]["name"], final_response.tool_calls[0]["args"])
    print(f"Assistant Response: {final_response_text}")

if __name__ == "__main__":
    main()

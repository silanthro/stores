"""
This example shows how to use stores with LangChain with native function calls.
"""

import os
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

import stores

def main():
    # Example request to demonstrate the use of tools with LangChain
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

    # Set up the initial message from the user to the model.
    messages = [{"role": "user", "content": request}]

    # Initialize the model and bind the tools to the model
    model = ChatGoogleGenerativeAI(model="gemini-2.0-flash-001")
    model_with_tools = model.bind_tools(index.tools)

    # Get the response from the model
    response = model_with_tools.invoke(messages)
    print(f"Model Response: {response.content}")

    # Get the tool calls from the response
    tool_calls = response.tool_calls
    print(f"Tool Calls: {tool_calls}")
    # LangChain returns an empty "content" while Gemini requires content to not be empty
    messages.append({"role": "assistant", "content": str(tool_calls)})

    # Convert tools list to a dictionary to be used next
    tools_dict = {tool.__name__.lower(): tool for tool in index.tools}
    
    # Execute the tool calls
    for tool_call in tool_calls:
        print(f"Tool Call: {tool_call}")
        selected_tool = tools_dict[tool_call["name"].lower()]
        tool_msg = selected_tool(**tool_call["args"])
        print(f"Tool Output: {tool_msg}")
        # Gemini will only generate a response if the last message in messages is from the user role.
        # For other models, you can set the role of the tool output to "tool". Example:
        # messages.append({"role": "tool", "tool_call_id": tool_call.get("id"), "content": tool_msg})
        messages.append({"role": "user", "content": f"Tool Output: {tool_msg}"})

    # Get the final response from the model
    final_response = model_with_tools.invoke(messages)
    # TODO: Model returns REPLY tool call instead of responding directly
    print(f"Final Model Response: {final_response.content}")

if __name__ == "__main__":
    main()

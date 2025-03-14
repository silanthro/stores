"""
This example shows how to use stores with LiteLLM with native function calls.
"""

import json
import os

from litellm import completion

import stores


def main():
    # Example request and system prompt to demonstrate the use of tools with LiteLLM
    request = "Make up a parenting poem and email it to x@gmail.com, without asking any questions"
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
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": request},
    ]

    # Get the response from the model
    # LiteLLM has a function to turn functions into dict: https://docs.litellm.ai/docs/completion/function_call#litellmfunction_to_dict---convert-functions-to-dictionary-for-openai-function-calling
    # But it doesn't support type unions: https://github.com/BerriAI/litellm/issues/4249
    # So we need to use the format_tools method
    response = completion(
        model="gemini/gemini-2.0-flash-001",
        messages=messages,
        tools=index.format_tools("google-gemini"),
        num_retries=3,
        timeout=60,
    )
    print(f"Assistant Response: {response.choices[0].message.content}")

    # Get the tool calls from the response
    tool_calls = response.choices[0].message.tool_calls
    print(f"Tool Calls: {tool_calls}")
    # Gemini returns an empty "content" while Gemini requires content to not be empty
    # So we fill content with a string of the tool calls to give it context
    messages.append({"role": "assistant", "content": str(tool_calls)})
    
    # Execute the tool calls
    for tool_call in tool_calls:
        print(f"Tool Call: {tool_call}")
        name = tool_call.function.name.replace("-", ".")
        args = json.loads(tool_call.function.arguments)
        output = index.execute(name, args)
        print(f"Tool Output: {output}")
        # Gemini will only generate a response if the last message in messages is from the user role.
        # For other models, you can set the role of the tool output to "tool". Example:
        # messages.append({"role": "tool", "tool_call_id": tool_call.get("id"), "content": tool_msg})
        messages.append({"role": "user", "content": f"Tool Output: {output}"})

    # Get the final response from the model. The model will return a REPLY tool call so we need to execute it.
    final_response = completion(
        model="gemini/gemini-2.0-flash-001",
        messages=messages,
        tools=index.format_tools("google-gemini"),
        num_retries=3,
        timeout=60,
    )
    final_tool_call = final_response.choices[0].message.tool_calls[0]
    final_name = final_tool_call.function.name.replace("-", ".")
    final_args = json.loads(final_tool_call.function.arguments)
    final_response_text = index.execute(final_name, final_args)
    print(f"Assistant Response: {final_response_text}")

if __name__ == "__main__":
    main()

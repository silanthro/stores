"""
This example shows how to use stores with LiteLLM with native function calls.
"""

import json
import os

from litellm import completion

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

    # Set up the user request, system instruction, model parameters, tools, and initial messages
    user_request = "Make up a parenting poem and email it to x@gmail.com, without asking any questions"
    system_instruction = "You are a helpful assistant who can generate poems in emails. You do not have to ask for confirmations."
    model = "gemini/gemini-2.0-flash-001"
    tools = index.format_tools("google-gemini")
    print(f"Tools: {json.dumps(tools, indent=2)}")
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": user_request},
    ]

    # Run the agent loop
    while True:
        # Get the response from the model
        # LiteLLM has a function to turn functions into dict: https://docs.litellm.ai/docs/completion/function_call#litellmfunction_to_dict---convert-functions-to-dictionary-for-openai-function-calling
        # But it doesn't support type unions: https://github.com/BerriAI/litellm/issues/4249
        # So we need to use the format_tools method
        response = completion(
            model=model,
            messages=messages,
            tools=tools,
            num_retries=3,
            timeout=60,
        )

        # Execute the tool calls
        tool_calls = response.choices[0].message.tool_calls
        for tool_call in tool_calls:
            print(f"Tool Call: {tool_call}")
            name = tool_call.function.name.replace("-", ".")
            args = json.loads(tool_call.function.arguments)

            # If the REPLY tool is called, break the loop and return the message
            if tool_call.function.name == "REPLY":
                print(f"Assistant Response: {args['msg']}")
                return

            # Otherwise, execute the tool call
            output = index.execute(name, args)
            messages.append(
                {"role": "assistant", "content": str(tool_call)}
            )  # Append the assistant's tool call as context
            messages.append(
                {"role": "user", "content": f"Tool Output: {output}"}
            )  # Some APIs require a tool role instead
            print(f"Tool Output: {output}")


if __name__ == "__main__":
    main()

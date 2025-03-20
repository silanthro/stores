"""
This example shows how to use stores with LiteLLM with native function calls.
"""

import json
import os

from litellm import completion

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
    user_request = "Make up a parenting poem and email it to x@gmail.com, without asking any questions"
    system_instruction = "You are a helpful assistant who can generate poems in emails. You do not have to ask for confirmations."
    model = "gemini/gemini-2.0-flash-001"
    tools = index.format_tools("google-gemini")
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

        text = response.choices[0].message.content
        tool_calls = response.choices[0].message.tool_calls

        # Check if the response contains only text and no tool calls, which indicates task completion for this example
        if text and not tool_calls:
            print(f"Assistant response: {text}")
            return  # End the agent loop

        # Otherwise, process the response, which could include both text and tool calls
        if text:
            messages.append({"role": "assistant", "content": text})

        if tool_calls:
            for tool_call in tool_calls:
                name = tool_call.function.name.replace("-", ".")
                args = json.loads(tool_call.function.arguments)

                # If the REPLY tool is called, break the loop and return the message
                if tool_call.function.name == "REPLY":
                    print(f"Assistant response: {args['msg']}")
                    return  # End the agent loop

                # Otherwise, execute the tool call
                print(f"Executing tool call: {name}({args})")
                output = index.execute(name, args)
                print(f"Tool output: {output}")
                messages.append(
                    {"role": "assistant", "tool_calls": [tool_call]}
                )  # Append the assistant's tool call as context
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(output),
                    }
                )  # Append the tool call result as context


if __name__ == "__main__":
    main()

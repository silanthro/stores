"""
This example shows how to use stores with LiteLLM without native function calls.
"""

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
    user_request = "Make up a parenting poem and email it to x@gmail.com"
    system_instruction = "You are a helpful assistant who can generate poems in emails. You do not have to ask for confirmations."
    model = "gemini/gemini-2.0-flash-001"
    messages = [
        {"role": "system", "content": system_instruction},
        {
            "role": "user",
            "content": stores.format_query(user_request, index.tools),
        },  # Describe the tools to the model
    ]

    # Run the agent loop
    while True:
        # Get the response from the model
        response = completion(
            model=model,
            messages=messages,
            num_retries=3,
            timeout=60,
        )

        # Check if the response contains only text and no tool calls, which indicates task completion for this example
        parsed_response = stores.llm_parse_json(response.choices[0].message.content)
        text = parsed_response.get("text")
        tool_calls = parsed_response.get("tool_calls")

        if text and tool_calls == []:
            print(f"Assistant response: {text}")
            return  # End the agent loop

        # Otherwise, process the response, which could include both text and tool calls
        if text:
            print(f"Assistant response: {text}")
            messages.append({"role": "assistant", "content": text})

        if tool_calls:
            for tool_call in tool_calls:
                name = tool_call.get("toolname")
                args = tool_call.get("kwargs")

                # Otherwise, execute the tool call
                print(f"Executing tool call: {name}({args})")
                output = index.execute(name, args)
                print(f"Tool output: {output}")
                messages.append(
                    {"role": "assistant", "content": str(tool_call)}
                )  # Append the assistant's tool call as context
                messages.append(
                    {
                        "role": "user",
                        "content": f"Tool output: {output}",
                    }
                )  # Append the tool call result as context


if __name__ == "__main__":
    main()

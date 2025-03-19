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

        # Append the assistant's response as context
        messages.append(
            {"role": "assistant", "content": response.choices[0].message.content}
        )

        # Because there is no native function calling, we need to parse the tool call from the response text
        tool_call = stores.llm_parse_json(response.choices[0].message.content)
        print(f"Tool Call: {tool_call}")

        # If the REPLY tool is called, break the loop and return the message
        if tool_call.get("toolname") == "REPLY":
            print(f"Assistant Response: {tool_call.get('kwargs', {}).get('msg')}")
            break

        # Otherwise, execute the tool call
        output = index.execute(tool_call.get("toolname"), tool_call.get("kwargs"))
        messages.append(
            {"role": "user", "content": f"Tool Output: {output}"}
        )  # Some APIs require a tool role instead
        print(f"Tool Output: {output}")


if __name__ == "__main__":
    main()

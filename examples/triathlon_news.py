import os
from multiprocessing import freeze_support

from dotenv import load_dotenv
from litellm import completion

import stores

load_dotenv()

if __name__ == "__main__":
    freeze_support()
    request = "Find the latest triathlon news and send it in an email to x@gmail.com"

    # Load custom tools
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

    messages = [{"role": "user", "content": stores.format_query(request, index.tools)}]

    while True:
        response = completion(
            model="gemini/gemini-2.0-flash-001",
            messages=messages,
            num_retries=3,
            timeout=60,
        )
        response_content = response.choices[0].message.content
        messages.append(
            {
                "role": "assistant",
                "content": response_content,
            }
        )
        print(f"Assistant: {response_content}")

        toolcall = stores.llm_parse_json(response_content)

        if toolcall.get("toolname") == "REPLY":
            print(f"Task completed: {toolcall.get('kwargs', {}).get('msg')}")
            break

        output = index.execute(toolcall.get("toolname"), toolcall.get("kwargs"))
        messages.append(
            {
                "role": "user",
                "content": f"Tool Output: {output}",
            }
        )
        print(f"User: Tool output: {output}")

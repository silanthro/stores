import os

from dotenv import load_dotenv
from litellm import completion

import stores

load_dotenv()


def main():
    request = "Send the contents of test.txt to x@gmail.com"

    # Load custom tools
    index = stores.Index(
        ["./custom_tools", "greentfrapp/file-ops"],
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
        print(response_content)
        input()

        toolcall = stores.llm_parse_json(response.choices[0].message.content)

        if toolcall.get("toolname") == "local:REPLY":
            print(toolcall.get("kwargs", {}).get("msg"))
            break

        output = index.execute(toolcall.get("toolname"), toolcall.get("kwargs"))
        messages.append(
            {
                "role": "user",
                "content": f"Tool Output: {output}",
            }
        )


if __name__ == "__main__":
    main()

import os

from dotenv import load_dotenv
from litellm import completion

import stores

load_dotenv()


def main():
    request = "Send an email to x@gmail.com containing a poem"

    # Load custom tools
    index = stores.Index(
        ["./custom_tools"],
        env_vars={
            "./custom_tools": {
                "GMAIL_ADDRESS": os.environ["GMAIL_ADDRESS"],
                "GMAIL_PASSWORD": os.environ["GMAIL_PASSWORD"],
            },
        },
    )

    messages = [{"role": "user", "content": stores.format_query(request, index.tools)}]

    response = completion(
        model="gemini/gemini-2.0-flash-001",
        messages=messages,
        num_retries=3,
        timeout=60,
    )

    print(response.choices[0].message.content)

    toolcall = stores.llm_parse_json(response.choices[0].message.content)

    output = index.execute(toolcall.get("toolname"), toolcall.get("kwargs"))


if __name__ == "__main__":
    main()

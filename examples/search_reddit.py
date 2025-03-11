import os

from dotenv import load_dotenv
from litellm import completion

import stores

load_dotenv()


def main():
    request = "Find interesting posts about labubu in the singapore subreddit. Summarize the posts and provide the comment and article URLs."

    # Load custom tools
    index = stores.Index(
        ["./custom_tools"],
        env_vars={
            "./custom_tools": {
                "GEMINI_API_KEY": os.environ["GEMINI_API_KEY"],
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
        input("Enter to continue")

        toolcall = stores.llm_parse_json(response.choices[0].message.content)

        if toolcall.get("toolname") == "REPLY":
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

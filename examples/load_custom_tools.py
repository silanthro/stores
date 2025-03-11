from litellm import completion

import stores


def main():
    request = "Create a plot simulating a bearish stock market"

    # Load custom tools
    index = stores.Index(
        ["./custom_tools"],
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

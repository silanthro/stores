# stores

Repository for useful tools, APIs and functions.

Usage:

```py
import stores
from litellm import completion

request = "Send an email to x@gmail.com containing a poem"

index = stores.Index(
    ["./custom_tools"],
    env_vars={
        "./custom_tools": {
            "GMAIL_ADDRESS": "<EMAIL>",
            "GMAIL_PASSWORD": "<PASSWORD>",
        },
    },
)

messages = [{"role": "user", "content": stores.format_query(request, index.tools)}]

response = completion(
    model="gemini/gemini-2.0-flash-001",
    messages=messages,
    num_retries=3,
    timeout=60,
).choices[0].message.content

print(response)

index.parse_and_execute(response)
```

## TODO

- Support rate limit of tools and other rules to prevent LLM abuse

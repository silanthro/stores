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

response = completion(
    model="gemini/gemini-2.0-flash-001",
    messages=[{
        "role": "user",
        "content": stores.format_query(request, index.tools),
    }],
).choices[0].message.content

print(response)

index.parse_and_execute(response)
```

## tools.toml

In a repository or folder, tools are declared via a `tools.toml` file.

At the moment this file simply declares a list of tools/functions that can be accessed by the LLM.

```toml
[index]

# An optional description
description = "Lorem ipsum"

# A list of tools declared via the module and function name
tools = [
    "foo.bar",
]
```

We are considering adding useful attributes such as required environment variables and dependencies.

## TODO

- Support rate limit of tools and other rules to prevent LLM abuse

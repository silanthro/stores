# stores

Repository of Python functions and tools for LLMs

## Why we built Stores

Just as tool use is often cited as a key development in human civilization, we believe that tool use represents a major transition in AI development.

**The aim of Stores is to make it super simple to build LLM Agents that use tools.**

There are two main elements:
1. A public repository of [tools](https://stores-tools.vercel.app) that anyone can contribute to
2. This Python library that handles tool installation and formatting

For more details, check out the [documentation](https://stores-tools.vercel.app/docs).

## Design principles

- **Open-source**: Each set of tools in the Stores collection is a public git repository. In the event the Stores database is no longer operational, the library and tools will still work as long as the git repositories exist.
- **Isolation**: Tools are isolated in their own virtual environments. This makes it trivial to manage tools with conflicting dependencies and reduces unnecessary access to sensitive environment variables.
- **Framework compatibility**: In order to pass information about tools, LLM providers often require different formats that can make it cumbersome to switch between providers. Stores makes it easy to output the required formats across providers.

## Usage

```sh
pip install stores
```

Or if you are using `uv`:

```sh
uv add stores
```

Then load one of the available indexes and use it with your favorite LLM package.

```python {6, 11}
import anthropic
import stores

client = anthropic.Anthropic()

index = stores.Index(["silanthro/hackernews"])

response = client.messages.create(
    model=model,
    messages=messages,
    tools=index.format_tools("anthropic"),
)
```

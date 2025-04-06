# Examples and Tutorials

This directory contains examples and tutorials to help you get started with the `stores` package.

## Tutorials

The `tutorials` directory contains example scripts demonstrating how to use Stores with the different LLM providers and frameworks.

The example scripts are tool calling or agent workflows to generate a haiku about dreams and email it to a recipient. They leverage the LLM's ability to generate text and call tools (added via Stores) to send the email.

| API or Framework                              | File Name                      |
| --------------------------------------------- | ------------------------------ |
| OpenAI's Chat Completions API                 | `openai_chat_completions.py`   |
| OpenAI's Response API                         | `openai_responses.py`          |
| OpenAI's Agents SDK                           | `openai_agents.py`             |
| Anthropic's Claude API                        | `anthropic_api.py`             |
| Google Gemini API with automatic tool calling | `google_gemini_auto_call.py`   |
| Google Gemini API with manual tool calling    | `google_gemini_manual_call.py` |
| LangChain with tool calling                   | `langchain_w_tool_calling.py`  |
| LangGraph agent                               | `langgraph_agent.py`           |
| LiteLLM with tool calling                     | `litellm_w_tool_calling.py`    |
| LlamaIndex agent                              | `llamaindex_agent.py`          |

## How to test the tutorials

1. Install the required dependencies for the example you want to run (see Installation section below)
2. Add GMAIL_ADDRESS and GMAIL_PASSWORD to your `.env` file (see Environment Variables section below)
3. Run `python examples/tutorials/<file_name>.py`

## Installation

First, install the package with the optional dependencies you need. The package supports several LLM providers and frameworks:

```bash
# For Anthropic (Claude)
pip install -e ".[anthropic]"

# For Google (Gemini)
pip install -e ".[google]"

# For OpenAI
pip install -e ".[openai]"

# For OpenAI Agents
pip install -e ".[openai-agent]"

# For LangChain
pip install -e ".[langchain]"

# For LangGraph
pip install -e ".[langgraph]"

# For LiteLLM
pip install -e ".[litellm]"

# For LlamaIndex
pip install -e ".[llamaindex]"
```

## Environment variables

The tutorial scripts require the following environment variables:

- GMAIL_ADDRESS: The Gmail address for sending emails.
- GMAIL_PASSWORD: This is NOT your regular Gmail password, but a 16-character App Password created via https://myaccount.google.com/apppasswords (see below). Treat this like you would treat your regular password e.g. do not upload this in plaintext or share this publicly

You will also need the API keys for the respective LLM providers that you are using.

### App Passwords

In the event that the App Password is no longer required, it can be revoked without affecting your regular password.

In order to create a 16-character App Password, 2-Step Verification must be set up.

See the Gmail Help article at https://support.google.com/mail/answer/185833?hl=en for detailed instructions.

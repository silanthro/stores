"""
This example shows how to use stores with LlamaIndex with native function calls.
"""

import os

from llama_index.core.agent import AgentRunner
from llama_index.core.tools import FunctionTool
from llama_index.llms.google_genai import GoogleGenAI

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

    # Initialize the LlamaIndex agent with tools
    llm = GoogleGenAI(model="models/gemini-2.0-flash-001")
    tools = [
        FunctionTool.from_defaults(fn=tool_function) for tool_function in index.tools
    ]  # Use LlamaIndex FunctionTool
    agent = AgentRunner.from_llm(tools, llm=llm, verbose=True)

    # Get the response from the LlamaIndex agent. LlamaIndex agent will automatically execute the tool call.
    response = agent.chat(
        "Send a haiku about dreams to x@gmail.com. Don't ask questions."
    )
    print(f"Assistant response: {response}")


if __name__ == "__main__":
    main()

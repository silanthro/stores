"""
This example shows how to use stores with LlamaIndex with native function calls.
"""

import os

from llama_index.core.agent import AgentRunner
from llama_index.core.tools import FunctionTool
from llama_index.llms.gemini import Gemini

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

    # Set up the user request, model parameters, and tools
    user_request = "Make up a parenting poem in an email and send it to x@gmail.com, without asking any questions"
    model = "models/gemini-2.0-flash-001"
    tools = [
        FunctionTool.from_defaults(fn=tool_function) for tool_function in index.tools
    ]  # Convert tools to LlamaIndex FunctionTool format

    # Initialize the model with Gemini
    llm = Gemini(model=model)

    # Create LlamaIndex agent with tools
    agent = AgentRunner.from_llm(tools, llm=llm, verbose=True)

    # Run the agent. LlamaIndex agent will automatically end the loop when appropriate.
    response = agent.chat(user_request)

    # Print the final response from the agent
    print(f"Assistant response: {response}")


if __name__ == "__main__":
    main()

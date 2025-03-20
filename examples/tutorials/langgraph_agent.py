"""
This example shows how to use stores with LangChain and a LangGraph agent.
"""

import os

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent

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

    # Initialize the LangGraph agent
    agent_model = ChatGoogleGenerativeAI(model="gemini-2.0-flash-001")
    agent_executor = create_react_agent(agent_model, index.tools)

    # Get the response from the agent. The LangGraph agent will automatically execute the tool call.
    response = agent_executor.invoke(
        {
            "messages": [
                HumanMessage(
                    content="Send a haiku about dreams to x@gmail.com. Don't ask questions."
                )
            ]
        }
    )
    print(f"Assistant response: {response['messages'][-1].content}")


if __name__ == "__main__":
    main()

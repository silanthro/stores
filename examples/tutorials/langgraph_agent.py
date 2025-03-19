"""
This example shows how to use stores with LangChain and a LangGraph agent.
"""

import os

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent

import stores


def main():
    # Load custom tools and set the required environment variables
    index = stores.Index(
        ["silanthro/send-gmail"],
        env_vars={
            "silanthro/send-gmail": {
                "GMAIL_ADDRESS": os.environ["GMAIL_ADDRESS"],
                "GMAIL_PASSWORD": os.environ["GMAIL_PASSWORD"],
            },
        },
    )

    # Set up the user request, system instruction, model parameters, tools, and initial messages
    user_request = "Make up a parenting poem and email it to x@gmail.com"
    system_instruction = "You are a helpful assistant who can generate poems in emails. You do not have to ask for confirmations."
    model = "gemini-2.0-flash-001"
    messages = {
        "messages": [
            SystemMessage(content=system_instruction),
            HumanMessage(content=user_request),
        ]
    }

    # Initialize the agent with LangChain
    agent_model = ChatGoogleGenerativeAI(model=model)
    agent_executor = create_react_agent(agent_model, index.tools)

    # Get the agent to execute the request, call tools, and update messages
    response = agent_executor.invoke(messages)

    # Print the final response from the model
    print(f"Assistant Response: {response['messages'][-1].content}")


if __name__ == "__main__":
    main()

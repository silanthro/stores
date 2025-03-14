"""
This example shows how to use stores with LangChain and a LangGraph agent.
"""

import os

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent

import stores


def main():
    # Example request and system instruction to demonstrate the use of tools with LangChain
    request = "Make up a parenting poem and email it to x@gmail.com"
    system_instruction = "You are a helpful assistant who can generate poems in emails. When necessary, you have tools at your disposal."

    # Load custom tools and set the required environment variables
    index = stores.Index(
        ["./custom_tools"],
        env_vars={
            "./custom_tools": {
                "GMAIL_ADDRESS": os.environ["GMAIL_ADDRESS"],
                "GMAIL_PASSWORD": os.environ["GMAIL_PASSWORD"],
            },    
        },
    )

    # Set up the initial messages for the system and from the user
    messages = {
        "messages": [
            SystemMessage(content=system_instruction),
            HumanMessage(content=request)
        ]
    }

    # Initialize the agent with the model and tools
    model = ChatGoogleGenerativeAI(model="gemini-2.0-flash-001")
    agent_executor = create_react_agent(model, index.tools)

    # Get the agent to execute the request, call tools, and update messages
    response = agent_executor.invoke(messages)

    # Print the final response from the model
    # You can stream the messages: https://python.langchain.com/docs/tutorials/agents/#streaming-messages
    print(f"Assistant Response: {response['messages'][-1].content}")

if __name__ == "__main__":
    main()

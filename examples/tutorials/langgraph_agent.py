"""
This example shows how to use stores with LangChain and a LangGraph agent.
"""

import os
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

load_dotenv()

import stores

def main():
    # Example request to demonstrate the use of tools with LangChain
    request = "Make up a parenting poem and email it to alfredlua@gmail.com"

    # Load default and custom tools and set the required environment variables
    from stores.tools import DEFAULT_TOOLS
    index = stores.Index(
        DEFAULT_TOOLS + ["./custom_tools"],
        env_vars={
            "./custom_tools": {
                "GMAIL_ADDRESS": os.environ["GMAIL_ADDRESS"],
                "GMAIL_PASSWORD": os.environ["GMAIL_PASSWORD"],
            },    
        },
    )

    # Set up the initial message from the user to the model.
    messages = {"messages": [HumanMessage(content=request)]}

    # Initialize the agent with the model and tools
    model = ChatGoogleGenerativeAI(model="gemini-2.0-flash-001")
    agent_executor = create_react_agent(model, index.tools)

    # Get the agent to execute the request, call tools, and update messages
    response = agent_executor.invoke(messages)
    # Print the final response from the model
    # You can stream the messages: https://python.langchain.com/docs/tutorials/agents/#streaming-messages
    print(f"Model Response: {response['messages'][-1].content}")

if __name__ == "__main__":
    main()

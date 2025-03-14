"""
This example shows how to use stores with LlamaIndex with native function calls.
"""

import os

import stores


def main():
    # Example request and system prompt to demonstrate the use of tools with LlamaIndex
    request = "Make up a parenting poem and email it to x@gmail.com, without asking any questions"
    system_prompt = "You are a helpful assistant who can generate poems in emails. When necessary, you have tools at your disposal."

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
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": request},
    ]

    # Need to use their agent
    # https://docs.llamaindex.ai/en/stable/module_guides/deploying/agents/
    # https://medium.com/llamaindex-blog/data-agents-eed797d7972f
    

if __name__ == "__main__":
    main()

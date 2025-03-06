# stores

Search index for useful APIs and functions.

Usage:

Loading default tools.

```py
import stores
from litellm import completion

request = "Retrieve 10 news about AI"

index = stores.Index()
tools = index.query(request)

messages = [{
    "role": "user",
    "message": stores.format_query(request, tools)
}]
response = completion(
    model="gemini/gemini-2.0-flash-001",
    messages=messages,
    num_retries=3,
    timeout=60,
)
output = stores.execute(response)
```

Loading tools that need auth.

```py
import stores
from litellm import completion

request = "Send an email to founders@pebblely.com"

index = stores.Index()
tools = index.query(request)

messages = [{
    "role": "user",
    "message": stores.format_query(request, tools)
}]
response = completion(
    model="gemini/gemini-2.0-flash-001",
    messages=messages,
    num_retries=3,
    timeout=60,
)
output = stores.execute(response)
```


Loading local index.

```py
import stores
from litellm import completion

request = "Plot a chart of revenue across months from revenue.csv and save to chart.png"

index = stores.Index([
    data_loader_fn,
    graph_fn,
])
tools = index.query(request)

messages = [{
    "role": "user",
    "message": stores.format_query(request, tools)
}]
response = completion(
    model="gemini/gemini-2.0-flash-001",
    messages=messages,
    num_retries=3,
    timeout=60,
)
output = stores.execute(response)
```

## Notes

Key implementation decisions and questions.

1. How is the search implemented?

Do we index the tools using a vector database? Or can we do something simpler using a library similar to Algolia? Or both?

2. Where do the tools execute?

For simpler tools like file opening or calculator, we can do it locally. But what about more complex tools that require a server, such as scraping a website?

3. How to handle tool creation and support contributions?

We need to create a framework/template that allows developers to easily add their own tools and share them.

4. How does this work with conversation history?

For instance, if a tool requires extra information that has not been provided, the LLM should request for more information.

5. Can we support more complex flows beyond singular function calls?

Can we support chained calls similar to a Zapier graph, or parallel calls? If so, what happens when a chained call fails?

5. How does this fit into current workflows, such as agentic flows or deep research?

import os
import sys

# Add project root to Python path
sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END

from utils.etl_tools import ETLTools
from utils.llm_pick import pick_llm
from Models.schema import ETLAgentSchema


@tool
def extract_load_tool(
    url: str,
    output_folder: str,
    format: str
) -> str:
    """
    Extract data from an API endpoint and save it
    to the desired location.

    Args:
        url: API endpoint from which to extract data.
        output_folder: Folder where the extracted data
                      will be saved.
        format: Output format: csv, json, or parquet.

    Returns:
        Success or failure message.
    """

    etl_tools = ETLTools()

    return etl_tools.extract_load(
        url,
        output_folder,
        format
    )


@tool
def transform_load_tool(
    input_file_path: str,
    output_folder: str,
    output_format: str,
    user_question: str
) -> str:
    """
    Transform data from a file according to the
    user's question and save the transformed data.

    Args:
        input_file_path: Path to input data file.
        output_folder: Folder where transformed data
                       should be saved.
        output_format: Output format: csv, json, parquet.
        user_question: User's requested transformation.

    Returns:
        Transformation result.
    """

    etl_tools = ETLTools()

    # Get sample/context from input file
    top_3_rows = etl_tools.transform_load_context(
        input_file_path
    )

    llm = pick_llm("low")

    prompt = f"""
You are a Python Data Analyst who uses Pandas.

Your task is to generate Pandas code that performs
the ETL operation requested by the user.

IMPORTANT RULES:

1. Return ONLY executable Python/Pandas code.
2. Do NOT provide explanations.
3. Do NOT use markdown code fences.
4. Do NOT write ```python.
5. Create a Pandas DataFrame from the input file.
6. Perform the transformation requested by the user.
7. Save the transformed result to the requested output folder.
8. Use the requested output format.

Input file:
{input_file_path}

Output folder:
{output_folder}

Output format:
{output_format}

User question:
{user_question}

Sample data:
{top_3_rows}
"""

    response = llm.invoke(prompt)

    pandas_code = response.content.strip()


    if pandas_code.startswith("```python"):
        pandas_code = pandas_code[
            len("```python"):
        ]

    if pandas_code.startswith("```"):
        pandas_code = pandas_code[
            len("```"):
        ]

    if pandas_code.endswith("```"):
        pandas_code = pandas_code[
            :-len("```")
        ]

    pandas_code = pandas_code.strip()

    results = etl_tools.execute_code(
        pandas_code
    )

    return f"""
The data was transformed and saved.

Output folder:
{output_folder}

Output format:
{output_format}

Pandas code executed:

{pandas_code}

Execution result:

{results}
"""


tools = [
    extract_load_tool,
    transform_load_tool
]


# Create Groq LLM
llm = pick_llm("low")
llm_bind = llm.bind_tools(tools)


def llm_node(state: ETLAgentSchema):
    """
    LLM decides which ETL tool should be called.
    """

    messages = state["messages"]

    system_prompt = """
You are a Python Data Analyst with access to ETL tools.

You can perform two types of operations:

1. extract_load_tool
   - Extract data from an API
   - Save the data as CSV, JSON, or Parquet

2. transform_load_tool
   - Read an existing file
   - Transform/filter the data
   - Save the transformed result

Analyze the user's request and call the appropriate tool.

If the user wants to extract data from an API,
use extract_load_tool.

If the user wants to transform existing data,
use transform_load_tool.

If a tool has already successfully completed the
requested operation, provide a final response to
the user and do not call another tool.
"""

    # Put system instructions + conversation together
    prompt_messages = [
        (
            "system",
            system_prompt
        )
    ] + messages

    response = llm_bind.invoke(
        prompt_messages
    )

    return {"messages": [response]}

def tool_node(state: ETLAgentSchema):
    """
    Execute tools requested by the LLM.
    """

    tools_results = []

    tools_by_name = {
        tool.name: tool
        for tool in tools
    }

    last_message = state["messages"][-1]

    tool_calls = last_message.tool_calls

    for tool_call in tool_calls:

        tool_name = tool_call["name"]

        tool_args = tool_call["args"]

        tool = tools_by_name.get(
            tool_name
        )

        if tool is None:
            raise ValueError(
                f"Unknown tool: {tool_name}"
            )

        observation = tool.invoke(
            tool_args
        )

        tools_results.append(
            ToolMessage(
                content=str(observation),
                tool_call_id=tool_call["id"]
            )
        )

    return {"messages": tools_results}


etl_analyst_graph = StateGraph(
    ETLAgentSchema
)
# ============================================================

etl_analyst_graph.add_node(
    "llm_node",
    llm_node
)

etl_analyst_graph.add_node(
    "tool_node",
    tool_node
)

etl_analyst_graph.add_edge(
    START,
    "llm_node"
)

def is_tool_call(
    state: ETLAgentSchema
) -> str:

    last_message = state["messages"][-1]

    tool_calls = getattr(
        last_message,
        "tool_calls",
        []
    )

    if tool_calls:
        return "tool_node"

    return "end"


etl_analyst_graph.add_conditional_edges(
    "llm_node",
    is_tool_call,
    {
        "tool_node": "tool_node",
        "end": END
    }
)


etl_analyst_graph.add_edge(
    "tool_node",
    "llm_node"
)


etl_analyst = etl_analyst_graph.compile()


if __name__ == "__main__":

    try:
        from IPython.display import Image

        img = Image(
            etl_analyst
            .get_graph()
            .draw_mermaid_png()
        )

        with open(
            "etl_analyst_graph.png",
            "wb"
        ) as f:
            f.write(img.data)

        print(
            "Graph saved as "
            "etl_analyst_graph.png"
        )

    except Exception as e:
        print(
            f"Could not generate graph image: {e}"
        )

    response = etl_analyst.invoke(
        {
            "messages": [
                HumanMessage(
                    content="""
I want to extract the data from the API endpoint
'https://pokeapi.co/api/v2/pokemon'
and save it to the data/extract folder
in CSV format.
"""
                )
            ]
        }
    )


    print(
        "\n=============================="
    )

    print("FINAL RESPONSE")

    print(
        "==============================\n"
    )

    for message in response["messages"]:
        print(
            f"\n{message.__class__.__name__}:"
        )

        print(
            message.content
        )
import os
import sys

# Add project root to Python path
sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import StateGraph, START, END

from Models.schema import RouterSchema, DataAgentSchema
from agents.etl_analyst import etl_analyst
from agents.sql_analyst import sql_analyst
from utils.llm_pick import pick_llm


llm = pick_llm("low")

llm_router = llm.with_structured_output(RouterSchema)


def router_node(state: DataAgentSchema):
    """
    Decide whether the user's request should go to
    the SQL agent or ETL agent.
    """

    message = state["messages"][-1].content

    route_response = llm_router.invoke(message)

    route_response_dict = route_response.model_dump()

    route = route_response_dict["answer"].lower()

    return {"route_response": route}



def etl_node(state: DataAgentSchema):
    """
    Send the user's request to the ETL agent.
    """

    message = state["messages"][-1].content

    response = etl_analyst.invoke(
        {
            "messages": [
                HumanMessage(content=message)
            ]
        }
    )

    return {"messages": [response["messages"][-1]]}


def sql_node(state: DataAgentSchema):
    """
    Send the user's request to the SQL agent.
    """

    message = state["messages"][-1].content

    input_schema = {
        "messages": [],
        "user_question": message,
        "curated_ques": "",
        "prompt_query_context": "",
        "generated_sql_query": "",
        "is_safe": "No",
        "comments": "",
        "sql_query_execution_result": "",
        "final_answer": ""
    }

    response = sql_analyst.invoke(input_schema)

    return {"messages": [AIMessage(content=response.final_answer)]}


data_agent_graph = StateGraph(DataAgentSchema)


data_agent_graph.add_node(
    "router_node",
    router_node
)

data_agent_graph.add_node(
    "etl_node",
    etl_node
)

data_agent_graph.add_node(
    "sql_node",
    sql_node
)


data_agent_graph.add_edge(
    START,
    "router_node"
)


def route_edge(state: DataAgentSchema) -> str:

    route = state["route_response"].lower()

    if route == "sql":
        return "sql_node"

    elif route == "etl":
        return "etl_node"

    else:
        raise ValueError(
            f"Invalid route response: {route}"
        )


data_agent_graph.add_conditional_edges(
    "router_node",
    route_edge,
    {
        "sql_node": "sql_node",
        "etl_node": "etl_node"
    }
)

data_agent_graph.add_edge(
    "sql_node",
    END
)

data_agent_graph.add_edge(
    "etl_node",
    END
)



data_agent = data_agent_graph.compile()


try:
    from IPython.display import Image

    img = Image(
        data_agent.get_graph().draw_mermaid_png()
    )

    with open(
        "data_agent_graph.png",
        "wb"
    ) as f:
        f.write(img.data)

    print("Graph saved as data_agent_graph.png")

except Exception as e:
    print(f"Could not generate graph image: {e}")


if __name__ == "__main__":

    user_message = """
    I want to extract the data from the API endpoint
    'https://pokeapi.co/api/v2/pokemon'
    and save it to data/extract folder in the csv folder.
    """

    initial_state = {
        "messages": [
            HumanMessage(
                content=user_message
            )
        ],
        "route_response": ""
    }

    response = data_agent.invoke(
        initial_state
    )

    print("\n==============================")
    print("FINAL RESPONSE")
    print("==============================\n")

    print(response)
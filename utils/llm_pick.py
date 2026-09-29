from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()


def pick_llm(level: str):

    level = level.lower()

    if level == "low":
        llm = ChatGroq(
            model="openai/gpt-oss-20b",
            temperature=0
        )

    elif level == "medium":
        llm = ChatGroq(
            model="openai/gpt-oss-120b",
            temperature=0
        )

    elif level == "high":
        llm = ChatGroq(
            model="openai/gpt-oss-120b",
            temperature=0
        )

    else:
        raise ValueError(
            f"Unsupported level: {level}"
        )

    return llm


if __name__ == "__main__":
    llm_obj = pick_llm("low")

    response = llm_obj.invoke(
        "What is the capital of France?"
    )

    print(response.content)
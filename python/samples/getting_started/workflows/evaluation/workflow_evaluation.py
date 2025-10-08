# Copyright (c) Microsoft. All rights reserved.

import asyncio

from agent_framework import (
    AgentExecutorResponse,
    AgentExecutorRequest,
    AgentRunUpdateEvent,
    AgentRunResponseUpdate,
    ChatAgent,
    ChatMessage,
    Executor,
    executor,
    handler,
    Role,
    WorkflowContext,
    WorkflowBuilder,
    WorkflowOutputEvent,
)
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import AzureCliCredential

# from ._tool_definitions import (
#     calculator_tool_spec,
#     date_tool_spec,
#     google_search_tool_spec,
#     wiki_search_tool_spec,
#     current_weather_tool_spec,
#     historical_weather_tool_spec,
#     wolfram_alpha_tool_spec,
#     time_series_intraday_tool_spec,
#     time_series_daily_tool_spec,
#     ticker_search_tool_spec,
# )

from _tools import (
    run_calculator,
    get_date_information,
    google_search,
    wikipedia_search,
    get_current_weather,
    get_historical_weather,
    wolfram_alpha_query,
    get_intraday_time_series,
    get_daily_time_series,
    find_stock_ticker,
)

"""
Sample: Evaluate Agents in a workflow
"""


@executor(id="start_executor")
async def start_executor(input: str, ctx: WorkflowContext[list[ChatMessage]]) -> None:
    chat_message = ChatMessage(role="user", text=input)
    await ctx.send_message([chat_message])


class ResearchLead(Executor):
    agent: ChatAgent

    def __init__(self, chat_client: AzureOpenAIChatClient, id: str = "writer"):
        self.agent = chat_client.create_agent(
            instructions=("""
You are an excellent research leader, leverage the other researcher agents to achieve the goal.
Summerize the findings from other agents and provide a short answer.
"""
            ),
            name="research_lead",
        )
        super().__init__(id=id)

    @handler
    async def fan_in_handle(self, responses: list[AgentExecutorResponse], ctx: WorkflowContext[WorkflowOutputEvent]) -> None:
        instructions = self.agent.chat_options.instructions if self.agent.chat_options and self.agent.chat_options.instructions else ""
        user_message = responses[0].full_conversation[0]

        messages: list[ChatMessage] = []
        messages.append(ChatMessage(role=Role.SYSTEM, text=instructions))
        messages.append(ChatMessage(role=Role.USER, text=user_message.text))

        # HACK: before agent framework fixes the tool output, filter out the tool messages for the research data aggregation
        for response in responses:
            print(f"* * * AgentExecutorResponse from {response.executor_id}:")
            if response.agent_run_response is not None and response.agent_run_response.messages is not None:
                for message in response.agent_run_response.messages:
                    print(f"  {message.role}: {message.text}")
                    if message.role != Role.TOOL:
                       messages.append(message)
        messages.append(ChatMessage(role="user", text="Based on the information from other agents, please provide a comprehensive answer to the original question."))
        response = await self.agent.run(messages)
        await ctx.yield_output(response.messages[-1].text)


async def main(query: str):
    tool_restrictions = """
Only use the tools provided and only use the information from the tools to answer the question.
If the tools do not provide enough information, respond with 'no further information provided'.
"""
    response = None

    """Build and run a simple two node agent workflow: Writer then Reviewer."""
    # Create the Azure chat client. AzureCliCredential uses your current az login.
    chat_client = AzureOpenAIChatClient(credential=AzureCliCredential())

    research_lead = ResearchLead(chat_client=chat_client, id="research_lead")

    general_tools_assistant = chat_client.create_agent(
        instructions=(
            "You are an excellent research assistant."
        ),
        name="general_tools_assistant",
        tools=[
            run_calculator,
            get_date_information,
            google_search,
            wikipedia_search,
            wolfram_alpha_query,
        ]
    )

    weather_tools_assistant = chat_client.create_agent(
        instructions=(
            f"You are an expert in using weather tools to find current and historical weather data. {tool_restrictions}"
        ),
        name="weather_tools_assistant",
        tools=[
            get_current_weather,
            get_historical_weather,
        ]
    )

    financial_tools_assistant = chat_client.create_agent(
        instructions=(
            f"You are an expert in using financial tools to find stock market data and information. {tool_restrictions}"
        ),
        name="financial_tools_assistant",
        tools=[
            get_intraday_time_series,
            get_daily_time_series,
            find_stock_ticker,
        ]
    )

    workflow = WorkflowBuilder()    \
        .set_start_executor(start_executor)    \
        .add_fan_out_edges(start_executor, [general_tools_assistant, weather_tools_assistant, financial_tools_assistant]) \
        .add_fan_in_edges([general_tools_assistant, weather_tools_assistant, financial_tools_assistant], research_lead) \
        .build()

    # Stream events from the workflow. We aggregate partial token updates per executor for readable output.
    last_executor_id = None

    events = workflow.run_stream(query)
    async for event in events:
        if isinstance(event, AgentRunUpdateEvent):
            eid = event.executor_id
            if eid != last_executor_id:  # type: ignore[reportUnnecessaryComparison]
                if last_executor_id is not None:
                    print()
                print(f"{eid}:", end=" ", flush=True)
                last_executor_id = eid
            print(event.data, end="", flush=True)

            if isinstance(event.data, AgentRunResponseUpdate) and "result" in event.data.contents[0].__dict__:
                print(f"* * * AgentRunResponseUpdate: {event.data.contents[0].result}")

        elif isinstance(event, WorkflowOutputEvent):
            print("===== Final Output =====")
            print(event.data)
            response = event.data



if __name__ == "__main__":
    # query = "Compute all the prime numbers between 20 and 40 and then find the two largest prime numbers. What is the product of these two numbers, and what is the difference from the product of all the prime numbers between 1 and 20?\n\nPlease output the following information:\n\n1. The two largest primes between 20 and 40\n2. Product of the two largest primes between 20 and 40\n3. The difference between product of prime numbers between 1 and 20 and the product of the two largest primes between 20 and 40"
    # query = "Can you find Microsoft's stock price on the day before Windows XP was released and on the day of its release? Then, provide the percentage change between the two stock prices and the date difference between the two dates.\n\nOutput the following:\n1. A List with the price on the day before and on the day of the release\n2. The percentage change in price\n3. The difference in days between the dates"
    query = "what's the weather like in Seattle tomorrow?"
    asyncio.run(main(query=query))

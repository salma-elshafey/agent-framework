# Copyright (c) Microsoft. All rights reserved.

import asyncio
import os
import json

from agent_framework import (
    AgentExecutorResponse,
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
import asyncio
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import AzureCliCredential

# Additional imports for evaluation (if needed):
from azure.ai.evaluation import ToolCallAccuracyEvaluator
# from azure.ai.projects import AIProjectClient



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

from dotenv import load_dotenv
load_dotenv()


@executor(id="start_executor")
async def start_executor(input: str, ctx: WorkflowContext[list[ChatMessage]]) -> None:
    chat_message = ChatMessage(role="user", text=input)
    await ctx.send_message([chat_message])


class ResearchLead(Executor):
    agent: ChatAgent

    def __init__(self, chat_client: AzureOpenAIChatClient, id: str = "writer"):
        self.agent = chat_client.create_agent(
            instructions="You are a research leader. Summarize findings from other agents and provide a clear answer.",
            name="research_lead",
        )
        super().__init__(id=id)

    @handler
    async def fan_in_handle(self, responses: list[AgentExecutorResponse], ctx: WorkflowContext[WorkflowOutputEvent]) -> None:
        user_query = responses[0].full_conversation[0].text
        
        messages = [
            ChatMessage(role=Role.SYSTEM, text="Summarize findings from other agents."),
            ChatMessage(role=Role.USER, text=user_query)
        ]
        
        # Add agent responses
        for response in responses:
            if response.agent_run_response and response.agent_run_response.messages:
                final_message = next((msg for msg in reversed(response.agent_run_response.messages) 
                                    if msg.role == Role.ASSISTANT and msg.text), None)
                if final_message:
                    messages.append(ChatMessage(role=Role.ASSISTANT, 
                                              text=f"[{response.executor_id}]: {final_message.text}"))
        
        messages.append(ChatMessage(role=Role.USER, text="Provide a comprehensive answer."))
        final_response = await self.agent.run(messages)
        await ctx.yield_output(final_response.messages[-1].text)


async def main(query: str, expected_tool_calls: list[str]) -> None:
    tool_restrictions = """
Only use the tools provided and only use the information from the tools to answer the question.
If the tools do not provide enough information, respond with 'no further information provided'.
"""
    response = None
    
    # Store all tool calls in sequential order as they happen in the workflow
    sequential_tool_calls = []

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

    from tool_utils import extract_tool_definitions_by_agent, format_tool_calls_for_converter

    workflow = WorkflowBuilder()    \
        .set_start_executor(start_executor)    \
        .add_fan_out_edges(start_executor, [general_tools_assistant, weather_tools_assistant, financial_tools_assistant]) \
        .add_fan_in_edges([general_tools_assistant, weather_tools_assistant, financial_tools_assistant], research_lead) \
        .build()

    # Get tool definitions for reference
    all_tool_definitions = extract_tool_definitions_by_agent()

    # Stream workflow events and display all agent activities
    print(f"\nWorkflow Execution for: '{query}'")
    print("─" * 60)
    
    events = workflow.run_stream(query)
    step = 0
    current_messages = {}  # Track ongoing messages per agent
    pending_tool_calls = {}  # Track tool calls waiting for complete arguments
    accumulating_args = {}  # Accumulate arguments by call_id
    call_order = []  # Track the order of tool calls for argument assignment
    
    async for event in events:
        if isinstance(event, AgentRunUpdateEvent):
            agent = event.executor_id
            
            if isinstance(event.data, AgentRunResponseUpdate):
                # Handle tool calls and results
                if event.data.contents:
                    for content in event.data.contents:
                        content_type = type(content).__name__
                        if hasattr(content, 'name') and content.name:
                            # Initial function call - don't print yet, wait for complete args
                            call_id = getattr(content, 'call_id', None)
                            if call_id:
                                accumulating_args[call_id] = ""
                                pending_tool_calls[call_id] = {
                                    "agent": agent,
                                    "function": content.name,
                                    "call_id": call_id
                                }
                                call_order.append(call_id)
                            
                        elif content_type == "FunctionCallContent" and not (hasattr(content, 'name') and content.name):
                            # Argument chunk - accumulate
                            args_chunk = getattr(content, 'arguments', '')
                            call_id = getattr(content, 'call_id', '')
                            
                            if args_chunk:
                                # Determine target call_id based on context
                                target_call_id = None
                                
                                # First try to use the call_id if it's provided and valid
                                if call_id and call_id in accumulating_args:
                                    target_call_id = call_id
                                # If no call_id or invalid, find the most recent incomplete call for this agent
                                else:
                                    # Look for the most recent call from this agent that's still accumulating
                                    for cid in reversed(call_order):
                                        if (cid in accumulating_args and 
                                            cid in pending_tool_calls and 
                                            pending_tool_calls[cid]['agent'] == agent):
                                            target_call_id = cid
                                            break
                                
                                if target_call_id:
                                    accumulating_args[target_call_id] += args_chunk
                                    
                                    # Check if arguments are complete for this call_id
                                    complete_args = accumulating_args[target_call_id].strip()
                                    if complete_args.endswith('}'):
                                        try:
                                            import json
                                            parsed_args = json.loads(complete_args)
                                            call_info = pending_tool_calls[target_call_id]
                                            
                                            # Now print with complete arguments
                                            step += 1
                                            args_str = ", ".join([f"{k}='{v}'" if isinstance(v, str) else f"{k}={v}" 
                                                                for k, v in parsed_args.items()])
                                            print(f"{step}. [TOOL CALL] {call_info['agent']}: {call_info['function']}({args_str})")
                                            
                                            # Store complete tool call
                                            sequential_tool_calls.append({
                                                "step": step,
                                                "agent": call_info['agent'],
                                                "function": call_info['function'],
                                                "call_id": target_call_id,
                                                "args": parsed_args
                                            })
                                            
                                            # Clean up completed call
                                            del accumulating_args[target_call_id]
                                            del pending_tool_calls[target_call_id]
                                            call_order.remove(target_call_id)
                                            
                                        except json.JSONDecodeError:
                                            # Arguments still incomplete, keep accumulating
                                            pass
                        
                        elif hasattr(content, 'result') and content.call_id:
                            # Tool result
                            step += 1
                            print(f"{step}. [TOOL RESULT] {agent}: {content.result}")
                        
                        elif hasattr(content, 'text') and content.text:
                            # Accumulate text for complete messages
                            if agent not in current_messages:
                                current_messages[agent] = ""
                            current_messages[agent] += content.text
                
                # Show completed messages
                elif agent in current_messages and current_messages[agent]:
                    step += 1
                    message = current_messages[agent].strip()
                    if message:
                        print(f"{step}. [AGENT RESPONSE] {agent}: {message}")
                    current_messages[agent] = ""

        elif isinstance(event, WorkflowOutputEvent):
            step += 1
            print(f"{step}. [FINAL OUTPUT] research_lead: {event.data}")

    print("─" * 60)
    
    # Get tool calls and format for evaluation
    formatted_tool_calls = format_tool_calls_for_converter(sequential_tool_calls)
    # Start Evaluation ONLY on financial_tools_assistant agent executor tool calls
    model_config = {
        "azure_endpoint": os.environ.get("AZURE_OPENAI_ENDPOINT"),
        "api_key": os.environ.get("AZURE_OPENAI_API_KEY"),
        "azure_deployment": os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"),
    }
    evaluator = ToolCallAccuracyEvaluator(model_config=model_config)
    tool_calls_to_be_evaluated = []
    for tool_call in formatted_tool_calls:
        if tool_call['agent'] == "financial_tools_assistant":
            tool_calls_to_be_evaluated.append(tool_call)

    financial_tool_definitions = all_tool_definitions['financial_tools_assistant']

    evaluation_result = evaluator(query=query, tool_calls=tool_calls_to_be_evaluated, tool_definitions=financial_tool_definitions)
    print("[TOOL CALL ACCURACY EVALUATION RESULT]", evaluation_result)

if __name__ == "__main__":
    # query = "Compute all the prime numbers between 20 and 40 and then find the two largest prime numbers. What is the product of these two numbers, and what is the difference from the product of all the prime numbers between 1 and 20?\n\nPlease output the following information:\n\n1. The two largest primes between 20 and 40\n2. Product of the two largest primes between 20 and 40\n3. The difference between product of prime numbers between 1 and 20 and the product of the two largest primes between 20 and 40"
    # expected_tool_calls = ["calculator", "google_search", "wikipedia_search"]
    # asyncio.run(main(query=query, expected_tool_calls=expected_tool_calls))

    # query = "Can you find Microsoft's stock price on the day before Windows XP was released and on the day of its release? Then, provide the percentage change between the two stock prices and the date difference between the two dates.\n\nOutput the following:\n1. A List with the price on the day before and on the day of the release\n2. The percentage change in price\n3. The difference in days between the dates"
    # expected_tool_calls = ["financial_tools_assistant"]
    # asyncio.run(main(query=query, expected_tool_calls=expected_tool_calls))

    query = "Search the web for MSFT stock performance in the past couple of months"
    expected_tool_calls = ["get_date_information", "get_current_weather"]
    asyncio.run(main(query=query, expected_tool_calls=expected_tool_calls))

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
#from azure.ai.evaluation import ToolCallAccuracyEvaluator
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

# Tool utilities for evaluation
from tool_utils import extract_tool_definitions_by_agent, format_tool_calls_for_converter

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

async def run_workflow_with_response_tracking(query: str):
    """Run multi-agent workflow and track response IDs with complete interaction sequence."""
    tool_restrictions = """
Only use the tools provided and only use the information from the tools to answer the question.
If the tools do not provide enough information, respond with 'no further information provided'.
"""
    
    # Storage for tracking workflow execution
    interaction_sequence = []  # Complete chronological sequence of all interactions
    all_agent_response_ids = {}  # Track ALL response IDs per agent (list)
    all_agent_message_ids = {}   # Track ALL message IDs per agent (list)
    latest_agent_response_ids = {}  # Track latest response ID per agent (for compatibility)
    latest_agent_message_ids = {}   # Track latest message ID per agent (for compatibility)
    
    print(f"\nStarting Workflow: '{query}'")
    print("=" * 80)
    
    # Create Azure OpenAI chat client
    chat_client = AzureOpenAIChatClient(credential=AzureCliCredential())
    
    # Create workflow components
    research_lead = ResearchLead(chat_client=chat_client, id="research_lead")
    
    # Create specialized agents with comprehensive tool sets
    general_tools_assistant = chat_client.create_agent(
        instructions="You are an excellent research assistant with access to search, calculation, and reference tools.",
        name="general_tools_assistant",
        tools=[run_calculator, get_date_information, google_search, wikipedia_search, wolfram_alpha_query]
    )
    
    weather_tools_assistant = chat_client.create_agent(
        instructions=f"You are an expert in using weather tools. {tool_restrictions}",
        name="weather_tools_assistant",
        tools=[get_current_weather, get_historical_weather]
    )
    
    financial_tools_assistant = chat_client.create_agent(
        instructions=f"You are an expert in using financial tools. {tool_restrictions}",
        name="financial_tools_assistant",
        tools=[get_daily_time_series, find_stock_ticker, get_intraday_time_series]
    )
    
    # Build workflow
    workflow = WorkflowBuilder() \
        .set_start_executor(start_executor) \
        .add_fan_out_edges(start_executor, [general_tools_assistant, weather_tools_assistant, financial_tools_assistant]) \
        .add_fan_in_edges([general_tools_assistant, weather_tools_assistant, financial_tools_assistant], research_lead) \
        .build()
    
    # Stream workflow events and capture complete sequence
    events = workflow.run_stream(query)
    step = 0
    current_messages = {}      # Track ongoing messages per agent
    pending_tool_calls = {}    # Track tool calls waiting for complete arguments
    accumulating_args = {}     # Accumulate arguments by call_id
    call_order = []           # Track order of tool calls
    
    async for event in events:
        if isinstance(event, AgentRunUpdateEvent):
            agent = event.executor_id
                        
            # Handle both text content and structured response updates
            if isinstance(event.data, AgentRunResponseUpdate):
                # CAPTURE ALL RESPONSE IDs
                if event.data.response_id:
                    # Initialize agent lists if not exists
                    if agent not in all_agent_response_ids:
                        all_agent_response_ids[agent] = set()
                    # Add to complete list
                    all_agent_response_ids[agent].add(event.data.response_id)
                    # Update latest for compatibility
                    latest_agent_response_ids[agent] = event.data.response_id
                   # print(f"Agent '{agent}' Response ID: {event.data.response_id}")
                
                # CAPTURE ALL MESSAGE IDs  
                if event.data.message_id:
                    # Initialize agent lists if not exists
                    if agent not in all_agent_message_ids:
                        all_agent_message_ids[agent] = set()
                    # Add to complete list
                    all_agent_message_ids[agent].add(event.data.message_id)
                    # Update latest for compatibility
                    latest_agent_message_ids[agent] = event.data.message_id
                   # print(f"Agent '{agent}' Message ID: {event.data.message_id}")
                
                # Handle tool calls and results
                if event.data.contents:
                    for content in event.data.contents:
                        content_type = type(content).__name__
                        if hasattr(content, 'name') and content.name:
                            # print("CONTENT:", content)
                            # Initial function call
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
                            # Argument chunk - accumulate by agent
                            args_chunk = getattr(content, 'arguments', '')
                            call_id = getattr(content, 'call_id', '')
                            
                            if args_chunk:
                                # Find target call_id for this agent
                                target_call_id = None
                                if call_id and call_id in accumulating_args:
                                    target_call_id = call_id
                                else:
                                    # Find most recent call from this agent
                                    for cid in reversed(call_order):
                                        if (cid in accumulating_args and 
                                            cid in pending_tool_calls and 
                                            pending_tool_calls[cid]['agent'] == agent):
                                            target_call_id = cid
                                            break
                                
                                if target_call_id:
                                    accumulating_args[target_call_id] += args_chunk
                                    
                                    # Check if arguments are complete
                                    complete_args = accumulating_args[target_call_id].strip()
                                    if complete_args.endswith('}'):
                                        try:
                                            parsed_args = json.loads(complete_args)
                                            call_info = pending_tool_calls[target_call_id]
                                            
                                            # Add tool call to interaction sequence
                                            step += 1
                                            args_str = ", ".join([f"{k}='{v}'" if isinstance(v, str) else f"{k}={v}" 
                                                                for k, v in parsed_args.items()])
                                            print(f"{step}. [TOOL CALL] {call_info['agent']}: {call_info['function']}({args_str})")
                                            
                                            interaction_sequence.append({
                                                "step": step,
                                                "type": "tool_call",
                                                "agent": call_info['agent'],
                                                "function": call_info['function'],
                                                "call_id": target_call_id,
                                                "args": parsed_args,
                                                "response_id": latest_agent_response_ids.get(agent),
                                                "message_id": latest_agent_message_ids.get(agent)
                                            })
                                            
                                            # Clean up completed call
                                            del accumulating_args[target_call_id]
                                            del pending_tool_calls[target_call_id]
                                            call_order.remove(target_call_id)
                                            
                                        except json.JSONDecodeError:
                                            pass  # Keep accumulating
                        
                        elif hasattr(content, 'result') and content.call_id:
                            # Add tool result to interaction sequence
                            step += 1
                            print(f"{step}. [TOOL RESULT] {agent}: {content.result}")
                            
                            interaction_sequence.append({
                                "step": step,
                                "type": "tool_result",
                                "agent": agent,
                                "call_id": content.call_id,
                                "result": content.result,
                                "response_id": latest_agent_response_ids.get(agent),
                                "message_id": latest_agent_message_ids.get(agent)
                            })
                        
                        elif hasattr(content, 'text') and content.text:
                            # Accumulate text for complete messages
                            if agent not in current_messages:
                                current_messages[agent] = ""
                            current_messages[agent] += content.text
                
                # Check if this update marks end of message (no contents or empty contents)
                if not event.data.contents or (len(event.data.contents) == 0):
                    # Message is complete, process accumulated text
                    if agent in current_messages and current_messages[agent]:
                        step += 1
                        message = current_messages[agent].strip()
                        if message:
                            print(f"{step}. [AGENT RESPONSE] {agent}: {message}")
                            
                            interaction_sequence.append({
                                "step": step,
                                "type": "agent_response",
                                "agent": agent,
                                "message": message,
                                "response_id": latest_agent_response_ids.get(agent),
                                "message_id": latest_agent_message_ids.get(agent)
                            })
                        current_messages[agent] = ""
            
            elif isinstance(event.data, str):
                # Handle simple text updates (like in agents streaming example)
                if agent not in current_messages:
                    current_messages[agent] = ""
                current_messages[agent] += event.data

        elif isinstance(event, WorkflowOutputEvent):
            # Add final output to interaction sequence
            step += 1
            print(f"{step}. [FINAL OUTPUT] research_lead: {event.data}")
            
            interaction_sequence.append({
                "step": step,
                "type": "final_output",
                "agent": "research_lead",
                "message": event.data
            })
    
    # Process any remaining accumulated messages
    for agent, message in current_messages.items():
        if message.strip():
            step += 1
            print(f"{step}. [AGENT RESPONSE] {agent}: {message.strip()}")
            
            interaction_sequence.append({
                "step": step,
                "type": "agent_response",
                "agent": agent,
                "message": message.strip(),
                "response_id": latest_agent_response_ids.get(agent),
                "message_id": latest_agent_message_ids.get(agent)
            })

    print("=" * 80)
    
    # Extract tool calls for backwards compatibility
    sequential_tool_calls = [
        interaction for interaction in interaction_sequence 
        if interaction["type"] == "tool_call"
    ]
    
    return {
        "interaction_sequence": interaction_sequence,  # Complete chronological sequence
        "sequential_tool_calls": sequential_tool_calls,  # Just tool calls (for compatibility)
        "agent_response_ids": latest_agent_response_ids,  # Latest response ID per agent (compatibility)
        "agent_message_ids": latest_agent_message_ids,    # Latest message ID per agent (compatibility)
        "all_agent_response_ids": all_agent_response_ids,  # ALL response IDs per agent
        "all_agent_message_ids": all_agent_message_ids,    # ALL message IDs per agent
        "query": query
    }

if __name__ == "__main__":
    # Example queries for testing
    
    # query = "Compute all the prime numbers between 20 and 40 and then find the two largest prime numbers. What is the product of these two numbers, and what is the difference from the product of all the prime numbers between 1 and 20?\n\nPlease output the following information:\n\n1. The two largest primes between 20 and 40\n2. Product of the two largest primes between 20 and 40\n3. The difference between product of prime numbers between 1 and 20 and the product of the two largest primes between 20 and 40"
    
    # query = "Can you find Microsoft's stock price on the day before Windows XP was released and on the day of its release? Then, provide the percentage change between the two stock prices and the date difference between the two dates.\n\nOutput the following:\n1. A List with the price on the day before and on the day of the release\n2. The percentage change in price\n3. The difference in days between the dates"
    
    query = "Search the web for MSFT stock performance in the past couple of months"
    
    # Run the workflow with response tracking
    asyncio.run(run_workflow_with_response_tracking(query))

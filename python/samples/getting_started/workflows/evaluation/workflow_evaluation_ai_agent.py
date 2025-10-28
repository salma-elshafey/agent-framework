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
from agent_framework_azure_ai import AzureAIAgentClient
from azure.identity.aio import AzureCliCredential


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
Multi-Agent Workflow Evaluation with Response Tracking

This sample demonstrates how to:
1. Create a multi-agent workflow using AzureAIAgentClient
2. Track response IDs and message IDs for evaluation purposes
3. Capture complete interaction sequences including tool calls and results
4. Generate comprehensive summaries from multiple specialized agents

The workflow includes:
- General tools agent (search, calculation, reference)
- Weather tools agent (current and historical weather)
- Financial tools agent (stock data and analysis)
- Research lead agent (summarizes findings from all agents)
"""

from dotenv import load_dotenv
load_dotenv()


@executor(id="start_executor")
async def start_executor(input: str, ctx: WorkflowContext[list[ChatMessage]]) -> None:
    """Start executor that initiates the workflow by sending the user query to all agents.
    
    Args:
        input: The user query string
        ctx: Workflow context for sending messages
    """
    chat_message = ChatMessage(role="user", text=input)
    await ctx.send_message([chat_message])


class ResearchLead(Executor):
    """Research Lead agent that aggregates and summarizes findings from multiple specialized agents.
    
    This executor receives responses from all specialized agents (general tools, weather tools, 
    financial tools) and creates a comprehensive summary of their findings.
    """
    
    agent: ChatAgent

    def __init__(self, chat_client: AzureAIAgentClient, id: str = "research_lead"):
        """Initialize the Research Lead agent.
        
        Args:
            chat_client: The Azure AI agent client for creating the agent
            id: Unique identifier for this executor (default: "research_lead")
        """
        self.agent = chat_client.create_agent(
            instructions="You are a research leader. Summarize findings from multiple specialized agents and provide a clear, comprehensive answer to the user's query.",
            name="research_lead",
        )
        super().__init__(id=id)

    @handler
    async def fan_in_handle(self, responses: list[AgentExecutorResponse], ctx: WorkflowContext[WorkflowOutputEvent]) -> None:
        print("\n" + "="*80)
        print("RESEARCH LEAD: Analyzing findings from all agents...")
        print("="*80)
        user_query = responses[0].full_conversation[0].text
        
        # Collect all agent findings
        agent_findings = []
        
        for response in responses:
            executor_id = response.executor_id
            
            # Extract findings from agent response messages
            findings = []
            if response.agent_run_response and response.agent_run_response.messages:
                for msg in response.agent_run_response.messages:
                    if msg.role == Role.ASSISTANT and msg.text and msg.text.strip():
                        findings.append(msg.text.strip())
            
            # Combine findings for this agent
            if findings:
                combined_findings = " ".join(findings)
                agent_findings.append(f"[{executor_id}]: {combined_findings}")
        
        # Create comprehensive summary request
        summary_text = "\n".join(agent_findings) if agent_findings else "No specific findings were provided by the agents."
        
        messages = [
            ChatMessage(role=Role.SYSTEM, text="You are a research leader. Summarize findings from multiple specialized agents and provide a clear, comprehensive answer to the user's query."),
            ChatMessage(role=Role.USER, text=f"Original query: {user_query}\n\nFindings from specialized agents:\n{summary_text}\n\nPlease provide a comprehensive answer based on these findings.")
        ]
        
        try:
            final_response = await self.agent.run(messages)
            
            if final_response.messages and final_response.messages[-1].text:
                output_text = final_response.messages[-1].text
            else:
                output_text = f"Based on the available findings, here's what I found regarding '{user_query}': {summary_text}"
            
            await ctx.yield_output(output_text)
            
        except Exception as e:
            print(f"Error in research lead: {e}")
            # Use the fallback - this is what's currently being triggered
            fallback_output = f"Based on the available findings, here's what I found regarding '{user_query}': {summary_text}"
            await ctx.yield_output(fallback_output)

async def run_workflow_with_response_tracking(query: str) -> dict:
    """Run multi-agent workflow and track response IDs with complete interaction sequence.
    
    This function creates a workflow with multiple specialized agents, executes it with the given query,
    and tracks all interactions for evaluation purposes.
    
    Args:
        query (str): The user query to process through the multi-agent workflow
        
    Returns:
        dict: A dictionary containing:
            - interaction_sequence: Complete chronological sequence of all interactions
            - agent_response_ids: Latest response ID per agent
            - agent_message_ids: Latest message ID per agent  
            - all_agent_response_ids: All response IDs per agent
            - all_agent_message_ids: All message IDs per agent
            - query: The original query
    
    Note:
        This version uses AzureAIAgentClient which provides complete responses (no streaming).
    """
    tool_restrictions = """
Only use the tools provided and only use the information from the tools to answer the question.
If the tools do not provide enough information, respond with 'no further information provided'.
"""
    
    # Storage for tracking workflow execution
    interaction_sequence = []  # Complete chronological sequence of all interactions
    all_agent_response_ids = {}  # Track ALL response IDs per agent
    all_agent_message_ids = {}   # Track ALL message IDs per agent
    latest_agent_response_ids = {}  # Track latest response ID per agent
    latest_agent_message_ids = {}   # Track latest message ID per agent
    
    print(f"\nStarting Workflow: '{query}'")
    print("=" * 80)
    
    # Create Azure AI Foundry chat client with proper async context management
    async with AzureAIAgentClient(async_credential=AzureCliCredential()) as chat_client:
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
        
        # Run workflow and capture complete sequence (no streaming with AzureAIAgentClient)
        events = workflow.run_stream(query)
        step = 0
        current_messages = {}      # Track ongoing messages per agent
        
        # Track if we've seen the research lead start processing
        research_lead_processing = False
        
        async for event in events:
            
            if isinstance(event, WorkflowOutputEvent):
                step += 1
                print(f"\n" + "="*80)
                print("RESEARCH LEAD FINAL SUMMARY:")
                print("="*80)
                print(f"{event.data}")
                print("="*80)
                
                interaction_sequence.append({
                    "step": step,
                    "type": "final_output",
                    "agent": "research_lead",
                    "message": event.data
                })
                
            elif isinstance(event, AgentRunUpdateEvent):
                agent = event.executor_id
                
                # Check if research lead is starting to process
                if agent == "research_lead":
                    research_lead_processing = True
                        
                # Handle both text content and structured response updates
                if isinstance(event.data, AgentRunResponseUpdate):
                    # CAPTURE ALL RESPONSE IDs
                    if event.data.response_id:
                        # Initialize agent lists if not exists
                        if agent not in all_agent_response_ids:
                            all_agent_response_ids[agent] = set()
                        all_agent_response_ids[agent].add(event.data.response_id)
                if event.data.message_id:
                    if agent not in all_agent_message_ids:
                        all_agent_message_ids[agent] = set()
                    all_agent_message_ids[agent].add(event.data.message_id)
                
                # Handle tool calls and results
                if event.data.contents:
                    for content in event.data.contents:
                        content_type = type(content).__name__
                        if hasattr(content, 'name') and content.name:
                            call_id = getattr(content, 'call_id', None)
                            args = getattr(content, 'arguments', '{}')
                            
                            try:
                                parsed_args = json.loads(args) if args else {}
                                step += 1
                                args_str = ", ".join([f"{k}='{v}'" if isinstance(v, str) else f"{k}={v}" 
                                                    for k, v in parsed_args.items()])
                                print(f"{step}. [TOOL CALL] {agent}: {content.name}({args_str})")
                                
                                interaction_sequence.append({
                                    "step": step,
                                    "type": "tool_call",
                                    "agent": agent,
                                    "function": content.name,
                                    "call_id": call_id,
                                    "args": parsed_args,
                                    "response_id": latest_agent_response_ids.get(agent),
                                    "message_id": latest_agent_message_ids.get(agent)
                                })
                            except json.JSONDecodeError:
                                # Fallback if arguments can't be parsed
                                step += 1
                                print(f"{step}. [TOOL CALL] {agent}: {content.name}()")
                                interaction_sequence.append({
                                    "step": step,
                                    "type": "tool_call",
                                    "agent": agent,
                                    "function": content.name,
                                    "call_id": call_id,
                                    "args": {},
                                    "response_id": latest_agent_response_ids.get(agent),
                                    "message_id": latest_agent_message_ids.get(agent)
                                })
                        
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
                            # Use research_lead as agent if we're in research lead processing
                            display_agent = "research_lead" if research_lead_processing else agent
                            if display_agent not in current_messages:
                                current_messages[display_agent] = ""
                            current_messages[display_agent] += content.text
                
                # Check if this update marks end of message (no contents or empty contents)
                if not event.data.contents or (len(event.data.contents) == 0):
                    # Message is complete, process accumulated text
                    display_agent = "research_lead" if research_lead_processing else agent
                    
                    if display_agent in current_messages and current_messages[display_agent]:
                        step += 1
                        message = current_messages[display_agent].strip()
                        if message:
                            # Special formatting for research lead
                            if display_agent == "research_lead":
                                print(f"\n" + "="*80)
                                print("RESEARCH LEAD FINAL SUMMARY:")
                                print("="*80)
                                print(f"{message}")
                                print("="*80)
                            else:
                                print(f"{step}. [AGENT RESPONSE] {display_agent}: {message}")
                            
                            interaction_sequence.append({
                                "step": step,
                                "type": "research_summary" if display_agent == "research_lead" else "agent_response",
                                "agent": display_agent,
                                "message": message,
                                "response_id": latest_agent_response_ids.get(agent),
                                "message_id": latest_agent_message_ids.get(agent)
                            })
                        current_messages[display_agent] = ""
            
            elif isinstance(event.data, str):
                # Handle simple text updates (non-streaming complete responses)
                display_agent = "research_lead" if research_lead_processing else agent
                step += 1
                
                # Special formatting for research lead
                if display_agent == "research_lead":
                    print(f"\n" + "="*80)
                    print("RESEARCH LEAD FINAL SUMMARY:")
                    print("="*80)
                    print(f"{event.data}")
                    print("="*80)
                else:
                    print(f"{step}. [AGENT RESPONSE] {display_agent}: {event.data}")
                
                interaction_sequence.append({
                    "step": step,
                    "type": "research_summary" if display_agent == "research_lead" else "agent_response",
                    "agent": display_agent,
                    "message": event.data,
                    "response_id": latest_agent_response_ids.get(agent),
                    "message_id": latest_agent_message_ids.get(agent)
                })
    
    return {
        "interaction_sequence": interaction_sequence,  # Complete chronological sequence
        "all_agent_response_ids": all_agent_response_ids,
        "all_agent_message_ids": all_agent_message_ids,
        "query": query
    }

def main():
    """Main function to run the workflow evaluation example."""
    # Example queries for testing different agent capabilities
    
    example_queries = [
        "Search the web for MSFT stock performance in the past couple of months",
        "What is the current weather in Seattle and Microsoft's stock price?",
        "Calculate the prime numbers between 20 and 40 and find their product",
    ]
    
    query = example_queries[2]
    
    # Run the workflow with response tracking
    asyncio.run(run_workflow_with_response_tracking(query))


if __name__ == "__main__":
    main()

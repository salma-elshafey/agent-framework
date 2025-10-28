# Copyright (c) Microsoft. All rights reserved.

"""
Multi-Agent Workflow Evaluation with Efficient Thread Retrieval

This sample demonstrates a multi-agent workflow that:
1. Processes queries through specialized agents (general, weather, financial tools)
2. Tracks response and message IDs for evaluation
3. Captures complete interaction sequences
4. Aggregates findings through a research lead agent
5. Provides more efficient thread ID retrieval

EFFICIENT THREAD RETRIEVAL:
- find_thread_by_run_id_efficiently(): Searches recent threads first instead of all threads
- This is more efficient than the original method when threads are created recently
"""

import asyncio
import json
import os
from typing import Dict, List, Optional

from dotenv import load_dotenv

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
from azure.identity import AzureCliCredential
from azure.identity.aio import AzureCliCredential as AsyncAzureCliCredential

# Optional imports for conversation analysis
try:
    from azure.ai.evaluation import AIAgentConverter
    from azure.ai.projects import AIProjectClient
    HAS_AI_EVALUATION = True
except ImportError:
    HAS_AI_EVALUATION = False

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

load_dotenv()


@executor(id="start_executor")
async def start_executor(input: str, ctx: WorkflowContext[List[ChatMessage]]) -> None:
    """Initiates the workflow by sending the user query to all specialized agents."""
    await ctx.send_message([ChatMessage(role="user", text=input)])


class ResearchLead(Executor):
    """Aggregates and summarizes findings from specialized agents."""
    
    def __init__(self, chat_client: AzureAIAgentClient, id: str = "research_lead"):
        self.agent = chat_client.create_agent(
            instructions="You are a research leader. Summarize findings from multiple specialized agents and provide a clear, comprehensive answer to the user's query.",
            name="research_lead",
            store=True
        )
        super().__init__(id=id)

    @handler
    async def fan_in_handle(self, responses: List[AgentExecutorResponse], ctx: WorkflowContext[WorkflowOutputEvent]) -> None:
        user_query = responses[0].full_conversation[0].text
        
        # Extract findings from all agent responses
        agent_findings = self._extract_agent_findings(responses)
        summary_text = "\n".join(agent_findings) if agent_findings else "No specific findings were provided by the agents."
        
        # Generate comprehensive summary
        messages = [
            ChatMessage(role=Role.SYSTEM, text="You are a research leader. Summarize findings from multiple specialized agents and provide a clear, comprehensive answer to the user's query."),
            ChatMessage(role=Role.USER, text=f"Original query: {user_query}\n\nFindings from specialized agents:\n{summary_text}\n\nPlease provide a comprehensive answer based on these findings.")
        ]
        
        try:
            final_response = await self.agent.run(messages)
            output_text = (final_response.messages[-1].text if final_response.messages and final_response.messages[-1].text 
                          else f"Based on the available findings, here's what I found regarding '{user_query}': {summary_text}")
        except Exception:
            output_text = f"Based on the available findings, here's what I found regarding '{user_query}': {summary_text}"
        
        await ctx.yield_output(output_text)
    
    def _extract_agent_findings(self, responses: List[AgentExecutorResponse]) -> List[str]:
        """Extract findings from agent responses."""
        agent_findings = []
        
        for response in responses:
            findings = []
            if response.agent_run_response and response.agent_run_response.messages:
                for msg in response.agent_run_response.messages:
                    if msg.role == Role.ASSISTANT and msg.text and msg.text.strip():
                        findings.append(msg.text.strip())
            
            if findings:
                combined_findings = " ".join(findings)
                agent_findings.append(f"[{response.executor_id}]: {combined_findings}")
        
        return agent_findings

async def run_workflow_with_response_tracking(query: str, chat_client: Optional[AzureAIAgentClient] = None) -> Dict:
    """Run multi-agent workflow and track thread IDs, run IDs, and interaction sequence.
    
    Args:
        query: The user query to process through the multi-agent workflow
        chat_client: Optional AzureAIAgentClient instance
        
    Returns:
        Dictionary containing interaction sequence, thread/run IDs, and conversation analysis
    """
    if chat_client is None:
        async with AzureAIAgentClient(async_credential=AsyncAzureCliCredential()) as client:
            return await _run_workflow_with_client(query, client)
    else:
        return await _run_workflow_with_client(query, chat_client)


async def _run_workflow_with_client(query: str, chat_client: AzureAIAgentClient) -> Dict:
    """Execute workflow with given client and track all interactions."""
    
    # Initialize tracking variables
    thread_ids = {}
    run_ids = {}
    all_agent_response_ids = {}
    all_agent_message_ids = {}
    
    # Tool restrictions for specialized agents
    tool_restrictions = ("Only use the tools provided and only use the information from the tools to answer the question. "
                        "If the tools do not provide enough information, respond with 'no further information provided'.")
    
    # Create workflow components
    workflow = _create_workflow(chat_client, tool_restrictions)
    
    # Process workflow events
    events = workflow.run_stream(query)
    await _process_workflow_events(events, thread_ids, run_ids, all_agent_response_ids, all_agent_message_ids)
    
    # Generate conversation analysis
    converted_conversations = await _analyze_conversations(thread_ids, run_ids)
    
    return {
        # "interaction_sequence": interaction_sequence,
        "thread_ids": thread_ids,
        "run_ids": run_ids,
        "all_agent_response_ids": all_agent_response_ids,
        "all_agent_message_ids": all_agent_message_ids,
        "converted_conversations": converted_conversations,
        "query": query
    }


def _create_workflow(chat_client: AzureAIAgentClient, tool_restrictions: str):
    """Create the multi-agent workflow with specialized agents."""
    research_lead = ResearchLead(chat_client=chat_client, id="research_lead")
    
    # Create specialized agents
    general_tools_assistant = chat_client.create_agent(
        instructions="You are an excellent research assistant with access to search, calculation, and reference tools.",
        name="general_tools_assistant",
        tools=[run_calculator, get_date_information, google_search, wikipedia_search, wolfram_alpha_query],
        store=True
    )
    
    weather_tools_assistant = chat_client.create_agent(
        instructions=f"You are an expert in using weather tools. {tool_restrictions}",
        name="weather_tools_assistant",
        tools=[get_current_weather, get_historical_weather],
        store=True
    )
    
    financial_tools_assistant = chat_client.create_agent(
        instructions=f"You are an expert in using financial tools. {tool_restrictions}",
        name="financial_tools_assistant",
        tools=[get_daily_time_series, find_stock_ticker, get_intraday_time_series],
        store=True
    )
    
    # Build and return workflow
    return (WorkflowBuilder()
            .set_start_executor(start_executor)
            .add_fan_out_edges(start_executor, [general_tools_assistant, weather_tools_assistant, financial_tools_assistant])
            .add_fan_in_edges([general_tools_assistant, weather_tools_assistant, financial_tools_assistant], research_lead)
            .build())


async def _process_workflow_events(events, thread_ids, run_ids, all_agent_response_ids, all_agent_message_ids):
    """Process workflow events and track interactions."""
    
    async for event in events:
        if isinstance(event, WorkflowOutputEvent):
            print(f"FINAL OUTPUT: {event.data}\n")
            
        elif isinstance(event, AgentRunUpdateEvent):
            agent = event.executor_id

            _track_agent_ids(event, agent, run_ids, thread_ids, all_agent_response_ids, all_agent_message_ids)


def _track_agent_ids(event, agent, run_ids, thread_ids, all_agent_response_ids, all_agent_message_ids):
    """Track agent response and message IDs."""
    if isinstance(event.data, AgentRunResponseUpdate):
        if event.data.response_id:
            run_ids[agent] = event.data.response_id
            if agent not in all_agent_response_ids:
                all_agent_response_ids[agent] = set()
            all_agent_response_ids[agent].add(event.data.response_id)
        
        if event.data.message_id:
            if agent not in all_agent_message_ids:
                all_agent_message_ids[agent] = set()
            all_agent_message_ids[agent].add(event.data.message_id)
                
        # Check for thread_id using conversation_id from raw_representation (most direct approach)
        if (hasattr(event.data, 'raw_representation') and 
            event.data.raw_representation and 
            hasattr(event.data.raw_representation, 'conversation_id') and 
            event.data.raw_representation.conversation_id):
            thread_ids[agent] = event.data.raw_representation.conversation_id



async def _analyze_conversations(thread_ids: Dict, run_ids: Dict) -> Dict:
    """Analyze conversations using AIAgentConverter if available."""
    if not HAS_AI_EVALUATION:
        return {"error": "azure.ai.evaluation not available - skipping conversation analysis"}
    
    try:
        project_endpoint = os.environ.get("AZURE_AI_PROJECT_ENDPOINT")
        if not project_endpoint:
            return {"error": "AZURE_AI_PROJECT_ENDPOINT not set - skipping conversation analysis"}
        
        sync_project_client = AIProjectClient(
            endpoint=project_endpoint,
            credential=AzureCliCredential()
        )
        converter = AIAgentConverter(sync_project_client)
        converted_conversations = {}
        
        for agent_name, run_id in run_ids.items():
            if run_id:
                try:
                    thread_id = thread_ids.get(agent_name)
                    
                    if thread_id:
                        converted_data = converter.convert(thread_id=thread_id, run_id=run_id)
                        converted_conversations[agent_name] = {
                            "thread_id": thread_id,
                            "run_id": run_id,
                            "converted_data": converted_data
                        }
                    else:
                        converted_conversations[agent_name] = {
                            "thread_id": None,
                            "run_id": run_id,
                            "error": "Could not find thread_id for this run_id"
                        }
                except Exception as e:
                    converted_conversations[agent_name] = {
                        "thread_id": thread_ids.get(agent_name),
                        "run_id": run_id,
                        "error": str(e)
                    }
        
        return converted_conversations
    
    except Exception as e:
        return {"error": f"Conversation analysis failed: {str(e)}"}


async def main_async():
    """Run the workflow evaluation and display results."""
    example_queries = [
        "Search the web for MSFT stock performance in the past couple of months",
        "What is the current weather in Seattle and Microsoft's stock price?",
        "Calculate the prime numbers between 20 and 40 and find their product",
    ]
    
    query = example_queries[0]
    result = await run_workflow_with_response_tracking(query)
    
    # Display conversation analysis results
    _display_conversation_analysis(result.get('converted_conversations', {}))
    

def _display_conversation_analysis(converted_conversations: Dict):
    """Display conversation analysis results."""
    if not converted_conversations:
        print("No converted conversations available")
        return
    
    for agent_name, conversion_result in converted_conversations.items():
        print(f"\n=== {agent_name.upper()} CONVERSATION ANALYSIS ===")
        print(f"Thread ID: {conversion_result.get('thread_id')}")
        print(f"Run ID: {conversion_result.get('run_id')}")
        
        if 'error' in conversion_result:
            print(f"Error: {conversion_result['error']}")
        elif 'converted_data' in conversion_result:
            print(json.dumps(conversion_result['converted_data'], indent=2))
        
        print(f"=== END {agent_name.upper()} ANALYSIS ===\n")

def main():
    """Main function to run the workflow evaluation example."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()

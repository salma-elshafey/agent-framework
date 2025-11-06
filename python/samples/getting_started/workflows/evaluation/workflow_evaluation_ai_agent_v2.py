# Copyright (c) Microsoft. All rights reserved.

"""
Multi-Agent Travel Planning Workflow Evaluation with AzureAIAgentClientV2

This sample demonstrates a multi-agent travel planning workflow using the V2 client that:
1. Processes travel queries through 7 specialized agents
2. Tracks response and conversation IDs for evaluation
3. Uses the new Prompt Agents API (V2)
4. Captures complete interaction sequences
5. Aggregates findings through a travel planning coordinator

WORKFLOW STRUCTURE (7 agents):
- Travel Agent Executor → Hotel Search, Flight Search, Activity Search, Booking Confirmation (fan-out)
- Hotel Search Executor → Booking Information Aggregation Executor
- Flight Search Executor → Booking Information Aggregation Executor
- Booking Confirmation Executor → Booking Payment Executor
- All 7 agents → Travel Planning Coordinator (ResearchLead) for final aggregation

Agents:
1. Travel Agent - Main coordinator (no tools to avoid thread conflicts)
2. Hotel Search - Searches hotels with tools
3. Flight Search - Searches flights with tools  
4. Activity Search - Searches activities with tools
5. Booking Confirmation - Confirms bookings with tools
6. Booking Payment - Processes payments with tools
7. Booking Information Aggregation - Aggregates hotel & flight booking info
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

# Add the local packages to the path
packages_path = Path(__file__).parent.parent.parent.parent.parent.parent / "packages"
sys.path.insert(0, str(packages_path / "core"))
sys.path.insert(0, str(packages_path / "azure-ai"))

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

# Import V2 client directly from source file to avoid installed package conflicts
from agent_framework_azure_ai._client import AzureAIClient
from azure.identity.aio import AzureDeveloperCliCredential
from azure.ai.projects.aio import AIProjectClient

from _tools import (
    # Travel planning tools
    search_hotels,
    get_hotel_details,
    search_flights,
    get_flight_details,
    search_activities,
    get_activity_details,
    confirm_booking,
    check_availability,
    process_payment,
    validate_payment_method,
)

load_dotenv()


@executor(id="start_executor")
async def start_executor(input: str, ctx: WorkflowContext[List[ChatMessage]]) -> None:
    """Initiates the workflow by sending the user query to all specialized agents."""
    await ctx.send_message([ChatMessage(role="user", text=input)])


class ResearchLead(Executor):
    """Aggregates and summarizes travel planning findings from all specialized agents."""
    
    def __init__(self, chat_client: AzureAIClient, id: str = "travel_planning_coordinator"):
        # store=True to preserve conversation history for evaluation
        self.agent = chat_client.create_agent(
            id="travel_planning_coordinator",
            instructions=(
                "You are the Travel Planning Coordinator. Your role is to synthesize information from multiple "
                "specialized travel agents into a cohesive, actionable travel plan. You receive inputs from: "
                "hotel search specialists, flight search specialists, activity planners, booking confirmation agents, "
                "payment processors, and booking information aggregators. Provide a clear, comprehensive travel plan "
                "that addresses the user's original query with all necessary details including accommodations, "
                "transportation, activities, and booking status."
            ),
            name="travel_planning_coordinator",
            store=True
        )
        super().__init__(id=id)

    @handler
    async def fan_in_handle(self, responses: List[AgentExecutorResponse], ctx: WorkflowContext[WorkflowOutputEvent]) -> None:
        user_query = responses[0].full_conversation[0].text
        
        # Extract findings from all agent responses
        agent_findings = self._extract_agent_findings(responses)
        summary_text = "\n".join(agent_findings) if agent_findings else "No specific findings were provided by the agents."
        
        # Generate comprehensive travel plan summary
        messages = [
            ChatMessage(role=Role.SYSTEM, text="You are a travel planning coordinator. Summarize findings from multiple specialized travel agents and provide a clear, comprehensive travel plan based on the user's query."),
            ChatMessage(role=Role.USER, text=f"Original query: {user_query}\n\nFindings from specialized travel agents:\n{summary_text}\n\nPlease provide a comprehensive travel plan based on these findings.")
        ]
        
        try:
            final_response = await self.agent.run(messages)
            output_text = (final_response.messages[-1].text if final_response.messages and final_response.messages[-1].text 
                          else f"Based on the available findings, here's your travel plan for '{user_query}': {summary_text}")
        except Exception:
            output_text = f"Based on the available findings, here's your travel plan for '{user_query}': {summary_text}"
        
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


async def run_workflow_with_response_tracking(query: str, chat_client: Optional[AzureAIClient] = None) -> Dict:
    """Run multi-agent workflow and track conversation IDs, response IDs, and interaction sequence.
    
    Args:
        query: The user query to process through the multi-agent workflow
        chat_client: Optional AzureAIClient instance
        
    Returns:
        Dictionary containing interaction sequence, conversation/response IDs, and conversation analysis
    """
    if chat_client is None:
        # Use AzureDeveloperCliCredential to avoid Azure CLI timeout issues
        credential = AzureDeveloperCliCredential()
        
        # Create AIProjectClient with the correct API version for V2 prompt agents
        project_client = AIProjectClient(
            endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
            credential=credential,
            api_version="2025-11-15-preview",
        )
        
        try:
            async with AzureAIClient(
                project_client=project_client,
                async_credential=credential
            ) as client:
                return await _run_workflow_with_client(query, client)
        finally:
            await credential.close()
            await project_client.close()
    else:
        return await _run_workflow_with_client(query, chat_client)


async def _run_workflow_with_client(query: str, chat_client: AzureAIClient) -> Dict:
    """Execute workflow with given client and track all interactions."""
    
    # Initialize tracking variables
    conversation_ids = {}
    response_ids = {}
    workflow_output = None
    
    # Tool restrictions for specialized agents
    tool_restrictions = ("Only use the tools provided and only use the information from the tools to answer the question. "
                        "If the tools do not provide enough information, respond with 'no further information provided'.")
    
    # Create workflow components and keep agent references
    # Pass project_client and credential to create separate client instances per agent
    workflow, agent_map = await _create_workflow(
        chat_client.project_client, 
        chat_client.credential,
        tool_restrictions
    )
    
    # Process workflow events
    events = workflow.run_stream(query)
    workflow_output = await _process_workflow_events(events, conversation_ids, response_ids)
    
    return {
        "conversation_ids": conversation_ids,
        "response_ids": response_ids,
        "output": workflow_output,
        "query": query
    }


async def _create_workflow(project_client, credential, tool_restrictions: str):
    """Create the multi-agent travel planning workflow with specialized agents.
    
    IMPORTANT: Each agent needs its own client instance because the V2 client stores
    agent_name and agent_version as instance variables, causing all agents to share
    the same agent identity if they share a client.
    """
    
    # Create separate client for ResearchLead
    research_lead_client = AzureAIClient(
        project_client=project_client,
        async_credential=credential,
        agent_name="travel_planning_coordinator"
    )
    research_lead = ResearchLead(chat_client=research_lead_client, id="travel_planning_coordinator")
    
    # Agent 1: Travel Agent Executor (main coordinator)
    # Create separate client with unique agent_name
    travel_agent_client = AzureAIClient(
        project_client=project_client,
        async_credential=credential,
        agent_name="travel_agent"
    )
    travel_agent = travel_agent_client.create_agent(
        id="travel_agent",
        instructions=(
            "You are the main Travel Agent coordinator. You receive user travel queries and coordinate with "
            "specialized agents. Summarize findings from specialized agents and provide comprehensive travel plans."
        ),
        name="travel_agent",
        store=True
    )
    
    # Agent 2: Hotel Search Executor
    hotel_search_client = AzureAIClient(
        project_client=project_client,
        async_credential=credential,
        agent_name="hotel_search_agent"
    )
    hotel_search_agent = hotel_search_client.create_agent(
        id="hotel_search_agent",
        instructions=f"You are a hotel search specialist. {tool_restrictions}",
        name="hotel_search_agent",
        tools=[search_hotels, get_hotel_details, check_availability],
        store=True
    )
    
    # Agent 3: Flight Search Executor
    flight_search_client = AzureAIClient(
        project_client=project_client,
        async_credential=credential,
        agent_name="flight_search_agent"
    )
    flight_search_agent = flight_search_client.create_agent(
        id="flight_search_agent",
        instructions=f"You are a flight search specialist. {tool_restrictions}",
        name="flight_search_agent",
        tools=[search_flights, get_flight_details, check_availability],
        store=True
    )
    
    # Agent 4: Activity Search Executor
    activity_search_client = AzureAIClient(
        project_client=project_client,
        async_credential=credential,
        agent_name="activity_search_agent"
    )
    activity_search_agent = activity_search_client.create_agent(
        id="activity_search_agent",
        instructions=f"You are an activities and attractions specialist. {tool_restrictions}",
        name="activity_search_agent",
        tools=[search_activities, get_activity_details],
        store=True
    )
    
    # Agent 5: Booking Confirmation Executor
    booking_confirmation_client = AzureAIClient(
        project_client=project_client,
        async_credential=credential,
        agent_name="booking_confirmation_agent"
    )
    booking_confirmation_agent = booking_confirmation_client.create_agent(
        id="booking_confirmation_agent",
        instructions=f"You are a booking confirmation specialist. Verify and confirm travel bookings. {tool_restrictions}",
        name="booking_confirmation_agent",
        tools=[confirm_booking, check_availability],
        store=True
    )
    
    # Agent 6: Booking Payment Executor
    booking_payment_client = AzureAIClient(
        project_client=project_client,
        async_credential=credential,
        agent_name="booking_payment_agent"
    )
    booking_payment_agent = booking_payment_client.create_agent(
        id="booking_payment_agent",
        instructions=f"You are a payment processing specialist. Handle payment transactions for travel bookings. {tool_restrictions}",
        name="booking_payment_agent",
        tools=[process_payment, validate_payment_method],
        store=True
    )
    
    # Agent 7: Booking Information Aggregation Executor
    booking_info_client = AzureAIClient(
        project_client=project_client,
        async_credential=credential,
        agent_name="booking_info_aggregation_agent"
    )
    booking_info_aggregation_agent = booking_info_client.create_agent(
        id="booking_info_aggregation_agent",
        instructions=(
            "You are a booking information aggregator. You collect hotel and flight booking details, "
            "summarize key information (prices, dates, confirmation numbers), and provide aggregated "
            "booking information. Do not use tools - just summarize the information received."
        ),
        name="booking_info_aggregation_agent",
        store=True
    )
    
    # Build workflow WITHOUT feedback loops to prevent concurrent thread access:
    # 1. start_executor → travel_agent
    # 2. travel_agent → hotel_search, flight_search, activity_search, booking_confirmation (fan-out)
    # 3. hotel_search → booking_info_aggregation
    # 4. flight_search → booking_info_aggregation
    # 5. booking_confirmation → booking_payment
    # 6. activity_search, booking_info_aggregation, booking_payment → research_lead (final aggregation)
    # 
    # Max iterations set to 10 (though shouldn't be needed without cycles)
    # store=True preserves conversation history on each agent's thread for evaluation
    
    workflow = (WorkflowBuilder(max_iterations=10)
            .set_start_executor(start_executor)
            .add_edge(start_executor, travel_agent)
            .add_fan_out_edges(travel_agent, [hotel_search_agent, flight_search_agent, activity_search_agent, booking_confirmation_agent])
            .add_edge(hotel_search_agent, booking_info_aggregation_agent)
            .add_edge(flight_search_agent, booking_info_aggregation_agent)
            .add_edge(booking_confirmation_agent, booking_payment_agent)
            .add_fan_in_edges([activity_search_agent, booking_info_aggregation_agent, booking_payment_agent], 
                             research_lead)
            .build())
    
    # Return workflow and agent map for thread ID extraction
    agent_map = {
        "travel_agent": travel_agent,
        "hotel_search_agent": hotel_search_agent,
        "flight_search_agent": flight_search_agent,
        "activity_search_agent": activity_search_agent,
        "booking_confirmation_agent": booking_confirmation_agent,
        "booking_payment_agent": booking_payment_agent,
        "booking_info_aggregation_agent": booking_info_aggregation_agent,
        "travel_planning_coordinator": research_lead.agent,
    }
    
    return workflow, agent_map


async def _process_workflow_events(events, conversation_ids, response_ids):
    """Process workflow events and track interactions."""
    workflow_output = None
    
    async for event in events:
        if isinstance(event, WorkflowOutputEvent):
            workflow_output = event.data
            # Handle Unicode characters that may not be displayable in Windows console
            try:
                print(f"\nFINAL OUTPUT: {event.data}\n")
            except UnicodeEncodeError:
                output_str = str(event.data).encode('ascii', 'replace').decode('ascii')
                print(f"\nFINAL OUTPUT: {output_str}\n")
            
        elif isinstance(event, AgentRunUpdateEvent):
            _track_agent_ids(event, event.executor_id, response_ids, conversation_ids)
    
    return workflow_output


def _track_agent_ids(event, agent, response_ids, conversation_ids):
    """Track agent response and conversation IDs."""
    if isinstance(event.data, AgentRunResponseUpdate):
        # Check for conversation_id and response_id from raw_representation
        # V2 API stores conversation_id directly on raw_representation (ChatResponseUpdate)
        if hasattr(event.data, 'raw_representation') and event.data.raw_representation:
            raw = event.data.raw_representation
            
            # Try conversation_id directly on raw (this is the V2 pattern)
            if hasattr(raw, 'conversation_id') and raw.conversation_id:
                conversation_ids[agent] = raw.conversation_id
            
            # Extract response_id from the OpenAI event (available from first event)
            if hasattr(raw, 'raw_representation') and raw.raw_representation:
                openai_event = raw.raw_representation
                
                # Check if event has response object with id
                if hasattr(openai_event, 'response') and hasattr(openai_event.response, 'id'):
                    print(event)
                    print(openai_event)
                    response_ids[agent] = openai_event.response.id


async def main_async():
    """Run the workflow evaluation and display results."""
    example_queries = [
        "Plan a 3-day trip to Paris from December 15-18, 2025. Budget is $2000. Need hotel near Eiffel Tower, round-trip flights from New York JFK, and recommend 2-3 activities per day.",
        "Find a budget hotel in Tokyo for January 5-10, 2026 under $150/night near Shibuya station, book activities including a sushi making class",
        "Search for round-trip flights from Los Angeles to London departing March 20, 2026, returning March 27, 2026. Economy class, 2 passengers. Recommend tourist attractions and museums.",
    ]
    
    query = example_queries[0]
    print(f"\n=== Starting V2 Workflow Evaluation ===")
    print(f"Query: {query}\n")
    
    result = await run_workflow_with_response_tracking(query)
    print(result)
    
    # Save conversation and response IDs to JSON file
    output_data = {
        "agents": {},
        "query": result["query"],
        "output": result.get("output", "")
    }
    
    # Create agent-specific mappings
    for agent_name in result["conversation_ids"].keys():
        output_data["agents"][agent_name] = {
            "conversation_id": result["conversation_ids"].get(agent_name),
            "response_id": result["response_ids"].get(agent_name)
        }
    
    # Save to JSON file
    output_file = os.path.join(os.getcwd(), "workflow_agent_ids2.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\nAgent IDs saved to: {output_file}")
    print(f"Total agents tracked: {len(output_data['agents'])}")



def main():
    """Main function to run the workflow evaluation example."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()

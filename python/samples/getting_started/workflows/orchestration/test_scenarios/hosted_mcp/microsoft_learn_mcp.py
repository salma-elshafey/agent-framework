# Fetch Workflow Traces from App Insights
#
# This script demonstrates:
# 1. Running a workflow with HostedMCPTool (Microsoft Learn)
# 2. Capturing the workflow.id locally
# 3. Fetching all traces from App Insights using the workflow.id
# 4. Analyzing the complete trace including tool calls

from pathlib import Path
import time

import os
import json
from datetime import timedelta
from dotenv import load_dotenv
load_dotenv()

from agent_framework import SequentialBuilder, HostedMCPTool, WorkflowOutputEvent
from agent_framework.azure import AzureAIClient
from azure.identity.aio import AzureCliCredential as AsyncAzureCliCredential

from appinsights_traces import AppInsightsTraceCollector

from azure.monitor.opentelemetry import configure_azure_monitor
from agent_framework.observability import create_resource, enable_instrumentation

# Configure Azure Monitor exporter
connection_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
if connection_string:
    configure_azure_monitor(
        connection_string=connection_string,
        resource=create_resource(),
        enable_live_metrics=True,
    )
    print("Azure Monitor configured")
else:
    print("WARNING: APPLICATIONINSIGHTS_CONNECTION_STRING not set")

# Enable instrumentation with sensitive data capture
enable_instrumentation(enable_sensitive_data=True)
print("Instrumentation enabled")

# Verify App Insights config
print(f"\nApp Insights resource ID: {os.environ.get('APPINSIGHTS_RESOURCE_ID', 'NOT SET')[:50]}...")

# Create MCP Tool

microsoft_learn_mcp = HostedMCPTool(
    name="Microsoft-Learn",
    url="https://learn.microsoft.com/api/mcp",
    description="Search Microsoft Learn documentation.",
    approval_mode="never_require",
    allowed_tools=["microsoft_docs_search"],
)

print(f"MCP Tool: {microsoft_learn_mcp.name}")

# Run Workflow and Capture workflow.id

# Store workflow ID for later trace fetching
captured_workflow_id = None

async def run_workflow_and_capture_id(query: str):
    """Run workflow and capture the workflow.id."""
    global captured_workflow_id
    
    async with AsyncAzureCliCredential() as credential:
        async with AzureAIClient(credential=credential) as client:
            agent = client.create_agent(
                name="LearnAgent",
                instructions="You answer questions using Microsoft Learn. Always use the MCP tool to search.",
                tools=microsoft_learn_mcp,
            )
            
            # Build workflow
            workflow = SequentialBuilder().participants([agent]).build()
            
            # Capture workflow ID from the workflow object
            captured_workflow_id = workflow.id
            print(f"Workflow ID: {captured_workflow_id}")
            print(f"Query: {query}\n")
            
            # Run workflow
            final_output = None
            async for event in workflow.run_stream(query):
                if isinstance(event, WorkflowOutputEvent):
                    print(event.data)
            
            return final_output, captured_workflow_id

async def main():
    query = "What is Azure Bicep and how do I create a storage account with it?"
    result, workflow_id = await run_workflow_and_capture_id(query)

    print("Waiting 30 seconds for traces to propagate to App Insights...")
    time.sleep(30)
    print("Done waiting.")

    # Fetch Traces from App Insights
    collector = AppInsightsTraceCollector(
        timespan=timedelta(hours=1)  # Look back 1 hour
    )

    print(f"Fetching traces for workflow.id: {workflow_id}")

    spans = collector.fetch_workflow_traces(workflow_id)
    print(f"\nTotal spans fetched: {len(spans)}")

    output_file = f"appinsights_workflow_{workflow_id[:8]}_traces.jsonl"
    collector.save_traces_to_file(spans, str(output_file), format="jsonl")

    print(f"\nTrace file: {output_file}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

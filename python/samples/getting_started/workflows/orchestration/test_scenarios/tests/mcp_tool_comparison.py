# MCP Tool Tracing Comparison
#
# This script compares traces from different MCP tool types:
# 1. MCPStdioTool (local subprocess)
# 2. MCPStreamableHTTPTool (HTTP/SSE)
# 3. MCPWebsocketTool (WebSocket)
# 4. HostedMCPTool (Azure AI Foundry) - optional

import sys
from pathlib import Path
import asyncio
import json
import subprocess
import time
import signal
from typing import Optional

# Setup paths
script_dir = Path(__file__).parent
test_scenarios_dir = script_dir.parent
repo_root = test_scenarios_dir.parents[4]
python_packages_dir = repo_root / "python" / "packages" / "core"

sys.path.insert(0, str(python_packages_dir))
sys.path.insert(0, str(test_scenarios_dir))
sys.path.insert(0, str(test_scenarios_dir / "common"))
sys.path.insert(0, str(test_scenarios_dir / "common" / "hr_workflow"))

print(f"Test scenarios dir: {test_scenarios_dir}")

import os
from datetime import timedelta
from dotenv import load_dotenv
load_dotenv()

from agent_framework import SequentialBuilder, MCPStdioTool, MCPStreamableHTTPTool, MCPWebsocketTool, HostedMCPTool, WorkflowOutputEvent
from agent_framework.azure import AzureAIClient
from azure.identity.aio import AzureCliCredential as AsyncAzureCliCredential

# Import tracing utilities
from tracing import get_trace_output_path
from appinsights_traces import AppInsightsTraceCollector
from azure.monitor.opentelemetry import configure_azure_monitor
from agent_framework.observability import create_resource, enable_instrumentation

# Path to HR MCP server
hr_mcp_server_path = test_scenarios_dir / "common" / "hr_workflow" / "hr_mcp_server.py"
hr_mcp_server_http_path = test_scenarios_dir / "common" / "hr_workflow" / "hr_mcp_server_http.py"
hr_mcp_server_ws_path = test_scenarios_dir / "common" / "hr_workflow" / "hr_mcp_server_ws.py"


# Flag to track if Azure Monitor has been configured
_azure_monitor_configured = False


def setup_azure_monitor():
    """Configure Azure Monitor once for all tests."""
    global _azure_monitor_configured
    
    if _azure_monitor_configured:
        return
    
    connection_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if connection_string:
        configure_azure_monitor(
            connection_string=connection_string,
            resource=create_resource(),
            enable_live_metrics=True,
        )
        print("Azure Monitor configured")
        _azure_monitor_configured = True
    else:
        print("WARNING: APPLICATIONINSIGHTS_CONNECTION_STRING not set")
    
    # Enable instrumentation with sensitive data capture
    enable_instrumentation(enable_sensitive_data=True)
    print("Agent Framework instrumentation enabled (sensitive data capture: ON)")


class ServerManager:
    """Manages MCP server lifecycle (HTTP or WebSocket)."""
    
    def __init__(self, script_path: Path, port: int, server_type: str = "HTTP"):
        self.script_path = script_path
        self.port = port
        self.server_type = server_type
        self.process: Optional[subprocess.Popen] = None
    
    def start(self):
        """Start the server."""
        print(f"Starting {self.server_type} server on port {self.port}...")
        self.process = subprocess.Popen(
            [sys.executable, str(self.script_path), "--port", str(self.port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        # Give the server time to start
        time.sleep(3)
        print(f"{self.server_type} server started (PID: {self.process.pid})")
    
    def stop(self):
        """Stop the server."""
        if self.process:
            print(f"Stopping {self.server_type} server (PID: {self.process.pid})...")
            if sys.platform == "win32":
                self.process.terminate()
            else:
                self.process.send_signal(signal.SIGTERM)
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            print(f"{self.server_type} server stopped")


async def test_stdio_tool() -> tuple[str, str]:
    """Test MCPStdioTool tracing."""
    print("\n" + "="*70)
    print("TEST 1: MCPStdioTool")
    print("="*70)
    
    mcp_tool = MCPStdioTool(
        name="hr-research",
        command=sys.executable,
        args=[str(hr_mcp_server_path)],
        description="HR research tools for candidate sourcing",
    )
    
    try:
        async with mcp_tool:
            print(f"Connected to MCP server. Available tools: {[f.name for f in mcp_tool.functions]}")
            
            async with AsyncAzureCliCredential() as credential:
                async with AzureAIClient(credential=credential) as client:
                    agent = client.create_agent(
                        name="TalentScout",
                        instructions="You search for candidates using the HR tools. Search for Python developers in Seattle.",
                        tools=mcp_tool,
                    )
                    
                    workflow = SequentialBuilder().participants([agent]).build()
                    workflow_id = workflow.id
                    print(f"Workflow ID: {workflow_id}")
                    
                    final_output = None
                    async for event in workflow.run_stream("Find Python developers in Seattle with at least 5 years experience"):
                        if isinstance(event, WorkflowOutputEvent):
                            final_output = event.data
                    
                    print(f"\nResult: {str(final_output)[:200]}...")
                    return workflow_id, "stdio"
    except Exception as e:
        print(f"ERROR in stdio test: {e}")
        return None, None


async def test_http_tool() -> tuple[str, str]:
    """Test MCPStreamableHTTPTool tracing."""
    print("\n" + "="*70)
    print("TEST 2: MCPStreamableHTTPTool")
    print("="*70)
    
    # Start HTTP server
    server_manager = ServerManager(hr_mcp_server_http_path, port=8080, server_type="HTTP")
    server_manager.start()
    
    try:
        mcp_tool = MCPStreamableHTTPTool(
            name="hr-research-http",
            url="http://localhost:8080/mcp",
            description="HR research tools via HTTP",
        )
        
        async with mcp_tool:
            print(f"Connected to HTTP MCP server. Available tools: {[f.name for f in mcp_tool.functions]}")
            
            async with AsyncAzureCliCredential() as credential:
                async with AzureAIClient(credential=credential) as client:
                    agent = client.create_agent(
                        name="TalentScout-HTTP",
                        instructions="You search for candidates using the HR tools. Search for Python developers in Seattle.",
                        tools=mcp_tool,
                    )
                    
                    workflow = SequentialBuilder().participants([agent]).build()
                    workflow_id = workflow.id
                    print(f"Workflow ID: {workflow_id}")
                    
                    final_output = None
                    async for event in workflow.run_stream("Find Python developers in Seattle with at least 5 years experience"):
                        if isinstance(event, WorkflowOutputEvent):
                            final_output = event.data
                    
                    print(f"\nResult: {str(final_output)[:200]}...")
                    return workflow_id, "http"
    except Exception as e:
        print(f"ERROR in HTTP test: {e}")
        return None, None
    finally:
        server_manager.stop()


async def test_websocket_tool() -> tuple[str, str]:
    """Test MCPWebsocketTool tracing."""
    print("\n" + "="*70)
    print("TEST 3: MCPWebsocketTool")
    print("="*70)
    
    # Start WebSocket server
    server_manager = ServerManager(hr_mcp_server_ws_path, port=8082, server_type="WebSocket")
    server_manager.start()
    
    try:
        mcp_tool = MCPWebsocketTool(
            name="hr-research-ws",
            url="ws://localhost:8082/ws",
            description="HR research tools via WebSocket",
        )
        
        async with mcp_tool:
            print(f"Connected to WebSocket MCP server. Available tools: {[f.name for f in mcp_tool.functions]}")
            
            async with AsyncAzureCliCredential() as credential:
                async with AzureAIClient(credential=credential) as client:
                    agent = client.create_agent(
                        name="TalentScout-WS",
                        instructions="You search for candidates using the HR tools. Search for Python developers in Seattle.",
                        tools=mcp_tool,
                    )
                    
                    workflow = SequentialBuilder().participants([agent]).build()
                    workflow_id = workflow.id
                    print(f"Workflow ID: {workflow_id}")
                    
                    final_output = None
                    async for event in workflow.run_stream("Find Python developers in Seattle with at least 5 years experience"):
                        if isinstance(event, WorkflowOutputEvent):
                            final_output = event.data
                    
                    print(f"\nResult: {str(final_output)[:200]}...")
                    return workflow_id, "websocket"
    except Exception as e:
        print(f"ERROR in WebSocket test: {e}")
        return None, None
    finally:
        server_manager.stop()


async def test_hosted_mcp_tool() -> tuple[Optional[str], Optional[str]]:
    """Test HostedMCPTool tracing (optional - requires Azure AI Foundry)."""
    print("\n" + "="*70)
    print("TEST 4: HostedMCPTool (Optional)")
    print("="*70)
    
    # Check if we have the required environment variables
    if not os.environ.get("AZURE_OPENAI_ENDPOINT"):
        print("SKIPPED: AZURE_OPENAI_ENDPOINT not set. Set this to test HostedMCPTool.")
        return None, None
    
    try:
        microsoft_learn_mcp = HostedMCPTool(
            name="Microsoft-Learn",
            url="https://learn.microsoft.com/api/mcp",
            description="Search Microsoft Learn documentation.",
            approval_mode="never_require",
            allowed_tools=["microsoft_docs_search"],
        )
        
        async with AsyncAzureCliCredential() as credential:
            async with AzureAIClient(credential=credential) as client:
                agent = client.create_agent(
                    name="LearnAgent",
                    instructions="You answer questions using Microsoft Learn. Always use the MCP tool to search.",
                    tools=microsoft_learn_mcp,
                )
                
                workflow = SequentialBuilder().participants([agent]).build()
                workflow_id = workflow.id
                print(f"Workflow ID: {workflow_id}")
                
                final_output = None
                async for event in workflow.run_stream("What is Azure Bicep?"):
                    if isinstance(event, WorkflowOutputEvent):
                        final_output = event.data
                
                print(f"\nResult: {str(final_output)[:200]}...")
                return workflow_id, "hosted"
    except Exception as e:
        print(f"ERROR in hosted MCP test: {e}")
        return None, None


def analyze_appinsights_spans(spans: list, tool_type: str):
    """Analyze App Insights spans and show key information."""
    print(f"\n  Tool Type: {tool_type}")
    print(f"  Total spans: {len(spans)}")
    
    # Find unique operation IDs
    op_ids = set()
    for span in spans:
        op_id = span.custom_dimensions.get("workflow.id") or span.operation_id
        if op_id:
            op_ids.add(op_id)
    print(f"  Unique operation_Ids: {len(op_ids)}")
    
    # Get agent spans
    agent_spans = [s for s in spans if s.custom_dimensions.get("gen_ai.operation.name") == "invoke_agent"]
    print(f"  invoke_agent spans: {len(agent_spans)}")
    for span in agent_spans:
        agent_name = span.custom_dimensions.get("gen_ai.agent.name", "unknown")
        print(f"    - {agent_name}: {span.duration}ms")
    
    # Get tool spans
    tool_spans = [s for s in spans if s.custom_dimensions.get("gen_ai.operation.name") == "execute_tool"]
    print(f"  execute_tool spans: {len(tool_spans)}")
    for span in tool_spans[:5]:  # Show first 5
        tool_name = span.custom_dimensions.get("gen_ai.tool.name", "N/A")
        print(f"    - {tool_name}")
        
        # Show tool arguments if available
        tool_args = span.custom_dimensions.get("gen_ai.tool.call.arguments")
        if tool_args:
            print(f"      Arguments: {str(tool_args)[:100]}...")
    
    # Get chat spans
    chat_spans = [s for s in spans if s.custom_dimensions.get("gen_ai.operation.name") == "chat"]
    print(f"  chat spans: {len(chat_spans)}")


async def fetch_and_save_traces(workflow_id: str, tool_type: str):
    """Fetch traces from App Insights and save to file."""
    print(f"\nFetching traces for {tool_type} workflow: {workflow_id}")
    
    # Initialize the collector
    collector = AppInsightsTraceCollector(timespan=timedelta(hours=1))
    
    # Fetch all traces for this workflow
    spans = collector.fetch_workflow_traces(workflow_id)
    print(f"  Fetched {len(spans)} spans from App Insights")
    
    if len(spans) > 0:
        # Save traces to file
        output_file = get_trace_output_path("mcp_comparison", f"{tool_type}_appinsights_{workflow_id[:8]}")
        collector.save_traces_to_file(spans, str(output_file), format="jsonl")
        print(f"  Saved traces to: {output_file}")
        
        # Analyze the traces
        analyze_appinsights_spans(spans, tool_type)
        
        return spans
    else:
        print(f"  WARNING: No traces found for workflow {workflow_id}")
        return []


async def main():
    """Run all MCP tool comparison tests."""
    print("="*70)
    print("MCP Tool Tracing Comparison")
    print("="*70)
    
    # Configure Azure Monitor once for all tests
    setup_azure_monitor()
    
    # Check App Insights configuration
    if not os.environ.get("APPINSIGHTS_RESOURCE_ID"):
        print("\nWARNING: APPINSIGHTS_RESOURCE_ID not set.")
        print("Cannot fetch traces from App Insights.")
        print("Set this environment variable to enable trace fetching.\n")
    
    workflow_results = []
    
    # Test 1: MCPStdioTool
    try:
        workflow_id, tool_type = await test_stdio_tool()
        if workflow_id:
            workflow_results.append((workflow_id, tool_type))
    except Exception as e:
        print(f"FAILED: MCPStdioTool test: {e}")
        import traceback
        traceback.print_exc()
    
    # Wait between tests
    print("\nWaiting 2 seconds before next test...")
    await asyncio.sleep(2)
    
    # Test 2: MCPStreamableHTTPTool
    try:
        workflow_id, tool_type = await test_http_tool()
        if workflow_id:
            workflow_results.append((workflow_id, tool_type))
    except Exception as e:
        print(f"FAILED: MCPStreamableHTTPTool test: {e}")
        import traceback
        traceback.print_exc()
    
    # Wait between tests
    print("\nWaiting 2 seconds before next test...")
    await asyncio.sleep(2)
    
    # Test 3: MCPWebsocketTool
    try:
        workflow_id, tool_type = await test_websocket_tool()
        if workflow_id:
            workflow_results.append((workflow_id, tool_type))
    except Exception as e:
        print(f"FAILED: MCPWebsocketTool test: {e}")
        import traceback
        traceback.print_exc()
    
    # Wait between tests
    print("\nWaiting 2 seconds before next test...")
    await asyncio.sleep(2)
    
    # Test 4: HostedMCPTool (optional)
    try:
        workflow_id, tool_type = await test_hosted_mcp_tool()
        if workflow_id:
            workflow_results.append((workflow_id, tool_type))
    except Exception as e:
        print(f"FAILED: HostedMCPTool test: {e}")
        import traceback
        traceback.print_exc()
    
    # Wait for traces to propagate to App Insights
    if workflow_results and os.environ.get("APPINSIGHTS_RESOURCE_ID"):
        print("\n" + "="*70)
        print("WAITING FOR TRACES TO PROPAGATE")
        print("="*70)
        print("Waiting 30 seconds for traces to propagate to App Insights...")
        time.sleep(30)
        print("Done waiting.")
        
        # Fetch and save traces for each workflow
        print("\n" + "="*70)
        print("FETCHING TRACES FROM APP INSIGHTS")
        print("="*70)
        
        for workflow_id, tool_type in workflow_results:
            try:
                await fetch_and_save_traces(workflow_id, tool_type)
            except Exception as e:
                print(f"ERROR fetching traces for {tool_type}: {e}")
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Completed tests: {len(workflow_results)}")
    for workflow_id, tool_type in workflow_results:
        print(f"  {tool_type}: {workflow_id}")

if __name__ == "__main__":
    asyncio.run(main())

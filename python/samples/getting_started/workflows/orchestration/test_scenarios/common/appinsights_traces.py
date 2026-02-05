# Copyright (c) Microsoft. All rights reserved.

"""
Application Insights Trace Collector for Workflow Traces.

This module provides utilities to fetch complete workflow traces from 
Application Insights by correlating workflow.id with operation_Id.

Workflow:
1. Run a workflow and capture workflow.id locally
2. Query App Insights to find operation_Ids with matching workflow.id
3. Fetch all spans for those operation_Ids
4. Return traces ordered by timestamp
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from azure.identity import DefaultAzureCredential
from azure.monitor.query import LogsQueryClient, LogsQueryStatus


@dataclass
class TraceSpan:
    """Represents a single trace span from App Insights."""
    timestamp: datetime
    operation_id: str
    span_id: str
    name: str
    target: str
    duration: float
    custom_dimensions: dict[str, Any]
    raw_row: dict[str, Any]


class AppInsightsTraceCollector:
    """
    Collector for fetching workflow traces from Application Insights.
    
    Uses the workflow.id captured locally to correlate and fetch
    all related spans from App Insights.
    
    Example:
        collector = AppInsightsTraceCollector()
        traces = collector.fetch_workflow_traces("a8769f49-4daf-44af-9569-0169820c0108")
        for trace in traces:
            print(f"{trace.timestamp} - {trace.name}")
    """
    
    def __init__(
        self,
        resource_id: str | None = None,
        credential: DefaultAzureCredential | None = None,
        timespan: timedelta | None = None,
    ):
        """
        Initialize the App Insights trace collector.
        
        Args:
            resource_id: Application Insights resource ID in format:
                        /subscriptions/{sub}/resourceGroups/{rg}/providers/microsoft.insights/components/{name}
                        Defaults to APPINSIGHTS_RESOURCE_ID env var.
            credential: Azure credential for authentication.
                       Defaults to DefaultAzureCredential.
            timespan: Time range to query. Defaults to last 24 hours.
        """
        self.resource_id = resource_id or os.environ.get("APPINSIGHTS_RESOURCE_ID")
        if not self.resource_id:
            raise ValueError(
                "resource_id is required. Set via parameter or "
                "APPINSIGHTS_RESOURCE_ID environment variable. "
                "Format: /subscriptions/{sub}/resourceGroups/{rg}/providers/microsoft.insights/components/{name}"
            )
        
        self.credential = credential or DefaultAzureCredential()
        self.client = LogsQueryClient(self.credential)
        self.timespan = timespan or timedelta(hours=24)
    
    def _build_operation_ids_query(self, workflow_id: str) -> str:
        """
        Build KQL query to find operation_Ids for a workflow.
        
        Searches for any span that has the workflow.id in customDimensions.
        
        Args:
            workflow_id: The workflow.id to search for.
            
        Returns:
            KQL query string.
        """
        return f"""
union traces, dependencies
| where customDimensions["workflow.id"] == "{workflow_id}"
| distinct operation_Id
"""
    
    def _build_traces_query(self, operation_ids: list[str]) -> str:
        """
        Build KQL query to fetch all spans for given operation_Ids.
        
        Args:
            operation_ids: List of operation_Ids to fetch.
            
        Returns:
            KQL query string.
        """
        operation_ids_json = json.dumps(operation_ids)
        return f"""
let operation_ids = dynamic({operation_ids_json});
union traces, dependencies, requests
| where operation_Id in (operation_ids)
| project 
    timestamp,
    operation_Id,
    id,
    operation_Name,
    target,
    duration,
    customDimensions,
    itemType
| order by timestamp asc
"""
    
    def _build_combined_query(self, workflow_id: str) -> str:
        """
        Build a single KQL query that finds operation_Ids and fetches all traces.
        
        Searches for any span that has the workflow.id in customDimensions,
        then also fetches all spans (including server-side) that share the same gen_ai.response.id.
        
        Args:
            workflow_id: The workflow.id to search for.
            
        Returns:
            KQL query string.
        """
        return f"""
// Step 1: Find operation_Ids with workflow.id
let workflow_operation_ids = 
    union traces, dependencies
    | where customDimensions["workflow.id"] == "{workflow_id}"
    | distinct operation_Id;
// Step 2: Get all client-side spans and extract response IDs
let client_spans = 
    union traces, dependencies, requests
    | where operation_Id in (workflow_operation_ids);
// Step 3: Extract gen_ai.response.id values from client spans
let response_ids = 
    client_spans
    | where isnotempty(customDimensions["gen_ai.response.id"])
    | distinct tostring(customDimensions["gen_ai.response.id"]);
// Step 4: Find ALL spans that share the same response_id (including server-side)
let response_id_spans = 
    union traces, dependencies, requests
    | where customDimensions["gen_ai.response.id"] in (response_ids);
// Step 5: Combine client spans and response_id correlated spans (deduplicated)
union client_spans, response_id_spans
| summarize arg_max(timestamp, *) by operation_Id, id
| project 
    timestamp,
    operation_Id,
    id,
    operation_Name,
    target,
    duration,
    customDimensions,
    itemType
| order by timestamp asc
"""
    
    def query_workflow_operation_ids(self, workflow_id: str) -> list[str]:
        """
        Find all operation_Ids associated with a workflow.
        
        Args:
            workflow_id: The workflow.id to search for.
            
        Returns:
            List of unique operation_Ids.
        """
        query = self._build_operation_ids_query(workflow_id)
        
        response = self.client.query_resource(
            resource_id=self.resource_id,
            query=query,
            timespan=self.timespan,
        )
        
        if response.status != LogsQueryStatus.SUCCESS:
            raise RuntimeError(f"Query failed: {response.partial_error}")
        
        operation_ids = []
        for table in response.tables:
            for row in table.rows:
                operation_ids.append(row[0])
        
        return operation_ids
    
    def fetch_traces_by_operation_ids(
        self, 
        operation_ids: list[str]
    ) -> list[TraceSpan]:
        """
        Fetch all trace spans for the given operation_Ids.
        
        Args:
            operation_ids: List of operation_Ids to fetch.
            
        Returns:
            List of TraceSpan objects ordered by timestamp.
        """
        if not operation_ids:
            return []
        
        query = self._build_traces_query(operation_ids)
        
        response = self.client.query_resource(
            resource_id=self.resource_id,
            query=query,
            timespan=self.timespan,
        )
        
        if response.status != LogsQueryStatus.SUCCESS:
            raise RuntimeError(f"Query failed: {response.partial_error}")
        
        return self._parse_response(response)
    
    def fetch_workflow_traces(self, workflow_id: str) -> list[TraceSpan]:
        """
        Fetch all traces for a workflow in a single query.
        
        This is more efficient than calling query_workflow_operation_ids
        and fetch_traces_by_operation_ids separately.
        
        Args:
            workflow_id: The workflow.id to fetch traces for.
            
        Returns:
            List of TraceSpan objects ordered by timestamp.
        """
        query = self._build_combined_query(workflow_id)
        
        response = self.client.query_resource(
            resource_id=self.resource_id,
            query=query,
            timespan=self.timespan,
        )
        
        if response.status != LogsQueryStatus.SUCCESS:
            raise RuntimeError(f"Query failed: {response.partial_error}")
        
        return self._parse_response(response)
    
    def _parse_response(self, response) -> list[TraceSpan]:
        """
        Parse the query response into TraceSpan objects.
        
        Args:
            response: LogsQueryResult from the query.
            
        Returns:
            List of TraceSpan objects.
        """
        spans = []
        
        for table in response.tables:
            # Handle both object columns (with .name) and string columns
            if table.columns and hasattr(table.columns[0], 'name'):
                columns = [col.name for col in table.columns]
            else:
                columns = list(table.columns)
            
            for row in table.rows:
                row_dict = dict(zip(columns, row))
                
                # Parse customDimensions
                custom_dims = row_dict.get("customDimensions", {})
                if isinstance(custom_dims, str):
                    try:
                        custom_dims = json.loads(custom_dims)
                    except json.JSONDecodeError:
                        custom_dims = {}
                
                span = TraceSpan(
                    timestamp=row_dict.get("timestamp"),
                    operation_id=row_dict.get("operation_Id", ""),
                    span_id=row_dict.get("id", ""),
                    name=row_dict.get("name", ""),
                    target=row_dict.get("target", ""),
                    duration=row_dict.get("duration", 0),
                    custom_dimensions=custom_dims,
                    raw_row=row_dict,
                )
                spans.append(span)
        
        return spans
    
    def get_unique_operation_names(self, spans: list[TraceSpan]) -> list[str]:
        """Get unique operation names from spans."""
        return list(set(
            span.custom_dimensions.get("gen_ai.operation.name", span.name)
            for span in spans
        ))
    
    def get_agent_spans(self, spans: list[TraceSpan]) -> list[TraceSpan]:
        """Filter to only agent invocation spans."""
        return [
            span for span in spans
            if span.custom_dimensions.get("gen_ai.operation.name") == "invoke_agent"
        ]
    
    def get_tool_spans(self, spans: list[TraceSpan]) -> list[TraceSpan]:
        """Filter to only tool execution spans."""
        return [
            span for span in spans
            if span.custom_dimensions.get("gen_ai.operation.name") == "execute_tool"
            or "gen_ai.tool.name" in span.custom_dimensions
        ]
    
    def get_chat_spans(self, spans: list[TraceSpan]) -> list[TraceSpan]:
        """Filter to only chat/LLM spans."""
        return [
            span for span in spans
            if span.custom_dimensions.get("gen_ai.operation.name") == "chat"
        ]
    
    def spans_to_dict(self, spans: list[TraceSpan]) -> list[dict[str, Any]]:
        """Convert spans to dictionaries for JSON serialization."""
        return [
            {
                "timestamp": span.timestamp.isoformat() if span.timestamp else None,
                "operation_id": span.operation_id,
                "span_id": span.span_id,
                "name": span.name,
                "target": span.target,
                "duration": span.duration,
                "custom_dimensions": span.custom_dimensions,
            }
            for span in spans
        ]
    
    def save_traces_to_file(
        self, 
        spans: list[TraceSpan], 
        file_path: str,
        format: str = "jsonl"
    ) -> None:
        """
        Save traces to a file.
        
        Args:
            spans: List of TraceSpan objects.
            file_path: Path to save the file.
            format: Output format ('jsonl' or 'json').
        """
        traces_dict = self.spans_to_dict(spans)
        
        with open(file_path, "w", encoding="utf-8") as f:
            if format == "jsonl":
                for trace in traces_dict:
                    f.write(json.dumps(trace, default=str) + "\n")
            else:
                json.dump(traces_dict, f, indent=2, default=str)
        
        print(f"Saved {len(spans)} traces to {file_path}")

# Copyright (c) Microsoft. All rights reserved.

"""
Tracing utilities for workflow test scenarios.

This module provides comprehensive tracing support for capturing workflow
execution traces that can be used for evaluation and dataset creation.

Features:
- Local file export (JSONL format) with full span attributes
- Azure Monitor integration (optional)
- Trace collection and management utilities
- Test result persistence for dataset creation
"""

import json


import os
from datetime import datetime
from pathlib import Path
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    SpanExportResult,
)


def get_trace_output_path(pattern_name: str, test_name: str) -> Path:
    """Generate a standardized output path for trace files."""
    current_file = Path(__file__).resolve()
    test_scenarios_dir = current_file.parent.parent
    data_dir = test_scenarios_dir / "data" / pattern_name
    data_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{test_name}_{timestamp}.jsonl"
    return data_dir / filename

# ============================================================================
# File Span Exporter
# ============================================================================


class FileSpanExporter(ConsoleSpanExporter):
    """
    Custom OpenTelemetry span exporter that writes comprehensive span data
    to a file in JSON Lines format.

    This exporter captures:
    - Full span context (trace_id, span_id, parent_id)
    - All span attributes including gen_ai.* attributes
    - Span events (logs within spans)
    - Span links (relationships to other spans)
    - Resource attributes (service name, SDK info)
    - Tool execution metadata
    """

    def __init__(self, file_path: str) -> None:
        """
        Initialize the file span exporter.

        Args:
            file_path: Path to the output file (will be created/cleared)
        """
        super().__init__()
        self.file_path = file_path
        self._init_file()

    def _init_file(self) -> None:
        """Initialize/clear the output file."""
        Path(self.file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.file_path, "w", encoding="utf-8") as f:
            f.write("")

    def set_output_file(self, file_path: str) -> None:
        """Switch to a new output file (clears the new file)."""
        self.file_path = file_path
        self._init_file()

    def export(self, spans) -> SpanExportResult:
        """
        Export spans to the file in JSON Lines format.

        Args:
            spans: Iterable of ReadableSpan objects

        Returns:
            SpanExportResult indicating success or failure
        """
        try:
            with open(self.file_path, "a", encoding="utf-8") as f:
                for span in spans:
                    span_dict = self._build_span_dict(span)
                    f.write(json.dumps(span_dict, default=str) + "\n")
            return SpanExportResult.SUCCESS
        except Exception as e:
            print(f"Error exporting spans: {e}")
            return SpanExportResult.FAILURE

    def _build_span_dict(self, span) -> dict[str, Any]:
        """
        Build a comprehensive dictionary representation of a span.

        Args:
            span: ReadableSpan object

        Returns:
            Dictionary with all span data
        """
        span_dict = {
            "name": span.name,
            "context": {
                "trace_id": format(span.context.trace_id, "032x"),
                "span_id": format(span.context.span_id, "016x"),
                "trace_state": str(span.context.trace_state) if span.context.trace_state else None,
            },
            "parent_id": format(span.parent.span_id, "016x") if span.parent else None,
            "start_time": span.start_time,
            "end_time": span.end_time,
            "status": {
                "status_code": span.status.status_code.name,
                "description": span.status.description,
            },
            "kind": span.kind.name if hasattr(span, "kind") else None,
            "attributes": {},
            "events": [],
            "links": [],
        }

        # Extract all span attributes
        if span.attributes:
            span_dict["attributes"].update(dict(span.attributes))

        # Extract resource attributes (service name, SDK info, etc.)
        if hasattr(span, "resource") and span.resource and hasattr(span.resource, "attributes"):
            for key, value in span.resource.attributes.items():
                span_dict["attributes"][f"resource.{key}"] = value

        # Extract events (logs within spans) - often contain tool execution details
        if hasattr(span, "events") and span.events:
            for event in span.events:
                event_dict = {
                    "name": event.name,
                    "timestamp": event.timestamp,
                    "attributes": dict(event.attributes) if event.attributes else {},
                }
                span_dict["events"].append(event_dict)

        # Extract tool execution metadata for tool spans
        if span.attributes and "gen_ai.tool.name" in span.attributes:
            tool_name = span.attributes.get("gen_ai.tool.name")
            tool_call_id = span.attributes.get("gen_ai.tool.call.id")
            span_dict["attributes"]["tool_execution"] = {
                "tool_name": tool_name,
                "tool_call_id": tool_call_id,
            }

        # Extract links (relationships to other spans)
        if hasattr(span, "links") and span.links:
            for link in span.links:
                link_dict = {
                    "context": {
                        "trace_id": format(link.context.trace_id, "032x"),
                        "span_id": format(link.context.span_id, "016x"),
                    },
                    "attributes": dict(link.attributes) if link.attributes else {},
                }
                span_dict["links"].append(link_dict)

        return span_dict


# ============================================================================
# Tracing Configuration
# ============================================================================

# Global reference to the single file exporter for dynamic file switching
_file_exporter: FileSpanExporter | None = None
_instrumentation_enabled: bool = False


def configure_tracing(
    output_file: str,
    enable_azure_monitor: bool = False,
    service_name: str = "workflow-test-scenarios",
) -> None:
    """
    Configure tracing with local file export and optional Azure Monitor.

    This function sets up:
    1. Azure Monitor export (optional, configured FIRST to set up TracerProvider)
    2. Local file export (always enabled, added to existing provider)
    3. Agent Framework instrumentation with sensitive data capture

    On subsequent calls, only switches the output file (avoids TracerProvider issues).

    Args:
        output_file: Path to the local trace file (JSONL format)
        enable_azure_monitor: Whether to also export to Azure Monitor
        service_name: Service name for trace attribution
    """
    global _file_exporter, _instrumentation_enabled

    # Import here to avoid circular imports and optional dependencies
    from agent_framework.observability import enable_instrumentation

    # First call: set up exporters
    if _file_exporter is None:
        # Configure Azure Monitor FIRST (it creates its own TracerProvider)
        if enable_azure_monitor:
            connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
            if connection_string:
                try:
                    from azure.monitor.opentelemetry import configure_azure_monitor
                    from agent_framework.observability import create_resource

                    configure_azure_monitor(
                        connection_string=connection_string,
                        resource=create_resource(),
                        enable_live_metrics=True,
                    )
                    print("Azure Monitor observability configured")
                except ImportError:
                    print("Warning: azure-monitor-opentelemetry not installed, skipping Azure Monitor")
            else:
                print("Warning: APPLICATIONINSIGHTS_CONNECTION_STRING not set, skipping Azure Monitor")

        # Now get the tracer provider (either Azure Monitor's or create new one)
        tracer_provider = trace.get_tracer_provider()
        if not isinstance(tracer_provider, TracerProvider):
            tracer_provider = TracerProvider()
            trace.set_tracer_provider(tracer_provider)

        # Add our file exporter to the existing provider
        _file_exporter = FileSpanExporter(output_file)
        file_processor = SimpleSpanProcessor(_file_exporter)
        tracer_provider.add_span_processor(file_processor)
    else:
        # Subsequent calls: just switch the output file
        _file_exporter.set_output_file(output_file)

    print(f"Local trace export configured to: {output_file}")

    # Enable Agent Framework instrumentation with sensitive data capture
    enable_instrumentation(enable_sensitive_data=True)
    print("Agent Framework instrumentation enabled (sensitive data capture: ON)")


# ============================================================================
# Trace Collection Utilities
# ============================================================================


class TraceCollector:
    """
    Utility class for collecting and managing traces during workflow execution.

    This class provides methods to:
    - Read traces from JSONL files
    - Filter traces by various criteria
    - Extract trace IDs for evaluation
    """

    def __init__(self, trace_file: str | None = None) -> None:
        """
        Initialize the trace collector.

        Args:
            trace_file: Path to the trace file (JSONL format). Optional.
        """
        self.trace_file = trace_file
        self._traces: list[dict[str, Any]] = []

    def load_traces(self) -> list[dict[str, Any]]:
        """
        Load traces from the file.

        Returns:
            List of trace dictionaries
        """
        self._traces = []
        try:
            with open(self.trace_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        self._traces.append(json.loads(line))
        except FileNotFoundError:
            print(f"Trace file not found: {self.trace_file}")
        return self._traces

    def get_unique_trace_ids(self) -> list[str]:
        """
        Get unique trace IDs from loaded traces.

        Returns:
            List of unique trace IDs
        """
        if not self._traces:
            self.load_traces()

        trace_ids = set()
        for span in self._traces:
            if "context" in span and "trace_id" in span["context"]:
                trace_ids.add(span["context"]["trace_id"])
        return list(trace_ids)

    def get_spans_by_name(self, name_pattern: str) -> list[dict[str, Any]]:
        """
        Get spans matching a name pattern.

        Args:
            name_pattern: Pattern to match against span names

        Returns:
            List of matching spans
        """
        if not self._traces:
            self.load_traces()

        return [span for span in self._traces if name_pattern in span.get("name", "")]

    def get_tool_execution_spans(self) -> list[dict[str, Any]]:
        """
        Get all tool execution spans.

        Returns:
            List of tool execution spans
        """
        if not self._traces:
            self.load_traces()

        return [
            span
            for span in self._traces
            if span.get("attributes", {}).get("gen_ai.operation.name") == "execute_tool"
            or "gen_ai.tool.name" in span.get("attributes", {})
        ]

    def get_agent_spans(self) -> list[dict[str, Any]]:
        """
        Get all agent execution spans.

        Returns:
            List of agent spans
        """
        if not self._traces:
            self.load_traces()

        return [
            span
            for span in self._traces
            if "gen_ai.agent.name" in span.get("attributes", {})
            or span.get("attributes", {}).get("gen_ai.operation.name") == "agent"
        ]

    def clear(self) -> None:
        """Clear all loaded traces from memory."""
        self._traces = []


# ============================================================================
# Test Result Persistence
# ============================================================================


def save_test_result(
    output_dir: str,
    test_name: str,
    pattern: str,
    traces: list[dict[str, Any]],
    workflow_output: Any,
    metadata: dict[str, Any] | None = None,
) -> str:
    """
    Save a test result for dataset creation.

    Args:
        output_dir: Directory for output files
        test_name: Name of the test case
        pattern: Workflow pattern (magentic, group_chat, handoff, etc.)
        traces: List of trace dictionaries
        workflow_output: Final output from the workflow
        metadata: Additional metadata about the test

    Returns:
        Path to the saved result file
    """
    # Ensure output directory exists
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Create result structure
    result = {
        "test_name": test_name,
        "pattern": pattern,
        "timestamp": datetime.now().isoformat(),
        "trace_count": len(traces),
        "trace_ids": list(set(
            span["context"]["trace_id"]
            for span in traces
            if "context" in span and "trace_id" in span["context"]
        )),
        "workflow_output": str(workflow_output) if workflow_output else None,
        "metadata": metadata or {},
    }

    # Save result metadata
    result_file = Path(output_dir) / f"{pattern}_{test_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)

    # Save traces separately
    traces_file = Path(output_dir) / f"{pattern}_{test_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_traces.jsonl"
    with open(traces_file, "w", encoding="utf-8") as f:
        for trace in traces:
            f.write(json.dumps(trace, default=str) + "\n")

    print(f"Test result saved: {result_file}")
    print(f"Traces saved: {traces_file}")

    return str(result_file)

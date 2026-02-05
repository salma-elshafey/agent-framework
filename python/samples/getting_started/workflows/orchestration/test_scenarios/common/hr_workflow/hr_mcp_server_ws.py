# Copyright (c) Microsoft. All rights reserved.

"""
HR MCP Server with WebSocket Transport.

This server provides the same HR research tools as hr_mcp_server.py but uses
WebSocket transport instead of stdio for testing MCPWebsocketTool.

Usage:
    python hr_mcp_server_ws.py [--port PORT]
    
Default port is 8082. The server will be available at ws://localhost:PORT/ws
"""

import argparse
import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.websocket import websocket_server
from mcp.types import TextContent, Tool

try:
    from starlette.applications import Starlette
    from starlette.routing import WebSocketRoute
    from starlette.websockets import WebSocket
    import uvicorn
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False
    print("Warning: Missing dependencies.")
    print("Install with: pip install starlette uvicorn")

# Import mock data from shared data module
from data import (
    EXTERNAL_JOB_BOARD_CANDIDATES,
    LINKEDIN_PROFILES,
    SALARY_DATA,
)

# Create the MCP server
server = Server("hr-research-mcp-ws")


# ============================================================================
# Tool Handlers
# ============================================================================


def search_linkedin_profiles_handler(
    skills: list[str],
    location: str | None = None,
    min_experience_years: int | None = None,
    open_to_work_only: bool = False,
) -> dict[str, Any]:
    """Search LinkedIn for candidate profiles matching criteria."""
    results = []
    skills_lower = [s.lower() for s in skills]

    for profile in LINKEDIN_PROFILES:
        profile_skills_lower = [s.lower() for s in profile["skills"]]
        if not any(skill in profile_skills_lower for skill in skills_lower):
            continue
        if location and location.lower() not in profile["location"].lower():
            continue
        if min_experience_years and profile["experience_years"] < min_experience_years:
            continue
        if open_to_work_only and not profile["open_to_work"]:
            continue

        matching_skills = [s for s in profile["skills"] if s.lower() in skills_lower]
        match_score = len(matching_skills) / len(skills) if skills else 0

        results.append({
            **profile,
            "matching_skills": matching_skills,
            "match_score": round(match_score, 2),
        })

    results.sort(key=lambda x: x["match_score"], reverse=True)

    return {
        "total_results": len(results),
        "profiles": results,
        "search_criteria": {
            "skills": skills,
            "location": location,
            "min_experience_years": min_experience_years,
            "open_to_work_only": open_to_work_only,
        },
    }


def get_market_salary_data_handler(job_title: str, location: str) -> dict[str, Any]:
    """Get market salary benchmarks for a job title and location."""
    title_key = job_title.lower().replace(" ", "_")
    location_key = location.lower().replace(",", "").replace(" ", "_")

    location_mapping = {
        "seattle_wa": "seattle",
        "san_francisco_ca": "san_francisco",
        "austin_tx": "austin",
        "boston_ma": "boston",
        "new_york_ny": "new_york",
        "nyc": "new_york",
        "sf": "san_francisco",
    }
    location_key = location_mapping.get(location_key, location_key)

    if title_key in SALARY_DATA:
        title_data = SALARY_DATA[title_key]
        if location_key in title_data:
            salary_info = title_data[location_key]
            return {
                "job_title": job_title,
                "location": location,
                "currency": "USD",
                "salary_percentiles": salary_info,
                "median_salary": salary_info["p50"],
                "salary_range": f"${salary_info['p25']:,} - ${salary_info['p75']:,}",
                "market_insights": {
                    "demand_level": "high" if salary_info["p50"] > 170000 else "moderate",
                    "yoy_growth": "5-8%",
                    "data_source": "Mock Market Data",
                    "last_updated": "2025-01-15",
                },
            }

    return {
        "job_title": job_title,
        "location": location,
        "error": "No salary data available for this job title and location combination",
        "available_titles": list(SALARY_DATA.keys()),
        "suggestion": "Try a more common job title or major metro area",
    }


def query_external_job_boards_handler(
    job_id: str | None = None,
    skills: list[str] | None = None,
    location: str | None = None,
    min_experience_years: int | None = None,
) -> dict[str, Any]:
    """Query external job boards for candidates."""
    results = []

    for candidate in EXTERNAL_JOB_BOARD_CANDIDATES:
        if job_id and job_id not in candidate["applied_jobs"]:
            continue
        if skills:
            skills_lower = [s.lower() for s in skills]
            candidate_skills_lower = [s.lower() for s in candidate["skills"]]
            if not any(skill in candidate_skills_lower for skill in skills_lower):
                continue
        if location and location.lower() not in candidate["location"].lower():
            continue
        if min_experience_years and candidate["years_experience"] < min_experience_years:
            continue

        results.append(candidate)

    results.sort(key=lambda x: x["years_experience"], reverse=True)

    return {
        "total_results": len(results),
        "candidates": results,
        "sources": list(set(c["source"] for c in results)),
        "search_criteria": {
            "job_id": job_id,
            "skills": skills,
            "location": location,
            "min_experience_years": min_experience_years,
        },
    }


# ============================================================================
# MCP Tool Definitions
# ============================================================================


def format_result_as_text(name: str, result: dict[str, Any]) -> str:
    """Format tool result as structured text instead of JSON."""
    if name == "search_linkedin_profiles":
        lines = [f"Total Results: {result['total_results']}", ""]
        for profile in result.get("profiles", []):
            lines.extend([
                f"Profile ID: {profile['profile_id']}",
                f"Name: {profile['name']}",
                f"Headline: {profile['headline']}",
                f"Location: {profile['location']}",
                f"Skills: {', '.join(profile['skills'])}",
                f"Experience Years: {profile['experience_years']}",
                f"Current Company: {profile['current_company']}",
                f"Education: {profile['education']}",
                f"Open to Work: {profile['open_to_work']}",
                f"Match Score: {profile['match_score']}",
                "",
            ])
        return "\n".join(lines)
    
    elif name == "query_external_job_boards":
        lines = [f"Total Results: {result['total_results']}", ""]
        for candidate in result.get("candidates", []):
            lines.extend([
                f"Candidate ID: {candidate['candidate_id']}",
                f"Source: {candidate['source']}",
                f"Name: {candidate['name']}",
                f"Email: {candidate['email']}",
                f"Phone: {candidate['phone']}",
                f"Skills: {', '.join(candidate['skills'])}",
                f"Years Experience: {candidate['years_experience']}",
                f"Education: {candidate['education']}",
                f"Current Company: {candidate['current_company']}",
                f"Current Title: {candidate['current_title']}",
                f"Location: {candidate['location']}",
                f"Visa Required: {candidate['visa_required']}",
                f"Salary Expectation: ${candidate['salary_expectation']:,}",
                f"Application Date: {candidate['application_date']}",
                f"Resume Summary: {candidate['resume_summary']}",
                "",
            ])
        return "\n".join(lines)
    
    elif name == "get_market_salary_data":
        if "error" in result:
            return f"Error: {result['error']}\nSuggestion: {result.get('suggestion', 'N/A')}"
        lines = [
            f"Job Title: {result['job_title']}",
            f"Location: {result['location']}",
            f"Currency: {result['currency']}",
            f"Median Salary: ${result['median_salary']:,}",
            f"Salary Range: {result['salary_range']}",
            "",
            "Salary Percentiles:",
            f"  P10: ${result['salary_percentiles']['p10']:,}",
            f"  P25: ${result['salary_percentiles']['p25']:,}",
            f"  P50: ${result['salary_percentiles']['p50']:,}",
            f"  P75: ${result['salary_percentiles']['p75']:,}",
            f"  P90: ${result['salary_percentiles']['p90']:,}",
        ]
        return "\n".join(lines)
    
    else:
        # Fallback for unknown tools or errors
        return json.dumps(result, indent=2)


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="search_linkedin_profiles",
            description="Search LinkedIn for candidate profiles matching specified skills, location, and experience criteria.",
            inputSchema={
                "type": "object",
                "properties": {
                    "skills": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of skills to search for",
                    },
                    "location": {"type": "string", "description": "Location to filter by"},
                    "min_experience_years": {"type": "integer", "description": "Minimum years of experience"},
                    "open_to_work_only": {"type": "boolean", "description": "Only open to work candidates", "default": False},
                },
                "required": ["skills"],
            },
        ),
        Tool(
            name="get_market_salary_data",
            description="Get market salary benchmarks for a job title in a specific location.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_title": {"type": "string", "description": "Job title to look up"},
                    "location": {"type": "string", "description": "Location for salary data"},
                },
                "required": ["job_title", "location"],
            },
        ),
        Tool(
            name="query_external_job_boards",
            description="Query external job boards for candidates who have applied to jobs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "Filter by specific job ID"},
                    "skills": {"type": "array", "items": {"type": "string"}, "description": "Skills to search for"},
                    "location": {"type": "string", "description": "Location to filter by"},
                    "min_experience_years": {"type": "integer", "description": "Minimum years of experience"},
                },
                "required": [],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    if name == "search_linkedin_profiles":
        result = search_linkedin_profiles_handler(
            skills=arguments.get("skills", []),
            location=arguments.get("location"),
            min_experience_years=arguments.get("min_experience_years"),
            open_to_work_only=arguments.get("open_to_work_only", False),
        )
    elif name == "get_market_salary_data":
        result = get_market_salary_data_handler(
            job_title=arguments.get("job_title", ""),
            location=arguments.get("location", ""),
        )
    elif name == "query_external_job_boards":
        result = query_external_job_boards_handler(
            job_id=arguments.get("job_id"),
            skills=arguments.get("skills"),
            location=arguments.get("location"),
            min_experience_years=arguments.get("min_experience_years"),
        )
    else:
        result = {"error": f"Unknown tool: {name}"}

    return [TextContent(type="text", text=format_result_as_text(name, result))]


# ============================================================================
# WebSocket Endpoint
# ============================================================================


async def handle_websocket(websocket: WebSocket):
    """Handle WebSocket connection for MCP."""
    async with websocket_server(websocket.scope, websocket.receive, websocket.send) as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def create_app() -> "Starlette":
    """Create the Starlette application with WebSocket MCP endpoint."""
    return Starlette(
        debug=True,
        routes=[
            WebSocketRoute("/ws", endpoint=handle_websocket),
        ],
    )


# ============================================================================
# Main Entry Point
# ============================================================================


if __name__ == "__main__":
    if not HAS_DEPS:
        print("Cannot start server - missing dependencies.")
        print("Install with: pip install starlette uvicorn")
        exit(1)
    
    parser = argparse.ArgumentParser(description="HR MCP Server with WebSocket transport")
    parser.add_argument("--port", type=int, default=8082, help="Port to listen on")
    args = parser.parse_args()
    
    port = args.port
    host = "0.0.0.0"
    
    print(f"Starting HR MCP Server (WebSocket) on port {port}")
    print(f"MCP endpoint: ws://localhost:{port}/ws")
    
    app = create_app()
    uvicorn.run(app, host=host, port=port)

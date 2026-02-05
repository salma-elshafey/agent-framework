# Copyright (c) Microsoft. All rights reserved.

"""
HR MCP Server with Streamable HTTP Transport.

This server provides the same HR research tools as hr_mcp_server.py but uses
streamable HTTP transport instead of stdio for testing MCPStreamableHTTPTool.

Usage:
    python hr_mcp_server_http.py [--port PORT]
    
Default port is 8080. The server will be available at http://localhost:PORT/mcp
"""

import argparse
import json
import os
from typing import Any, Annotated

from pydantic import Field

# Try to import FastMCP
try:
    from fastmcp import FastMCP
    HAS_FASTMCP = True
except ImportError:
    HAS_FASTMCP = False
    print("Warning: FastMCP not installed.")
    print("Install with: pip install fastmcp")

# Import mock data from shared data module
from data import (
    EXTERNAL_JOB_BOARD_CANDIDATES,
    LINKEDIN_PROFILES,
    SALARY_DATA,
)

# Create the FastMCP server
mcp = FastMCP("hr-research-mcp-http")


# ============================================================================
# Tool Handlers
# ============================================================================


@mcp.tool()
def search_linkedin_profiles(
    skills: Annotated[list[str], Field(description="List of skills to search for (e.g., ['Python', 'Azure'])")],
    location: Annotated[str | None, Field(description="Location to filter by (e.g., 'Seattle, WA')")] = None,
    min_experience_years: Annotated[int | None, Field(description="Minimum years of experience required")] = None,
    open_to_work_only: Annotated[bool, Field(description="Only return candidates marked as open to work")] = False,
) -> dict[str, Any]:
    """
    Search LinkedIn for candidate profiles matching specified skills, location, and experience criteria.
    Returns matching profiles with relevance scores.
    """
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


@mcp.tool()
def get_market_salary_data(
    job_title: Annotated[str, Field(description="Job title to look up (e.g., 'Senior Software Engineer')")],
    location: Annotated[str, Field(description="Location for salary data (e.g., 'Seattle', 'San Francisco')")],
) -> dict[str, Any]:
    """
    Get market salary benchmarks and percentiles for a job title in a specific location.
    Useful for compensation planning and offer calibration.
    """
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


@mcp.tool()
def query_external_job_boards(
    job_id: Annotated[str | None, Field(description="Filter by specific job ID (e.g., 'JOB-SWE-2025-001')")] = None,
    skills: Annotated[list[str] | None, Field(description="List of skills to search for")] = None,
    location: Annotated[str | None, Field(description="Location to filter by")] = None,
    min_experience_years: Annotated[int | None, Field(description="Minimum years of experience required")] = None,
) -> dict[str, Any]:
    """
    Query external job boards (Indeed, LinkedIn Jobs, Glassdoor, ZipRecruiter) for candidates
    who have applied to jobs. Returns candidate profiles with resume summaries and salary expectations.
    """
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
# Main Entry Point
# ============================================================================


if __name__ == "__main__":
    if not HAS_FASTMCP:
        print("Cannot start server - FastMCP not installed.")
        print("Install with: pip install fastmcp")
        exit(1)
    
    parser = argparse.ArgumentParser(description="HR MCP Server with HTTP transport")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    args = parser.parse_args()
    
    port = args.port
    host = "0.0.0.0"
    
    print(f"Starting HR MCP Server (Streamable HTTP) on port {port}")
    print(f"MCP endpoint: http://localhost:{port}/mcp")
    
    mcp.run(transport="http", host=host, port=port, path="/mcp", stateless_http=True)

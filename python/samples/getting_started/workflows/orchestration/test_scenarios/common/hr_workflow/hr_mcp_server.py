# Copyright (c) Microsoft. All rights reserved.

"""
HR MCP Server - Model Context Protocol server for HR research tools.

This server provides candidate research tools for testing MCP integration
in HR workflows. It returns predefined mock data for deterministic testing.

Tools:
- search_linkedin_profiles: Search for candidate profiles by skills/location
- get_market_salary_data: Get salary benchmarks for job titles
- query_external_job_boards: Query external job board applicants
- query_agency_candidates: Query recruitment agency candidate submissions

Usage:
    python hr_mcp_server.py
"""

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# Import mock data from shared data module
from data import (
    EXTERNAL_JOB_BOARD_CANDIDATES,
    LINKEDIN_PROFILES,
    SALARY_DATA,
)

# Create the MCP server
server = Server("hr-research-mcp")


# ============================================================================
# Tool Handlers
# ============================================================================


def search_linkedin_profiles_handler(
    skills: list[str],
    location: str | None = None,
    min_experience_years: int | None = None,
    open_to_work_only: bool = False,
) -> dict[str, Any]:
    """
    Search LinkedIn for candidate profiles matching criteria.

    Args:
        skills: List of skills to search for (matches if candidate has ANY of these)
        location: Optional location filter (partial match)
        min_experience_years: Minimum years of experience
        open_to_work_only: Only return candidates marked as open to work

    Returns:
        Dictionary with matching profiles and search metadata
    """
    results = []
    skills_lower = [s.lower() for s in skills]

    for profile in LINKEDIN_PROFILES:
        # Check skills (any match)
        profile_skills_lower = [s.lower() for s in profile["skills"]]
        if not any(skill in profile_skills_lower for skill in skills_lower):
            continue

        # Check location
        if location and location.lower() not in profile["location"].lower():
            continue

        # Check experience
        if min_experience_years and profile["experience_years"] < min_experience_years:
            continue

        # Check open to work
        if open_to_work_only and not profile["open_to_work"]:
            continue

        # Calculate skill match score
        matching_skills = [s for s in profile["skills"] if s.lower() in skills_lower]
        match_score = len(matching_skills) / len(skills) if skills else 0

        results.append(
            {
                **profile,
                "matching_skills": matching_skills,
                "match_score": round(match_score, 2),
            }
        )

    # Sort by match score descending
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


def get_market_salary_data_handler(
    job_title: str,
    location: str,
) -> dict[str, Any]:
    """
    Get market salary benchmarks for a job title and location.

    Args:
        job_title: Job title to look up (e.g., "Software Engineer", "Data Engineer")
        location: Location for salary data (e.g., "Seattle", "San Francisco")

    Returns:
        Dictionary with salary percentiles and market insights
    """
    # Normalize inputs
    title_key = job_title.lower().replace(" ", "_")
    location_key = location.lower().replace(",", "").replace(" ", "_")

    # Handle common location variations
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

    # Try to find matching salary data
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

    # Return not found response
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
    """
    Query external job boards (Indeed, LinkedIn Jobs, Glassdoor, etc.) for candidates.

    Args:
        job_id: Filter by specific job ID the candidates applied to
        skills: List of skills to search for (matches if candidate has ANY of these)
        location: Optional location filter (partial match)
        min_experience_years: Minimum years of experience

    Returns:
        Dictionary with matching candidates and search metadata
    """
    results = []

    for candidate in EXTERNAL_JOB_BOARD_CANDIDATES:
        # Filter by job_id if provided
        if job_id and job_id not in candidate["applied_jobs"]:
            continue

        # Filter by skills if provided
        if skills:
            skills_lower = [s.lower() for s in skills]
            candidate_skills_lower = [s.lower() for s in candidate["skills"]]
            if not any(skill in candidate_skills_lower for skill in skills_lower):
                continue

        # Filter by location if provided
        if location and location.lower() not in candidate["location"].lower():
            continue

        # Filter by experience if provided
        if min_experience_years and candidate["years_experience"] < min_experience_years:
            continue

        results.append(candidate)

    # Sort by years of experience descending
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
            description="Search LinkedIn for candidate profiles matching specified skills, location, and experience criteria. Returns matching profiles with relevance scores.",
            inputSchema={
                "type": "object",
                "properties": {
                    "skills": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of skills to search for (e.g., ['Python', 'Azure', 'Kubernetes'])",
                    },
                    "location": {
                        "type": "string",
                        "description": "Location to filter by (e.g., 'Seattle, WA')",
                    },
                    "min_experience_years": {
                        "type": "integer",
                        "description": "Minimum years of experience required",
                    },
                    "open_to_work_only": {
                        "type": "boolean",
                        "description": "Only return candidates marked as open to new opportunities",
                        "default": False,
                    },
                },
                "required": ["skills"],
            },
        ),
        Tool(
            name="get_market_salary_data",
            description="Get market salary benchmarks and percentiles for a job title in a specific location. Useful for compensation planning and offer calibration.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_title": {
                        "type": "string",
                        "description": "Job title to look up (e.g., 'Senior Software Engineer', 'Data Engineer')",
                    },
                    "location": {
                        "type": "string",
                        "description": "Location for salary data (e.g., 'Seattle', 'San Francisco, CA')",
                    },
                },
                "required": ["job_title", "location"],
            },
        ),
        Tool(
            name="query_external_job_boards",
            description="Query external job boards (Indeed, LinkedIn Jobs, Glassdoor, ZipRecruiter) for candidates who have applied to jobs. Returns candidate profiles with resume summaries and salary expectations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "Filter by specific job ID (e.g., 'JOB-SWE-2025-001')",
                    },
                    "skills": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of skills to search for (e.g., ['Python', 'Azure'])",
                    },
                    "location": {
                        "type": "string",
                        "description": "Location to filter by (e.g., 'Seattle, WA')",
                    },
                    "min_experience_years": {
                        "type": "integer",
                        "description": "Minimum years of experience required",
                    },
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
# Main Entry Point
# ============================================================================


async def main() -> None:
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

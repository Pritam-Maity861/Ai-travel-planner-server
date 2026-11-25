import os

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("flights")


@mcp.tool()
async def search_flights(dep_iata: str, arr_iata: str, limit: int = 10) -> dict:
    """Flights between two airports (IATA codes), e.g. CCU -> DXB. No fare data."""
    api_key = os.environ.get("AVIATIONSTACK_API_KEY", "")
    if not api_key:
        return {"error": "AVIATIONSTACK_API_KEY not configured"}

    async with httpx.AsyncClient(timeout=20) as client:
        try:
            resp = await client.get(
                "http://api.aviationstack.com/v1/flights",  # free plan is HTTP only
                params={
                    "access_key": api_key,
                    "dep_iata": dep_iata.upper(),
                    "arr_iata": arr_iata.upper(),
                    "limit": limit,
                },
            )
            data = resp.json()
        except Exception as exc:
            return {"error": f"Failed to fetch flights: {str(exc)}"}

    if "error" in data:
        return {"error": data["error"].get("message", "AviationStack API error"), "raw": data}

    flights = [
        {
            "airline": f.get("airline", {}).get("name") if f.get("airline") else "Unknown",
            "flight": f.get("flight", {}).get("iata") if f.get("flight") else "Unknown",
            "departure": f.get("departure", {}).get("scheduled") if f.get("departure") else None,
            "arrival": f.get("arrival", {}).get("scheduled") if f.get("arrival") else None,
        }
        for f in data.get("data", [])
    ]
    return {"dep": dep_iata.upper(), "arr": arr_iata.upper(), "flights": flights}


if __name__ == "__main__":
    mcp.run(transport="stdio")

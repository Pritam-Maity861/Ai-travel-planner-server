import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("weather")
GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


@mcp.tool()
async def get_forecast(city: str, days: int = 7) -> dict:
    """Daily weather forecast (max 16 days ahead) for a city."""
    async with httpx.AsyncClient(timeout=15) as client:
        geo_resp = await client.get(GEO_URL, params={"name": city, "count": 1})
        geo = geo_resp.json()
        if not geo.get("results"):
            return {"error": f"City not found: {city}"}
        place = geo["results"][0]
        resp = await client.get(
            FORECAST_URL,
            params={
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "forecast_days": max(1, min(days, 16)),
                "timezone": "auto",
            },
        )
        return {
            "city": place["name"],
            "country": place.get("country"),
            "daily": resp.json().get("daily", {}),
        }


if __name__ == "__main__":
    mcp.run(transport="stdio")

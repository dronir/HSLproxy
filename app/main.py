from os import stat_result
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
from string import Template
from itertools import islice
import logging
import aiohttp

app = FastAPI()

logging.basicConfig(level=logging.WARNING)


# First a simple ping endpoint that returns the current datetime in UTC


class PingReply(BaseModel):
    pong: datetime


@app.get('/', response_model=PingReply)
async def index():
    """Testing. Returns the current timestamp."""
    return {"pong": datetime.utcnow()}


# The actual endpoint for the departure proxy


class Settings:
    url = "https://api.digitransit.fi/routing/v1/routers/hsl/index/graphql"
    graphql_template = Template("""{  
  stops(name: "$stopname") {
    stoptimesWithoutPatterns(numberOfDepartures: $n_departures) {
      stop {name code}
      serviceDay
      scheduledDeparture
      realtimeDeparture
      trip {route {shortName}}
      headsign
    }
  }
}""")


class Departure(BaseModel):
    stop: str
    line: str
    destination: str
    scheduled: datetime
    estimated: Optional[datetime]


class DepartureList(BaseModel):
    departures: List[Departure]
    timestamp: Optional[datetime]


@app.get("/departures", response_model=DepartureList)
async def departure_proxy(stops: str, n: int = 5):
    """Get the next departures for the stops that match the given string.

    The search string `stops` can be a stop ID code (such as H3030)
    or a string that gets matched against stop names. For example,
    the string "malm" will match "Malmin asema", "Malmin tori" etc.

    The number `n` is the total number of results returned. The resulting
    departures will be sorted by the _real-time estimate_ of the departure time.
    """
    logging.debug(f"Request for {n} departures from: {stops}.")
    raw_data = await get_departures(stops, n)
    # TODO: Validate result based on HSL API schema?
    logging.debug(raw_data)
    try:
        return parse_json(raw_data, n)
    except HTTPException as E:
        raise E
    except Exception as E:
        logging.error(f"Parsing response from HSL API failed.")
        raise HTTPException(status_code=500, detail="Received response from HSL API but failed to parse it.")


async def get_departures(stops: str, n: int) -> dict:
    """Make HTTP request to the HSL API and return the result.
    """
    query = Settings.graphql_template.substitute(stopname=stops, n_departures=n)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(Settings.url,
                                    data=query,
                                    headers={"Content-Type": "application/graphql"}) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logging.error(f"HTTP error {response.status} when fetching data.")
                    raise HTTPException(status_code=502, 
                                        detail=f"Request to HSL API failed with code {response.status}.")
    except aiohttp.ClientConnectorError as E:
        logging.error(f"Error while retrieving data: {E}")
        raise HTTPException(status_code=500, detail="Unexpected error when fetching data from HSL.")


def parse_json(raw_data: dict, n: int) -> dict:
    """Parse JSON from HSL API into a DepartureResponse.
    """
    found_stops = raw_data["data"]["stops"]
    if len(found_stops) == 0:
        raise HTTPException(status_code=404, detail="No stops matching the query were found.")
    all_departures = []
    for stop in found_stops:
        all_departures += [single_departure(d) for d in stop["stoptimesWithoutPatterns"]]

    departures = list(islice(sorted(all_departures, key=lambda x: x["estimated"]), n))
    return {"departures": departures, "timestamp": datetime.utcnow()}


def single_departure(data: dict) -> dict:
    """Clean up a single departure from the HSL JSON.
    """
    scheduled, estimate = get_timestamps(data)
    stop_code = data["stop"]["code"]
    stop_name = data["stop"]["name"]
    return {"stop": f"{stop_code} {stop_name}",
            "line": data["trip"]["route"]["shortName"],
            "destination": data["headsign"],
            "scheduled": scheduled,
            "estimated": estimate
            }


def get_timestamps(departure):
    """Get scheduled/realtime departure datetimes from JSON.
    """
    day_start_unix = departure['serviceDay']
    scheduled_time = departure['scheduledDeparture']
    real_time = departure['realtimeDeparture']
    datetime_scheduled = datetime.utcfromtimestamp(day_start_unix + scheduled_time)
    datetime_realtime = datetime.utcfromtimestamp(day_start_unix + real_time)
    return datetime_scheduled, datetime_realtime
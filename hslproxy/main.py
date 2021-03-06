from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from datetime import datetime
from string import Template
from itertools import islice
from pprint import pformat
import os
import logging
import aiohttp

LOG_LEVEL_DICT = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR
}

env_log_level = os.environ.get("HSLPROXY_LOG_LEVEL", "WARNING")
actual_log_level = LOG_LEVEL_DICT.get(env_log_level, "WARNING")

log = logging.getLogger("HSLproxy")
log.setLevel(actual_log_level)
log.addHandler(logging.StreamHandler())

app = FastAPI()


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
    destination: Optional[str]
    scheduled: datetime
    estimated: datetime

    def __lt__(self, other: Departure):
        return self.estimated < other.estimated


class DepartureList(BaseModel):
    departures: List[Departure]
    timestamp: datetime


JsonLike = Dict[str, Any]


@app.get("/departures", response_model=DepartureList)
async def departure_proxy(stops: str, n: int = 5):
    """Get the next departures for the stops that match the given string.

    The search string `stops` can be a stop ID code (such as H3030)
    or a string that gets matched against stop names. For example,
    the string "malm" will match "Malmin asema", "Malmin tori" etc.

    The number `n` is the total number of results returned. The resulting
    departures will be sorted by the _real-time estimate_ of the departure.

    Note that all timestamps are in UTC.
    """
    log.debug(f"Request for {n} departures from: '{stops}'.")
    raw_data = await get_departures(stops, n)
    # TODO: Validate result based on HSL API schema?
    log.debug("HSL API returned the following:")
    log.debug(pformat(raw_data))
    try:
        return parse_json(raw_data, n)
    except HTTPException as E:
        raise E
    except Exception as E:
        log.error(f"Parsing response from HSL API failed: {E}")
        raise HTTPException(status_code=500,
                            detail="Received response from HSL API but failed to parse it.")


async def get_departures(stops: str, n: int) -> JsonLike:
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
                    log.error(f"HTTP error {response.status} when fetching data.")
                    raise HTTPException(status_code=502,
                                        detail=f"Request to HSL API failed with code {response.status}.")
    except aiohttp.ClientConnectorError as E:
        log.error(f"Error while retrieving data: {E}")
        raise HTTPException(status_code=500,
                            detail="Unexpected error when fetching data from HSL.")


def parse_json(raw_data: JsonLike, n: int) -> DepartureList:
    """Parse JSON from HSL API into a DepartureResponse.
    """
    found_stops = raw_data["data"]["stops"]
    all_departures = []
    for stop in found_stops:
        all_departures += [single_departure(d) for d in stop["stoptimesWithoutPatterns"]]

    departures = list(islice(sorted(all_departures), n))
    log.debug("Parsed the HSL data into the following output:")
    log.debug(pformat(departures))
    return DepartureList(departures=departures, timestamp=datetime.utcnow())


def single_departure(data: JsonLike) -> Departure:
    """Clean up a single departure from the HSL JSON.
    """
    scheduled = get_timestamp(data, "scheduledDeparture")
    estimated = get_timestamp(data, "realtimeDeparture")
    stop_code = data["stop"]["code"]
    stop_name = data["stop"]["name"]
    return Departure(stop=f"{stop_code} {stop_name}",
                     line=data["trip"]["route"]["shortName"],
                     destination=data["headsign"],
                     scheduled=scheduled,
                     estimated=estimated
                     )


def get_timestamp(departure: JsonLike, key: str) -> datetime:
    day_start_unix = departure['serviceDay']
    ts = departure[key]
    return datetime.utcfromtimestamp(day_start_unix + ts)

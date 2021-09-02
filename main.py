from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
from string import Template
from itertools import islice
import logging
import aiohttp

app = FastAPI()

logging.basicConfig(level=logging.DEBUG)


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
    UTC_offset = timedelta(hours=3)
    graphql_template = Template("""{  
  stops(name: "$stopname") {
    stoptimesWithoutPatterns(numberOfDepartures: $n_departures) {
      stop {name code}
      serviceDay
      scheduledDeparture
      realtimeDeparture
      trip {
        route {
          shortName
        }
      }
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
    if raw_data is None:
        return {"departures": []}
    logging.debug(raw_data)
    return parse_json(raw_data, n)


async def get_departures(stops: str, n: int) -> Optional[dict]:
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
                    return None
    except aiohttp.ClientConnectorError as E:
        logging.error(f"Error while retrieving data: {E}")
        return None


def parse_json(raw_data: dict, n: int) -> DepartureList:
    """Parse JSON from HSL API into a DepartureResponse."""
    found_stops = raw_data["data"]["stops"]
    if len(found_stops) == 0:
        return DepartureList.parse_obj({"departures": []})
    all_departures = []
    for stop in found_stops:
        all_departures += [single_departure(d) for d in stop["stoptimesWithoutPatterns"]]

    departures = list(islice(sorted(all_departures, key=lambda x: x["estimated"]), n))
    return DepartureList.parse_obj({"departures": departures})


def single_departure(data: dict):
    scheduled, realtime = get_timestamps(data)
    stop_code = data["stop"]["code"]
    stop_name = data["stop"]["name"]
    return {"scheduled": scheduled,
            "estimated": realtime,
            "destination": data["headsign"],
            "line": data["trip"]["route"]["shortName"],
            "stop": f"{stop_code} {stop_name}"
            }


def get_timestamps(departure):
    """Get scheduled/realtime departure datetimes from JSON.
    """
    day_start_unix = departure['serviceDay']
    scheduled_time = departure['scheduledDeparture']
    real_time = departure['realtimeDeparture']
    datetime_scheduled = datetime.utcfromtimestamp(day_start_unix + scheduled_time)
    datetime_realtime = datetime.utcfromtimestamp(day_start_unix + real_time)
    return datetime_scheduled + Settings.UTC_offset, datetime_realtime + Settings.UTC_offset

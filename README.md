
# HSL departure proxy

This is a simple web API for departures from public 
transportation stops in the greater Helsinki area.

You can make a request to this service with the name of a stop,
and it will call the official HSL API, get the next departures
from that stop and return them to you in a simple JSON format.

The list of departures contains the stop names, bus/tram/train
lines with their destinations, the scheduled departure time
and the real-time estimate for the actual departure time.

For example, a request to this API such as `/departures?stops=H3030&n=3`
will return something like:

```json
{
  "departures": [
    {
      "stop": "H3030 Sumatrantie",
      "line": "70",
      "destination": "Kamppi via Töölö",
      "scheduled": "2021-09-03T07:20:00",
      "estimated": "2021-09-03T07:20:23"
    },
    {
      "stop": "H3030 Sumatrantie",
      "line": "53",
      "destination": "Arabia",
      "scheduled": "2021-09-03T07:17:00",
      "estimated": "2021-09-03T07:21:11"
    },
    {
      "stop": "H3030 Sumatrantie",
      "line": "78",
      "destination": "Rautatientori via Sörnäinen(M)",
      "scheduled": "2021-09-03T07:23:00",
      "estimated": "2021-09-03T07:23:00"
    }
  ],
  "timestamp": "2021-09-03T07:19:02.108248"
}
```

Note that all timestamps returned are in UTC.


## Installation and usage

### Installation using Poetry

Running`poetry install` creates a virtualenv and installs
the dependencies.

### Running locally

Running `poetry run uvicorn main:app` in the `app/` directory starts
the service on the  local machine. Navigate to 
[http://127.0.0.1:8000/docs] to see the API documentation.

Setting the environment variable `HSLPROXY_LOG_LEVEL=DEBUG` will
enable more detailed logging.

### Deploy with Docker 

- Build the dockerfile with: `docker build -t hslproxy .`

- Run `docker run -d --name HSLproxy -p 8000:80 hslproxy`
  and the app should now be running on port 8000 of your Docker host.

- For debug output, add `--env HSLPROXY_LOG_LEVEL=DEBUG` to the command.
  You can examine the logs with `docker logs HSLproxy`.

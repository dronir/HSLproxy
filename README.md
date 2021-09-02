
# HSL departure proxy

This is a simple web API for departures from public 
transportation stops in the greater Helsinki area.

You can make a request to this service with the name of a stop,
and it will call the official HSL API, get the next departures
from that stop and return them to you in a simple JSON format.

## Installation and usage

### Installation using Pipenv

Running`pipenv install` creates a virtualenv and installs
the dependencies.

### Running locally

Running `pipenv run uvicorn main:app` starts the service on the
local machine. Navigate to [http://127.0.0.1:8000/docs]
to see the API documentation.

### Deploy with Docker

TODO.

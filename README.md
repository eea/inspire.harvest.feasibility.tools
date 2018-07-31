# Tools for the INSPIRE Data Harvesting Feasibility Study


## Availability monitor

Install the Python package requirements (requires Python 3.6+):

`pip install -r requirements.txt`

Start the monitor:

`python monitoring/availability.py --endpoints-csv data/endpoints.csv --output availability.csv --check-interval 10`

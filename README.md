# Tools for the INSPIRE Data Harvesting Feasibility Study


## Availability monitor

Install the Python package requirements (requires Python 3.6+):

`pip install -r requirements.txt`

Start the monitor:

`python monitoring/availability.py --endpoints-csv data/endpoints.csv --output availability.csv --check-interval 10`


## Performance Testing

A JMeter test plan for download services is available in the directory `performance`.

```
cd performance

# To test a single service URL: 
./test_download_svc.sh http://gis.tirol.gv.at/inspire/downloadservice/Natura2000_FFH_Richtlinie_ETRS89UTM32N.zip

# Run the test for all services listed in a file:
xargs -I {} ./test_download_svc.sh {} < ../data/endpoints.csv
```

# Tools for the INSPIRE Data Harvesting Feasibility Study


## Requirements:

- JMeter 4.0

- the Python tools require Python 3.6+. Install package requirements by running:

		pip install -r requirements.txt


## Availability Monitoring

The monitoring script ``monitoring/availability.py`` takes an input file containing one service URL per line:
  
	python monitoring/availability.py --endpoints-csv data/endpoints.csv --output availability.csv --check-interval 10


## Performance Testing

A JMeter test plan for download services, and several related utilities are available in the directory `performance`.
Recommended JVM memory settings for JMeter are:

	-Xms1g -Xmx4g -XX:MaxMetaspaceSize=1g   

Lower limits produced out of memory errors and heap dumps for some of the services tested.


### Preparing test data

Prepare a list of the services to undergo testing, in a tab-separated CSV file with fields: country code, service type, service URL.

Service types are abbreviated as follows:
 
	Get Download Service Metadata = GDSM	
	Describe Spatial Data Set = DSDS
	Get Spatial Data Set = GSDS 

E.g.:
 
	AT	GDSM	https://gis.tirol.gv.at/inspire/downloadservice/DownloadServiceFeed.xml

Since JMeter expects the scheme, port, host and path as distinct parameters, we process the initial CSV to split the URL's into the respective segments, and assign each service a UUID4:

	cd performance	
	python parse_service_targets.py ../data/performance_service_targets.csv

Processed data is output to CSV file named ``performance_service_targets_parsed.csv``, with records like: 

	AT	GDSM	7e87dfd3665a4231b669d174d986d5c9	https	gis.tirol.gv.at	443	/inspire/downloadservice/DownloadServiceFeed.xml
 
Notes:
 - make sure there is an empty last line in the file, otherwise the last service won't be tested.
 - you can comment lines in the CSV file with ``#`` to skip testing the respective services.


### Test execution

Start the tests using the test runner script:
 
	./test_download_svc.sh ../data/performance_service_targets_parsed.csv


For each service listed in the CSV file, the test runner will:
- create a results directory in ``performance/results/<country code>/<service UUID>``, e.g.:


	AT/0f8114070b2c493dbd921c6c1f939f9d/

- create a metadata.json file with fields ``country_code``, ``service_type``, ``url`` 
- run JMeter in non-GUI mode with the test plan ``test_download_svc.jmx``
- produce the HTML dashboard report
- run the JMeter plugins ``AggregateReport`` and ``LatenciesOverTime``


### Test artifacts

After the tests, each service results directory will contain the following:

    html_reports/   <- HTML dashboard report directory
        ...
        index.html  <- dashboard landing page
    aggregate.csv   <- statistics
    latency.csv     <- non-aggregated latency data 
    results         <- raw JMeter output
    metadata.json   <- JSON document with fields: "country_code", "service_type", "url"
	        

When all tests are completed, a HTML dashboard collating all results can be produced: 

	pyhon index_results.py results

Latency data, only available in raw form until this stage, is also aggregated while collecting the results.  	
The output file is ``results/index.html``, which contains statistics for each tested service, grouped by country and service type.

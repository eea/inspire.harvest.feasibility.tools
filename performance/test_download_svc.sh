#!/usr/bin/env bash

function run_jmeter() {
	jmeter -n -t test_download_svc.jmx \
		-Jusers=11 \
		-Jrampup=60 \
		-Jduration=300 \
		-Jproto=$1 \
		-Jhost=$2 \
		-Jport=$3 \
		-Jpath=$4 \
		-l $5/results -e -o $5/html_reports
}

OLDIFS=$IFS
IFS=$'\t'
while read COUNTRY_CODE SERVICE_TYPE URL_HASH SCHEME HOST PORT RPATH
do
	URL="${SCHEME}://${HOST}${RPATH//[$'\t\r\n ']}"
	if [ "${COUNTRY_CODE:0:1}" = "#" ]
	then
		echo "Skipping ${URL}"
	else
		NOTIFY="
		Test parameters
		===============
		Country      : ${COUNTRY_CODE}
		Service type : ${SERVICE_TYPE}
		URL hash     : ${URL_HASH}
		Scheme       : ${SCHEME}
		Host         : ${HOST}
		Port         : ${PORT}
		Path         : ${RPATH//[$'\t\r\n ']}
		"
		NOTIFY="${NOTIFY//[$'\t']}"
		echo $NOTIFY

		RESULTS_DIR=results/${COUNTRY_CODE}/${URL_HASH}
		mkdir -p ${RESULTS_DIR}

		METADATA="
		{
		    \"country_code\": \""${COUNTRY_CODE}"\",
		    \"service_type\": \""${SERVICE_TYPE}"\",
		    \"url\": \""${URL}"\"
		}
		"
		METADATA="${METADATA//[$'\t']}"
		echo $METADATA > ${RESULTS_DIR}/metadata.json

		run_jmeter $SCHEME $HOST $PORT $RPATH $RESULTS_DIR
	fi
done < $1
IFS=${OLDIFS}

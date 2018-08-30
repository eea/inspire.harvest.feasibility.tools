#!/usr/bin/env bash

# Extract the protocol
PROTO="$(echo $1 | grep :// | sed -e's,^\(.*://\).*,\1,g')"

# Remove the protocol
URL="$(echo ${1/$PROTO/})"

# Strip the :// from the protocol
PROTO="$(echo ${PROTO} | sed -e's,^\(.*\)://.*,\1,g')"

# Extract the user, if any
USERPASS="$(echo ${URL} | grep @ | cut -d@ -f1)"
PASS="$(echo ${USERPASS} | grep : | cut -d: -f2)"

if [ -n "$PASS" ]; then
  USER="$(echo ${USERPASS} | grep : | cut -d: -f1)"
else
  USER=${USERPASS}
fi

# Extract the host
HOST="$(echo ${URL/$USER@/} | cut -d/ -f1)"
PORT="$(echo ${HOST} | sed -e 's,^.*:,:,g' -e 's,.*:\([0-9]*\).*,\1,g' -e 's,[^0-9],,g')"

if [ -z "$PORT" ]; then
	if [ ${PROTO}="https" ]; then
		PORT=443
	else
		PORT=80
	fi
fi

# Extract the path, if any
RPATH="$(echo ${URL} | grep / | cut -d/ -f2-)"

RESULTS_DIR=results/${HOST}/${RPATH}
mkdir -p ${RESULTS_DIR}

echo "Testing $1"
echo "  proto: $PROTO"
echo "   user: $USER"
echo "   pass: $PASS"
echo "   host: $HOST"
echo "   port: $PORT"
echo "   path: $RPATH"

jmeter -n -t test_download_svc.jmx \
	-Jusers=11 \
	-Jrampup=60 \
	-Jduration=300 \
	-Jproto=${PROTO} \
	-Jhost=${HOST} \
	-Jport=${PORT} \
	-Jpath=${RPATH} \
	-l ${RESULTS_DIR}/results -e -o ${RESULTS_DIR}/html_reports

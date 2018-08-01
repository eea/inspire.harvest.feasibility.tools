#!/bin/sh

if [ -z "$AVAILABILITY_CHECK_INTERVAL" ]; then
  export AVAILABILITY_CHECK_INTERVAL=300
fi

case "$1" in
    run)
        exec python monitoring/availability.py \
            --endpoints-csv data/endpoints.csv \
            --output data/$(date +%Y%m%d_%H%M%S)_availability.csv \
            --check-interval ${AVAILABILITY_CHECK_INTERVAL}
        ;;
    *)
esac

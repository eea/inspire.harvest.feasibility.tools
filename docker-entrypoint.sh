#!/bin/sh

if [ -z "CHECK_INTERVAL" ]; then
  export CHECK_INTERVAL=300
fi

case "$1" in
    availability)
        exec python monitoring/availability.py \
            --endpoints-csv data/availability_service_targets.csv \
            --output out/availability_$(date +%Y%m%d_%H%M%S).csv \
            --check-interval ${CHECK_INTERVAL}
        ;;
    reliability)
        exec python monitoring/reliability.py \
            --endpoints-csv data/reliability_service_targets.csv \
            --output out/reliability_$(date +%Y%m%d_%H%M%S) \
            --check-interval ${CHECK_INTERVAL}
        ;;
    *)
esac

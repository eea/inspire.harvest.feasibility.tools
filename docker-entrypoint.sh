#!/bin/sh

if [ -z "$CHECK_NAME" ]; then
  echo "CHECK_NAME is undefined"
  exit 1
fi

if [ -z "$AVAILABILITY_CHECK_INTERVAL" ]; then
  export AVAILABILITY_CHECK_INTERVAL=300
fi


case "$1" in
    run)
        exec python monitoring/${CHECK_NAME}.py \
            --endpoints-csv data/monitoring_targets.csv \
            --output out/${CHECK_NAME}_$(date +%Y%m%d_%H%M%S).csv \
            --check-interval ${AVAILABILITY_CHECK_INTERVAL}
        ;;
    *)
esac

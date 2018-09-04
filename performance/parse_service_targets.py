import argparse
import csv
from uuid import uuid4
from pathlib import Path
from urllib.parse import urlsplit


if __name__ == "__main__":
    parser = argparse.ArgumentParser("""
        Parse service URL's for JMeter usage, takes in a CSV file with fields:
         Country Code | Service Type | URL
        and outputs a CSV file with fields:
         Country Code | Service Type | URL hash | scheme | host | port | path
         
        The output file is written to the same path as the input file, and appends '_parsed' to the name.  
    """)
    parser.add_argument("source_csv", help="Path to CSV file ")
    args = parser.parse_args()
    with open(args.source_csv) as f:
        reader = csv.reader(f, delimiter="\t")
        targets = []
        for row in reader:
            country_code, service_type, url = row
            if country_code.startswith == "#":
                continue
            parts = urlsplit(url)
            proto, host, path, query, fragment = parts
            targets.append([country_code, service_type, uuid4().hex, parts])

    source_path = Path(args.source_csv)
    output_fname = f"{source_path.stem}_parsed{source_path.suffix}"
    output_path = source_path.parent / output_fname

    with open(output_path, 'w') as f:
        writer = csv.writer(f, delimiter="\t")
        for t in targets:
            url_parts = t[3]
            if url_parts.query != "":
                path = f"{url_parts.path}?{url_parts.query}"
            else:
                path = url_parts.path

            if url_parts.port is not None:
                port = url_parts.port
            elif url_parts.scheme == "http":
                port = 80
            else:
                port = 443

            _t = t[:3] + [url_parts.scheme, url_parts.hostname, port, path]
            writer.writerow(_t)

    print(f"Done - parsed targets written to:\n{output_path}")

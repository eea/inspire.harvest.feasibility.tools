import os
import argparse
import csv
from pathlib import Path
import json
from jinja2 import Environment, FileSystemLoader
import pycountry


SERVICE_TYPES = {
    "GDSM": "Get Download Service Metadata",
    "DSDS": "Describe Spatial Data Set",
    "GSDS": "Get Spatial Data Set",
}


def get_country_dirs(root_dir):
    return Path(root_dir).glob("[A-Z][A-Z]")


def get_test_dirs(root_dir):
    return [p for p in Path(root_dir).glob("*") if p.is_dir()]


def render_template(template_path, context):
    env = Environment(loader=FileSystemLoader(str(template_path.parent)))
    return env.get_template(str(template_path)).render(context)


def write_index(results, template_path, output_dir):
    with open(output_dir / "index.html", "w") as fh:
        html = render_template(
            template_path, {"results": results, "service_types": SERVICE_TYPES}
        )
        fh.write(html.strip())


def reversed_blocks(file, blocksize=4096):
    """Generate blocks of file's contents in reverse order."""
    file.seek(0, os.SEEK_END)
    here = file.tell()
    while 0 < here:
        delta = min(blocksize, here)
        here -= delta
        file.seek(here, os.SEEK_SET)
        yield file.read(delta)


def reversed_lines(file):
    """Generate the lines of file in reverse order."""
    part = ""
    quoting = False
    for block in reversed_blocks(file):
        for c in reversed(block):
            if c == '"':
                quoting = not quoting
            elif c == "\n" and part and not quoting:
                yield part[::-1]
                part = ""
            part += c
    if part:
        yield part[::-1]


def get_stats(csv_path):
    if not Path(csv_path).exists():
        return {}
    with open(csv_path) as csvf:
        reader = csv.reader(reversed_lines(csvf), delimiter=",")
        last_row = next(reader)
    headers = [
        ("label", str),
        ("samples", int),
        ("avg", float),
        ("med", float),
        ("90pct", float),
        ("95pct", float),
        ("99pct", float),
        ("min", float),
        ("max", float),
        ("error_rate", str),
        ("throughput", float),
        ("received_kbps", float),
        ("std_dev", float)
    ]
    return {h[0]: h[1](last_row[i]) for i, h in enumerate(headers)}


def get_latency(csv_path):
    if not Path(csv_path).exists():
        return None
    with open(csv_path) as csvf:
        reader = csv.DictReader(csvf)
        latencies = [float(r["HTTP Request"]) for r in reader]
        return round(sum(latencies) / 1000.0 / len(latencies), 2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        "Walks through a results directory and builds a HTML index file"
    )
    parser.add_argument("results_path", default="results")
    parser.add_argument("-t", "--template", default="index_template.html")
    args = parser.parse_args()

    data = {}
    for country_dir in sorted(get_country_dirs(args.results_path)):
        country_code = country_dir.name
        try:
            country = pycountry.countries.lookup(country_code).name
        except LookupError:
            country = "Unknown"
        data[country_code] = {
            "country_name": country,
            "service_types": {t: [] for t in SERVICE_TYPES},
        }
        for test_dir in get_test_dirs(country_dir):
            try:
                with open(test_dir / "metadata.json", "r") as f:
                    metadata = json.load(f)
                    stats = get_stats(str(test_dir / "aggregate.csv"))
                    stats["latency"] = get_latency(str(test_dir / "latency.csv"))
                    data[country_code]["service_types"][
                        metadata["service_type"]
                    ].append(
                        {
                            "test_dir": str(Path(*test_dir.parts[1:])),
                            "url": metadata["url"],
                            "stats": stats,
                        }
                    )
            except FileNotFoundError:
                print(f"Missing metadata file in {str(test_dir)}")

    write_index(data, Path(args.template), Path(args.results_path))

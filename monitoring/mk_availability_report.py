import csv
import argparse
from datetime import datetime
from collections import defaultdict
from pathlib import Path

import attr
from jinja2 import Environment, FileSystemLoader
import pytz
import pandas
import pdfkit
import pycountry

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick


SERVICE_TYPES = {
    "GDSM": "Get Download Service Metadata",
    "DSDS": "Describe Spatial Data Set",
    "GSDS": "Get Spatial Data Set",
}


def to_int(value):
    try:
        return int(value)
    except ValueError:
        return None


def to_float(value):
    try:
        return float(value)
    except ValueError:
        return None


def to_str(value):
    try:
        return str(value)
    except ValueError:
        return None


def to_bool(value):
    try:
        return bool(int(value))
    except ValueError:
        return None


def to_date(value):
    try:
        return datetime.strptime(value[:26], "%Y-%m-%dT%H:%M:%S.%f").replace(
            tzinfo=pytz.UTC
        )
    except ValueError:
        return None


@attr.s
class AvailabilityCheck:
    ts = attr.ib(converter=to_date)
    url_id = attr.ib(converter=to_int)
    status_code = attr.ib(converter=to_int)
    content_length = attr.ib(converter=to_int)
    content_type = attr.ib(converter=to_str)
    duration = attr.ib(converter=to_float)
    last_modified = attr.ib(converter=to_str)
    timed_out = attr.ib(converter=to_bool)
    connection_error = attr.ib(converter=to_bool)


def get_services(csv_path):
    data = defaultdict(lambda: defaultdict(list))
    indexed_data = {}
    index = 0
    with open(csv_path) as csv_file:
        reader = csv.reader(csv_file, delimiter="\t")
        for r in reader:
            data[r[0]][r[1]].append(r[2])
            indexed_data[r[2]] = index
            index += 1
    return data, indexed_data


def load_data(csv_path):
    data = defaultdict(list)
    with open(csv_path) as f:
        reader = csv.reader(f, delimiter="\t")
        for r in reader:
            data[int(r[1])].append(AvailabilityCheck(*r))
    return data


def stats(observations):
    oks = len([o for o in observations if o.status_code == 200])
    return float(oks) / len(observations)


def plot_availability(observations, suffix, root_dir):
    print(f"Rendering chart for id {suffix} ...")
    raw = pandas.DataFrame(index=[o.ts for o in observations])
    raw["available"] = [1 if o.status_code == 200 else 0 for o in observations]
    raw["time_out"] = [o.timed_out for o in observations]
    raw["conn_error"] = [o.connection_error for o in observations]

    hourly = pandas.DataFrame()
    hourly["available"] = raw.available.resample("H").mean()
    hourly["time_out"] = raw.time_out.resample("H").mean()
    hourly["conn_error"] = raw.conn_error.resample("H").mean()

    fig, ax1 = plt.subplots()

    ax1.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))

    plt.xticks(rotation=45)    

    plot_avail, = ax1.plot(hourly.index, hourly.available, color="green", label="available")
    plot_time_out, = ax1.plot(hourly.index, hourly.time_out, color="pink", label="time out")
    plot_conn_err, = ax1.plot(hourly.index, hourly.conn_error, color="red", label="connection error")

    axes = plt.gca()
    axes.set_ylim([0, 1.1])

    plt.legend(
        handles=[
            plot_avail, 
            plot_time_out, 
            plot_conn_err
        ],
        bbox_to_anchor=(0., 1.02, 1., .102), loc=3,
        ncol=3, mode="expand", borderaxespad=0.
        )

    ax1.fill_between(hourly.index, hourly.available, color="green", alpha=.1)

    plt.savefig(f"{root_dir}/availability_{suffix}.png", bbox_inches="tight")
    plt.close()
 

if __name__ == "__main__":
    parser = argparse.ArgumentParser("Availability report builder")
    parser.add_argument("-s", "--services-csv")
    parser.add_argument("-r", "--results-csv")
    parser.add_argument("-g", "--make-graphs", action="store_true", default=False)
    args = parser.parse_args()

    report_dir = Path("availability_report")
    report_dir.mkdir(exist_ok=True)
    graphs_dir = report_dir / "img"
    if args.make_graphs:
        graphs_dir.mkdir(exist_ok=True)

    data = load_data(args.results_csv)
    stats = []

    for url_id in sorted(data.keys()):
        if args.make_graphs:                    
            plot_availability(data[url_id], suffix=url_id, root_dir=str(graphs_dir))
        availability = len([o for o in data[url_id] if o.status_code == 200]) / float(len(data[url_id]))
        stats.append(availability)

    country_services, indexed_services = get_services(args.services_csv)

    countries = {}
    for country_code in country_services:
        try:
            country = pycountry.countries.lookup(country_code).name
        except LookupError:
            country = f"Unknown ({country_code})"
        countries[country_code] = country

    report_data = {
        "countries": countries,
        "country_services": country_services,
        "indexed_services": indexed_services,
        "stats": stats,
        "service_types": SERVICE_TYPES,
    }
    template_path = Path("availability_template.html")
    template_env = Environment(loader=FileSystemLoader(str(template_path.parent)))
    report_content = template_env.get_template(str(template_path)).render(report_data)
    with open(report_dir / "availability_report.html", "w") as f:
        f.write(report_content.strip())

    pdf_options = {
        "page-size": "A4",
        # "dpi": 300,
        "orientation": "Landscape",
        "encoding": "utf-8",
        "margin-top": "0.5cm",
        "margin-bottom": "0.5cm",
        "margin-left": "0cm",
        "margin-right": "0cm",
    }

    pdfkit.from_file(
        str(report_dir / "availability_report.html"), str(report_dir / "availability_report.pdf"),
        options=pdf_options
    )

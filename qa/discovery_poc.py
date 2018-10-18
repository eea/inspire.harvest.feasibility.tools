import argparse
from pathlib import Path

import logme

from qa.common import load_urls, fetch_url, find_files, get_tree_from_file

from qa.gemet import check_gemet_thesaurus, check_ps_keyword


from qa.inspire import (
    WFS_PROTO,
    check_priority_ds_thesaurus,
    check_n2k_keywords,
    get_online_resources,
    check_supported_protocols,
    check_list_stored_queries_support,
    check_n2k_stored_query_exists,
    get_n2k_spatial_data,
)

from qa.etf import check_md_conformance


log = logme.log(scope="module", name="inspire_qa")

DEFAULT_ETF_CHECK_INTERVAL = 30
DEFAULT_ETF_TEST_TIMEOUT = 180


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--urls-csv")
    parser.add_argument("--files-path", default=Path.cwd())
    parser.add_argument("--etf-url")
    parser.add_argument("--etf-timeout", default=DEFAULT_ETF_TEST_TIMEOUT)
    parser.add_argument("--etf-interval", default=DEFAULT_ETF_CHECK_INTERVAL)
    args = parser.parse_args()

    urls = {}
    files = {}

    if args.urls_csv is not None:
        urls = load_urls(args.metadata_urls)
    else:
        files = find_files(args.files_path)

    if not urls and not files:
        log.error("No metadata URL or file could be found")
        exit(1)

    countries = urls.keys() or files.keys()

    previous_country_name = None
    previous_status = None

    for country in countries:
        if previous_country_name is not None and previous_status is not None:
            log.info(f"OVERALL {previous_country_name} TESTS RESULT: {previous_status}")
            log.info("=" * 80)

        try:
            country_name = country.official_name
        except AttributeError:
            country_name = country.name

        previous_country_name, previous_status = country_name, "FAILED"

        if urls:
            url = urls[country]

            log.info(f"Processing {country_name} metadata from {url}")
            dataset_metadata_path, _ = fetch_url(
                url, save_as=f"{country.alpha_2}_dataset_metadata.xml"
            )
            if dataset_metadata_path is None:
                log.info(f"Stopping - no metadata available from {url}")
                continue
        else:
            dataset_metadata_path = files[country]

        if args.etf_url is not None:
            if not check_md_conformance(
                args.etf_url,
                dataset_metadata_path,
                check_interval=args.etf_interval,
                timeout=args.etf_timeout,
            ):
                continue
        else:
            log.info(f"Skipping ETF metadata interoperability conformance test.")

        dataset_metadata_tree = get_tree_from_file(dataset_metadata_path)
        if dataset_metadata_tree is None:
            log.error(
                f"XML syntax error while parsing {dataset_metadata_path}"
                f" - resource may have been removed by the INSPIRE Geoportal"
            )
            continue

        nsmap = dataset_metadata_tree.getroot().nsmap

        extr_ns = {
            "gmd": "http://www.isotc211.org/2005/gmd",
            "gco": "http://www.isotc211.org/2005/gco",
            "gmx": "http://www.isotc211.org/2005/gmx",
            "gml": "http://www.opengis.net/gml",
            "xlink": "http://www.w3.org/1999/xlink",
        }

        nsmap.update(extr_ns)

        if not check_gemet_thesaurus(dataset_metadata_tree, nsmap=nsmap):
            # continue
            pass

        if not check_ps_keyword(dataset_metadata_tree, nsmap=nsmap):
            # continue
            pass

        if not check_priority_ds_thesaurus(dataset_metadata_tree, nsmap=nsmap):
            # continue
            pass

        if not check_n2k_keywords(dataset_metadata_tree, nsmap=nsmap):
            continue

        log.info(f"Testing resource protocols & links ...")
        resources = get_online_resources(dataset_metadata_tree, nsmap=nsmap)
        if not resources:
            continue

        if not check_supported_protocols(resources.keys()):
            continue

        log.info(f"Testing ListStoredQueries support at {resources[WFS_PROTO]} ...")
        stored_queries_base_url = check_list_stored_queries_support(
            resources[WFS_PROTO]
        )
        if stored_queries_base_url is None:
            continue

        log.info("Testing for Natura2000 stored query ...")
        if not check_n2k_stored_query_exists(stored_queries_base_url):
            continue

        log.info("Getting Natura2000 spatial data from stored query ...")
        spatial_data_path = get_n2k_spatial_data(country.alpha_2, resources[WFS_PROTO])

        if spatial_data_path is None:
            continue

        previous_status = "PASSED"


if __name__ == "__main__":
    main()

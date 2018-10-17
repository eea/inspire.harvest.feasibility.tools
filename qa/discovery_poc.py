import argparse
import logme

from qa.common import load_urls, fetch_url, get_tree_from_file

from qa.gemet import check_gemet_thesaurus, check_ps_keyword


from qa.inspire import (
    WFS_PROTO,
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
    parser.add_argument("metadata_urls")
    parser.add_argument("--etf-url")
    parser.add_argument("--etf-timeout", default=DEFAULT_ETF_TEST_TIMEOUT)
    parser.add_argument("--etf-interval", default=DEFAULT_ETF_CHECK_INTERVAL)
    args = parser.parse_args()

    urls = load_urls(args.metadata_urls)

    previous_country_name = None
    previous_status = None

    for url_data in urls:
        if previous_country_name is not None and previous_status is not None:
            log.info(f"OVERALL {previous_country_name} TESTS RESULT: {previous_status}")
            log.info("=" * 80)

        country, url = url_data
        try:
            country_name = country.official_name
        except AttributeError:
            country_name = country.name

        previous_country_name, previous_status = country_name, "FAILED"

        log.info(f"Processing {country_name} metadata from {url}")
        dataset_metadata_path, _ = fetch_url(
            url, save_as=f"{country.alpha_2}_dataset_metadata.xml"
        )
        if dataset_metadata_path is None:
            log.info(f"Stopping - no metadata available from {url}")
            continue

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

        if not check_gemet_thesaurus(dataset_metadata_tree, nsmap=nsmap):
            continue

        if not check_ps_keyword(dataset_metadata_tree, nsmap=nsmap):
            continue

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

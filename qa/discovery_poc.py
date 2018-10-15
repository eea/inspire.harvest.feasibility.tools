import argparse
import logme

from qa.common import (
    load_urls,
    fetch_url,
    get_tree_from_file,
)

from qa.gemet import (
    check_gemet_thesaurus,
    check_ps_keyword,
)


from qa.inspire import (
    WFS_PROTO,
    check_n2k_keywords,
    get_online_resources,
    check_supported_protocols,
    check_list_stored_queries_support,
    check_n2k_stored_query_exists,
    get_n2k_spatial_data,
)


log = logme.log(scope='module', name='inspire_qa')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("metadata_urls")
    args = parser.parse_args()

    urls = load_urls(args.metadata_urls)

    for url_data in urls:
        country, url = url_data
        log.info(f"Processing {country.name} metadata from {url}")
        dataset_metadata_path, _ = fetch_url(url, save_as=f"{country.alpha_2}_dataset_metadata.xml")
        if dataset_metadata_path is None:
            log.info(f"Stopping - no metadata available from {url}")
            return

        dataset_metadata_tree = get_tree_from_file(dataset_metadata_path)
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
        stored_queries_base_url = check_list_stored_queries_support(resources[WFS_PROTO])
        if stored_queries_base_url is None:
            continue

        log.info("Testing for Natura2000 stored query ...")
        if not check_n2k_stored_query_exists(stored_queries_base_url):
            continue

        log.info("Getting Natura2000 spatial data from stored query ...")
        spatial_data_path = get_n2k_spatial_data(country.alpha_2, resources[WFS_PROTO])

        if spatial_data_path is None:
            continue

        log.info("=" * 80)


if __name__ == "__main__":
    main()

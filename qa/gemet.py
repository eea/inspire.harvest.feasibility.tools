from pathlib import Path
import json
import pycountry
import logme

from qa.common import (
    fetch_url,
    check,
)


log = logme.log(scope='module', name='inspire_qa')

# In theory, Protected Sites labels can be found using INSPIRE Theme documents as well,
# e.g.:
#  http://inspire.ec.europa.eu/theme/ps/ps.ro.xml
# However, resources for some languages (Catalan, Norwegian) are currently missing,
# so the GEMET API is queried instead.
PS_URL_PATTERN = "https://www.eionet.europa.eu/gemet/getConcept?concept_uri=" \
                 "http://inspire.ec.europa.eu/theme/ps&language={language_code}"


DEFAULT_PS_LANGUAGES = (
    "Bulgarian",
    "Catalan",
    "Croatian",
    "Czech",
    "Danish",
    "Dutch",
    "English",
    "Estonian",
    "Finnish",
    "French",
    "German",
    "Modern Greek (1453-)",
    "Hungarian",
    "Italian",
    "Latvian",
    "Lithuanian",
    "Maltese",
    "Norwegian",
    "Polish",
    "Portuguese",
    "Romanian",
    "Slovak",
    "Slovenian",
    "Spanish",
    "Swedish",
)

GEMET_THESAURUS_NAME = "GEMET - INSPIRE themes, version 1.0"

DEFAULT_PS_LABELS_CACHE_PATH = "ps_labels.json"


def get_ps_label(language_code):
    url = PS_URL_PATTERN.format(language_code=language_code)
    log.info(f"Getting GEMET PS label for '{language_code}': {url}")
    label_lokup = fetch_url(url, save=False)
    doc = json.loads(label_lokup.decode("utf-8"))
    try:
        return doc["preferredLabel"]["string"]
    except AttributeError:
        return None


def get_ps_labels(languages=DEFAULT_PS_LANGUAGES, cache_path=DEFAULT_PS_LABELS_CACHE_PATH, refresh=False):
    cache_path = Path(cache_path)
    if not refresh:
        if cache_path.exists():
            with open(cache_path, "r") as f:
                labels = json.load(f)
                return labels
        else:
            log.warning(f"PS labels cache file {str(cache_path)} not found, populating from GEMET")

    labels = {}
    for lang in languages:
        try:
            lang_code = pycountry.languages.get(name=lang).alpha_2
        except KeyError:
            log.warning(f"Could not find language code for '{lang}'")
            continue
        labels[lang_code] = get_ps_label(lang_code)

    with open(cache_path, "w") as f:
        json.dump(labels, f)

    return labels


@check("GEMET thesaurus reference", log)
def check_gemet_thesaurus(tree, nsmap=None):
    nsmap = nsmap or tree.getroot().nsmap
    thesaurus_names = tree.xpath(
        "//gmd:descriptiveKeywords/gmd:MD_Keywords/gmd:thesaurusName/gmd:CI_Citation/gmd:title/gco:CharacterString",
        namespaces=nsmap
    )

    for name in thesaurus_names:
        if name.text == GEMET_THESAURUS_NAME:
            return True

    return False


@check("Protected Sites localized label", log)
def check_ps_keyword(tree, ps_labels=None, nsmap=None):
    ps_labels = ps_labels or get_ps_labels().values()
    nsmap = nsmap or tree.getroot().nsmap
    descriptive_kw_sections = tree.xpath(
        "//gmd:identificationInfo/gmd:MD_DataIdentification/gmd:descriptiveKeywords",
        namespaces=nsmap
    )

    for section in descriptive_kw_sections:
        md_keywords = section.findall(
            "gmd:MD_Keywords/gmd:keyword/gco:CharacterString",
            namespaces=nsmap
        )

        for kw in md_keywords:
            if kw.text in ps_labels:
                return True

    return False


if __name__ == "__main__":
    from pprint import pprint
    pprint(get_ps_labels())

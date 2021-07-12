import re
import warnings

from six.moves import urllib_parse


def parse_url(url, warning=True):
    """Parse URLs especially for Google Drive links.

    file_id: ID of file on Google Drive.
    is_download_link: Flag if it is download link of Google Drive.
    """
    parsed = urllib_parse.urlparse(url)
    query = urllib_parse.parse_qs(parsed.query)
    is_gdrive = parsed.hostname == "drive.google.com"
    is_download_link = parsed.path.endswith("/uc")

    file_id = None
    if is_gdrive and "id" in query:
        file_ids = query["id"]
        if len(file_ids) == 1:
            file_id = file_ids[0]
    match = re.match(r"^/file/d/(.*?)/view$", parsed.path)
    if match:
        file_id = match.groups()[0]

    if warning and is_gdrive and not is_download_link:
        warnings.warn(
            "You specified Google Drive Link but it is not the correct link "
            "to download the file. Maybe you should try: {url}".format(
                url="https://drive.google.com/uc?id={}".format(file_id)
            )
        )

    return file_id, is_download_link


def google_drive_url_normalizer(url_or_id):
    """Normalize and handle URLs or IDs especially for Google Drive links.

    url_or_id: Downloadable URL or ID of a Google Drive link.
    """
    if ('drive.google.com' in url_or_id):
        arr = url_or_id.split("/")[-3:]
        for gdid in arr:
            if len(gdid) == 33:
                break
        return 'https://drive.google.com/uc?id=' + gdid
        
    elif len(url_or_id) == 33:
        return "https://drive.google.com/uc?id={id}".format(id=url_or_id)
    else:
        return url_or_id
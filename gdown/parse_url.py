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

    if is_gdrive and not is_download_link:
        warnings.warn(
            "You specified Google Drive Link but it is not the correct link "
            "to download the file. Maybe you should try: {url}".format(
                url="https://drive.google.com/uc?id={}".format(file_id)
            )
        )

    return file_id, is_download_link

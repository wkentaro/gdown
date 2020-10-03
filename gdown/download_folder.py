from .download import download
import ast
from bs4 import BeautifulSoup
import requests
import sys

if sys.version_info.major < 3:
    from pathlib2 import Path
else:
    from pathlib import Path
client = requests.session()

folders_url = "https://drive.google.com/drive/folders/"
files_url = "https://drive.google.com/uc?id="
folder_type = "application/vnd.google-apps.folder"


def get_folder_list(folder, quiet=False, use_cookies=True):
    """Get folder structure of Google Drive folder URL.

    Parameters
    ----------
    url: str
        URL of the Google Drive folder.
        Must be of the format 'https://drive.google.com/drive/folders/{url}'.
    quiet: bool, optional
        Suppress terminal output.
    use_cookies: bool, optional
        Flag to use cookies. Default is True.

    Returns
    -------
    return_code: bool
        Returns False if the download completed unsuccessfully.
        May be due to invalid URLs, permission errors, rate limits, etc.
    folder_list: dict
        Returns the folder structure of the Google Drive folder.
    """
    return_code = True

    folder_list = {}

    folder_page = client.get(folder)

    if folder_page.status_code != 200:
        return False, None
    folder_soup = BeautifulSoup(folder_page.text, features="html.parser")

    if not use_cookies:
        client.cookies.clear()
    # finds the script tag with window['_DRIVE_ivd']
    # in it and extracts the encoded array
    byte_string = folder_soup.find_all("script")[-3].contents[0][24:-113]

    # decodes the array and evaluates it as a python array
    folder_arr = ast.literal_eval(
        byte_string.replace("\\/", "/")
        .encode("utf-8")
        .decode("unicode-escape")
        .replace("\n", "")
        .replace("null", '"null"')
    )

    folder_list["file_name"] = folder_soup.title.contents[0][:-15]
    folder_list["file_id"] = folder[39:]
    folder_list["file_type"] = folder_type
    folder_list["file_contents"] = []

    folder_file_list = [i[0] for i in folder_arr[0]]
    folder_name_list = [i[2] for i in folder_arr[0]]
    folder_type_list = [i[3] for i in folder_arr[0]]

    for file in range(len(folder_file_list)):
        if folder_type_list[file] != folder_type:
            if not quiet:
                print(
                    "Processing file",
                    folder_file_list[file],
                    folder_name_list[file],
                )
            folder_list["file_contents"].append(
                {
                    "file_name": folder_name_list[file],
                    "file_id": folder_file_list[file],
                    "file_type": folder_type_list[file],
                    "file_contents": None,
                }
            )
            if not return_code:
                return return_code, None
        else:
            if not quiet:
                print(
                    "Retrieving folder",
                    folder_file_list[file],
                    folder_name_list[file],
                )
            return_code, folder_structure = get_folder_list(
                folders_url + folder_file_list[file],
                use_cookies=use_cookies,
            )
            if not return_code:
                return return_code, None
            folder_list["file_contents"].append(folder_structure)
    return return_code, folder_list


def get_directory_structure(directory, previous_path):
    """Converts a Google Drive folder structure into a local directory list.

    Parameters
    ----------
    directory: dict
        Dictionary containing the Google Drive folder structure.
    previous_path: pathlib.Path
        Path containing the parent's file path.

    Returns
    -------
    directory_structure: list
        List containing a tuple of the files' ID and file path.
    """
    directory_structure = []
    for file in directory["file_contents"]:
        if file["file_type"] == folder_type:
            for i in get_directory_structure(
                file, previous_path / file["file_name"]
            ):
                directory_structure.append(i)
        elif file["file_contents"] is None:
            directory_structure.append(
                (file["file_id"], previous_path / file["file_name"])
            )
    return directory_structure


def download_folder(
    folder, output=None, quiet=False, proxy=None, speed=None, use_cookies=True
):
    """Downloads entire folder from URL.

    Parameters
    ----------
    url: str
        URL of the Google Drive folder.
        Must be of the format 'https://drive.google.com/drive/folders/{url}'.
    output: str, optional
        String containing the path of the output folder.
        Defaults to current working directory.
    quiet: bool, optional
        Suppress terminal output.
    proxy: str, optional
        Proxy.
    speed: float, optional
        Download byte size per second (e.g., 256KB/s = 256 * 1024).
    use_cookies: bool, optional
        Flag to use cookies. Default is True.

    Returns
    -------
    return_code: bool
        Returns False if the download completed unsuccessfully.
        May be due to invalid URLs, permission errors, rate limits, etc.

    Example
    -------
    gdown.download_folder(
        "https://drive.google.com/drive/folders/" +
        "1ZXEhzbLRLU1giKKRJkjm8N04cO_JoYE2",
        use_cookies=True
    )
    """
    if not quiet:
        print("Retrieving folder list")
    return_code, folder_list = get_folder_list(
        folder,
        quiet=quiet,
        use_cookies=False,
    )

    if not return_code:
        return return_code
    if not quiet:
        print("Retrieving folder list completed")
        print("Building directory structure")
    if output is None:
        output = Path.cwd()
    else:
        output = Path(output)
    directory_structure = get_directory_structure(
        folder_list,
        output / folder_list["file_name"],
    )

    if not quiet:
        print("Building directory structure completed")
    for file in directory_structure:
        file[1].parent.mkdir(parents=True, exist_ok=True)

        return_code = download(
            files_url+file[0],
            output=str(file[1]),
            quiet=quiet,
            proxy=proxy,
            speed=speed,
            use_cookies=use_cookies,
        )

        if not return_code:
            if not quiet:
                print("Download ended unsuccessfully")
            return return_code
    if return_code and not quiet:
        print("Download completed")
    return return_code

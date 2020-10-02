from bs4 import BeautifulSoup
from .download import download
import requests, ast

client = requests.session()

def download_folder(folder, quiet = False, proxy = None, speed = None):
    """
    Download entire folder from URL.

    Parameters
    ----------

    url: str
        URL of the Google Drive folder. Must be of the format 'https://drive.google.com/drive/folders/{url}'
    quiet: bool, optional
        Suppress terminal output.
    proxy: str, optional
        Proxy.
    speed: float, optional
        Download byte size per second (e.g., 256KB/s = 256 * 1024).

    Returns
    -------

    output: str
        Output filename.

    Example
    -------

    gdown.download_folder("https://drive.google.com/drive/folders/1ZXEhzbLRLU1giKKRJkjm8N04cO_JoYE2")

    """

    folder_soup = BeautifulSoup(client.get(folder).text, features = "html.parser")

    # finds the script tag with window['_DRIVE_ivd'] in it and extracts the encoded array
    byte_string = folder_soup.find_all('script')[-3].contents[0][24:-113] 

    # decodes the array and evaluates it as a python array
    folder_arr = ast.literal_eval(byte_string.replace('\\/', "/").encode('utf-8').decode('unicode-escape').replace("\n", "").replace('null', '"null"'))

    folder_file_list = [i[0] for i in folder_arr[0]]
    folder_name_list = [i[2] for i in folder_arr[0]]
    folder_type_list = [i[3] for i in folder_arr[0]]

    for file in range(len(folder_file_list)):
        if folder_type_list[file] != "application/vnd.google-apps.folder":
            download("https://drive.google.com/uc?id=" + folder_file_list[file], folder_name_list[file], quiet = True, proxy = proxy, speed = speed)
            if quiet == False:
                print("https://drive.google.com/uc?id=" + folder_file_list[file], folder_name_list[file])
        else:
            if quiet == False:
                print("Processing folder", folder_name_list[file], "(https://drive.google.com/drive/folders/" + folder_file_list[file] + ")")
            download_folder("https://drive.google.com/drive/folders/" + folder_file_list[file], quiet = quiet, proxy = proxy, speed = speed)

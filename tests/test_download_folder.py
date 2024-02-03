import os.path as osp
import tempfile

from gdown.download_folder import _parse_google_drive_file
from gdown.download_folder import download_folder

here = osp.dirname(osp.abspath(__file__))


def test_valid_page():
    html_file = osp.join(here, "data/folder-page-sample.html")
    with open(html_file) as f:
        content = f.read()
    folder = "".join(
        [
            "https://drive.google.com",
            "/drive/folders/1KpLl_1tcK0eeehzN980zbG-3M2nhbVks",
        ]
    )
    gdrive_file, id_name_type_iter = _parse_google_drive_file(
        folder,
        content,
    )
    assert gdrive_file.id == "1KpLl_1tcK0eeehzN980zbG-3M2nhbVks"

    assert gdrive_file.name == "gdown_folder_test"
    assert gdrive_file.type == "application/vnd.google-apps.folder"
    assert gdrive_file.children == []
    assert gdrive_file.is_folder()

    expected_children_ids = [
        "1aMZqPaU03E7XOQNXtjSCdguRHBaIQ82m",
        "1hVAxfM7_doToqQ24eVd65cgiaoLi0TtO",
        "1Z2VYnXb01h-3uvEptoQ48Fo__eAn0wc1",
        "14xzOzvKjP0at07jfonV7qVrTKoctFijz",
        "1wlapSEt6N9Ayf7fzCTOkra_4GIg-cqeD",
    ]

    expected_children_names = [
        "directory-0",
        "directory-1",
        "fractal.jpg",
        "this is a file.txt",
        "tux.jpg",
    ]

    expected_children_types = [
        "application/vnd.google-apps.folder",
        "application/vnd.google-apps.folder",
        "image/jpeg",
        "text/plain",
        "image/jpeg",
    ]

    children_info = list(id_name_type_iter)
    actual_children_ids = [t[0] for t in children_info]
    actual_children_names = [t[1] for t in children_info]
    actual_children_types = [t[2] for t in children_info]

    assert actual_children_ids == expected_children_ids
    assert actual_children_names == expected_children_names
    assert actual_children_types == expected_children_types


def test_download_folder_dry_run():
    url = "https://drive.google.com/drive/folders/1KpLl_1tcK0eeehzN980zbG-3M2nhbVks"
    tmp_dir = tempfile.mkdtemp()
    files = download_folder(url=url, output=tmp_dir, skip_download=True)
    assert len(files) == 6
    for file in files:
        assert hasattr(file, "id")
        assert hasattr(file, "path")
        assert hasattr(file, "local_path")

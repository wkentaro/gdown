import sys

from gdown import parse_google_drive_file

if sys.version_info.major < 3:
    from pathlib2 import Path
else:
    from pathlib import Path


def test_valid_page():
    content = Path("tests/data/folder-page-sample.html").read_text()
    folder = "".join(
        [
            "https://drive.google.com",
            "/drive/folders/1KpLl_1tcK0eeehzN980zbG-3M2nhbVks",
        ]
    )
    gdrive_file, id_name_type_iter = parse_google_drive_file(
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

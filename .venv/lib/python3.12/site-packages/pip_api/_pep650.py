import subprocess

from pip_api._call import call


def invoke_install(path, *, dependency_group=None, **kwargs):
    try:
        call(
            "install", "--requirement", dependency_group or "requirements.txt", cwd=path
        )
    except subprocess.CalledProcessError as e:
        return e.returncode
    return 0


def invoke_uninstall(path, *, dependency_group=None, **kwargs):
    try:
        call(
            "uninstall",
            "--requirement",
            dependency_group or "requirements.txt",
            cwd=path,
        )
    except subprocess.CalledProcessError as e:
        return e.returncode
    return 0


def get_dependencies_to_install(path, *, dependency_group=None, **kwargs):
    # See https://github.com/pypa/pip/issues/53
    raise Exception("pip is unable to do a dry run")


def get_dependency_groups(path, **kwargs):
    raise Exception("pip is unable to discover dependency groups")


def update_dependencies(
    path, dependency_specifiers, *, dependency_group=None, **kwargs
):
    # See https://github.com/pypa/pip/issues/1479
    raise Exception("pip is unable to update dependency files")

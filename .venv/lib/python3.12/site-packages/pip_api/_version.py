from pip_api._call import call


def version() -> str:
    result = call("--version")

    # result is of the form:
    # pip <version> from <directory> (python <python version>)

    return result.split(" ")[1]

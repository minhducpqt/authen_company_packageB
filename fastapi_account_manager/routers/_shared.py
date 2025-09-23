import importlib.resources as pkg_resources
from .. import templates as _templates_pkg

def templates_dir() -> str:
    # resolve package templates folder (works when installed as wheel)
    return pkg_resources.files(_templates_pkg).joinpath("").__fspath__()

"""
    Basic manipulations needed by others
"""

def get_path_list(
    path_str: str
    ) -> list[ str ]:
    """
        [/some/file/path] => ["some","file","path"]
    """
    from os import path, sep
    return path.normpath( path_str ).split( sep )
#/def get_path_list

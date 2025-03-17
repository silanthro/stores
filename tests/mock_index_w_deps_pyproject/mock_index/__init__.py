import pip_install_test


def get_package():
    return pip_install_test.__name__


async def async_get_package():
    return pip_install_test.__name__

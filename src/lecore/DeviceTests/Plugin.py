"""
Pytest plugin of lecore (entry point pytest11), registers marker of device tests and runs firmware upgrade last
"""
#: Test run as the last one of its class, the device reboots into new firmware
LAST_TEST = 'test_08_upgrade'


def pytest_configure(config):
    config.addinivalue_line("markers", "hardware: test needs a real device (deselect by -m 'not hardware')")


def pytest_collection_modifyitems(items):
    # Inherited tests are collected before tests of subclasses, move the upgrade after the last test of its class
    for item in [i for i in items if i.name == LAST_TEST]:
        cls = getattr(item, 'cls', None)
        if cls is None:
            continue
        last = max(n for n, i in enumerate(items) if getattr(i, 'cls', None) is cls)
        items.remove(item)
        items.insert(last, item)

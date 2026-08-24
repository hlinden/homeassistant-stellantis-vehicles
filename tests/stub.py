import sys, types, importlib.abc, importlib.machinery

class AnyMeta(type):
    def __getattr__(cls, name):
        if name.startswith("__"):
            raise AttributeError(name)
        value = f"{cls.__name__}.{name}"
        setattr(cls, name, value)
        return value

class FakeModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        cls = AnyMeta(name, (object,), {"__init__": lambda self, *a, **k: None})
        setattr(self, name, cls)
        return cls

class Finder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in ("aiohttp", "paho", "voluptuous", "PIL", "Crypto") or fullname.startswith(("homeassistant", "aiohttp.", "paho.", "voluptuous.", "PIL.", "Crypto.")):
            return importlib.machinery.ModuleSpec(fullname, self, is_package=True)
        return None
    def create_module(self, spec):
        return FakeModule(spec.name)
    def exec_module(self, module):
        module.__path__ = []

sys.meta_path.insert(0, Finder())

# a few real behaviours needed by the code under test
import homeassistant.exceptions as hae
class ServiceValidationError(Exception):
    def __init__(self, *args, translation_domain=None, translation_key=None, translation_placeholders=None):
        super().__init__(translation_key or "error")
        self.translation_key = translation_key
        self.translation_placeholders = translation_placeholders
class ConfigEntryAuthFailed(Exception): pass
class HomeAssistantError(Exception): pass
hae.ServiceValidationError = ServiceValidationError
hae.ConfigEntryAuthFailed = ConfigEntryAuthFailed
hae.HomeAssistantError = HomeAssistantError

import homeassistant.util as hu
class _dt:
    @staticmethod
    def get_default_time_zone():
        from datetime import timezone
        return timezone.utc
hu.dt = _dt

import homeassistant.helpers.update_coordinator as uc
class DataUpdateCoordinator:
    def __init__(self, *args, **kwargs): pass
uc.DataUpdateCoordinator = DataUpdateCoordinator

def callback(f): return f
import homeassistant.core as hc
hc.callback = callback

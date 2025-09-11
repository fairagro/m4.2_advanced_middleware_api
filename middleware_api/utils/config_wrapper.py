"""
Defines the ConfigWrapper class that wraps a yaml file and supports
overriding single entries in the yaml tree by env vars or docker
secret files in /run/secrets.
"""
from abc import abstractmethod
import os
from pathlib import Path
from typing import Dict, Generator, List, TypeAlias, cast, overload

import yaml


KeyType: TypeAlias = str | int
DictType: TypeAlias = Dict[str, "ValueType"]
ListType: TypeAlias = List["ValueType"]
ValueType: TypeAlias = "DictType | ListType | str"
WrapType: TypeAlias = "ConfigWrapper | str | None"


class ConfigWrapper:
    """
    Wraps nested dicts and lists (aka loaded yaml) and supports Env/Docker-Secret-Overrides.
    """

    def __init__(self, path: str = "") -> None:
        self._path = path.upper()

    def _build_path(self, key: str) -> str:
        return f"{self._path}_{key}" if self._path else key

    def _wrap(self, value: ValueType | None, key: str) -> WrapType:
        return ConfigWrapper._from_value(value, self._build_path(key))

    @staticmethod
    def _from_value(value: ValueType | None, path: str) -> WrapType:
        if isinstance(value, dict):
            return ConfigWrapperDict(value, path)
        if isinstance(value, list):
            return ConfigWrapperList(value, path)
        return value

    @classmethod
    def from_data(cls, data: DictType | ListType, prefix: str = "") -> "ConfigWrapper":
        wrapped = cls._from_value(data, prefix)
        if not isinstance(wrapped, ConfigWrapper):
            raise TypeError(
                f"'ConfigWrapper' only wraps lists or dicts. "
                f"You're trying to wrap a '{type(data)}'"
            )
        return wrapped
        
    @classmethod
    def from_yaml_file(cls, path: Path, prefix: str = "") -> "ConfigWrapper":
        """
        Creates a ConfigWrapper from a yaml file
        """
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            return cls.from_data(data, prefix)

    @staticmethod
    def _get_path_str(value: ValueType | None, key: KeyType) -> str:
        if isinstance(value, dict) and 'id' in value:
            return cast(str, value['id'])
        return str(key)

    @overload
    def __getitem__(self, key: str) -> WrapType: ...
    @overload
    def __getitem__(self, key: int) -> WrapType: ...

    @abstractmethod
    def __getitem__(self, key: KeyType) -> WrapType:
        raise NotImplementedError(
            "Please do not use class 'ConfigWrapper' directly, but a derived class")  

    def get(self, key: KeyType, default_value: ValueType | None = None) -> WrapType:
        """
        Returns the value of a config key. If the value is a dict or list, it's again
        wrapped into to ConfigWrapper object.
        """
        try:
            return self[key]
        except KeyError:
            key_str = ConfigWrapper._get_path_str(default_value, key)
            return self._wrap(default_value, key_str)

    @classmethod
    def _unwrap(cls, wrapper: WrapType) -> ValueType:
        if isinstance(wrapper, ConfigWrapperDict):
            return {k: cls._unwrap(v) for k, v in wrapper.items()}
        if isinstance(wrapper, ConfigWrapperList):
            return [cls._unwrap(wrapper[i]) for i in range(len(wrapper))]
        if isinstance(wrapper, str):
            return wrapper
        raise TypeError(f"Cannot unwrap element of type '{type(wrapper)}'")

    def unwrap(self) -> DictType | ListType:
        unwrapped = ConfigWrapper._unwrap(self)
        if isinstance(unwrapped, (dict, list)):
            return unwrapped
        raise TypeError(f"Unwrapped values must be of type list or dict, found '{type(unwrapped)}'")
        
    @abstractmethod
    def __iter__(self) -> Generator[KeyType, None, None]:
        raise NotImplementedError(
            "Please do not use class 'ConfigWrapper' directly, but a derived class")
    
    @abstractmethod
    def items(self) -> Generator[tuple[KeyType, WrapType], None, None]:
        raise NotImplementedError(
            "Please do not use class 'ConfigWrapper' directly, but a derived class")
    
    @abstractmethod
    def __len__(self) -> int:
        raise NotImplementedError(
            "Please do not use class 'ConfigWrapper' directly, but a derived class")
    
    def _override_key_access(self, key: str) -> str | None:
        # self._path should alwys be upper case
        full_key = self._path + '_' + key.upper()

        # 1️⃣ Check ENV
        if full_key in os.environ:
            return os.environ[full_key]

        # 2️⃣ Check Docker secret file
        secret_file = Path(f"/run/secrets/{full_key.lower()}")
        if secret_file.exists():
            return secret_file.read_text(encoding="utf-8").strip()

        return None


class ConfigWrapperDict(ConfigWrapper):
    """
    A ConfigWrapper flavour that specifically wraps dicts
    """

    def __init__(self, data: DictType, path: str = "") -> None:
        super().__init__(path)
        self._data = data

    def _all_keys(self) -> set[str]:
        """all keys including discovered ENV/Secrets"""
        keys = set(self._data.keys())
        for env_key in os.environ:
            if env_key.startswith(self._path + "_"):
                key_suffix = env_key[len(self._path) + 1 :]
                keys.add(key_suffix.lower())
        secrets_dir = Path("/run/secrets")
        path_lower = self._path.lower()
        if secrets_dir.exists():
            for secret_file in secrets_dir.iterdir():
                if secret_file.name.startswith(path_lower + "_"):
                    key_suffix = secret_file.name[len(path_lower) + 1 :]
                    keys.add(key_suffix.lower())
        return keys

    def __getitem__(self, key: str) -> WrapType:
        override_value = self._override_key_access(key)
        if override_value is not None:
            return override_value
        value = self._data[key]
        return super()._wrap(value, key)
    
    def __iter__(self) -> Generator[str, None, None]:
        """
        iterate over dict keys
        """
        for key in self._all_keys():
            yield key

    def items(self) -> Generator[tuple[str, WrapType], None, None]:
        """
        iterate over key-value pairs
        """
        for key in self._all_keys():
            yield key, self[key]

    def __len__(self) -> int:
        return len(self._all_keys())

class ConfigWrapperList(ConfigWrapper):
    """
    A ConfigWrapper flavour that specifically wraps lists
    """

    def __init__(self, data: ListType, path: str = "") -> None:
        super().__init__(path)
        self._data = data

    def __getitem__(self, key: int) -> WrapType:
        value = self._data[key]
        key_str = ConfigWrapper._get_path_str(value, key)
        override_value = self._override_key_access(key_str)
        if override_value is not None:
            return override_value
        return super()._wrap(value, key_str)

    def __iter__(self) -> Generator[int, None, None]:
        """
        iterate over list indices
        """
        for idx in range(len(self._data)):
            yield idx

    def items(self) -> Generator[tuple[int, WrapType], None, None]:
        """
        iterate over index-value pairs
        """
        for idx, value in enumerate(self._data):
            key_str = ConfigWrapper._get_path_str(value, idx)
            yield idx, super()._wrap(value, key_str)

    def __len__(self) -> int:
        return len(self._data)
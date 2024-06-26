# Copyright (c) Yugabyte, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
# in compliance with the License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License
# is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
# or implied. See the License for the specific language governing permissions and limitations
# under the License.
#

import copy
import os
import shlex
import sys

from typing import List, Optional, Set, Dict, Any, Mapping, Optional

from yugabyte_db_thirdparty.devtoolset import DEVTOOLSET_ENV_VARS
from yugabyte_db_thirdparty.string_util import split_into_word_set, parse_bool
from yugabyte_db_thirdparty.custom_logging import log, heading, log_separator


# A mechanism to save some environment variabls to a file in the dependency's build directory to
# make debugging easier.
ENV_VARS_TO_SAVE = split_into_word_set("""
    ASAN_OPTIONS
    CC
    CFLAGS
    CPPFLAGS
    CXX
    CXXFLAGS
    LANG
    LDFLAGS
    PATH
    PYTHONPATH
    NM
    AR
    LD
    AS
""")


def write_env_vars(file_path: str) -> None:
    env_script = ''
    for k, v in sorted(dict(os.environ).items()):
        if (k in ENV_VARS_TO_SAVE or
                k in DEVTOOLSET_ENV_VARS or
                k.startswith('YB_')):
            env_script += 'export %s=%s\n' % (k, shlex.quote(v))
    with open(file_path, 'w') as output_file:
        output_file.write(env_script)


def get_bool_env_var(env_var_name: str) -> bool:
    v = os.getenv(env_var_name)
    if v is None:
        return False
    return parse_bool(v)


def dict_set_or_del(d: Any, k: Any, v: Any) -> None:
    """
    Set the value of the given key in a dictionary to the given value, or delete it if the value
    is None.
    """
    if v is None:
        if k in d:
            del d[k]
    else:
        d[k] = v


class EnvVarContext:
    """
    Sets the given environment variables and restores them on exit. A None value means the variable
    is undefined.
    """

    env_vars: Mapping[str, Optional[str]]
    saved_env_vars: Dict[str, Optional[str]]

    def __init__(self, env_vars: Mapping[str, Optional[str]] = {}, **kwargs_env_vars: Any) -> None:
        """
        Allows creating the environment variable context either by specifying a dictionary, where
        keys (environment variable names) could be computed (this is useful when environment
        variable names are specified using constants) or by specifying keyword arguments, where
        keyword argument names become environment variable names.

        >>> with EnvVarContext(MY_ENV_VAR='my_env_var_value'):
        ...     print(os.getenv('MY_ENV_VAR'))
        my_env_var_value
        >>> my_env_var_name = 'AWESOME_ENV_VAR'
        >>> with EnvVarContext({my_env_var_name: 'awesome_value'}):
        ...     print(os.getenv('AWESOME_ENV_VAR'))
        awesome_value

        Also allows to unset environment variables by setting their value to None.
        >>> os.environ['SHOULD_NOT_SET_THIS_VAR'] = 'undesirable_value'
        >>> with EnvVarContext(SHOULD_NOT_SET_THIS_VAR=None):
        ...     print(os.getenv('SHOULD_NOT_SET_THIS_VAR'))
        None
        """
        self.env_vars = dict(copy.deepcopy(env_vars))
        self.env_vars.update(kwargs_env_vars)

    def __enter__(self) -> None:
        self.saved_env_vars = {}
        for env_var_name, new_value in self.env_vars.items():
            self.saved_env_vars[env_var_name] = os.environ.get(env_var_name)
            dict_set_or_del(os.environ, env_var_name, new_value)

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        for env_var_name, saved_value in self.saved_env_vars.items():
            dict_set_or_del(os.environ, env_var_name, saved_value)


def get_env_var_name_and_value_str(env_var_name: str) -> str:
    return f"{env_var_name}={os.getenv(env_var_name)}"


def dump_env_vars_to_log(program_name: Optional[str] = None) -> None:
    if program_name is not None:
        heading('Environment of {}:'.format(program_name))
    for key in os.environ:
        log('{}={}'.format(key, os.environ[key]))
    log_separator()


def unset_env_var_if_set_and_log(name: str) -> None:
    """
    Unset certain environment variables that might interfere with the build, and log each one.
    """
    if name in os.environ:
        log('Unsetting %s for third-party build (was set to "%s").', name, os.environ[name])
        del os.environ[name]


def get_dir_list_from_env_var(env_var_name: str) -> List[str]:
    """
    Get a colon-separated directory list from an environment variable.
    """
    env_var_value = os.getenv(env_var_name)
    if env_var_value is None:
        return []
    return env_var_value.split(':')


def join_dir_list(dirs: List[str]) -> str:
    d = [d.strip() for d in dirs]
    return ':'.join([d for d in dirs if d])


def get_flag_list_from_env_var(env_var_name: str) -> List[str]:
    """
    Get a whitespace-separated list from an environment variable.
    """
    env_var_value = os.getenv(env_var_name)
    if env_var_value is None:
        return []
    return env_var_value.strip().split()

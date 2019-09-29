#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
# vim:ts=4:sw=4:softtabstop=4:smarttab:expandtab

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#    http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Basic configuration holder objects.

"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json
import shutil
import sys, os
import tempfile
import warnings

import git
import yaml


class BasicConfigError(Exception):
    pass

class ConfigLockError(BasicConfigError):
    pass

class ConfigReadError(BasicConfigError):
    pass


class ConfigHolder(dict):
    """ConfigHolder() Holds named configuration information. For convenience,
it maps attribute access to the real dictionary. This object is lockable, use
the 'lock' and 'unlock' methods to set its state. If locked, new keys or
attributes cannot be added, but existing ones may be changed."""
    def __init__(self, init={}, name=None, repo_dir=None):
        name = name or self.__class__.__name__.lower()
        dict.__init__(self, init)
        dict.__setattr__(self, "_locked", 0)
        dict.__setattr__(self, "_name", name)
        dict.__setattr__(self, "_repo_dir", repo_dir)

    def __getstate__(self):
        return self.__dict__.items()

    def __setstate__(self, items):
        for key, val in items:
            self.__dict__[key] = val

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, dict.__repr__(self))

    def __str__(self):
        n = self._name
        s = ["{}(name={!r}):".format(self.__class__.__name__, n)]
        s = s + ["  {}.{} = {!r}".format(n, it[0], it[1]) for it in self.items()]
        s.append("\n")
        return "\n".join(s)

    def __setitem__(self, key, value):
        if self._locked and not key in self:
            raise ConfigLockError("setting attribute on locked config holder")
        return super(ConfigHolder, self).__setitem__(key, value)

    def __getitem__(self, name):
        return super(ConfigHolder, self).__getitem__(name)

    def __delitem__(self, name):
        return super(ConfigHolder, self).__delitem__(name)

    __getattr__ = __getitem__
    __setattr__ = __setitem__
#    __delattr__ = __delitem__

    def lock(self):
        dict.__setattr__(self, "_locked", 1)

    def unlock(self):
        dict.__setattr__(self, "_locked", 0)

    def islocked(self):
        return self._locked

    def copy(self):
        ch = ConfigHolder(self)
        if self.islocked():
            ch.lock()
        return ch

    def add_section(self, name):
        setattr(self, name, SECTION(name))
        # self.name = SECTION(name)


class SECTION(ConfigHolder):
    def __init__(self, name):
        super(SECTION, self).__init__(name=name)

    def __repr__(self):
        return super(SECTION, self).__str__()


class BlobConfig(ConfigHolder):

    def mergetree(self, tree, globalspace=None):
        for item in tree.traverse():
            if item.type == 'blob' and blob_readable(item):
                self.mergeblob(item, globalspace)

    def mergeblob(self, blob, globalspace=None):
        """Merge in a Python syntax configuration file that should assign
        global variables that become keys in the configuration. Returns
        True if file read OK, False otherwise."""
        gb = globalspace or {} # temporary global namespace for config files.
        gb["SECTION"] = SECTION
        gb["sys"] = sys # in case config stuff needs these.
        gb["os"] = os
        try:
            read_blob(blob, gb, self)
        except:
            ex, val, tb = sys.exc_info()
            warnings.warn("BlobConfig: error reading %s: %s (%s)." % (filename, ex, val))
            return False
        else:
            return True


def blob_readable(blob):
    fn, ext = os.path.splitext(blob.name)
    return ext in ['.py', '.conf', '.yaml', '.yml', '.json']


def read_blob(blob, glbl, loc):
    fn, ext = os.path.splitext(blob.name)
    if ext in ['.py', '.conf']:
        exec(blob.data_stream.read().decode(), glbl, loc)
    elif ext in ['.yaml', '.yml']:
        c = yaml.safe_load(blob.data_stream)
        loc.update(c)
    elif ext in ['.json']:
        c = json.load(blob.data_stream)
        loc.update(c)

def get_pathname(basename):
    if isinstance(basename, list):
        return os.path.expandvars(os.path.join(*basename))
    return os.path.expandvars(basename)


def check_config(fname):
    """check_config(filename) -> bool
    Check is a config file can be read without errors and contains
    something.
    """
    fname = get_pathname(fname)
    cf = BlobConfig()
    if cf.mergefile(fname):
        return bool(cf)
    else:
        return False

# main function for getting a configuration file. gets it from the common
# configuration location (/etc/pycopia), but if a full path is given then
# use that instead.
def get_config(fname, branch='master', repo_uri=None, initdict=None, globalspace=None, keep_repo=False, **kwargs):
    if repo_uri is None:
        if 'GITFIG_REPO_URI' not in os.environ:
            raise Exception('No git config repo...')
        repo_uri = os.environ.get('GITFIG_REPO_URI')

    temp_dir = tempfile.mkdtemp()
    repo = git.Repo.clone_from(repo_uri, temp_dir)
    ref = {r.remote_head: r for r in repo.refs if isinstance(r, git.RemoteReference)}[branch]
    tree = ref.commit.tree

    fpath = get_pathname(fname)
    cf = BlobConfig()
    for item in tree.traverse():
        if item.path == fpath:
            merged = False
            if item.type == 'blob':
                merged = cf.mergeblob(item, globalspace)
            elif item.type == 'tree':
                merged = cf.mergetree(item, globalspace)

            if not merged:
                if not keep_repo:
                    shutil.rmtree(temp_dir)
                raise ConfigReadError("did not successfully read %r." % (fpath,))

            if initdict:
                cf.update(initdict)
            cf.update(kwargs)
            if not keep_repo:
                shutil.rmtree(temp_dir)
            return cf
    if not keep_repo:
        shutil.rmtree(temp_dir)
    raise ConfigReadError("did not find %r." % (fpath,))

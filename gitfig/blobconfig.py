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
from datetime import datetime, timedelta

import git
import yaml


class BasicConfigError(Exception):
    pass

class ConfigLockError(BasicConfigError):
    pass

class ConfigReadError(BasicConfigError):
    pass


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


class ConfigHolder(dict):
    """ConfigHolder() Holds named configuration information. For convenience,
it maps attribute access to the real dictionary. This object is lockable, use
the 'lock' and 'unlock' methods to set its state. If locked, new keys or
attributes cannot be added, but existing ones may be changed."""
    def __init__(self, init={}, name=None):
        name = name or self.__class__.__name__.lower()
        dict.__init__(self, init)
        dict.__setattr__(self, "_locked", 0)
        dict.__setattr__(self, "_name", name)

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


class RepoObject(object):
    def __init__(self, repo_path=None, branch='master'):
        try:
            repo = git.Repo(repo_path)
        except (git.NoSuchPathError, git.InvalidGitRepositoryError):
            repo_dir = tempfile.mkdtemp()
            repo = git.Repo.clone_from(repo_path, repo_dir)
            self._repo_dir = repo_dir
        else:
            self._repo_dir = repo_path
        self._repo = repo
        self._last_fetch = datetime.now()
        self._branch = branch

    def get_ref(self, branch=None):
        if branch is None:
            branch = self._branch
        return {r.remote_head: r for r in self._repo.refs if isinstance(r, git.RemoteReference)}[branch]

    def sync(self):
        # how to avoid multiple fetch requests?
        # lock config until sync is done?
        # if datetime.now() >= self._last_fetch + timedelta(minutes=5):
        if datetime.now() >= self._last_fetch + timedelta(seconds=20):
            for remote in self._repo.remotes:
                remote.fetch()
            self._last_fetch = datetime.now()

    def cleanup(self):
        if not self._repo_dir.startswith(tempfile.gettempdir()):
            return
        shutil.rmtree(self._repo_dir)


class BlobConfig(ConfigHolder):
    # raise for repo errors
    # raise ConfigReadError("did not find %r." % (fpath,))
    # raise ConfigReadError("did not successfully read %r." % (fpath,))

    def set_repo(self, repo_path=None, branch='master'):
        dict.__setattr__(self, '_repo', RepoObject(repo_path, branch))

    def get_dynamic(self, key):
        self._repo.sync()
        return self[key]

    def sync_config(self, fname, globalspace=None):
        fpath = get_pathname(fname)
        ref = self._repo.get_ref()
        tree = ref.commit.tree
        for item in tree.traverse():
            if item.path == fpath:
                if item.type == 'blob':
                    self.mergeblob(item, globalspace)
                elif item.type == 'tree':
                    self.mergetree(item, globalspace)

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
            warnings.warn("BlobConfig: error reading blob: %s (%s)." % (ex, val))


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

def get_config(fname, branch='master', repo_path=None, initdict=None, globalspace=None, cleanup=False, **kwargs):
    '''
        `initdict` and extra kwargs will be updated into configuration
        branch: which branch to get configuration
        repo_path: if not set will be used from environment GITFIG_REPO_PATH

    '''
    if repo_path is None:
        if 'GITFIG_REPO_PATH' not in os.environ:
            raise Exception('No git config repo...')
        repo_path = os.environ.get('GITFIG_REPO_PATH')
    cf = BlobConfig()
    if initdict:
        cf.update(initdict)
    cf.update(kwargs)
    cf.set_repo(repo_path=repo_path, branch=branch)
    cf.sync_config(fname, globalspace=globalspace)
    if cleanup:
        cf._repo.cleanup()
    return cf

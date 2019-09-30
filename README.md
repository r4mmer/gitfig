# GitFig

![](https://github.com/r4mmer/gitfig/workflows/PyPi/badge.svg)

This project aims to setup a git based configuration module

### Setup

You need a git repo, that's it.
Pass the repo path (url or directory) to the `get_config` function or as environment variable

### Selection

A configuration repo can hold configurations for any number of projects, you can use branches to separate them or folders
when calling `get_config` pass the path to the file/directory relative to the root of the repo

```
.
├── README.md
├── production
│   ├── proj1
│   │   ├── backend.yaml
│   │   └── frontend.yaml
│   └── proj2
│       ├── bar.yaml
│       └── foo.yaml
└── staging
    ├── proj1
    │   ├── backend.yaml
    │   └── frontend.yaml
    └── proj2
        ├── bar.yaml
        └── foo.yaml
```

i.e. 'production/proj1/backend.yaml' or ["production", "proj1", "backend.yaml"]

If a directory is passed (like "staging/proj2"), all files from the directory will be merged in one config object

### Config files

Supports:

Yaml: ".yaml" and ".yml" extensions

JSON: ".json"

Python files will be processed

So a file like this:
```python

# file.py
import datetime

foo = 'bar'
ts_start = datetime.now().timestamp()
hostinfo = os.uname()
```

Will generate this configuration:
```python
{
  'datetime': <class 'datetime.datetime'>,
  'foo': 'bar',
  'ts_start': 1569798356.432969,
  'hostinfo': posix.uname_result(sysname='Linux', nodename='mambo-vlk', release='4.15.0-64-generic', version='#73-Ubuntu SMP Thu Sep 12 13:16:13 UTC 2019', machine='x86_64')
}
```

Imported modules are still on the config object (for now), the `os` and `sys` modules are already imported if needed


### Example

```python
>>> import os
>>> from gitfig import get_config
>>> os.environ['GITFIG_REPO_PATH'] = 'https://github.com/r4mmer/config.git'
>>> c = get_config('prod/proj1/backend.py', 'proj', initdict={'lol': 'haha'})
>>> c.foo
'bar'
>>> c.lol
'haha'
>>> c['lol']
'haha'
```

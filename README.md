# snowmobile

[![Documentation Status](https://readthedocs.org/projects/snowmobile/badge/?version=latest)](https://snowmobile.readthedocs.io/en/latest/?badge=latest#)
[![PyPI version](https://badge.fury.io/py/snowmobile.svg)](https://badge.fury.io/py/snowmobile)
[![codecov](https://codecov.io/gh/GEM7318/Snowmobile/branch/0.2.1/graph/badge.svg?token=UCMCWRIIJ8)](https://codecov.io/gh/GEM7318/Snowmobile)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/GEM7318/Snowmobile/blob/master/LICENSE.txt)

`snowmobile` is a wrapper around the 
[Snowflake Connector for Python](https://docs.snowflake.com/en/user-guide/python-connector.html).

### Documentation
&nbsp;**[snowmobile.readthedocs.io](https://snowmobile.readthedocs.io/en/latest/index.html)**

### Installation
&nbsp;`pip install snowmobile`

---

### Development

&nbsp;**See [0.2.0](https://github.com/GEM7318/Snowmobile/tree/0.2.0) for latest updates.**

#### Installs

- Core
    - pip: `pip install --user requirements/requirements_37.reqs`
    - conda: `conda env create -f requirements/environment.yml`
- docs: `pip install --user docs/requirements.txt`

#### Run

- test: `pytest --cov-report=xml --cov=snowmobile test/`
- docs: `sphinx-build -b html . _build`


# Clin

**Clin** is a command-line utility to manage [Nakadi](https://nakadi.io/)
resources from schema files in "Infrastructure as Code" style.
![](https://github.com/zalando-incubator/clin/raw/master/docs/gifs/demo.gif)

## User Guide

### Prerequisites

* [Python](https://www.python.org/) >= 3.7

### Installing
You can install **clin** directly from [PyPI](https://pypi.org/project/clin/)
using pip:

```bash
pip install clin
```

### Getting started

After this you should be able to run the `clin` tool:
```bash
~ clin --help
Usage: clin [OPTIONS] COMMAND [ARGS]...
...
```

Please refer to the [documentation](https://github.com/zalando-incubator/clin/tree/master/docs)
and [examples](https://github.com/zalando-incubator/clin/tree/master/docs/examples).

## Contributing

Please read [CONTRIBUTING](https://github.com/zalando-incubator/clin/blob/master/CONTRIBUTING.md)
for details on our process for submitting pull requests to us, and please ensure
you follow the [CODE_OF_CONDUCT](https://github.com/zalando-incubator/clin/blob/master/CODE_OF_CONDUCT.md).

### Prerequisites

* [Python](https://www.python.org/) >= 3.7
* [Poetry](https://python-poetry.org/) for packaging and dependency
  management. See the [official docs](https://python-poetry.org/docs/) for
  instructions on installation and basic usage.

### Installing
After cloning the repository, use `poetry` to create a new virtual environment
and restore all dependencies.

```bash
poetry install
```

If you're using an IDE (eg. PyCharm), make sure that it's configured to use the
virtual environment created by poetry as the project's interpreter. You can find
the path to the used environment with `poetry env info`.

### Running the tests

```bash
poetry run pytest
```

## Versioning

We use [SemVer](http://semver.org) for versioning. For the versions available,
see the [tags on this repository](https://github.com/zalando-incubator/clin/tags).

## Authors

* **Dmitry Erokhin** [@Dmitry-Erokhin](https://github.com/Dmitry-Erokhin)
* **Daniel Stockhammer** [@dstockhammer](https://github.com/dstockhammer)

See also the list of [contributors](Chttps://github.com/zalando-incubator/clin/blob/master/ONTRIBUTORS.md)
who participated in this project.

## License

This project is licensed under the MIT License. See the
[LICENSE](https://github.com/zalando-incubator/clin/blob/master/LICENSE) file
for details.

''' Copyright (c) 2020 Arne Bachmann. '''

from setuptools import setup

setup(
  name = 'awful',
  version = "0.5.1",  # TODO use same version in awfl.py
  python_requires = '>=3.5',  # https://www.python.org/dev/peps/pep-0508/#environment-markers
  description = "Arguably Worst F*cked-Up Language",
  classifiers = [c.strip() for c in """
        Development Status :: 5 - Production/Stable
        Intended Audience :: Developers
        Intended Audience :: Other Audience
        License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)
        Operating System :: OS Independent
        Programming Language :: Other
        Programming Language :: Python
        Programming Language :: Python :: 3
        Programming Language :: Python :: 3.5
        Programming Language :: Python :: 3.6
        Programming Language :: Python :: 3.7
        Programming Language :: Python :: 3 :: Only
        """.split('\n') if c.strip()],  # https://pypi.python.org/pypi?:action=list_classifiers
  keywords = 'AWFUL programming language',
  author           = 'Arne Bachmann',
  maintainer       = 'Arne Bachmann',
  author_email     = 'ArneBachmann@users.noreply.github.com',
  maintainer_email = 'ArneBachmann@users.noreply.github.com',
  url              = 'http://github.com/ArneBachmann/awful',
  license = 'MPL-2.0',
  packages = ["awful"],
  package_dir = {"awful": "awful"},
#  package_data = {"awful": []},
  include_package_data = False,  # if True, will *NOT* package the data!
  zip_safe = False,
  entry_points = {
    'console_scripts': [
      'awful=awful.run:main'  # Subversion offline solution
    ]
  }
)

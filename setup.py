import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.txt')).read()
CHANGES = open(os.path.join(here, 'CHANGES.txt')).read()

requires = [
    'fpdf',
    'futures',
    'lepl',
    'M2Crypto',
    'passbook',
    'Pillow',
    'pyramid',
    'pyramid_beaker',
    'pyramid_chameleon',
    'pyramid_zodbconn',
    'pycrypto',
    'PyJWT',
    'pyramid_debugtoolbar',
    'pyramid_marrowmailer',
    'pyramid_mailer',
    'pyramid_tm',
    'python-dateutil',
    'qrcode',
    'requests',
    'selenium',
    'six',
    'stripe',
    'transaction',
    'waitress',
    'ZODB3'
    ]

setup(name='ticketing',
      version='0.0',
      description='ticketing',
      long_description=README + '\n\n' + CHANGES,
      classifiers=[
        "Programming Language :: Python",
        "Framework :: Pyramid",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        ],
      author='',
      author_email='',
      url='',
      keywords='web pylons pyramid',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      install_requires=requires,
      dependency_links=[
          "https://github.com/devartis/passbook.git@1.0.0#egg=Passbook-1.0.0",
      ],
      tests_require=requires,
      test_suite="ticketing",
      entry_points="""\
      [paste.app_factory]
      main = ticketing:main
      """,
      )

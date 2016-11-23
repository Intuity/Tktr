Troubleshooting
===============

+ If an "Unsupported Locale" error occurs under Ubuntu, type 'sudo locale-gen en_GB' and restart the paster instance
+ SSL issues encountered when building out under OS X can be fixed by - note you need to use M2Crypto version 0.22.6rc4
  to fix a number of dependencies on deprecated libraries:
    brew uninstall openssl (may not be necessary)
    brew uninstall swig (also may not be necessary)
	brew install openssl
    brew install swig
    env LDFLAGS="-L$(brew --prefix openssl)/lib" \
    CFLAGS="-I$(brew --prefix openssl)/include" \
    SWIG_FEATURES="-cpperraswarn -includeall -I$(brew --prefix openssl)/include" \
    bin/buildout -c development.cfg

Setup Under Ubuntu
==================

1) apt-get update
2) apt-get install build-essential libssl-dev swig libjpeg-dev
3) apt-get install python-dev virtualenv python-openssl (also check system defaults to python-2.7)
4) useradd -d /home/pyramid -m pyramid
5) su - pyramid
6) mkdir Ticketing
7) Upload files (maybe via zip) to the Ticketing directory you need:
    templates
    ticketing
    backup_database_fiveminuted.sh
    backup_database_hourly.sh
    base.cfg
    bootstrap.py
    build_and_test.sh
    CHANGES.txt
    deployment.cfg
    development.cfg
    Issues.txt
    MANIFEST.in
    README.txt
    setup.cfg
    setup.py
    testing.cfg
    TODO.txt
8) ln -s deployment.cfg buildout.cfg
9) python bootstrap.py
10) To fix buildout issues:
	cd /usr/include/openssl/
	ln -s ../x86_64-linux-gnu/openssl/opensslconf.h .
	pip install fpdf
10) bin/buildout
11) exit; Then under root run sudo locale-gen en_GB
12) su - pyramid
13) Update parameters in data/paste.ini for hostname and raven authentication messages
14) Check public keys have downloaded from Raven authentication
13) bin/supervisord (brings up the instance on port 6543)
14) bin/supervisorctl (shows running processes)
15) stop all (under supervisor stops all processes)

# Tktr
A platform for ticketing events such as May Balls and June Events for Cambridge Colleges

## Pre-requisites
It is strongly recommended that Tkt is installed on Ubuntu Server, as this is where it has been developed
and deployed previously - however it should be possible to install Tkt under any Linux distribution.
To install Tkt you will need:

 - Python 2.7 installed
 - VirtualEnv
 - Packages (from Aptitude): build-essential libssl-dev swig libjpeg-dev python-dev virtualenv python-openssl


## Installation
Execute the following steps on the command line to install Tkt:

1) git clone git@github.com:Intuity/Tkt.git
2) cd Tkt
3) virtualenv venv
4) source venv/bin/activate
5) python bootstrap.py -c deployment.cfg
6) bin/buildout -c deployment.cfg
7) bin/pserve data/paste.ini

## Troubleshooting

### "Unsupported Locale" errors under Ubuntu
To resolve "Unsupported Locale" errors run 'sudo locale-gen en_GB' from the command line, and then restart
the paster/gunicorn instance.

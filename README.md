# Tktr
A platform for ticketing events such as May Balls and June Events for Cambridge Colleges

**Sections:**

- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
 * ["Unsupported Locale" errors under Ubuntu](#unsupported-locale-errors-under-ubuntu)

## Requirements
It is strongly recommended that Tktr is installed on Ubuntu Server, as this is where it has been developed
and deployed previously - however it should be possible to install Tktr under any Linux distribution.
To install and run Tktr you will need:

 - Python 2.7 installed
 - VirtualEnv
 - Packages (from Aptitude): build-essential libssl-dev swig libjpeg-dev python-dev virtualenv python-openssl


## Installation
Execute the following steps on the command line to install Tktr:

1. git clone git@github.com:Intuity/Tktr.git
2. cd Tktr
3. virtualenv venv
4. source venv/bin/activate
5. python bootstrap.py -c deployment.cfg
6. bin/buildout -c deployment.cfg
7. bin/pserve data/paste.ini

Visit http://127.0.0.1:6543 in your web browser and you should see the configuration wizard. However, before proceeding kill the pserve
instance by pressing `CTRL+C` and move on to [Configuration](#configuration)

## Configuration
Whilst the buildout procedure leaves Tktr in a working state, there are a number of configuration options that you may wish to set.

Firstly, open `data/paste.ini` in a text editor and change the following lines and make changes to the following sections:

#### Marrow Mailer Configuration
Marrow Mailer is used by Tktr to send emails via a specified transport (be this SMTP, or a bulk mailing service like Mailchimp). For most 
uses, a SMTP account with a decent provider (such as GMail) will be sufficient - however be mindful of daily usage limits. The most common
options to update within `paste.ini` are:

```bash
mail.transport.use = smtp                           # Select a transport to use - SMTP will suit most users
mail.transport.timeout.int = 30                     # If your email provider is slow, increase this timeout
mail.transport.max_messages_per_connection.int = 5  # Set this to a sensible value to avoid overloading your email host
...
sender_name = Tktr Ticketing System                 # This will be appear to the recipient as the sender's name
sender_email = donotreply@example.com               # This will appear as the sender's email - usually the same as the email account
mail.transport.host = smtp.example.com              # Email host's hostname
mail.transport.port.int = 465                       # Email host's port number
mail.transport.tls = ssl                            # Email host's SSL/TLS settings (delete if no SSL)
mail.transport.username = donotreply@example.com    # Username for SMTP access to email host
mail.transport.password = mypassword                # Password for SMTP access to email host
```

#### Tktr API Authentication Configuration
Tktr offers an API for checking guests into your event, allowing for apps to be developed.

## Troubleshooting

### "Unsupported Locale" errors under Ubuntu
To resolve "Unsupported Locale" errors run 'sudo locale-gen en_GB' from the command line, and then restart
the paster/gunicorn instance.

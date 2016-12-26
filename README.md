# Tktr
A powerful ticketing platform for May Balls, June Events and Arts Festivals (or any other type of event really...) for the University of
Cambridge.

**Sections:**

- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [First Run Setup](#first-run-setup)
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

```bash
$> git clone git@github.com:Intuity/Tktr.git
$> cd Tktr
$> virtualenv venv
$> source venv/bin/activate
$> python bootstrap.py -c deployment.cfg
$> bin/buildout -c deployment.cfg
$> bin/pserve data/paste.ini
```

Visit http://127.0.0.1:6543 in your web browser and you should see the configuration wizard. However, before proceeding kill the pserve
instance by pressing `CTRL+C` and move on to [Configuration](#configuration)

## Configuration
Whilst the buildout procedure leaves Tktr in a working state, there are a number of configuration options that you may wish to set. Please
note that buildout will always overwrite configuration files within the `data/` folder with versions from `template/` - so make sure to keep
a record of your changes.

Firstly, open `data/paste.ini` in a text editor and change the following lines and make changes to the following sections:

#### Server Hostname and Port Configuration
Tktr can be configured to run on a custom port number (by default 6543) to suit your configuration. Although Tktr runs under its own web server,
we advise configuring a proxy-pass through a HTTP server such as Apache or Nginx to allow for easy configuration of hosting options and SSL
encryption. A number of settings exists within `data/paste.ini` to assist with different configurations:

```bash
[app:main]
...
hostname = http://127.0.0.1:6543                    # Set this to the external hostname for Tktr, compensating for any proxy-pass configuration
                                                    # for example, if using a proxy-pass from an SSL subdomain set hostname to an address of the
                                                    # form: https://mysubdomain.mydomain.com - this parameter is used to assemble absolute links
...
[server:main]
...
host = 0.0.0.0                                      # The host's IP address, for most purposes '0.0.0.0' is suitable
port = 6543                                         # The port number to serve on - ensure this doesn't clash with any other running services
```

#### Raven Session Authentication
Raven is the student and staff authentication system for the University of Cambridge, and is the main authentication system for Tktr. A
number of parameters exist to configure this authentication pathway. You may wish to update these parameters for your own deployment:

```bash
raven.testing = false                               # If you wish to use the demo Raven authentication system set this to 'true' - for
                                                    # staging into deployment, this should always be 'false'.
raven.checkstr = tktr_ticketing_system              # A string used to acknowledge a login via the Raven authentication system
raven.description = Tktr Login                      # A human-readable description that the Raven authentication system displays to the student/
                                                    # staff member when logging in. This should be recognisable as identifying your deployment.
raven.timeout_msg = Please try again.               # A help message in case authentication times out.
```

#### Session Cookie Configuration
Tktr tracks the customer's journey through the check-out process by using session objects. These objects hold the state of the customer's
ticket order, their logged-in identity and any other necessary information. To provide secure sessions, it is advisable to change the
default hashing secret. The following settings within `data/paste.ini` are relevant:

```bash
session.key = tktr_session                          # The name of the cookie used to track the customer (default value is fine)
session.secret = thisismysessionsecret              # The secret used to hash the customer's identity (change this value for security!)
```

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
Tktr offers an API for checking guests into your event, allowing for external apps and services to manage the check-in process. Some options
exist within the `paste.ini` file that control access. You will need to change the following options for your own security:

```bash
api.session_secret = myapisessionsecret             # This is used to generate API authentication keys, it should be a long random string.
api.session_expiry = 86400000                       # This parameter determines how long an authentication key exists for before
                                                    # re-authentication is required.
```

## First Run Setup
Once you've configured `data/paste.ini` to your requirements, start the server again by opening a terminal window within the 'Tktr' deployment
directory and typing `bin/pserve data/paste.ini` then open a web browser and go to the hostname you configured (make sure you've setup any
necessary Apache/Nginx proxy-passes - by default the hostname is `http://127.0.0.1:6543`).

When you have navigated to the configured hostname you'll be welcomed by the first-time setup screen, entitled 'Setup Ticketing'. This wizard
will guide you through the first few stages of setting up your database and administration accounts, as well as setting up some basic details
of your event such as the date and title.

Once you have completed setup, you'll be directed to login to the administration system at `http://127.0.0.1:6543/admin/login` (or whatever
hostname is appropriate to the value configured in `data/paste.ini`). The default username is 'admin', and the password is the one you entered
during the setup wizard.

If you want to begin again with a clean setup, simply stop the server (by pressing `CTRL+C` on the command line) then delete the contents of 
`data/database/` (making sure the `data/database/` folder still exists afterwards!) and then start the server again using the command
`bin/pserve data/paste.ini`. When you visit the ticketing system again, you'll find yourself taken back to the first-time setup procedure.

## Troubleshooting

### "Unsupported Locale" errors under Ubuntu
To resolve "Unsupported Locale" errors run 'sudo locale-gen en_GB' from the command line, and then restart
the paster/gunicorn instance.

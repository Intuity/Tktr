import os, socket
from marrow.mailer import Message
from pyramid_marrowmailer import get_mailer
from ticketing.models import PROP_KEYS

import logging
logging = logging.getLogger("ticketing") 

class Mail(object):

    def __init__(self, request):
        self.request = request

    def compose_from_template(self, template, replacements):
        base_path = self.request.registry._settings["base_dir"]
        rich_path = os.path.join(base_path, "templates/mail/%s_rich.html" % template)
        plain_path = os.path.join(base_path, "templates/mail/%s_plain.txt" % template)
        # Read in the templates
        # - Rich Template
        rich_content = None
        if os.path.isfile(rich_path):
            with open(rich_path, "r") as f:
                rich_content = f.read()
        if rich_content != None:
            rich_content = rich_content.replace("\n","").replace("\t","")
        # - Plain Template
        plain_content = None
        if os.path.isfile(plain_path):
            with open(plain_path, "r") as f:
                plain_content = f.read()
        # Run replacements
        replacements['AUTOINCLUDEDTEXT'] = PROP_KEYS.getProperty(self.request, PROP_KEYS.AUTO_EMAIL_INCLUDED_TEXT)
        replacements['AUTOINCLUDEDCONTACT'] = PROP_KEYS.getProperty(self.request, PROP_KEYS.AUTO_EMAIL_CONTACT_DETAILS)
        for key in replacements:
            rep_key = "!!%s!!" % key.upper()
            if rich_content != None: rich_content = rich_content.replace(rep_key, str(replacements[key]))
            if plain_content != None: plain_content = plain_content.replace(rep_key, str(replacements[key]))
        return {
            "rich":     rich_content,
            "plain":    plain_content
        }

    def send_email(self, user_id, subject, content, pdf_attachment=None):
        if user_id not in self.request.root.users:
            logging.error("When sending email, user ID %s does not exist" % user_id)
            return False
        user = self.request.root.users[user_id]
        if user.profile == None or user.profile.email == None:
            logging.error("When sending email, user ID %s does not have a profile or email address" % user_id)
            return False
        try:
            # Compose message
            send_name = self.request.registry._settings["sender_name"]
            send_email = self.request.registry._settings["sender_email"]
            message = Message(
                author  = '%s <%s>' % (send_name, send_email),
                subject = "%s - %s" % (PROP_KEYS.getProperty(self.request, PROP_KEYS.EVENT_NAME), subject),
                to      = user.profile.email,
                rich    = content["rich"],
                plain   = content["plain"]
            )
            # Attach any available PDFs
            if pdf_attachment != None:
                message.attach("tickets.pdf", data=pdf_attachment, maintype="application", subtype="pdf")
            # Dispatch Message
            get_mailer(self.request).send(message)
            logging.info("Sent email with subject '%s' to email %s" % (subject, user.profile.email))
            return True
        except socket.error:
            logging.exception("Socket error occurred when sending email to user %s" % user_id)
            return False
        except Exception:
            logging.exception("Email send exception occurred to user %s" % user_id)
            return False

    def send_bulk_email(self, user_ids, subject, content):
        emails = []
        for user_id in user_ids:
            if not user_id in self.request.root.users: continue
            user = self.request.root.users[user_id]
            if user.profile == None or user.profile.email == None: continue
            emails.append(user.email)
        if len(emails) <= 0: return False
        try:
            # Compose message
            send_name = self.request.registry._settings["sender_name"]
            send_email = self.request.registry._settings["sender_email"]
            message = Message(
                author  = '%s <%s>' % (send_name, send_email),
                subject = "%s - %s" % (PROP_KEYS.getProperty(self.request, PROP_KEYS.EVENT_NAME), subject),
                bcc     = emails,
                rich    = content["rich"],
                plain   = content["plain"]
            )
            # Dispatch Message
            get_mailer(self.request).send(message)
            logging.info("Sent email with subject '%s' to emails %s" % (subject, emails))
            return True
        except socket.error:
            logging.exception("Socket error occurred when sending email to user %s" % user_id)
            return False
        except Exception:
            logging.exception("Email send exception occurred to user %s" % user_id)
            return False

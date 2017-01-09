import os
from pyramid.url import route_path
from pyramid.httpexceptions import HTTPFound
from pyramid.view import view_config
from pyramid.security import remember

from Crypto.PublicKey import RSA
from Crypto.Hash import SHA
from Crypto.Signature import PKCS1_v1_5

import requests, urllib, re, datetime, base64, md5

from ticketing.macros.baselayout import BaseLayout

import logging
logging = logging.getLogger("ticketing") 

def includeme(config):
    config.add_route('raven_first_stage','/raven_first_stage')
    config.add_route('raven_second_stage','/raven_second_stage')


class RavenSession(object):
    raven_version = None
    raven_status = None
    raven_msg = None
    raven_issue_date = None
    raven_id = None
    raven_url = None
    raven_crsid = None
    raven_ptags = None
    raven_auth = None
    raven_sso = None
    raven_lifetime = None
    raven_params = None
    raven_key_id = None
    raven_signature = None
    rav_str = None
    raven_public_key = "data/keys/pubkey2"
    
    # Automatically populates
    def __init__(self, rav_str, basepath, test=False):
        parts = rav_str.split("!")
        self.rav_str            = rav_str
        self.raven_version      = str(parts[0])
        self.raven_status       = str(parts[1])
        self.raven_msg          = str(parts[2])
        self.raven_issue_date   = parts[3]
        self.raven_id           = parts[4]
        self.raven_url          = str(parts[5])
        self.raven_crsid        = str(parts[6]).lower().replace(" ","")
        self.raven_ptags        = parts[7]
        self.raven_auth         = parts[8]
        self.raven_sso          = parts[9]
        self.raven_lifetime     = parts[10]
        self.raven_params       = parts[11]
        self.raven_key_id       = parts[12]
        self.raven_signature    = parts[13]
        if test:
            self.raven_public_key = "data/keys/pubkey_test"
        self.raven_public_key = os.path.join(basepath, self.raven_public_key)
    
    # Verify signature is valid
    def verifySignature(self):
        key = RSA.importKey(open(self.raven_public_key).read())
        
        # Compile the parts to hash together
        parts = self.rav_str.split("!")
        parts.pop() # Remove the last two items related to signing
        parts.pop()
        to_hash = "!".join(parts)
        # Now hash it and verify
        our_hash = SHA.new(to_hash)
        #print our_hash
        verifier = PKCS1_v1_5.new(key)
        # Obtain the correct form of the signature
        signature = urllib.unquote(self.raven_signature)
        signature = signature.replace("-","+")
        signature = signature.replace(".","/")
        signature = signature.replace("_","=")
        signature = base64.b64decode(signature)
        if verifier.verify(our_hash, signature):
            return True
        else:
            return False

class Raven(BaseLayout):
    
    raven_auth_url  = "https://raven.cam.ac.uk/auth/authenticate.html"
    raven_auth_key  = "data/keys/pubkey2"
    raven_version   = "3"
    our_hostname    = "http://127.0.0.1:6543/raven_second_stage/"
    our_checkstr    = "sidsussex_ticketing"
    our_description = "May Ball Ticketing System"
    our_timeout_msg = "Session timed out, please try again."
    test = False
    
    def __init__(self, context, request):
        self.request = request
        self.context = context
        
        # Change variables to those carried in request settings
        self.our_hostname = (self.request.registry._settings.hostname + route_path("raven_second_stage", self.request))
        self.our_checkstr = self.request.registry._settings['raven.checkstr']
        self.our_description = self.request.registry._settings['raven.description']
        self.our_timeout_msg = self.request.registry._settings['raven.timeout_msg']
        
        if self.request.registry._settings['raven.testing'] == "true":
            self.test = True
            self.raven_auth_url = "https://demo.raven.cam.ac.uk/auth/authenticate.html"
            self.raven_auth_key = "data/keys/pubkey_test"
    
    @view_config(route_name="raven_first_stage", permission="public")
    def startAuth(self, aauth=None, interact=None, params=None): # Must pass in the present session!
        if not self.has_queued:
            return HTTPFound(location=self.request.route_path("queue"))
        elif self.request.session == None:
            logging.error("No session was found when trying to start Raven auth")
            return HTTPFound(location="/")
        # Setup the ongoing direction
        if "action" in self.request.GET:
            self.request.session["continue_action"] = str(self.request.GET["action"])
        # Form a check string for authentication
        date = datetime.datetime.now()
        check_str = base64.b64encode(str(md5.new(self.our_checkstr + date.strftime("%Y%m%dGMT%H%I%S0")).digest()))
        self.request.session["check_str"] = check_str
        params = check_str
        # Start forming request for authentication
        location = self.raven_auth_url + "?ver=" + self.raven_version
        location += "&url=" + urllib.quote(self.our_hostname)
        location += "&desc=" + urllib.quote(self.our_description)
        if aauth != None:
            location += "&aauth=" + urllib.quote(aauth)
        if interact != None:
            location += "&iact=" + urllib.quote(interact)
        if params != None:
            location += "&params=" + urllib.quote(params)
        location += "&msg=" + urllib.quote(self.our_timeout_msg)
        location += "&date=" + urllib.quote(date.strftime("%Y%m%dGMT%H%I%S0")) + "&skew=0"
        return HTTPFound(location=location)
    
    @view_config(route_name="raven_second_stage", permission="public")
    def secondStage(self):
        if not self.has_queued:
            return HTTPFound(location=self.request.route_path("queue"))
        raw_resp = urllib.unquote(self.request.GET["WLS-Response"])
        parts = raw_resp.split("!")

        # Check it was successful
        if parts[1] != "200":
            # Clean up
            self.request.session.pop("continue_action", None)
            self.request.session.pop("check_str", None)
            self.request.session.pop("raven_route", None)
            # Alert
            self.request.session.flash("Raven authentication was unsuccessful, please try again!", "error")
            logging.error("Raven authentication failed, received response %s" % raw_resp)
            return HTTPFound(location=self.request.route_path("welcome"))

        # Get Raven parts    
        raven = RavenSession(self.request.GET["WLS-Response"], self.request.registry._settings["base_dir"], test=self.test)
        
        # Make some verifications
        verify_success = (raven.raven_status == "200")
        valid = raven.verifySignature()
        check_success = ("check_str" in self.request.session and self.request.session["check_str"] == raven.raven_params)
        
        # Check if they are still a 'current' member of the University
        check_current = ("current" in raven.raven_ptags)
        self.request.session["raven_current"] = ("current" in raven.raven_ptags)

        # Get the continuing route
        route = self.request.session["raven_route"]
        
        # Remove temporary session parts
        self.request.session.pop("continue_action", None)
        self.request.session.pop("check_str", None)
        self.request.session.pop("raven_route", None)
        
        # If all checks are good then forward on to success
        if verify_success and valid and check_success:
            self.request.session["raven"] = raven
        else:
            self.request.session["raven"] = None
        
        # Forward on
        header = remember(self.request, str(raven.raven_crsid))
        logging.info("Raven authentication succeeded for %s" % raven.raven_crsid)
        return HTTPFound(location=route, headers=header)

    def jackdaw_lookup(self, crsid):
        letters = re.findall(r"(.*?)\d+", crsid)
        found_person = None
        try:
            if len(letters) > 0:
                letters = letters[0]
                payload = { "surname" : letters[len(letters) - 1], "initials" : letters[:len(letters) - 1], "max" : "100", "exact" : "", "soundex" : "", "Search" : "Search" }
                headers = { "content-type" : "application/x-www-form-urlencoded" }
                request = requests.post("http://jackdaw.cam.ac.uk/mailsearch/", data=payload, headers=headers)
        
                info_str = request.text.replace("\n","")
                info_str = info_str.replace("\r","")
        
                dl_match = re.findall(r"<dl>(.*?)</dl>", info_str)
                if len(dl_match) > 0:
                    info_matches = re.findall(r"<dt>(.*?)</dt>.*?<dd>(.*?)</dd>.*?<dd>(.*?)</dd>", dl_match[0])
                    found_person = None
                    for person in info_matches:
                        if crsid in person[2]:
                            found_person = person
                            break
                    if found_person == None:
                        return None
                    else:
                        return {
                            "name": found_person[0],
                            "college": found_person[1].split("-")[0],
                            "email": re.findall(r"<code>(.*?)</code>", found_person[2])[0],
                        }
            else:
                raise KeyError("Problem matching CRSid: " + crsid)
        except Exception as e:
            logging.exception("Failed to connect to Jackdaw %s" % str(e))
            return None

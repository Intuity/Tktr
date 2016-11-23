from pyramid.view import view_config
from datetime import datetime

from ticketing.models import Ticketing
from ticketing.macros.baselayout import BaseLayout
from ticketing.checkin.models import CheckIn
from ticketing.models import PROP_KEYS as PROP

class CheckInControl(BaseLayout):

    @view_config(
        route_name="checkin",
        context=Ticketing,
        permission="staff",
        renderer="templates/checkin.pt"
    )
    def checkin_view(self):
        payment_id = None
        mobile_client = False
        if "payment" in self.request.GET:
            payment_id = self.request.GET['payment']
        if "client" in self.request.GET and self.request.GET["client"] == "mobile":
            mobile_client = True
        return {
            "payment_id": payment_id,
            "mobile_client": mobile_client
        }

    @view_config(
        route_name="checkin_data",
        context="ticketing.models.Ticketing",
        permission="staff",
        renderer="json"
    )
    def checkin_data_view(self):
        if "action" in self.request.GET:
            action = self.request.GET["action"]
            cam_card = ("cam_card" in self.request.GET and self.request.GET["cam_card"].lower() == "true")
            user_card = ("user_card" in self.request.GET and self.request.GET["user_card"].lower() == "true")
            if not "identifier" in self.request.GET and action in ["lookup", "checkin"]:
                return {
                    "error": "No identifier provided"
                }
            identifier = (self.request.GET["identifier"] if "identifier" in self.request.GET else None)
            if action == "lookup":
                if "override" in self.request.session:
                    self.request.session["override"] = None
                    del self.request.session["override"]
                    #print "Removing override status"
                if not self.checkin_active:
                    return {
                        "error": "Check-in not currently active",
                    }
                if cam_card or user_card:
                    identifier = identifier.lower()
                    if not identifier in self.request.root.users:
                        # Check in tickets to see if CRSid is a guest of someone
                        found = None
                        for user in self.request.root.users.values():
                            for ticket in user.tickets:
                                if ticket.guest_info != None and ticket.guest_info.crsid != None and ticket.guest_info.crsid.lower() == identifier:
                                    found = ticket
                                    break
                        if found != None:
                            return {
                                "identifier": identifier,
                                "cam_card": cam_card,
                                "user_card": user_card,
                                "found": False,
                                "error": "Person is only registered as a guest of another",
                                "override_available": True
                            }
                        else:
                            return {
                                "identifier": identifier,
                                "cam_card": cam_card,
                                "user_card": user_card,
                                "found": False,
                                "error": "User identifier does not exist",
                                "override_available": False
                            }
                    user = self.request.root.users[identifier]
                    if len(user.tickets) == 0:
                        # Check whether we might be able to override
                        found = None
                        for user in self.request.root.users.values():
                            for ticket in user.tickets:
                                if ticket.guest_info != None and ticket.guest_info.crsid != None and ticket.guest_info.crsid.lower() == identifier:
                                    found = ticket
                                    break
                        return {
                            "identifier": identifier,
                            "cam_card": cam_card,
                            "user_card": user_card,
                            "found": True,
                            "no_tickets": True,
                            "error": ("Person has no tickets of their own, is a guest of another" if found != None else "Person has no tickets"),
                            "override_available": (found != None)
                        }
                    tickets = []
                    for tick in user.tickets:
                        tickets.append({
                            "tick_id": tick.__name__,
                            "guest_name": tick.guest_info.fullname,
                            "ticket_type": tick.tick_type.name,
                            "upgrades": " + ".join([x.name for x in tick.addons.values()]),
                            "dob": (tick.guest_info.dob.strftime("%d/%m/%Y") if tick.guest_info.dob else "Not Set!"),
                            "at_cam": tick.guest_info.raven_user,
                            "checked_in": (hasattr(tick, "checked_in") and tick.checked_in == True),
                            "checkin_data": (tick.checkin_data.export() if hasattr(tick, "checkin_data") and tick.checkin_data != None else None),
                            "notes": tick.notes
                        })
                    return {
                        "identifier": identifier,
                        "cam_card": cam_card,
                        "user_card": user_card,
                        "found": True,
                        "salutation": user.profile.title,
                        "owner": user.profile.fullname,
                        "crsid": user.profile.crsid,
                        "dob_day": user.profile.dob.day,
                        "dob_month": user.profile.dob.month,
                        "dob_year": user.profile.dob.year,
                        "at_cam": user.profile.raven_user,
                        "num_tickets": len(user.tickets),
                        "tickets": tickets,
                        "notes": user.notes
                    }
                else:
                    # If not a Cambridge card then lookup the purchase ID
                    identifier = identifier.upper()
                    if not identifier in self.request.root.payments:
                        return {
                            "identifier": identifier,
                            "cam_card": False,
                            "user_card": user_card,
                            "found": False,
                            "error": "Purchase reference does not exist on the system",
                            "override_available": False
                        }
                    else:
                        payment = self.request.root.payments[identifier]
                        owner = payment.owner
                        tickets = []
                        owner_checked = False
                        if self.checkin_show_all:
                            for tick in payment.owner.tickets:
                                tickets.append({
                                    "tick_id": tick.__name__,
                                    "guest_name": tick.guest_info.fullname,
                                    "ticket_type": tick.tick_type.name,
                                    "upgrades": " + ".join([x.name for x in tick.addons.values()]),
                                    "dob": (tick.guest_info.dob.strftime("%d/%m/%Y") if tick.guest_info.dob else "Not Set!"),
                                    "at_cam": tick.guest_info.raven_user,
                                    "checked_in": (hasattr(tick, "checked_in") and tick.checked_in == True),
                                    "checkin_data": (tick.checkin_data.export() if hasattr(tick, "checkin_data") and tick.checkin_data != None else None),
                                    "notes": tick.notes
                                })
                        else:
                            for tick in payment.tickets:
                                tickets.append({
                                    "tick_id": tick.__name__,
                                    "guest_name": tick.guest_info.fullname,
                                    "ticket_type": tick.tick_type.name,
                                    "upgrades": " + ".join([x.name for x in tick.addons.values()]),
                                    "dob": (tick.guest_info.dob.strftime("%d/%m/%Y") if tick.guest_info.dob else "Not Set!"),
                                    "at_cam": tick.guest_info.raven_user,
                                    "checked_in": (hasattr(tick, "checked_in") and tick.checked_in == True),
                                    "checkin_data": (tick.checkin_data.export() if hasattr(tick, "checkin_data") and tick.checkin_data != None else None),
                                    "notes": tick.notes
                                })
                                owner_checked = (tick.checked_in if tick.checked_in else False)
                        return {
                            "identifier": identifier,
                            "cam_card": False,
                            "user_card": user_card,
                            "found": True,
                            "salutation": owner.profile.title,
                            "owner": owner.profile.fullname,
                            "dob_day": owner.profile.dob.day,
                            "dob_month": owner.profile.dob.month,
                            "dob_year": owner.profile.dob.year,
                            "at_cam": owner.profile.raven_user,
                            "num_tickets": len(payment.tickets),
                            "tickets": tickets,
                            "notes": owner.notes,
                            "owner_checked": owner_checked
                        }
                return {
                    "identifier": identifier,
                    "cam_card": cam_card,
                    "user_card": user_card
                }
            elif action == "checkin":
                if not self.checkin_active:
                    return {
                        "error": "Check-in not currently active",
                    }
                override = None
                if "override" in self.request.session and self.request.session["override"] != None:
                    override = self.request.session["override"]
                    self.request.session["override"] = None
                    del self.request.session["override"]
                tickets = None
                owner_dob = None
                if override != None:
                    for user in self.request.root.users.values():
                        for tick in user.tickets:
                            if tick.__name__ == override:
                                tickets = [tick]
                                owner_dob = tick.owner.profile.dob
                                break
                elif cam_card or user_card:
                    identifier = identifier.lower()
                    if identifier in self.request.root.users:
                        user = self.request.root.users[identifier]
                        owner_dob = user.profile.dob
                        tickets = user.tickets
                else:
                    # If not a Cambridge card then lookup the purchase ID
                    identifier = identifier.upper()
                    if identifier in self.request.root.payments:
                        payment = self.request.root.payments[identifier]
                        owner_dob = payment.owner.profile.dob
                        if self.checkin_show_all:
                            tickets = payment.owner.tickets
                        else:
                            tickets = payment.tickets
                # If we can't track down the tickets then say so
                if tickets == None:
                    return {
                        "identifier": identifier,
                        "cam_card": cam_card,
                        "user_card": user_card,
                        "error": "Can't find tickets using the identifier provided.",
                        "success": False,
                        "override_available": False
                    }
                elif not "checked" in self.request.GET:
                    return {
                        "identifier": identifier,
                        "cam_card": cam_card,
                        "user_card": user_card,
                        "error": "Missing list of check-ins to perform.",
                        "success": False,
                        "override_available": False
                    }
                # Check the provided date of birth
                if self.guest_details_required:
                    dob_day = (int(self.request.GET["dob_day"]) if "dob_day" in self.request.GET else 0)
                    dob_month = (int(self.request.GET["dob_month"]) if "dob_month" in self.request.GET else 0)
                    dob_year = (int(self.request.GET["dob_year"]) if "dob_year" in self.request.GET else 0)
                    if dob_day != owner_dob.day or dob_month != owner_dob.month or dob_year != owner_dob.year:
                        return {
                            "identifier": identifier,
                            "cam_card": cam_card,
                            "user_card": user_card,
                            "error": "Date of birth does not match that which is stored.",
                            "success": False,
                            "override_available": False
                        }
                # Otherwise go through and mark off the checkins
                ids = self.request.GET["checked"].split("|")
                if len(ids) == 0 or len(ids[0]) < 5:
                    return {
                        "identifier": identifier,
                        "cam_card": cam_card,
                        "user_card": user_card,
                        "error": "Invalid check in IDs provided.",
                        "success": False,
                        "override_available": False
                    }
                checked_in = 0
                for tick_id in ids:
                    tick = [x for x in tickets if x.__name__ == tick_id]
                    if len(tick) == 0:
                        continue
                    tick = tick[0]
                    # Otherwise perform a check in if necessary
                    if not tick.checkin_status:
                        tick.checked_in = True
                        tick.checkin_data = CheckIn()
                        tick.checkin_data.__parent__ = tick
                        tick.checkin_data.date = datetime.now()
                        tick.checkin_data.enacted_by = self.user
                        tick.checkin_data.overriden = (override != None)
                        # TODO: Fill in who performed the override!
                        checked_in += 1
                if checked_in == 0:
                    return {
                        "identifier": identifier,
                        "cam_card": cam_card,
                        "user_card": user_card,
                        "error": "No check-ins have been performed as no new IDs were provided.",
                        "success": False,
                        "override_available": False
                    }
                return {
                    "identifier": identifier,
                    "cam_card": cam_card,
                    "success": True
                }
            elif action == "override":
                if not "password" in self.request.GET:
                    return {
                        "identifier": identifier,
                        "cam_card": cam_card,
                        "user_card": user_card,
                        "success": False,
                        "error": "No override password provided!"
                    }
                else:
                    password = self.request.GET["password"]
                    over_one = self.request.root.properties[PROP.CHECKIN_OVERRIDE_ONE]
                    over_two = self.request.root.properties[PROP.CHECKIN_OVERRIDE_TWO]
                    over_three = self.request.root.properties[PROP.CHECKIN_OVERRIDE_THREE]
                    match = ((password == over_one and len(over_one) > 3) or (password == over_two and len(over_two) > 3) or (password == over_three and len(over_three) > 3))
                    if not match:
                        return {
                            "identifier": identifier,
                            "cam_card": cam_card,
                            "user_card": user_card,
                            "success": False,
                            "error": "Override password did not match!"
                        }
                # Find the guest ticket
                found = None
                for user in self.request.root.users.values():
                    for ticket in user.tickets:
                        if ticket.guest_info != None and ticket.guest_info.crsid != None and ticket.guest_info.crsid.lower() == identifier:
                            found = ticket
                            break
                # If we haven't found a ticket error
                if found == None:
                    return {
                        "identifier": identifier,
                        "cam_card": cam_card,
                        "user_card": user_card,
                        "success": False,
                        "error": "Cannot find ticket for user to override!"
                    }
                # Else we step forward into a check-in procedure
                # - Check that the owner has made a check-in
                owner_checked = False
                for ticket in found.owner.tickets:
                    if ticket.guest_info == found.owner.profile:
                        owner_checked = (ticket.checked_in if ticket.checked_in else False)
                        break
                # - Return data
                # Save the override data
                self.request.session["override"] = found.__name__
                return {
                    "identifier": identifier,
                    "cam_card": cam_card,
                    "user_card": user_card,
                    "success": True,
                    "salutation": found.owner.profile.title,
                    "owner_name": found.owner.profile.fullname,
                    "owner_crsid": (found.owner.profile.crsid if found.owner.profile.crsid != None else "-"),
                    "owner_checked": owner_checked,
                    "owner_cam": (found.owner.profile.crsid != None),
                    "num_tickets": len(found.owner.tickets),
                    "owner_notes": found.owner.notes,
                    "tickets": [{
                        "tick_id": found.__name__,
                        "guest_name": found.guest_info.fullname,
                        "ticket_type": found.tick_type.name,
                        "upgrades": " + ".join([x.name for x in found.addons.values()]),
                        "dob": (found.guest_info.dob.strftime("%d/%m/%Y") if found.guest_info.dob else "Not Set!"),
                        "at_cam": found.guest_info.raven_user,
                        "checked_in": (hasattr(found, "checked_in") and found.checked_in == True),
                        "checkin_data": (found.checkin_data.export() if hasattr(found, "checkin_data") and found.checkin_data != None else None),
                        "notes": found.notes
                    }],
                    "dob_day": found.owner.profile.dob.day,
                    "dob_month": found.owner.profile.dob.month,
                    "dob_year": found.owner.profile.dob.year,
                }
            elif action == "statistics":
                all_ticks = []
                for payment in self.request.root.payments.values():
                    for tick in payment.tickets:
                        all_ticks.append(tick)
                return {
                    "total": len([x for x in all_ticks if x.payment != None]),
                    "checkedin": len([x for x in all_ticks if x.checkin_status]),
                    "active": self.checkin_active
                }
        return {
            "error": "No data requested",
            "override_available": False
        }
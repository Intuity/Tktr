from datetime import datetime
import json
import logging
from pyramid.view import view_config

from ticketing.api.api_baseview import APIBaseView, APIPrivilegeException, APIAuthenticationException
from ticketing.checkin.models import CheckIn
from ticketing.models import Ticketing
from ticketing.models import PROP_KEYS as PROP

logging = logging.getLogger("ticketing")

class APICheckin(APIBaseView):

    @view_config(
        route_name="api_checkin_query",
        context=Ticketing,
        permission="public",
        renderer="api_renderer",
        request_method="GET"
    )
    def api_checkin_query_get_view(self):
        return {
            "error": "This is a POST only route"
        }

    @view_config(
        route_name="api_checkin_query",
        context=Ticketing,
        permission="public",
        renderer="api_renderer",
        request_method="POST"
    )
    def api_checkin_query_post_view(self):
        try:
            # Check privileges are at a sufficient level
            self.verify_privileges("staff")
            # Check if check-in is active
            if (PROP.getProperty(self.request, PROP.CHECKIN_ACTIVE) != True):
                return {
                    "error": "Check-in is not active"
                }
            # Check the form of the query
            if "query_type" not in self.request.POST or "query_value" not in self.request.POST:
                return {
                    "error": "Query type or value missing from request"
                }
            query_type = self.request.POST["query_type"].lower()
            query_value = self.request.POST["query_value"]
            if query_type not in ["payment_id", "ticket_id", "checkin_code"]:
                logging.error("API: Check-in query requested with invalid type '%s' by user %s" % (query_type, self.auth_user.username))
                return {
                    "error": "Invalid query type"
                }
            # Log the query taking place
            logging.info("API: Check-in query requested with type '%s' and value '%s' by user %s" % (query_type, query_value, self.auth_user.username))
            # Execute the query
            if query_type == "payment_id":
                if not query_value in self.request.root.payments:
                    return {
                        "error": "No payment exists for the queried ID"
                    }
                payment = self.request.root.payments[query_value]
                if payment.owner == None or payment.owner.profile == None:
                    return {
                        "error": "Incomplete owner details"
                    }
                # Prepare information on the tickets in the payment
                tickets = []
                for tick in payment.tickets:
                    if tick.guest_info != None:
                        tickets.append({
                            "ticket_id":    tick.__name__,
                            "type":         tick.tick_type.name,
                            "addons":       [x.name for x in tick.addons.values()],
                            "notes":        tick.notes,
                            "guest_details": {
                                "title":    tick.guest_info.title,
                                "forename": tick.guest_info.forename,
                                "surname":  tick.guest_info.surname,
                                "dob":      (tick.guest_info.dob.isoformat() if tick.guest_info.dob != None else "n/a"),
                                "grad_status":  tick.guest_info.grad_status,
                                "college":  tick.guest_info.college
                            },
                            "checked_in": tick.checked_in,
                            "checkin_details": ({
                                "date":         (tick.checkin_data.date.isoformat() if tick.checkin_data.date else 0),
                                "enacted_by":   (tick.checkin_data.enacted_by.username if tick.checkin_data.enacted_by.username != None else 'n/a'),
                                "overridden":   tick.checkin_data.overridden
                            } if tick.checkin_data else 'n/a')
                        })
                    else:
                        tickets.append({
                            "ticket_id":    tick.__name__,
                            "type":         tick.tick_type.name,
                            "addons":       [x.name for x in tick.addons.values()],
                            "notes":        tick.notes,
                            "checked_in":   tick.checked_in,
                            "checkin_details": tick.checkin_data
                        })
                return {
                    "query_type":   query_type,
                    "query_value":  query_value,
                    # Payment details
                    "payment_id":   payment.__name__,
                    "notes":        payment.notes,
                    "paid":         payment.paid,
                    "owner": {
                        "title":    payment.owner.profile.title,
                        "forename": payment.owner.profile.forename,
                        "surname":  payment.owner.profile.surname,
                        "dob":      (payment.owner.profile.dob.isoformat() if payment.owner.profile.dob != None else "n/a"),
                        "grad_status":  payment.owner.profile.grad_status,
                        "college":  payment.owner.profile.college,
                        "notes":    payment.owner.notes
                    },
                    "tickets":      tickets,
                    "num_tickets":  len(payment.tickets)
                }
            elif query_type == "ticket_id":
                tickets = []
                for payment in self.request.root.payments.values():
                    tickets += payment.tickets
                tickets = [x for x in tickets if query_value.lower() in x.__name__.lower() and query_value.lower() in x.id_code.lower()]
                if len(tickets) == 1 and tickets[0].payment != None:
                    ticket = tickets[0]
                    payment = ticket.payment
                    return {
                        "query_type":   query_type,
                        "query_value":  query_value,
                        # Payment details
                        "payment_id":   payment.__name__,
                        "notes":        payment.notes,
                        "paid":         payment.paid,
                        "owner": {
                            "title":    payment.owner.profile.title,
                            "forename": payment.owner.profile.forename,
                            "surname":  payment.owner.profile.surname,
                            "dob":      (payment.owner.profile.dob.isoformat() if payment.owner.profile.dob != None else "n/a"),
                            "grad_status":  payment.owner.profile.grad_status,
                            "college":  payment.owner.profile.college,
                            "notes":    payment.owner.notes
                        },
                        "tickets": [{
                            "ticket_id":    ticket.__name__,
                            "type":         ticket.tick_type.name,
                            "addons":       [x.name for x in ticket.addons.values()],
                            "notes":        ticket.notes,
                            "guest_details": {
                                "title":    ticket.guest_info.title,
                                "forename": ticket.guest_info.forename,
                                "surname":  ticket.guest_info.surname,
                                "dob":      (ticket.guest_info.dob.isoformat() if ticket.guest_info.dob != None else "n/a"),
                                "grad_status":  ticket.guest_info.grad_status,
                                "college":  ticket.guest_info.college
                            },
                            "checked_in":   ticket.checked_in,
                            "checkin_details": ({
                                "date":         (ticket.checkin_data.date.isoformat() if ticket.checkin_data.date else 0),
                                "enacted_by":   (ticket.checkin_data.enacted_by.username if ticket.checkin_data.enacted_by.username != None else 'n/a'),
                                "overriden":   ticket.checkin_data.overriden
                            } if ticket.checkin_data else 'n/a')
                        }],
                        "num_tickets": 1
                    }
                else:
                    return {
                        "query_type": query_type,
                        "query_value": query_value,
                        "error": "Requested ticket not found"
                    }
            else:
                return {
                    "query_type": query_type,
                    "query_value": query_value,
                    "error": "Method not implemented"
                }
        except APIPrivilegeException as e:
            logging.error("API: A privilege exception was thrown for user %s during check-in query: %s" % (self.auth_user.username, str(e)))
            return {
                "error": str(e)
            }
        except APIAuthenticationException as e:
            logging.error("API: User accessing check-in query is not authenticated")
            return {
                "error": str(e)
            }
        except Exception as e:
            if self.auth_user != None:
                logging.error("API: An exception was thrown for user %s during check-in query: %s" % (self.auth_user.username, str(e)))
            else:
                logging.error("API: An exception was thrown during check-in query: %s" % str(e))
            return {
                "error": "An unexpected error occurred"
            }

    @view_config(
        route_name="api_checkin_enact",
        context=Ticketing,
        permission="public",
        renderer="api_renderer",
        request_method="GET"
    )
    def api_checkin_enact_get_view(self):
        return {
            "error": "This is a POST only route"
        }

    @view_config(
        route_name="api_checkin_enact",
        context=Ticketing,
        permission="public",
        renderer="api_renderer",
        request_method="POST"
    )
    def api_checkin_enact_post_view(self):
        try:
            # Check privileges are at a sufficient level
            self.verify_privileges("staff")
            # Check if check-in is active
            if (PROP.getProperty(self.request, PROP.CHECKIN_ACTIVE) != True):
                return {
                    "error": "Check-in is not active"
                }
            # Check that at least one ticket ID has been provided
            if "ticket_ids" not in self.request.POST:
                logging.error("API: Ticket IDs not provided in request by user %s" % self.auth_user.username)
                return {
                    "error": "Ticket IDs missing from request"
                }
            ticket_ids = None
            try:
                ticket_ids = json.loads(self.request.POST["ticket_ids"])
            except Exception as e:
                logging.error("API: Ticket IDs were provided in an invalid format by user %s: %s" % (self.auth_user.username, str(e)))
                return {
                    "error": "Ticket ID format is invalid"
                }
            if ticket_ids == None:
                logging.error("API: Ticket IDs not provided in request by user %s" % self.auth_user.username)
                return {
                    "error": "No ticket IDs were provided"
                }
            ticket_ids = [x for x in ticket_ids if isinstance(x, basestring)]
            if len(ticket_ids) == 0:
                logging.error("API: Ticket IDs not provided in request by user %s" % self.auth_user.username)
                return {
                    "error": "No ticket IDs were provided"
                }
            # Check that all of the ticket IDs provided are valid
            all_tickets = []
            for payment in self.request.root.payments.values():
                all_tickets += payment.tickets
            tickets = [x for x in all_tickets if x.__name__ in ticket_ids and x.id_code in ticket_ids]
            if len(tickets) == 0:
                logging.error("API: No tickets found for IDs %s provided by user %s" % (self.request.POST["ticket_ids"], self.auth_user.username))
                return {
                    "error": "No tickets were found for the IDs provided"
                }
            elif len(tickets) != len(ticket_ids):
                logging.error("API: Incorrect ticket count found for IDs %s provided by user %s" % (self.request.POST["ticket_ids"], self.auth_user.username))
                return {
                    "error": "Some tickets were not found"
                }
            # Check all are paid and not already checked-in
            already_checked_in = []
            for tick in tickets:
                if not tick.payment.paid:
                    logging.error("API: Could not enact check in as at least one of the tickets is unpaid, tickets %s by user %s" % (self.request.POST["ticket_ids"], self.auth_user.username))
                    return {
                        "error": "Payment is not complete for tickets"
                    }
                elif tick.checked_in:
                    already_checked_in.append(tick.__name__)
            if len(already_checked_in) > 0:
                logging.error("API: Some tickets are already checked in %s, new check-in enaction by user %s" % (",".join(already_checked_in), self.auth_user.username))
                return {
                    "error": "Some tickets are already checked-in",
                    "already_checked_in": already_checked_in,
                    "ticket_ids": ticket_ids
                }
            # Process the check-in for the tickets listed
            for tick in tickets:
                tick.checked_in = True
                tick.checkin_data = CheckIn()
                tick.checkin_data.__parent__ = tick
                tick.checkin_data.date = datetime.now()
                tick.checkin_data.enacted_by = self.auth_user
                tick.checkin_data.overriden = False
                # Log the action
                logging.info("API: Ticket %s was checked in by user %s" % (tick.__name__, self.auth_user.username))
            return {
                "checked_in": ticket_ids
            }
        except APIPrivilegeException as e:
            logging.error("API: A privilege exception was thrown for user %s during check-in enaction: %s" % (self.auth_user.username, str(e)))
            return {
                "error": str(e)
            }
        except APIAuthenticationException as e:
            logging.error("API: User accessing check-in enaction is not authenticated")
            return {
                "error": str(e)
            }
        except Exception as e:
            if self.auth_user != None:
                logging.error("API: An exception was thrown for user %s during check-in enaction: %s" % (self.auth_user.username, str(e)))
            else:
                logging.error("API: An exception was thrown during check-in enaction: %s" % str(e))
            return {
                "error": "An unexpected error occurred"
            }

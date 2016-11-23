var Ticketing = function() {
    
    this.selected_tickets = {};
    
    var calc_cost = function() {
        
        var total = 0;
        var count = 0;
        var ticket_limit = 0;
        
        for(var key in this.selected_tickets) {
            var ticket = this.selected_tickets[key];
            total += ticket["cost"] * ticket["quantity"];
            count += ticket["quantity"];
        }
        
        $("#ticket_count").html(count);
        $("#ticket_cost").html(total);
        
        if(count > 1) {
            $("#tickets_purchased").removeClass("hidden");
            $("#tickets_unselected").addClass("hidden");
            $("#ticket_plural").html("s"); 
        }
        else if(count > 0) {
            $("#tickets_purchased").removeClass("hidden");
            $("#tickets_unselected").addClass("hidden");
            $("#ticket_plural").html(""); 
        }
        else {
            $("#tickets_purchased").addClass("hidden");
            $("#tickets_unselected").removeClass("hidden");
        }
        
        if(count > 0 && this.ticket_limit > 0 && count > this.ticket_limit) $("#ticket_limit").html("This is over the maxiumum number of tickets (" + this.ticket_limit + ") you are currently allowed to purchase.");
        else $("#ticket_limit").html("");
        
    }; this.calc_cost = calc_cost;
    
    var modify_selected_tickets = function(type, quantity, cost) {
        this.selected_tickets[type] = {"cost" : cost, "quantity" : parseInt(quantity)};
        this.calc_cost();
    }; this.modify_selected_tickets = modify_selected_tickets;
    
    var set_ticket_limit = function(limit_amount) {
        if(limit_amount < 0) limit_amount = 0;
        this.ticket_limit = limit_amount;
    }; this.set_ticket_limit = set_ticket_limit;
    
	var queue_position = function() {
		try {
			$.getJSON("/queue_information", function(data) {
				// Update queue information
				try { 
					if(data["position"] == "ready") {
						window.location.href = "/queue_front";
					} else if(data["position"] == "waiting") {
						$("#position").text("You are at the front of the queue, just waiting for a slot to become available.");
					} else {
						var index = parseInt(data["position"]);
						if (index <= 0) window.location.href = "/queue";
						else $("#position").text("You are currently position " + (index + 1));
					}
					setTimeout("window.ticketing.show_queue_load();", 9500);
					setTimeout("window.ticketing.queue_position();", 10000);
				} catch(e) {
					setTimeout("window.ticketing.show_queue_load();", 9500);
					setTimeout("window.ticketing.queue_position();", 10000);
				}
				// Update stock status
				$("#stockstatus").empty();
				for(var key in data["stock"]) {
					var row = document.createElement("tr");
					var col_one = document.createElement("td");
					var col_two = document.createElement("td");
					col_one.innerHTML = key
					col_two.innerHTML = data["stock"][key];
					row.appendChild(col_one);
					row.appendChild(col_two);
					document.getElementById("stockstatus").appendChild(row);
				}
			});
		} catch(e) {
			setTimeout("window.ticketing.queue_position();", 5000);
		}
	}; this.queue_position = queue_position;
	
	var show_queue_load = function() {
		$("#position").html('<i class="icon-spinner icon-spin"></i> Updating current queue position.');
	}; this.show_queue_load = show_queue_load;
	
	this.seconds = 0;
	
	var start_timer = function(seconds) {
		this.seconds = seconds;
		if(this.seconds > 0) setTimeout("window.ticketing.step_timer();", 1000);
	}; this.start_timer = start_timer;
	
	this.count_up = 0;
	var step_timer = function() {
		this.seconds -= 1;
		// Ping server and check our timing is correct
		if(this.seconds >= 0 && this.count_up >= 30) {
			// Fetch the time from the server
			$.get("/timeleft", function(data) {
				try {
					window.ticketing.seconds = parseInt(data);
					window.ticketing.format_time(window.ticketing.seconds);
					window.ticketing.count_up = 0;
					setTimeout("window.ticketing.step_timer();", 1000);
				} catch(e) {
					console.log("Couldn't talk to server " + e);
					$("#timeleft").text("Server unavailable, please check your internet connection.");
					setTimeout("window.ticketing.step_timer();", 1000);
				}
			}).fail(function() {
				console.log("Couldn't talk to server");
				$("#timeleft").text("Server unavailable, please check your internet connection.");
				setTimeout("window.ticketing.step_timer();", 1000);
			});
		} else {
			// Format the time
			this.format_time(this.seconds);
			// Path choice
			if (this.seconds >= 0) setTimeout("window.ticketing.step_timer();", 1000);
			else window.location.href = "/timedout"; // Force refresh
			this.count_up += 1;
		}
	}; this.step_timer = step_timer;
	
	var format_time = function(raw_seconds) {
		raw_seconds = parseInt(raw_seconds); // Force into integer
		var minutes = Math.floor(raw_seconds / 60.0);
		var seconds = raw_seconds - minutes * 60;
		var time_str = "";
		if(seconds <= 0) time_str = minutes + ":00";
		else if(seconds < 10) time_str = minutes + ":0" + seconds;
		else time_str = minutes + ":" + seconds;
		$("#timeleft").text("You have " + time_str + " left to purchase tickets.");
	}; this.format_time = format_time;
	

	var close_cookie_policy = function () {
		// Set cookie
		var expiry = new Date();
		expiry.setDate(expiry.getDate() + 10);
		var cookie = "cookie_policy=cookie_agreed; expires=" + expiry.toUTCString() + "; path=/";
		document.cookie = cookie;
		// Close policy
		document.body.removeChild(document.getElementById("cookie_splash"));
	}; this.close_cookie_policy = close_cookie_policy;
	
	var check_username = function(typed) {
		typed = typed.replace(/\s/g, '');
		if(typed.length < 3) return;
		$.get("/admin/accounts/user/" + typed + "/check", function(data) {
			if(data == "true") {
				$("#usernamecheck").html('&nbsp;<i class="icon-ok-sign"></i> Username correct');
				$("#usernamecheck").css("color","green");
			} else {
				$("#usernamecheck").html('&nbsp;<i class="icon-remove-sign"></i> Username incorrect');
				$("#usernamecheck").css("color","red");
			}
		});
	}; this.check_username = check_username;
	
};

$(function() {
    $(".nojsblockout").remove();
});

$(document).ready(function() {
    window.ticketing = new Ticketing();
});
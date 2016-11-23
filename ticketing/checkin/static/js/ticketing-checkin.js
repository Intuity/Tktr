// Register base object if necessary
var Tick = Tick || {};
// Register checkin object
Tick.checkin = {};

Tick.checkin.key_timeout = null;
Tick.checkin.session_data = null;
Tick.checkin.override_data = null;
Tick.checkin.deactivated = false;
Tick.checkin.guest_details = false;
Tick.checkin.mobile_client = false;

Tick.checkin.animating = false;

Tick.checkin.lookup = function(ascii, cam_card, username_card) {
    $("#identifier").prop("disabled", true);
    
	$.ajax({
		dataType: "json",
		url: "/checkin/data",
		data: {
			action: "lookup",
			identifier: ascii,
			cam_card: cam_card,
            user_card: username_card
		},
		success: function(data) {
			if(data.found && !data.no_tickets) {
				Tick.checkin.session_data = data;
				$("#salutation").html(data.salutation);
				$("#holder").html(data.owner);
				$("#numtickets").html(data.num_tickets);
				if(data.cam_card) {
					$("#crsidbox").css("display", "table-row");
					$("#crsid").html(data.crsid);
				} else {
					$("#crsidbox").css("display", "none");
					$("#crsid").html("");
				}
				if(data.at_cam) $("#atcam").html("Yes");
				else $("#atcam").html("No");
				if(data.owner_checked) $("#owner_checked").html("Yes");
				else $("#owner_checked").html("No");
				$("#notes").html(data.notes);
				// Guests
				$("#gueststable").empty();
				$("#guestnotes").html("");
				var table = document.getElementById("gueststable");
				for(var i = 0; i < data.tickets.length; i++) {
					var guest = data.tickets[i];
					var row = document.createElement("tr");
                    if(Tick.checkin.guest_details) {
    					// Name
    					var g_name = document.createElement("td");
    					row.appendChild(g_name);
    					g_name.innerHTML = guest.guest_name;
    					// Date of birth
    					var g_dob = document.createElement("td");
    					row.appendChild(g_dob);
    					g_dob.innerHTML = guest.dob;
    					// At Cambridge
    					var g_atcam = document.createElement("td");
    					row.appendChild(g_atcam);
    					if(guest.at_cam) g_atcam.innerHTML = "Yes";
    					else g_atcam.innerHTML = "No";
                    }
					// Ticket type
					var g_type = document.createElement("td");
					row.appendChild(g_type);
					g_type.innerHTML = guest.ticket_type;
					// Ticket upgrades
					var g_upgrades = document.createElement("td");
					row.appendChild(g_upgrades);
					g_upgrades.innerHTML = guest.upgrades;
					// Actions
					var g_actions = document.createElement("td");
					row.appendChild(g_actions);
					if(!guest.checked_in) g_actions.innerHTML = '<a class="ll_btn" onclick="Tick.checkin.confirm_guest(' + i + ');"><i class="icon-check-empty"></i> Confirm</a>';
					else g_actions.innerHTML = "Already checked in!";
					// Append row to table
					table.appendChild(row);
					// Append any notes below
					var notes = guest.notes;
					if(notes == null || notes == "null") notes = "No notes";
					$("#guestnotes").html($("#guestnotes").html() + "<strong>" + guest.guest_name + "</strong><br />" + notes + "<br /><br />");
				}
				// Animate
				$("#statusicon").removeClass("icon-refresh").removeClass("icon-spin").addClass("icon-ok");
				$("#identifier").blur().val("");
                $("#identifier").prop("disabled", true);
				$("#errorbox").css("display", "none");
                $("#override").css("display", "none");
				$(".checkholder").removeClass("active");
				$("#frameone").addClass("active");
				Tick.checkin.key_timeout = null;
				Tick.checkin.animating = false;
                Tick.checkin.override_data = null;
            } else if(data.no_tickets) {
				$("#statusicon").removeClass("icon-refresh").removeClass("icon-spin").addClass("icon-remove");
				$("#errortext").html(data.error);
				$("#errorbox").css("display", "block");
				$("#identifier").val("");
                $("#identifier").prop("disabled", false);
                if(data.override_available) {
                    $("#override").css("display", "block");
                    $("#override a").css("display", "inline-block");
                    $("#overpwd").val('').css("display", "none");
                    $("#overridetext").css("display", "none");
                    Tick.checkin.override_data = data;
                }
			} else {
				$("#statusicon").removeClass("icon-refresh").removeClass("icon-spin").addClass("icon-remove");
				$("#errortext").html(data.error);
				$("#errorbox").css("display", "block");
				$("#identifier").val("");
                $("#identifier").prop("disabled", false);
                if(data.override_available) {
                    $("#override").css("display", "block");
                    $("#override a").css("display", "inline-block");
                    $("#overpwd").val('').css("display", "none");
                    $("#overridetext").css("display", "none");
                    Tick.checkin.override_data = data;
                }
			}
		},
		error: function(e) {
			$("#errortext").html("Had an error when communicating with the server - please try again.");
			$("#errorbox").css("display", "block");
			console.log(e);
		}
	});
};

Tick.checkin.typing_finished = function() {
	// Convert HEX to ASCII
	var hex = $("#identifier").val().toString();
	var cam_card = true;
    var username_card = false;
	var ascii = '';
	if(hex.toLowerCase().indexOf("crsid:") == 0) {
		ascii = hex.substr(6);
		cam_card = true;
    } else if(hex.toLowerCase().indexOf("user:") == 0) {
        ascii = hex.substr(5);
        cam_card = false;
        username_card = true;
	} else if(hex.toLowerCase().indexOf("ref:") == 0) {
		ascii = hex.substr(4);
		cam_card = false;
	} else if(hex.length < 10) {
		return;
	} else {
		for(var i = 0; i < hex.length; i += 2) {
			if(hex.substr(i, 2) == "00") break;
			ascii += String.fromCharCode(parseInt(hex.substr(i, 2), 16));
		}
		//console.log("ASCII: " + ascii);
		ascii = ascii.toUpperCase();
		if(ascii.indexOf("SSMB@") == 0) {
			//console.log("This is a Sidney Access Card!");
			ascii = ascii.substring(5);
			cam_card = false;
		} else if(ascii.indexOf("SSMBU@") == 0) {
		    ascii = ascii.substring(6);
            cam_card = false;
            username_card = true;
		}
		// Lookup some information
		if(!Tick.checkin.animating) {
			$("#statusicon").removeClass("icon-ok").removeClass("icon-terminal").addClass("icon-refresh").addClass("icon-spin");
			Tick.checkin.animating = true;
		}
	}
	
    Tick.checkin.lookup(ascii, cam_card, username_card);
};

Tick.checkin.cancel_checkin = function() {
	$("#statusicon").removeClass("icon-ok").addClass("icon-terminal");
	$("#errorbox").css("display", "none");
    $("#override").css("display", "none");
	$(".checkholder").addClass("active");
	$("#frameone").removeClass("active").removeClass("shoved");
	$("#frametwo").removeClass("active");
	$("#identifier").focus().val("");
	$("#dobday").val('');
	$("#dobmonth").val('');
	$("#dobyear").val('');
	$("#notes").val('');
	Tick.checkin.session_data = null;
    Tick.checkin.override_data = null;
    if(Tick.checkin.mobile_client) {
        window.location = "checkin://closed";
    }
};

Tick.checkin.check_guests = function() {
	// Grab data entered and date of birth
	var day = parseInt($("#dobday").val());
	var month = parseInt($("#dobmonth").val());
	var year = parseInt($("#dobyear").val());
	var data = Tick.checkin.session_data;
	data.entered_date = {
		"day": day,
		"month": month,
		"year": year
	};
	// Check we have a match
	if(Tick.checkin.guest_details && (day != data.dob_day || month != data.dob_month || year != data.dob_year)) {
		$("#errorbox").css("display","block");
		$("#errortext").html("Date of birth does not match stored data");
		return;
	}
	$("#dobday").val('');
	$("#dobmonth").val('');
	$("#dobyear").val('');
    if(Tick.checkin.override_data == null) {
        $("#override").css("display", "none");
    }
	$("#errorbox").css("display","none");
	// Transition
	$("#frameone").removeClass("active").addClass("shoved");
	$("#frametwo").addClass("active");
};

Tick.checkin.confirm_guest = function(index) {
	if(index >= Tick.checkin.session_data.tickets.length || index < 0) {
		alert("Invalid ticket index for check in!");
		return;
	} else if(Tick.checkin.session_data.tickets[index].checked_in) {
        // Uncheck a person
		//alert("This person is already checked-in!");
    	var rows = document.getElementById("gueststable").getElementsByTagName("tr");
    	var row = rows[index];
        var btn = null;
        try {
        	btn = row.getElementsByTagName("td")[5].getElementsByTagName("a")[0];
        } catch(e) {
            btn = row.getElementsByTagName("td")[2].getElementsByTagName("a")[0];
        }
        if(btn == null) return;
    	btn.innerHTML = '<i class="icon-check-empty"></i> Confirm';
    	btn.setAttribute("class", "ll_btn");
    	btn.setAttribute("disabled", "enabled");
    	// Mark them in the data structure as checked in
    	Tick.checkin.session_data.tickets[index].checked_in = false;
	} else {
    	var rows = document.getElementById("gueststable").getElementsByTagName("tr");
    	var row = rows[index];
        var btn = null;
        try {
        	btn = row.getElementsByTagName("td")[5].getElementsByTagName("a")[0];
        } catch(e) {
            btn = row.getElementsByTagName("td")[2].getElementsByTagName("a")[0];
        }
        if(btn == null) return;
    	btn.innerHTML = '<i class="icon-check"></i> Confirmed';
    	btn.setAttribute("class", "ll_btn disabled");
    	btn.setAttribute("disabled", "disabled");
    	// Mark them in the data structure as checked in
    	Tick.checkin.session_data.tickets[index].checked_in = true;
    	// Check if all are checked-in
    	/*var unchecked = false;
    	for(var i = 0; i < Tick.checkin.session_data.tickets.length; i++) {
    		if(!Tick.checkin.session_data.tickets[i].checked_in) {
    			unchecked = true;
    			break;
    		}
    	}*/
    	$("#allchecked").prop("disabled", false).removeClass("disabled");
    }
};

Tick.checkin.final_check = function() {
	$("#errorbox").css("display", "none");
    $("#override").css("display", "none");
	// First check all guests are marked as checked-in
	var full_checkin = true;
	var checked = null;
	for(var i = 0; i < Tick.checkin.session_data.tickets.length; i++) {
		if(!Tick.checkin.session_data.tickets[i].checked_in) {
			full_checkin = false;
		} else {
			if(checked == null) checked = Tick.checkin.session_data.tickets[i].tick_id;
			else checked += "|" + Tick.checkin.session_data.tickets[i].tick_id;
		}
	}
	// Warn about a partial checkin...
	if(checked == null) {
		$("#errortext").html("No guests have been marked for check-in");
		$("#errorbox").css("display", "block");
		return;
	} else if(!full_checkin && !confirm("Not all of the guests have been marked as checked-in, are you sure you want to proceed?")) {
		return;
	}
    
    var query_data = {
		action: "checkin",
		identifier: Tick.checkin.session_data.identifier,
		cam_card: Tick.checkin.session_data.cam_card,
        user_card: Tick.checkin.session_data.user_card,
		checked: checked
	};
    
    if(Tick.checkin.guest_details) {
        query_data['dob_day'] = Tick.checkin.session_data.entered_date.day;
        query_data['dob_month'] = Tick.checkin.session_data.entered_date.month;
        query_data['dob_year'] = Tick.checkin.session_data.entered_date.year;
    }
    
	// Run the check-in
	$.ajax({
		dataType: "json",
		url: "/checkin/data",
		data: query_data,
		success: function(data) {
            console.log(data);
			if(!data.error) {
				$("#infotext").html("Check-in successful!");
				setTimeout(function() { $("#infobox").css("display", "none"); }, 2000);
				$("#infobox").css("display", "block");
				$("#errorbox").css("display", "none");
                $("#override").css("display", "none");
				Tick.checkin.cancel_checkin();
			} else {
				$("#errortext").html(data.error);
				$("#errorbox").css("display", "block");
			}
		},
		error: function(e) {
			$("#errortext").html("Had an error when communicating with the server - please try again.");
			$("#errorbox").css("display", "block");
			console.log(e);
		}
	});
};

Tick.checkin.quick_stats = function() {
	$.ajax({
		dataType: "json",
		url: "/checkin/data",
		data: {
			action: "statistics",
		},
		success: function(data) {
			$("#quickstats").html(data.checkedin + " / " + data.total);
			if(!data.active && !Tick.checkin.deactivated) {
				$("#inactivecheckin").addClass("visible");
				$("#identifier").blur().prop("disabled", true);
				Tick.checkin.deactivated = true;
			} else if(data.active && Tick.checkin.deactivated) {
				$("#inactivecheckin").removeClass("visible");
				$("#identifier").prop("disabled", false).focus();
				Tick.checkin.deactivated = false;
			}
		}
	})
	setTimeout(Tick.checkin.quick_stats, 5000);
};

Tick.checkin.override = function() {
    // Make override request
    $.ajax({
        dataType: "json",
        url: "/checkin/data",
        data: {
            action: "override",
            password: $("#overpwd").val(),
            identifier: Tick.checkin.override_data.identifier,
            cam_card: Tick.checkin.override_data.cam_card,
            user_card: Tick.checkin.override_data.user_card
        },
        success: function(data) {
        	$("#statusicon").removeClass("icon-refresh").removeClass("icon-spin").addClass("icon-terminal");
            if(data.success) {
                $("#override").css("display", "block");
                $("#overridetext").css("display", "block");
                $("#override a").css("display", "none");
                $("#overpwd").css("display", "none");
				Tick.checkin.session_data = data;
				$("#salutation").html(data.salutation);
				$("#holder").html(data.owner_name);
				$("#numtickets").html(data.num_tickets);
				if(data.owner_cam) {
					$("#crsidbox").css("display", "table-row");
					$("#crsid").html(data.owner_crsid);
				} else {
					$("#crsidbox").css("display", "none");
					$("#crsid").html("");
				}
				if(data.owner_cam) $("#atcam").html("Yes");
				else $("#atcam").html("No");
				if(data.owner_checked) {
				    $("#owner_checked").html("Yes");
                    $("#dobday").val(data.dob_day);
                    $("#dobmonth").val(data.dob_month);
                    $("#dobyear").val(data.dob_year);
				}
				else $("#owner_checked").html("<span style='color:#F00;font-weight:bold;'>No</span>");
				$("#owner_notes").html(data.notes);
				// Guests
				$("#gueststable").empty();
				$("#guestnotes").html("");
				var table = document.getElementById("gueststable");
				for(var i = 0; i < data.tickets.length; i++) {
					var guest = data.tickets[i];
					var row = document.createElement("tr");
                    if(Tick.checkin.guest_details) {
    					// Name
    					var g_name = document.createElement("td");
    					row.appendChild(g_name);
    					g_name.innerHTML = guest.guest_name;
    					// Date of birth
    					var g_dob = document.createElement("td");
    					row.appendChild(g_dob);
    					g_dob.innerHTML = guest.dob;
    					// At Cambridge
    					var g_atcam = document.createElement("td");
    					row.appendChild(g_atcam);
    					if(guest.at_cam) g_atcam.innerHTML = "Yes";
    					else g_atcam.innerHTML = "No";
                    }
					// Ticket type
					var g_type = document.createElement("td");
					row.appendChild(g_type);
					g_type.innerHTML = guest.ticket_type;
					// Ticket upgrades
					var g_upgrades = document.createElement("td");
					row.appendChild(g_upgrades);
					g_upgrades.innerHTML = guest.upgrades;
					// Actions
					var g_actions = document.createElement("td");
					row.appendChild(g_actions);
					if(!guest.checked_in) g_actions.innerHTML = '<a class="ll_btn" onclick="Tick.checkin.confirm_guest(' + i + ');"><i class="icon-check-empty"></i> Confirm</a>';
					else g_actions.innerHTML = "Already checked in!";
					// Append row to table
					table.appendChild(row);
					// Append any notes below
					var notes = guest.notes;
					if(notes == null || notes == "null") notes = "No notes";
					$("#guestnotes").html($("#guestnotes").html() + "<strong>" + guest.guest_name + "</strong><br />" + notes + "<br /><br />");
				}
				// Animate
				$("#statusicon").removeClass("icon-refresh").removeClass("icon-spin").addClass("icon-ok");
				$("#identifier").blur().val("");
                $("#errorbox").css("display", "none");
				$(".checkholder").removeClass("active");
				$("#frameone").addClass("active");
				Tick.checkin.key_timeout = null;
				Tick.checkin.animating = false;
            } else {
                $("#errorbox").css("display", "block");
                $("#errortext").html(data.error);
            }
        }
    });
    $("#overpwd").val('');
    $("#override").css("display","none");
    $("#errorbox").css("display","none");
	$("#statusicon").removeClass("icon-ok").removeClass("icon-terminal").removeClass("item-remove").addClass("icon-refresh").addClass("icon-spin");
};

$(function() {
	Tick.checkin.quick_stats();
});

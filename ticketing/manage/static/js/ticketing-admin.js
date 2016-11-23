// Register base object if necessary
var Tick = Tick || {};
// Register admin object
Tick.admin = {};
// Drawer function
Tick.admin.toggle_expandable = function(expand, state) {
    if($(expand).children(".exp-body").hasClass('in') || state == "close") {
        $(expand).children(".exp-body").collapse('hide');
        $(expand).find(".exp-head h2 i").removeClass("icon-angle-up").addClass("icon-angle-down");
    } else {
        $(expand).children(".exp-body").collapse('show');
        $(expand).find(".exp-head h2 i").removeClass("icon-angle-down").addClass("icon-angle-up");
    }
};
// Toggle switch
Tick.admin.switch = function(aswitch, state) {
    if(state == "on") {
        $(aswitch).find(".onstate").removeClass("hidden");
        $(aswitch).find(".offstate").addClass("hidden");
        Tick.admin.toggle_expandable($(aswitch).closest(".expandable"), "open");
        $(aswitch).closest(".expandable").find("input.enabled").val("yes");
    } else if(state == "off") {
        $(aswitch).find(".offstate").removeClass("hidden");
        $(aswitch).find(".onstate").addClass("hidden");
        Tick.admin.toggle_expandable($(aswitch).closest(".expandable"), "close");
        $(aswitch).closest(".expandable").find("input.enabled").val("no");
    }
};
Tick.admin.select_quantity = function(quantity) {
	quantity = parseInt(quantity);
	$(".allocation_block").remove();
	for(var i = 0; i < quantity; i++) {
		// Create element
		var holder = document.createElement("div");
		holder.setAttribute("class", "allocation_block");
		var text = document.createElement("span");
		text.innerHTML = "Ticket " + (i + 1) + ":&nbsp;&nbsp;&nbsp;";
		holder.appendChild(text);
		// Ticket type selector
		var type_sel = document.createElement("select");
		type_sel.setAttribute("class", "ticktype");
		type_sel.setAttribute("onchange", "Tick.admin.select_type(this);");
		type_sel.setAttribute("name", "ticket-" + i + "-type");
		type_sel.setAttribute("id", "ticket-" + i + "-type");
		var type_first_option = document.createElement("option");
		type_first_option.setAttribute("disabled", "disabled");
		type_first_option.setAttribute("selected", "selected");
		type_first_option.setAttribute("value", "notype");
		type_first_option.innerHTML = "Select ticket type...";
		type_sel.appendChild(type_first_option);
		// Populate options
		for(var j = 0; j < Tick.admin.available_tickets.length; j++) {
			var ticket = Tick.admin.available_tickets[j];
			var type_option = document.createElement("option");
			type_option.setAttribute("value", ticket.id);
			type_option.innerHTML = ticket.name;
			type_sel.appendChild(type_option);
		}
		holder.appendChild(type_sel);
		// Spacer
		var spacer = document.createElement("span");
		spacer.innerHTML = "&nbsp;&nbsp;&nbsp;";
		holder.appendChild(spacer);
		// Ticket addon selector
		var addon_sel = document.createElement("select");
		addon_sel.setAttribute("disabled", "disabled");
		addon_sel.setAttribute("class", "addontype");
		addon_sel.setAttribute("name", "ticket-" + i + "-addon");
		addon_sel.setAttribute("id", "ticket-" + i + "-addon");
		var addon_first_option = document.createElement("option");
		addon_first_option.setAttribute("disabled", "disabled");
		addon_first_option.setAttribute("selected", "selected");
		addon_first_option.setAttribute("value", "notype");
		addon_first_option.innerHTML = "Select addon type...";
		addon_sel.appendChild(addon_first_option);
		holder.appendChild(addon_sel);
		// Add to the page
		document.getElementById("tickchoice").appendChild(holder);
	}
	// Shift the info
	var info = document.getElementById("tickchoiceinfo");
	document.getElementById("tickchoice").removeChild(info);
	document.getElementById("tickchoice").appendChild(info);
};
Tick.admin.select_type = function(selector) {
	// Get the ticket type
	var type_id = selector.value;
	var type = null;
	for(var i = 0; i < Tick.admin.available_tickets.length; i++) {
		if(Tick.admin.available_tickets[i].id == type_id) type = Tick.admin.available_tickets[i];
	}
	if(type == null) return;
	// Fill out the addon dropdown
	var addon_sel = $(selector).parent().children(".addontype");
	addon_sel.empty();
	addon_sel.prop("disabled", false);
	// Setup first option
	var addon_first_option = document.createElement("option");
	addon_first_option.setAttribute("value", "none");
	addon_first_option.innerHTML = "No Addon";
	addon_sel.prepend(addon_first_option);
	// Setup other options
	for(var addon_key in type.addons) {
		var addon_option = document.createElement("option");
		addon_option.setAttribute("value", addon_key);
		addon_option.innerHTML = type.addons[addon_key];
		addon_sel.append(addon_option);
	}
};
Tick.admin.select_report_type = function(selector) {
	// Get the ticket type
	var type_id = selector.value;
	var addon_sel = $(selector).parent().children("#ticketupgrade");
	if(type_id == "any") {
		addon_sel.selectedIndex = 0;
		addon_sel.prop("disabled", true);
	} else {
		var type = null;
		for(var i = 0; i < Tick.admin.available_tickets.length; i++) {
			if(Tick.admin.available_tickets[i].id == type_id) type = Tick.admin.available_tickets[i];
		}
		if(type == null) return;
		// Fill out the addon dropdown
		var addon_sel = $("#ticketupgrade");
		addon_sel.empty();
		addon_sel.prop("disabled", false);
		// Setup first option
		var addon_first_option = document.createElement("option");
		addon_first_option.setAttribute("value", "any");
		addon_first_option.innerHTML = "Any";
		addon_sel.prepend(addon_first_option);
		// Setup other options
		for(var addon_key in type.addons) {
			var addon_option = document.createElement("option");
			addon_option.setAttribute("value", addon_key);
			addon_option.innerHTML = type.addons[addon_key];
			addon_sel.append(addon_option);
		}
	}
};
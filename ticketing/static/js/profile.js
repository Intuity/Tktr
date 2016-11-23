var Profiles = function() {
    
    var CamStatusCheckAction = function() {
        if($("#is_cam_student").is(":checked")) {
            if($("#status_hidden_fields").hasClass("hidden")) $("#status_hidden_fields").removeClass("hidden");
			$("#email").prop("disabled", true);
			$("#email").val("");
        } else {
            if(!$("#status_hidden_fields").hasClass("hidden")) $("#status_hidden_fields").addClass("hidden");
			$("#email").prop("disabled", false);
			$("#email").val("");
        }
        
    }; this.CamStatusCheckAction = CamStatusCheckAction;
	
	var CrisdChanged = function() {
		$("#email").val($("#crsid").val() + "@cam.ac.uk");
	}; this.CrisdChanged = CrisdChanged;
    
};

$(document).ready(function() {
    window.profiles = new Profiles();
});